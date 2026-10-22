"""Read-only final integrity audit; no provider calls or publication changes."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO))
from forage.artifacts import load_book
from forage.align import _alignment_current, _split_paragraphs
from forage.full_run import MODEL, apply_replacements, review_context, run_book, validate_review
from forage.production import required_segments
from forage.publication import verify_revision
from forage.target_revision import measure

read = lambda p: json.loads(p.read_text())
manifest = read(ROOT / 'run.json')
for item in manifest['inputs']:
    assert hashlib.sha256((REPO / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
summary = {'unchanged_original_inputs': len(manifest['inputs']), 'books': {}}
for bid in manifest['books']:
    book = load_book(bid, workspace=ROOT)
    w = book.work_dir
    result = read(w / 'full_run_result.json')
    verified = verify_revision(book, result['review_revision'])
    ids = [s['id'] for s in required_segments(read(w / 'plan.json'))]
    drafts = {sid: (w / 'two_pass' / sid / 'draft.md').read_text().strip() for sid in ids}
    for label in ['initial_review', 'repair_review', 'final_review']:
        for sid in ids:
            context, documents = review_context(book, sid, drafts)
            assert context == read(w / 'fidelity' / label / f'{sid}.inputs.json'), (bid, label, sid, 'stale review inputs')
            validate_review(read(w / 'fidelity' / label / f'{sid}.json'), sid, documents, len(context['dependencies']))
        if label != 'final_review':
            revised = {}
            for sid in ids:
                repairs = read(w / 'repairs' / label / f'{sid}.json')
                plan = read(w / 'preservation' / f'{sid}.json')
                revised[sid] = apply_replacements(drafts[sid], repairs['replacements'], plan)
                assert revised[sid] == (w / 'repairs' / label / f'{sid}.md').read_text().strip()
            drafts = revised
    final_label = result.get('final_review_label', 'final_review')
    closure_rounds = (0 if final_label == 'final_review' else
                      1 if final_label == 'release_review' else
                      int(final_label.removeprefix('release_review_')))
    for closure_round in range(1, closure_rounds + 1):
        suffix = '' if closure_round == 1 else f'_{closure_round}'
        repair_folder = w / 'repairs' / ('blocking_closure' + suffix)
        review_folder = w / 'fidelity' / ('release_review' + suffix)
        previous_label = ('final_review' if closure_round == 1 else
                          'release_review' if closure_round == 2 else f'release_review_{closure_round - 1}')
        revised = {}
        for sid in ids:
            repair = read(repair_folder / f'{sid}.json')
            plan = read(w / 'preservation' / f'{sid}.json')
            revised[sid] = apply_replacements(drafts[sid], repair['replacements'], plan)
            assert revised[sid] == (repair_folder / f'{sid}.md').read_text().strip()
            confirmed = {a['id'] for a in repair['adjudications'] if a['decision'] == 'confirmed'}
            covered = set()
            for patch in repair['replacements']:
                linked = set(patch['finding_ids'])
                assert linked and linked <= confirmed
                covered.update(linked)
            assert covered == confirmed
        drafts = revised
        for sid in ids:
            context, documents = review_context(book, sid, drafts)
            assert context == read(review_folder / f'{sid}.inputs.json')
            validate_review(read(review_folder / f'{sid}.json'), sid,
                            documents, len(context['dependencies']))
            if (review_folder / f'{sid}.provenance.json').exists():
                assert context == read(w / 'fidelity' / previous_label / f'{sid}.inputs.json')
                assert read(review_folder / f'{sid}.json') == read(w / 'fidelity' / previous_label / f'{sid}.json')
    words = target = protected = 0
    for sid in ids:
        text = (w / 'segments' / f'{sid}.md').read_text().strip()
        assert text == drafts[sid], (bid, sid, 'final review text mismatch')
        checks = measure(text, read(w / 'preservation' / f'{sid}.json'))
        saved = read(w / 'segments' / f'{sid}.checks.json')
        assert all(checks[k] == saved[k] for k in checks), (bid, sid, 'stale measurements')
        assert all(p['present'] for p in checks['protected']), (bid, sid, 'missing protected passage')
        protected += len(checks['protected'])
        words += checks['words']
        target += checks['target_words']
        source = _split_paragraphs((w / 'chapters' / f'{sid}.md').read_text())
        assert _alignment_current(w / 'alignments' / f'{sid}.json', source, _split_paragraphs(text)), (bid, sid, 'stale alignment')
    assert (words, target, len(ids)) == (result['words'], result['target_words'], result['chapters'])
    assert result['model'] == MODEL
    label = result.get('final_review_label', 'final_review')
    findings = [f for sid in ids for f in read(w / 'fidelity' / label / f'{sid}.json')['findings']]
    for priority in ['must_fix', 'should_improve']:
        assert sum(f['priority'] == priority for f in findings) == result['unresolved_' + priority]
    assert read(w / 'book_critic.json')['verdict'] == result['book_critic']
    def forbidden_generate(**request):
        raise AssertionError('Completed-run resume attempted generation')
    assert run_book(book, forbidden_generate, 4) == result
    summary['books'][bid] = {'chapters': len(ids), 'words': words, 'target': target,
                             'protected_passages': protected, 'revision': verified['revision'],
                             'final_review_label': final_label,
                             'review_inputs_and_evidence': 'verified', 'local_patches': 'replayed exactly',
                             'final_alignments': 'current',
                             'completed_run_resume': 'latest snapshot retained without generation'}
responses = [read(p) for p in (ROOT / 'calls').rglob('response.json')]
assert all(r['completion']['model'] == MODEL for r in responses)
summary['completed_responses'] = len(responses)
summary['recorded_cost_usd'] = round(sum(r['cost_usd'] for r in responses), 6)
probe = read(ROOT / 'diagnostics/generation-probe.json')
summary['diagnostic_cost_usd'] = probe['estimated_cost_usd']
summary['total_recorded_cost_usd'] = round(summary['recorded_cost_usd'] + summary['diagnostic_cost_usd'], 6)
summary['provider_cache_read_tokens'] = sum(r['usage'].get('cache_read_input_tokens', 0) or 0 for r in responses)
summary['provider_cache_write_tokens'] = sum(r['usage'].get('cache_creation_input_tokens', 0) or 0 for r in responses)
unknown = [read(p) for p in (ROOT / 'calls').rglob('started.json') if not (p.parent / 'response.json').exists()]
summary['unsettled_requests'] = len(unknown)
summary['unsettled_reserve_usd'] = round(sum(r['maximum_cost_usd'] for r in unknown), 6)
print(json.dumps(summary, indent=2))
