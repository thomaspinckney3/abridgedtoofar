"""Provider-free publication of full-run findings and repair evidence.

The immutable package supplies review context; reviewer decisions stay in the
website database and return through the ordinary feedback pipeline.
"""
from __future__ import annotations

import hashlib
import json
import re

from .production_state import atomic_json, book_lock, digest, inventory, verify_inventory
from .review_anchors import chapter_hash

FILENAME = 'pipeline_review.json'


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _normalized(text):
    return ' '.join(text.split()).translate(str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"'}))


def paragraphs(text):
    return [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]


def draft_hash(paras):
    return hashlib.sha256(('\n\n'.join(paras).strip() + '\n').encode()).hexdigest()[:24]


def _item_id(book_id, item):
    return 'pipeline_' + digest({'book': book_id, 'item': {k: v for k, v in item.items() if k != 'id'}})[:40]


def _validate_evidence(evidence):
    if not isinstance(evidence, list) or any(
        not isinstance(e, dict) or not isinstance(e.get('document'), str)
        or type(e.get('paragraph')) is not int or e['paragraph'] < 1
        or not isinstance(e.get('quote'), str) or not e['quote'].strip()
        for e in evidence
    ):
        raise ValueError('Invalid pipeline evidence')


def _validate_history(history):
    for entry in history:
        if (not isinstance(entry, dict) or not isinstance(entry.get('pass'), str)
                or any(not isinstance(entry.get(k), list) for k in ['findings', 'adjudications', 'replacements'])):
            raise ValueError('Invalid pipeline repair history')
        for finding in entry['findings']:
            if not isinstance(finding, dict) or any(not isinstance(finding.get(k), str) for k in ['id', 'title', 'claim']):
                raise ValueError('Invalid historical finding')
        for adjudication in entry['adjudications']:
            if (not isinstance(adjudication, dict)
                    or any(not isinstance(adjudication.get(k), str) for k in ['id', 'reason', 'decision'])
                    or adjudication['decision'] not in {'confirmed', 'rejected', 'uncertain'}):
                raise ValueError('Invalid pipeline adjudication')
            _validate_evidence(adjudication.get('evidence'))
        for patch in entry['replacements']:
            if (not isinstance(patch, dict) or not isinstance(patch.get('old'), str)
                    or not patch['old'] or not isinstance(patch.get('new'), str)):
                raise ValueError('Invalid historical replacement')


def validate_package(value, book_id):
    if (not isinstance(value, dict) or value.get('version') != 1
            or value.get('book_id') != book_id or not isinstance(value.get('chapters'), dict)
            or not isinstance(value.get('items'), list) or len(value['items']) > 10000):
        raise ValueError('Invalid pipeline review package')
    for sid, context in value['chapters'].items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', sid):
            raise ValueError('Invalid pipeline review chapter')
        paras = context.get('paragraphs') if isinstance(context, dict) else None
        if (not isinstance(paras, list) or not paras or
                any(not isinstance(p, str) or not p.strip() for p in paras)
                or context.get('anchor') != chapter_hash(paras)):
            raise ValueError('Invalid pipeline review context')
    seen = set()
    for item in value['items']:
        if (not isinstance(item, dict) or item.get('id') != _item_id(book_id, item)
                or item['id'] in seen or item.get('segment_id') not in value['chapters']
                or item.get('kind') not in {'finding', 'repair'}
                or item.get('priority') not in {'must_fix', 'should_improve', 'tradeoff', 'review'}
                or any(not isinstance(item.get(k), str) or not item[k].strip()
                       for k in ['title', 'body', 'review_label', 'chapter_anchor'])
                or len(item['body']) > 4000
                or item['chapter_anchor'] != value['chapters'][item['segment_id']]['anchor']
                or not isinstance(item.get('evidence'), list)
                or not isinstance(item.get('history'), list)):
            raise ValueError('Invalid pipeline review item')
        _validate_evidence(item['evidence'])
        _validate_history(item['history'])
        if 'finding' in item and not isinstance(item['finding'], dict):
            raise ValueError('Invalid pipeline finding')
        seen.add(item['id'])
    return value


def _check_quotes(evidence, docs):
    _validate_evidence(evidence)
    for citation in evidence:
        try:
            para = docs[citation['document']][citation['paragraph'] - 1]
        except (KeyError, IndexError) as exc:
            raise ValueError('Pipeline evidence references a missing paragraph') from exc
        if (para['paragraph'] != citation['paragraph'] or
                _normalized(citation['quote']) not in _normalized(para['text'])):
            raise ValueError('Pipeline evidence does not match its reviewed context')


def _checked_review(root, label, sid):
    report = _read(root / 'fidelity' / label / f'{sid}.json')
    context = _read(root / 'fidelity' / label / f'{sid}.inputs.json')
    for finding in report['findings']:
        _check_quotes(finding['evidence'], context['documents'])
    return report, context


def _repair_history(root, sid, phases):
    history = []
    for phase, review_label in phases:
        repair_path = root / 'repairs' / phase / f'{sid}.json'
        if not repair_path.exists():
            continue
        repair = _read(repair_path)
        if not repair.get('adjudications') and not repair.get('replacements'):
            continue
        previous, inputs = _checked_review(root, repair.get('review_label', review_label), sid)
        for adjudication in repair['adjudications']:
            _check_quotes(adjudication['evidence'], inputs['documents'])
        before = '\n\n'.join(p['text'] for p in inputs['documents'][sid + '.revision'])
        # Replay patches against the frozen input, never against today's text.
        spans = []
        for patch in repair['replacements']:
            old, new = patch['old'], patch['new']
            if not old or before.count(old) != 1:
                raise ValueError('Repair history has an ambiguous patch')
            start = before.index(old)
            spans.append((start, start + len(old), new))
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            raise ValueError('Repair history has overlapping patches')
        after = before
        for start, end, new in reversed(spans):
            after = after[:start] + new + after[end:]
        if paragraphs(after) != paragraphs(repair_path.with_suffix('.md').read_text()):
            raise ValueError('Repair history does not reproduce saved output')
        history.append({'pass': phase, 'findings': previous['findings'],
                        'adjudications': repair['adjudications'],
                        'replacements': repair['replacements'],
                        'remaining_concerns': repair.get('remaining_concerns', [])})
    return history


def build_package(book, label):
    root = book.work_dir
    result = {'version': 1, 'book_id': book.book_id, 'chapters': {}, 'items': []}
    # Saved legacy full-run passes; future repair artifacts record review_label.
    phases = [('initial_review', 'initial_review'), ('repair_review', 'repair_review'),
              ('blocking_closure', 'final_review')]
    for folder in sorted((root / 'repairs').glob('blocking_closure_*')):
        n = int(folder.name.rsplit('_', 1)[1])
        phases.append((folder.name, 'release_review' if n == 2 else f'release_review_{n - 1}'))
    for path in sorted((root / 'fidelity' / label).glob('*.json')):
        if '.' in path.stem:
            continue
        sid = path.stem
        report, context = _checked_review(root, label, sid)
        paras = [p['text'].strip() for p in context['documents'][sid + '.revision']]
        alignment = _read(root / 'alignments' / f'{sid}.json')
        if paras != alignment['draft_paragraphs'] or paras != paragraphs((root / 'segments' / f'{sid}.md').read_text()):
            raise ValueError(f'Review no longer matches current chapter {sid}; run the critic first')
        anchor = chapter_hash(paras)
        result['chapters'][sid] = {'paragraphs': paras, 'anchor': anchor}
        history = _repair_history(root, sid, phases)
        for finding in report['findings']:
            body = '\n\n'.join(str(finding.get(k) or '') for k in
                              ['claim', 'reader_effect', 'minimal_repair']).strip()
            item = {'segment_id': sid, 'kind': 'finding', 'priority': finding['priority'],
                    'title': finding['title'], 'body': body, 'evidence': finding['evidence'],
                    'finding': finding, 'history': [], 'review_label': label,
                    'chapter_anchor': anchor}
            result['items'].append({**item, 'id': _item_id(book.book_id, item)})
        if history:
            patches = sum(len(h['replacements']) for h in history)
            item = {'segment_id': sid, 'kind': 'repair', 'priority': 'review',
                    'title': 'Review chapter repairs',
                    'body': f'{patches} edits across {len(history)} editorial passes. '
                            'Review the current chapter and the recorded before/after changes. '
                            'Any outstanding critic findings are listed separately.',
                    'evidence': [], 'history': history, 'review_label': label,
                    'chapter_anchor': anchor}
            result['items'].append({**item, 'id': _item_id(book.book_id, item)})
    if not result['chapters']:
        raise ValueError('No completed fidelity reviews to publish')
    return validate_package(result, book.book_id)


def response_entry(package, item):
    changed = item['kind'] == 'repair' and any(h['replacements'] for h in item['history'])
    return {'comment_id': item['id'], 'segment_id': item['segment_id'],
            'run_id': item['id'], 'feedback_key': item['id'],
            'draft_after_hash': draft_hash(package['chapters'][item['segment_id']]['paragraphs']),
            'action': 'applied' if changed else 'skipped',
            'reason': ('Review the chapter repairs. Outstanding findings require separate decisions.'
                       if item['kind'] == 'repair' else
                       'Critic finding awaiting a reviewer decision. Request a change or dismiss the finding.'),
            'draft_changed': changed,
            'comment_response': {'source': 'pipeline_' + item['kind']}}


def prepare_review(book):
    """Enrich a completed full-run snapshot without generation or text changes."""
    from .publication import snapshot_revision, verify_revision
    with book_lock(book):
        result_path = book.work_dir / 'full_run_result.json'
        result = _read(result_path)
        manifest = verify_revision(book, result['review_revision'])
        outputs = [f for f in manifest['outputs'] if f['path'] != FILENAME]
        if not verify_inventory(book.work_dir, outputs):
            raise ValueError('Completed run changed; refresh the pipeline before packaging review')
        package = build_package(book, result['final_review_label'])
        atomic_json(book.work_dir / FILENAME, package)
        summary = manifest['stage_summary']
        summary['stages']['pipeline_review'] = {'status': 'complete'}
        snapshot = snapshot_revision(book, text_revision=manifest['text_revision'],
            outputs=outputs + inventory(book.work_dir, [FILENAME]),
            media_index=_read(book.work_dir / 'media_manifest.json'),
            stage_summary=summary, lock_held=True)
        result['review_revision'] = snapshot['revision']
        atomic_json(result_path, result)
        return {'revision': snapshot['revision'], 'items': len(package['items']),
                'text_revision': manifest['text_revision']}
