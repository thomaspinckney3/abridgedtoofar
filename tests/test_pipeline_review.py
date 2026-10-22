"""Pipeline evidence -> hosted decisions -> external repair -> next publication."""
import copy
import json

import pytest

from forage import pipeline_review as pr, publication, review_apply, review_sync
from forage.llm import LLMResponse
from forage.production_state import atomic_json, inventory
from forage.review_anchors import chapter_hash
from .test_production_runner import pipeline, run_ok
from .test_review_lifecycle import _site, _comment
from .test_revision_review import decide


def package(book, kind='finding'):
    paras = pr.paragraphs((book.work_dir / 'segments/001.md').read_text())
    item = {'segment_id': '001', 'kind': kind, 'priority': 'must_fix' if kind == 'finding' else 'review',
            'title': 'Name the traveler', 'body': 'Use the source wording for the traveler.',
            'evidence': [], 'history': [], 'review_label': 'final_review',
            'chapter_anchor': chapter_hash(paras)}
    item['id'] = pr._item_id(book.book_id, item)
    return {'version': 1, 'book_id': book.book_id,
            'chapters': {'001': {'paragraphs': paras, 'anchor': chapter_hash(paras)}}, 'items': [item]}


def enrich(book, revision, data):
    manifest = publication.verify_revision(book, revision)
    atomic_json(book.work_dir / pr.FILENAME, data)
    return publication.snapshot_revision(book, text_revision=manifest['text_revision'],
        outputs=[o for o in manifest['outputs'] if o['path'] != pr.FILENAME] + inventory(book.work_dir, [pr.FILENAME]),
        media_index=json.loads((book.work_dir / 'media_manifest.json').read_text()),
        stage_summary=manifest['stage_summary'])['revision']


def notes(client):
    return client.get('/api/books/sample/comments').json()['comments']


@pytest.mark.parametrize('kind', ['finding', 'repair'])
def test_publish_decide_pull_apply_republish_preserves_history(pipeline, tmp_path, monkeypatch, kind):
    book, calls = pipeline
    original = run_ok(book)['review_revision']
    data = package(book, kind)
    revision = enrich(book, original, data)
    host, reviews, transport, client = _site(tmp_path)
    transport.publish(book, original)
    human = _comment(client, original)
    client.patch(f'/api/comments/{human["id"]}', json={'status': 'resolved'})
    before = calls.copy()
    transport.publish(book, revision)
    note = next(n for n in notes(client) if n.get('pipeline_review'))
    assert note['revision_review']['current'] and not note['stale']
    assert note['pipeline_review']['kind'] == kind
    assert note['scope'] == 'chapter' and note['draft_para'] is None
    assert calls == before
    assert review_sync.sync_feedback(book, transport)['pull']['counts'] == {'inactive': 2}
    assert client.get(f'/api/books/sample/comments?revision={original}').json()['comments'][0]['id'] == human['id']
    assert len(client.get(f'/api/books/sample/comments?revision={original}').json()['comments']) == 1
    assert client.patch(f'/api/comments/{note["id"]}', json={'status': 'resolved'}).status_code == 409
    assert client.delete(f'/api/comments/{note["id"]}').status_code == 409
    accepted = decide(client, note, 'accepted').json()
    assert accepted['status'] == 'resolved'
    transport.publish(book, revision)
    same = next(n for n in notes(client) if n['id'] == note['id'])
    assert same['revision_review']['state'] == 'accepted' and len(same['revision_reviews']) == 1
    assert decide(client, note, 'rejected', 'outdated page').status_code == 409
    reopened = decide(client, same, 'reopened').json()
    assert review_sync.sync_feedback(book, transport)['pull']['counts'] == {'inactive': 2}
    assert decide(client, reopened, 'rejected').status_code == 400
    requested = decide(client, reopened, 'rejected', 'Use wanderer instead.').json()
    assert review_sync.sync_feedback(book, transport)['pull']['counts'] == {'inactive': 1, 'eligible': 1}
    assert calls == before  # Website decisions and pulling never invoke generation.

    def provider(**kwargs):
        pending = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))['segments'][0]['pending']
        assert len(pending) == 1 and pending[0]['revision_request']['body'] == 'Use wanderer instead.'
        draft = (book.work_dir / 'segments/001.md').read_text().strip().replace('traveler', 'wanderer')
        calls['apply'] += 1
        return LLMResponse(json.dumps({'segment_id': '001', 'revised_draft': draft,
            'decisions': [{'feedback_key': p['feedback_key'], 'comment_id': p['comment_id'],
                'action': 'applied', 'reason': 'Used the requested word.',
                'changed_paragraphs': [0], 'target_paragraphs': []} for p in pending]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(review_apply, 'complete', provider)
    applied = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert applied['success'], applied
    assert calls['apply'] == 1 and calls['draft'] == before['draft']
    next_note = next(n for n in notes(client) if n['id'] == note['id'])
    assert next_note['revision_review']['current']
    assert next_note['revision_review']['state'] == 'pending'
    assert next_note['llm_responses'][0]['source'] == 'review_apply'
    assert next_note['llm_responses'][0]['body'] == 'Used the requested word.'
    assert len(next_note['revision_reviews']) == 3
    assert next_note['original_text'] == note['original_text']
    assert decide(client, requested, 'accepted').status_code == 409
    assert decide(client, next_note, 'accepted').status_code == 200
    assert host.status('sample')['release'] is None


def test_stale_review_and_malformed_package_are_blocked(pipeline, tmp_path):
    book, calls = pipeline
    original = run_ok(book)['review_revision']
    data = package(book)
    changed = copy.deepcopy(data)
    changed['chapters']['001']['paragraphs'] = ['Different text.']
    with pytest.raises(ValueError, match='context'):
        enrich(book, original, changed)
    revision = enrich(book, original, data)
    host, reviews, transport, client = _site(tmp_path)
    transport.publish(book, revision)
    note = notes(client)[0]
    manifest = publication.verify_revision(book, revision)
    alignment_path = book.work_dir / 'alignments/001.json'
    alignment = json.loads(alignment_path.read_text())
    alignment['draft_paragraphs'][0] += ' More words.'
    atomic_json(alignment_path, alignment)
    newer = publication.snapshot_revision(book, text_revision=manifest['text_revision'],
        outputs=inventory(book.work_dir, [o['path'] for o in manifest['outputs']]),
        media_index=json.loads((book.work_dir / 'media_manifest.json').read_text()),
        stage_summary=manifest['stage_summary'])['revision']
    transport.publish(book, newer)
    assert not notes(client)[0]['revision_review']['current']
    assert decide(client, note, 'accepted').status_code == 409


def test_prepare_review_validates_context_and_preserves_prose(pipeline):
    book, calls = pipeline
    result = run_ok(book)
    root = book.work_dir
    paras = pr.paragraphs((root / 'segments/001.md').read_text())
    atomic_json(root / 'fidelity/final_review/001.inputs.json', {
        'documents': {'001.revision': [{'paragraph': n, 'text': p} for n, p in enumerate(paras, 1)],
                      '001.source': [{'paragraph': 1, 'text': 'The source.'}]}})
    finding = {'title': 'Missing setup', 'claim': 'The setup was omitted.', 'priority': 'must_fix',
               'evidence': [{'document': '001.revision', 'paragraph': 1, 'quote': paras[0]}]}
    atomic_json(root / 'fidelity/final_review/001.json', {'findings': [finding]})
    atomic_json(root / 'full_run_result.json', {**result, 'final_review_label': 'final_review'})
    prose = (root / 'abridgment.txt').read_bytes()
    before = calls.copy()
    prepared = pr.prepare_review(book)
    assert prepared['text_revision'] == result['text_revision']
    assert pr.prepare_review(book) == prepared
    assert (root / 'abridgment.txt').read_bytes() == prose and calls == before
    alignment = json.loads((root / 'alignments/001.json').read_text())
    alignment['draft_paragraphs'][0] += ' Changed.'
    atomic_json(root / 'alignments/001.json', alignment)
    with pytest.raises(ValueError, match='changed'):
        pr.prepare_review(book)


def test_bad_repair_history_fails_packaging(pipeline):
    book, _ = pipeline
    run_ok(book)
    root = book.work_dir
    paras = pr.paragraphs((root / 'segments/001.md').read_text())
    context = {'documents': {'001.revision': [{'paragraph': n, 'text': p} for n, p in enumerate(paras, 1)]}}
    for label in ['initial_review', 'final_review']:
        atomic_json(root / f'fidelity/{label}/001.inputs.json', context)
        atomic_json(root / f'fidelity/{label}/001.json', {'findings': []})
    atomic_json(root / 'repairs/initial_review/001.json', {
        'adjudications': [], 'replacements': [{'old': 'not in draft', 'new': 'bad'}]})
    with pytest.raises(ValueError, match='ambiguous patch'):
        pr.build_package(book, 'final_review')


def test_superseded_pipeline_decision_returns_conflict_and_preserves_history(pipeline, tmp_path):
    book, _ = pipeline
    original = run_ok(book)['review_revision']
    first = enrich(book, original, package(book))
    _, reviews, transport, client = _site(tmp_path)
    transport.publish(book, first)
    old = notes(client)[0]
    accepted = decide(client, old, 'accepted').json()
    history = reviews.get(old['id'])['revision_reviews']
    data = package(book)
    data['items'][0]['title'] = 'Updated finding'
    data['items'][0]['id'] = pr._item_id(book.book_id, data['items'][0])
    transport.publish(book, enrich(book, original, data))
    assert len(notes(client)) == 1 and notes(client)[0]['id'] != old['id']
    response = decide(client, accepted, 'reopened')
    assert response.status_code == 409 and 'Reload' in response.json()['detail']
    assert reviews.get(old['id'])['revision_reviews'] == history
    historical = client.get(f'/api/books/sample/comments?revision={first}').json()['comments']
    assert historical[0]['revision_reviews'] == history
