"""The actual full-run producer must round-trip through hosted feedback."""
from collections import Counter
import json

import pytest

from forage import align, book_critic, full_run, production, publication, review_apply, review_sync
from forage.artifacts import Book, read_json
from forage.llm import LLMResponse
from forage.production_state import atomic_json, digest, inventory, text_revision
from .test_review_lifecycle import _site, _comment
from .test_revision_review import decide


@pytest.fixture(params=[False, True], ids=['canonical', 'legacy'])
def completed_run(tmp_path, monkeypatch, request):
    sources = {'001': 'This must survive. The traveler returns.\n\nThe ending remains.',
               '002': 'Another chapter. The story closes.'}
    source = tmp_path / 'books/sample/source.txt'
    source.parent.mkdir(parents=True)
    source.write_text('\n\n'.join(sources.values()))
    book = Book('sample', source, {'title': 'Sample', 'author': 'A. Author'}, tmp_path / 'work/sample')
    root = book.work_dir
    for folder in ['chapters', 'segments', 'preservation', 'fidelity/final_review']:
        (root / folder).mkdir(parents=True)
    plan = {'title': 'Sample', 'author': 'A. Author', 'merged_groups': {},
            '_meta': {'computed': {'target_word_count': sum(len(t.split()) for t in sources.values())}},
            'segments': [{'id': sid, 'title': sid, 'diegetic_status': 'diegetic',
                          'source_word_count': len(text.split()), 'target_word_count': len(text.split()),
                          'signatures': [{'passage_hint': text.split('.')[0] + '.', 'why': 'Signature.'}]}
                         for sid, text in sources.items()]}
    atomic_json(root / 'plan.json', plan)
    for name in ['chapters.json', 'chapter_classifications.json', 'cuts.json']:
        atomic_json(root / name, {})
    (root / 'book_synopsis.md').write_text('The traveler returns.\nThe story closes.')
    for sid, text in sources.items():
        (root / f'chapters/{sid}.md').write_text(text)
        atomic_json(root / f'preservation/{sid}.json', {'target_words': len(text.split()),
                    'verbatim': [{'id': 'V1', 'text': text.split('.')[0] + '.'}]})
        finding = {'id': 'F1', 'title': 'Name the traveler', 'claim': 'Use more precise wording.',
                   'priority': 'must_fix', 'evidence': []}
        atomic_json(root / f'fidelity/final_review/{sid}.json',
                    {'verdict': 'needs_repair' if sid == '001' else 'no_material_findings',
                     'findings': [finding] if sid == '001' else []})
        atomic_json(root / f'fidelity/final_review/{sid}.inputs.json',
                    {'documents': {sid + '.revision': [{'paragraph': i, 'text': p}
                     for i, p in enumerate(align._split_paragraphs(text), 1)]}})
    calls = Counter()
    def generate(**req):
        stage = req['stage']
        calls[stage] += 1
        if stage.startswith('align'):
            sid = stage.rsplit(':', 1)[-1]
            draft = align._split_paragraphs((root / f'segments/{sid}.md').read_text())
            value = [{'draft_para': i, 'source_paras': [i], 'note': 'compressed'} for i in range(len(draft))]
        else:
            value = [{'sentence': n, 'status': 'present', 'evidence': 'The story remains.'} for n in [1, 2]]
        return LLMResponse(json.dumps(value), full_run.MODEL, 1, 1, 0, 'end_turn')
    def forbidden(*args, **kwargs):
        pytest.fail('Unexpected generation or source preparation')
    for name in ['split_to_disk', 'classify_chapters', 'summarize_book', 'generate_cuts',
                 'build_lean_plan', 'draft_segment', 'run_coherence', 'run_coherence_fixes']:
        monkeypatch.setattr(production, name, forbidden)
    monkeypatch.setattr('forage.llm._anthropic', forbidden)
    monkeypatch.setattr('forage.llm._openai', forbidden)
    result = full_run.finish(book, sources, generate, 1, 'final_review')
    if request.param:
        manifest = publication.verify_revision(book, result['review_revision'])
        legacy_id = digest({'plan': plan, 'drafts': sources})
        media = read_json(root / 'media_manifest.json')
        media['text_revision'] = legacy_id
        atomic_json(root / 'media_manifest.json', media)
        snapshot = publication.snapshot_revision(book, text_revision=legacy_id,
            outputs=inventory(root, [i['path'] for i in manifest['outputs'] if i['path'] != 'full_run_inputs.json']),
            media_index=media, stage_summary=manifest['stage_summary'])
        result.update(review_revision=snapshot['revision'], text_revision=legacy_id)
        atomic_json(root / 'full_run_result.json', result)
        atomic_json(tmp_path / 'run.json', {'inputs': inventory(tmp_path,
            [source] + [root / f'chapters/{sid}.md' for sid in sources])})
        (root / 'full_run_inputs.json').unlink()
    monkeypatch.setattr(production, 'run_book_critic', lambda book: book_critic.run_book_critic(book, generate=generate))
    monkeypatch.setattr(production, 'align_chapter', lambda book, sid: align.align_chapter(book, sid, generate=generate))
    calls.clear()
    return book, result, calls


def apply_provider(book, monkeypatch, calls, old='traveler', new='wanderer'):
    def complete(**kwargs):
        calls['apply'] += 1
        sid = kwargs['stage'].rsplit(':', 1)[-1]
        pending = next(row['pending'] for row in review_apply.pending_review_feedback(
            book, edits_path=review_sync.imported_edits_path(book))['segments'] if row['segment_id'] == sid)
        before = (book.work_dir / f'segments/{sid}.md').read_text().strip()
        after = before.replace(old, new)
        return LLMResponse(json.dumps({'segment_id': sid, 'revised_draft': after,
            'decisions': [{'feedback_key': p['feedback_key'], 'comment_id': p['comment_id'],
                           'action': 'applied' if after != before else 'skipped',
                           'reason': 'Verified the source wording.',
                           'changed_paragraphs': [0] if after != before else [],
                           'target_paragraphs': [0]} for p in pending]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(review_apply, 'complete', complete)


def pipeline_note(client):
    return next(n for n in client.get('/api/books/sample/comments').json()['comments'] if n.get('pipeline_review'))


def test_unchanged_full_run_sync_preserves_revision_without_generation(completed_run, tmp_path):
    book, result, calls = completed_run
    host, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    original = inventory(book.work_dir, [i['path'] for i in publication.verify_revision(book, result['review_revision'])['outputs']])
    for _ in range(2):
        synced = review_sync.sync_feedback(book, transport, apply=True, republish=True)
        assert synced['success'] and synced['publication']['revision'] == result['review_revision']
    assert not calls
    assert inventory(book.work_dir, [i['path'] for i in original]) == original
    assert not (book.work_dir / 'production_state.json').exists()  # Free planning does not adopt files.


def test_full_run_finding_request_apply_republish_and_resume(completed_run, tmp_path, monkeypatch):
    book, result, calls = completed_run
    root = book.work_dir
    plan = (root / 'plan.json').read_bytes()
    source = inventory(root, [f'chapters/{sid}.md' for sid in ['001', '002']])
    original = publication.verify_revision(book, result['review_revision'])
    host, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    note = pipeline_note(client)
    assert decide(client, note, 'rejected', 'Use wanderer.').status_code == 200
    apply_provider(book, monkeypatch, calls)
    synced = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert synced['success'], synced
    revision = synced['publication']['revision']
    assert revision != result['review_revision']
    assert 'wanderer' in (root / 'segments/001.md').read_text()
    assert (root / 'plan.json').read_bytes() == plan
    assert inventory(root, [i['path'] for i in source]) == source
    assert calls == {'apply': 1, 'critic:book:sample': 1, 'align:sample:001': 1}
    note = pipeline_note(client)
    assert note['revision_review']['current'] and note['revision_review']['state'] == 'pending'
    assert note['llm_responses'][0]['source'] == 'review_apply'
    assert decide(client, note, 'accepted').status_code == 200
    before = calls.copy()
    assert review_sync.sync_feedback(book, transport, apply=True, republish=True)['success']
    assert calls == before
    resumed = full_run.run_book(book, lambda **kw: pytest.fail('Completed resume generated'), 1)
    assert resumed['review_revision'] == revision
    assert publication.verify_revision(book, result['review_revision']) == original
    assert host.status('sample')['release'] is None
    report = read_json(root / 'assembly_report.json')
    assert not any('ceiling' in k or 'overage' in k for k in report)


def test_skipped_feedback_publishes_response_without_rechecking_unchanged_text(completed_run, tmp_path, monkeypatch):
    book, result, calls = completed_run
    _, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    _comment(client, result['review_revision'], scope='chapter')
    apply_provider(book, monkeypatch, calls, new='traveler')
    synced = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert synced['success'] and synced['publication']['revision'] != result['review_revision']
    assert calls == {'apply': 1}
    notes = client.get('/api/books/sample/comments').json()['comments']
    response = next(n for n in notes if not n.get('pipeline_review'))
    assert response['revision_review']['current'] and response['llm_responses'][0]['action'] == 'skipped'


def test_refresh_failure_retries_without_reapplying_feedback(completed_run, tmp_path, monkeypatch):
    book, result, calls = completed_run
    host, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    _comment(client, result['review_revision'], scope='chapter')
    apply_provider(book, monkeypatch, calls)
    original_critic = production.run_book_critic
    def fail(book):
        raise RuntimeError('Offline critic failure')
    monkeypatch.setattr(production, 'run_book_critic', fail)
    failed = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert not failed['success'] and host.status('sample')['review']['revision'] == result['review_revision']
    monkeypatch.setattr(production, 'run_book_critic', original_critic)
    retried = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert retried['success'] and calls['apply'] == 1


@pytest.mark.parametrize('changed', [None, 'draft', 'plan', 'snapshot'])
def test_book_feedback_checks_current_bytes_including_legacy_identity(completed_run, tmp_path, changed):
    book, result, calls = completed_run
    _, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    _comment(client, result['review_revision'], scope='book')
    if changed:
        path = {'draft': book.work_dir / 'segments/002.md', 'plan': book.work_dir / 'plan.json',
                'snapshot': book.work_dir / 'publications' / result['review_revision'] / 'segments/002.md'}[changed]
        path.write_text(path.read_text() + ' ')
    counts = review_sync.sync_feedback(book, transport)['pull']['counts']
    # Canonical identity already proves local bytes; legacy IDs additionally
    # require the immutable publication to prove the same content.
    stale = changed in {'draft', 'plan'} or (changed == 'snapshot' and result['text_revision'] != text_revision(book))
    assert counts == {'inactive': 1, 'stale' if stale else 'eligible': 1}
    assert not calls


@pytest.mark.parametrize('changed', ['source', 'chapter', 'plan', 'snapshot', 'options', 'missing_draft', 'checks'])
def test_invalid_origin_fails_before_feedback_generation(completed_run, tmp_path, monkeypatch, changed):
    book, result, calls = completed_run
    _, _, transport, client = _site(tmp_path)
    transport.publish(book, result['review_revision'])
    _comment(client, result['review_revision'], scope='chapter')
    before = (book.work_dir / 'segments/001.md').read_bytes()
    apply_provider(book, monkeypatch, calls)
    options = {'coherence_fix': True} if changed == 'options' else None
    if changed == 'missing_draft':
        (book.work_dir / 'segments/002.md').unlink()
    elif changed == 'checks':
        atomic_json(book.work_dir / 'segments/002.checks.json', {'status': 'truncated'})
    elif changed != 'options':
        path = {'source': book.source_path, 'chapter': book.work_dir / 'chapters/001.md',
                'plan': book.work_dir / 'plan.json',
                'snapshot': book.work_dir / 'publications' / result['review_revision'] / 'segments/001.md'}[changed]
        path.write_text(path.read_text() + ' ')
    with pytest.raises(ValueError):
        review_sync.sync_feedback(book, transport, apply=True, republish=True, production_options=options)
    assert not calls and (book.work_dir / 'segments/001.md').read_bytes() == before
