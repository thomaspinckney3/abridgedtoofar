"""Reviewer decisions survive reload, remain revision-bound, and feed real stages."""
import json

import pytest

from forage.artifacts import Book
from forage.llm import LLMResponse
from forage.review_anchors import make_binding
from forage import review_apply, review_sync
from forage.webapp.store import ReviewStore
from .conftest import BOOK_ID, SEGMENT_ID, sign_in
from .test_production_runner import pipeline, run_ok
from .test_review_lifecycle import _site, _comment
from .test_review_sync import FeedTransport


def decide(client, note, action, body='', **overrides):
    review = note['revision_review']
    payload = {k: review[k] for k in ('response_id', 'version', 'chapter_anchor', 'publication_revision')}
    return client.post(f'/api/comments/{note["id"]}/revision-review',
                       json={**payload, 'action': action, 'body': body, **overrides})


def current(client, book=BOOK_ID):
    return client.get(f'/api/books/{book}/comments').json()['comments'][0]


@pytest.fixture
def revised(client, artifact_tree):
    sign_in(client)
    row = client.post(f'/api/books/{BOOK_ID}/comments', json={
        'segment_id': SEGMENT_ID, 'draft_para': 0, 'body': 'Clarify who speaks.'}).json()
    root = artifact_tree / 'work' / BOOK_ID
    alignment = root / 'alignments/001.json'
    data = json.loads(alignment.read_text())
    data['draft_paragraphs'][0] = 'Tommy spoke clearly.'
    alignment.write_text(json.dumps(data))
    (root / 'segments').mkdir()
    (root / 'segments/001.md').write_text('\n\n'.join(data['draft_paragraphs']))
    plan = json.loads((root / 'plan.json').read_text())
    plan['segments'][0].update(diegetic_status='diegetic', target_word_count=50)
    (root / 'plan.json').write_text(json.dumps(plan))
    (root / 'editorial').mkdir()
    entry = {'comment_id': row['id'], 'source_id': client.app.state.reviews.source_id,
             'segment_id': '001', 'action': 'applied', 'reason': 'Named the speaker.',
             'run_id': 'first', 'feedback_key': 'first-key', 'used_at': '2026-10-19T12:00:00Z',
             'comment_binding': make_binding(row, data['draft_paragraphs'], [0])}
    (root / 'editorial/review_apply_ledger.json').write_text(json.dumps({'entries': [entry]}))
    return client, root, current(client)


def test_accept_reopen_reject_preserves_identity_history_and_persistence(revised):
    client, root, original = revised
    accepted = decide(client, original, 'accepted', author='spoofed').json()
    assert accepted['status'] == 'resolved' and accepted['revision_review']['state'] == 'accepted'
    assert client.get(f'/api/books/{BOOK_ID}/edits.json').json()['comment_count'] == 0
    store = ReviewStore(client.app.state.reviews.db_path)
    assert store.get(original['id'])['revision_reviews'][0]['author'] == 'alice'
    assert decide(client, original, 'accepted').status_code == 409
    assert decide(client, accepted, 'rejected', 'Change it.').status_code == 409
    reopened = decide(client, accepted, 'reopened').json()
    assert reopened['revision_review']['state'] == 'reopened'
    rejected = decide(client, reopened, 'rejected', 'Keep the speaker, but shorten the line.').json()
    assert rejected['revision_review']['state'] == 'rejected' and rejected['status'] == 'open'
    assert [e['action'] for e in rejected['revision_reviews']] == ['accepted', 'reopened', 'rejected']
    for key in ('id', 'body', 'anchor', 'original_text', 'draft_para', 'created_at'):
        assert rejected[key] == original[key]
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    pulled = review_sync.pull_feedback(book, FeedTransport(feed))
    assert pulled['counts'] == {'eligible': 1}
    plan = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
    assert plan['pending_count'] == 1 and plan['blocked_count'] == 0
    item = plan['segments'][0]['pending'][0]
    assert 'Keep the speaker, but shorten the line.' in item['note']
    assert item['paragraph'] == 'Tommy spoke clearly.' and item['reviewed_paragraph'] == original['original_text']
    assert item['revision_request']['id'] == rejected['revision_reviews'][-1]['id']


@pytest.mark.parametrize('action,body', [('rejected', ''), ('rejected', '  '), ('rejected', None), ('invalid', 'x'), ({}, 'x')])
def test_bad_decisions_do_not_change_reviews(revised, action, body):
    client, _, note = revised
    assert decide(client, note, action, body).status_code == 400
    assert current(client)['revision_reviews'] == []


def test_auth_and_stale_decisions_are_rejected(revised):
    client, root, note = revised
    assert decide(client, note, 'reopened').status_code == 409
    assert decide(client, note, 'accepted', response_id='old').status_code == 409
    assert decide(client, note, 'accepted', publication_revision='f'*64).status_code == 409
    assert decide(client, note, 'accepted', version=True).status_code == 409
    path = root / 'alignments/001.json'
    data = json.loads(path.read_text())
    data['draft_paragraphs'][0] = 'A different correction.'
    path.write_text(json.dumps(data))
    assert decide(client, note, 'accepted').status_code == 409
    assert not current(client)['revision_review']['current']
    assert current(client)['revision_reviews'] == []
    client.delete('/api/session')
    assert decide(client, note, 'accepted').status_code == 401


def test_editing_the_note_invalidates_an_older_review_page(revised):
    client, _, note = revised
    assert client.patch(f'/api/comments/{note["id"]}', json={'body': 'A clarified concern.'}).status_code == 200
    assert decide(client, note, 'accepted').status_code == 409
    assert current(client)['revision_reviews'] == []


def test_reverting_to_original_text_does_not_allow_accepting_discarded_revision(revised):
    client, root, note = revised
    path = root / 'alignments/001.json'
    alignment = json.loads(path.read_text())
    alignment['draft_paragraphs'][0] = note['original_text']
    path.write_text(json.dumps(alignment))
    reverted = current(client)
    assert reverted['attachment_status'] == 'exact'
    assert not reverted['revision_review']['current']
    assert decide(client, reverted, 'accepted').status_code == 409


@pytest.fixture
def removed_passage(revised):
    client, root, note = revised
    path = root / 'alignments/001.json'
    alignment = json.loads(path.read_text())
    remaining = alignment['draft_paragraphs'][1:]
    alignment['draft_paragraphs'] = remaining
    alignment['mapping'] = [{'draft_para': 0, 'source_paras': [1], 'note': 'compressed'}]
    path.write_text(json.dumps(alignment))
    (root / 'segments/001.md').write_text('\n\n'.join(remaining) + '\n')
    (root / 'chapters').mkdir()
    (root / 'chapters/001.md').write_text(note['original_text'] + '\n\n' + '\n\n'.join(remaining))
    path = root / 'editorial/review_apply_ledger.json'
    ledger = json.loads(path.read_text())
    ledger['entries'][0]['comment_binding'] = make_binding(note, remaining, [])
    ledger['entries'][0]['draft_after_hash'] = review_apply._text_hash('\n\n'.join(remaining) + '\n')
    path.write_text(json.dumps(ledger))
    return client, root, current(client)


def test_removed_passage_can_be_reviewed_and_restored_by_feedback(removed_passage, monkeypatch):
    client, root, note = removed_passage
    assert note['attachment_status'] == 'removed' and note['revision_review']['current']
    accepted = decide(client, note, 'accepted').json()
    assert accepted['revision_review']['state'] == 'accepted'
    reopened = decide(client, accepted, 'reopened').json()
    rejected = decide(client, reopened, 'rejected', 'Restore the original passage.').json()
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    assert review_sync.pull_feedback(book, FeedTransport(feed))['counts'] == {'eligible': 1}
    pending = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
    item = pending['segments'][0]['pending'][0]
    assert pending['pending_count'] == 1 and item['target_paragraphs'] == []
    assert item['revision_request']['body'] == rejected['revision_review']['request']['body']
    def provider(**kwargs):
        return LLMResponse(json.dumps({'segment_id': '001',
            'revised_draft': (root / 'chapters/001.md').read_text(),
            'decisions': [{'feedback_key': item['feedback_key'], 'comment_id': item['comment_id'],
                           'action': 'applied', 'reason': 'Restored the passage.',
                           'changed_paragraphs': [0], 'target_paragraphs': [0]}]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(review_apply, 'complete', provider)
    applied = review_apply.apply_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
    assert applied['segments_applied'] == 1, applied
    assert (root / 'segments/001.md').read_text().startswith(note['original_text'])


def test_removed_passage_decision_and_request_reject_a_changed_chapter(removed_passage):
    client, root, note = removed_passage
    assert decide(client, note, 'rejected', 'Restore it.').status_code == 200
    path = root / 'alignments/001.json'
    alignment = json.loads(path.read_text())
    alignment['draft_paragraphs'][0] += ' More context.'
    path.write_text(json.dumps(alignment))
    (root / 'segments/001.md').write_text('\n\n'.join(alignment['draft_paragraphs']))
    changed = current(client)
    assert not changed['revision_review']['current']
    assert decide(client, changed, 'accepted').status_code == 409
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    assert review_sync.pull_feedback(book, FeedTransport(feed))['counts'] == {'inactive': 1}


def test_accepting_a_rejected_revision_cancels_the_pending_request(revised):
    client, root, note = revised
    rejected = decide(client, note, 'rejected', 'Shorten it.').json()
    accepted = decide(client, rejected, 'accepted').json()
    assert accepted['revision_review']['request'] is None
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    assert review_sync.pull_feedback(book, FeedTransport(feed))['counts'] == {'inactive': 1}


def test_reopened_revision_waits_for_rejection_feedback(revised):
    client, root, note = revised
    accepted = decide(client, note, 'accepted').json()
    reopened = decide(client, accepted, 'reopened').json()
    overlay = client.get(f'/api/books/{BOOK_ID}/edits.json').json()
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    assert review_apply.pending_review_feedback(book, overlay=overlay)['pending_count'] == 0
    assert reopened['status'] == 'open'


def test_request_cannot_apply_after_the_reviewed_chapter_changes(revised):
    client, root, note = revised
    rejected = decide(client, note, 'rejected', 'Shorten this.').json()
    overlay = client.get(f'/api/books/{BOOK_ID}/edits.json').json()
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    path = root / 'segments/001.md'
    path.write_text(path.read_text() + '\n\nAn intervening edit.')
    plan = review_apply.pending_review_feedback(book, overlay=overlay)
    assert plan['pending_count'] == 0 and plan['blocked_count'] == 1
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    assert review_sync.pull_feedback(book, FeedTransport(feed))['counts'] == {'stale': 1}


def test_new_response_needs_its_own_acceptance(revised):
    client, root, note = revised
    accepted = decide(client, note, 'accepted').json()
    ledger_path = root / 'editorial/review_apply_ledger.json'
    ledger = json.loads(ledger_path.read_text())
    ledger['entries'].append({**ledger['entries'][0], 'run_id': 'next',
                              'used_at': '2026-10-19T13:00:00Z', 'reason': 'Another response.'})
    ledger_path.write_text(json.dumps(ledger))
    new = current(client)
    assert new['revision_review']['state'] == 'pending' and new['status'] == 'open'
    assert new['revision_review']['response_id'] != accepted['revision_review']['response_id']
    assert decide(client, accepted, 'reopened').status_code == 409
    assert len(new['revision_reviews']) == 1
    counts = client.get(f'/api/books/{BOOK_ID}/chapters').json()['chapters'][0]['comments']
    assert counts == {'total': 1, 'open': 1}


def test_rejected_book_response_targets_its_chapter_from_any_page(client, artifact_tree):
    sign_in(client)
    row = client.post(f'/api/books/{BOOK_ID}/comments', json={'scope': 'book', 'body': 'Clarify the dialogue.'}).json()
    root = artifact_tree / 'work' / BOOK_ID
    paragraphs = ['Tommy spoke clearly.']
    data = json.loads((root / 'alignments/001.json').read_text())
    data['draft_paragraphs'] = paragraphs
    data['mapping'] = [{'draft_para': 0, 'source_paras': [0], 'note': 'compressed'}]
    (root / 'alignments/002.json').write_text(json.dumps(data))
    (root / 'segments').mkdir()
    (root / 'segments/002.md').write_text(paragraphs[0])
    plan = json.loads((root / 'plan.json').read_text())
    plan['segments'].append({'id': '002', 'title': 'Second', 'diegetic_status': 'diegetic', 'target_word_count': 50})
    (root / 'plan.json').write_text(json.dumps(plan))
    (root / 'editorial').mkdir()
    entry = {'comment_id': row['id'], 'source_id': client.app.state.reviews.source_id,
             'segment_id': '002', 'action': 'applied', 'reason': 'Changed chapter two.',
             'draft_after_hash': review_apply._text_hash(paragraphs[0] + '\n')}
    (root / 'editorial/review_apply_ledger.json').write_text(json.dumps({'entries': [entry]}))
    note = client.get(f'/api/books/{BOOK_ID}/chapters/001').json()['book_comments'][0]
    assert note['revision_review']['segment_id'] == '002' and note['revision_review']['current']
    rejected = decide(client, note, 'rejected', 'Shorten the dialogue further.')
    assert rejected.status_code == 200, rejected.text
    book = Book(BOOK_ID, root / 'source.txt', {}, root)
    feed = client.get(f'/api/books/{BOOK_ID}/feedback').json()
    assert review_sync.pull_feedback(book, FeedTransport(feed))['counts'] == {'eligible': 1}
    plan = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
    assert plan['pending_count'] == 1
    assert [s['segment_id'] for s in plan['segments']] == ['002']


def test_hosted_accept_reopen_reject_apply_republish_cycle(pipeline, monkeypatch, tmp_path):
    book, calls = pipeline
    a = run_ok(book)['review_revision']
    host, reviews, transport, client = _site(tmp_path)
    transport.publish(book, a)
    original = _comment(client, a)
    def provider(**kwargs):
        planned = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
        items = planned['segments'][0]['pending']
        before = (book.work_dir / 'segments/001.md').read_text().strip()
        after = before.replace('traveler', 'wanderer') if calls['apply'] == 0 else before.replace('wanderer', 'walker')
        if calls['apply']:
            assert items[0]['revision_request']['body'] == 'Use walker instead.'
        calls['apply'] += 1
        return LLMResponse(json.dumps({'segment_id': '001', 'revised_draft': after,
            'decisions': [{'feedback_key': p['feedback_key'], 'comment_id': p['comment_id'],
                'action': 'applied' if after != before else 'skipped', 'reason': 'Clarified the word.',
                'changed_paragraphs': [0] if after != before else [],
                'target_paragraphs': [0]} for p in items]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(review_apply, 'complete', provider)
    first = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert first['success'], first
    b = first['publication']['revision']
    note = current(client, 'sample')
    assert note['revision_review']['current'] and note['revision_review']['state'] == 'pending'
    assert note['llm_responses'][0]['body'] == 'Clarified the word.'
    assert (host.root / 'sample/publications' / b / 'review_responses.json').is_file()
    accepted = decide(client, note, 'accepted').json()
    counts = calls.copy()
    assert review_sync.sync_feedback(book, transport, apply=True, republish=True)['success']
    assert calls == counts
    reopened = decide(client, accepted, 'reopened').json()
    assert review_sync.sync_feedback(book, transport)['pull']['counts'] == {'inactive': 1}
    rejected = decide(client, reopened, 'rejected', 'Use walker instead.').json()
    second = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert second['success'], second
    c = second['publication']['revision']
    assert c != b and calls['apply'] == 2
    note = current(client, 'sample')
    assert note['revision_review']['state'] == 'pending' and len(note['revision_reviews']) == 3
    assert note['original_text'] == original['original_text']
    assert note['current_draft_para'] == 0
    assert 'walker' in client.get('/api/books/sample/chapters/001').json()['blocks'][0]['draft']
    assert decide(client, rejected, 'accepted').status_code == 409
    assert decide(client, note, 'accepted').status_code == 200
    counts = calls.copy()
    assert review_sync.sync_feedback(book, transport, apply=True, republish=True)['success']
    assert calls == counts
    history = host.status('sample')['review']['history']
    assert [x['revision'] for x in history] == [a, b, c]
    # Even a skipped request must deliver a new, reviewable response.
    reopened = decide(client, current(client, 'sample'), 'reopened').json()
    assert decide(client, reopened, 'rejected', 'Use walker instead.').status_code == 200
    before = (book.work_dir / 'segments/001.md').read_bytes()
    skipped = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert skipped['success'], skipped
    assert skipped['publication']['revision'] != c and calls['apply'] == 3
    assert (book.work_dir / 'segments/001.md').read_bytes() == before
    note = current(client, 'sample')
    assert note['revision_review']['state'] == 'pending'
    assert note['llm_responses'][0]['action'] == 'skipped'
    assert not (host.root / 'sample/feedback_pending').exists()
