"""Paragraph identity survives insertion and corrections; no provider calls."""
import json
from pathlib import Path

import pytest

from forage.review_anchors import anchor_hash, locate, make_binding
from forage import review_apply
from forage.artifacts import Book
from tests.conftest import BOOK_ID, SEGMENT_ID, sign_in


def note(text='Reviewed passage.', index=1):
    return {'id': 'n', 'draft_para': index, 'anchor': anchor_hash(text),
            'original_text': text, 'scope': 'paragraph', 'note': 'Clarify speaker.',
            'status': 'open'}


def test_insertion_relocates_by_identity_and_preserves_original():
    row = note()
    result = locate(row, ['Inserted.', 'Before.', 'Reviewed passage.', 'After.'])
    assert result['current_draft_para'] == 2 and not result['stale']
    assert row['draft_para'] == 1 and row['original_text'] == 'Reviewed passage.'


@pytest.mark.parametrize('paras', [[], ['Unrelated.', 'Wrong passage.'], ['Reviewed passage.'] * 2])
def test_missing_or_ambiguous_target_never_reuses_old_index(paras):
    result = locate(note(), paras)
    assert result['current_draft_para'] is None


def test_split_revision_uses_verified_binding_and_still_detects_later_changes():
    row = note()
    revised = ['Before.', 'First part of correction.', 'Second part of correction.', 'After.']
    binding = make_binding(row, revised, [1, 2])
    result = locate(row, revised, binding)
    assert result['current_draft_paras'] == [1, 2] and result['stale']
    assert locate(row, ['Inserted.', *revised], binding)['current_draft_paras'] == [2, 3]
    revised[1] = 'Different content again.'
    assert locate(row, revised, binding)['current_draft_para'] is None


def test_binding_cannot_retarget_another_original_note():
    row = note()
    binding = make_binding(row, ['Correction.'], [0])
    other = note('Different original.')
    assert locate(other, ['Correction.'], binding)['current_draft_para'] is None


def test_http_export_does_not_replace_reviewed_text_at_old_index(client, artifact_tree):
    sign_in(client)
    row = client.post(f'/api/books/{BOOK_ID}/comments', json={
        'segment_id': SEGMENT_ID, 'draft_para': 1, 'body': 'Clarify this.'}).json()
    path = artifact_tree / 'work' / BOOK_ID / 'alignments' / f'{SEGMENT_ID}.json'
    alignment = json.loads(path.read_text())
    alignment['draft_paragraphs'].insert(0, 'Inserted paragraph.')
    for entry in alignment['mapping']:
        entry['draft_para'] += 1
    path.write_text(json.dumps(alignment))
    current = client.get(f'/api/books/{BOOK_ID}/chapters/{SEGMENT_ID}').json()['comments'][0]
    assert current['draft_para'] == 1 and current['current_draft_para'] == 2
    assert not current['stale']
    alignment['draft_paragraphs'][2] = 'Completely revised passage.'
    path.write_text(json.dumps(alignment))
    current = client.get(f'/api/books/{BOOK_ID}/comments').json()['comments'][0]
    assert current['current_draft_para'] is None and current['stale']
    exported = client.get(f'/api/books/{BOOK_ID}/edits.json').json()['segments'][0]['comments'][0]
    assert exported['paragraph'] == row['original_text'] == 'The second, compressed.'


def test_legacy_stale_export_does_not_substitute_unrelated_text(client, artifact_tree):
    from forage.webapp.store import ReviewStore
    # The old schema did not save original_text; a stale old index proves nothing.
    store = client.app.state.reviews
    store.add(book_id=BOOK_ID, segment_id=SEGMENT_ID, draft_para=1,
              anchor=anchor_hash('Earlier text.'), quote='', severity='minor',
              kind='clarity', body='Fix that.', author='A')
    exported = client.get(f'/api/books/{BOOK_ID}/edits.json').json()['segments'][0]['comments'][0]
    assert exported['paragraph'] is None and exported['current_draft_para'] is None


def test_apply_retargets_shifted_note_and_blocks_unknown_before_provider(tmp_path, monkeypatch):
    book = Book('sample', tmp_path / 'source.txt', {}, tmp_path)
    (tmp_path / 'segments').mkdir()
    (tmp_path / 'segments/001.md').write_text('Inserted.\n\nReviewed passage.')
    overlay = {'segments': [{'segment_id': '001', 'comments': [note(index=0),
        {**note('No longer present.'), 'id': 'missing'}]}]}
    plan = review_apply.pending_review_feedback(book, overlay=overlay)
    assert plan['pending_count'] == plan['blocked_count'] == 1
    item = plan['segments'][0]['pending'][0]
    assert item['draft_para'] == 1 and item['original_draft_para'] == 0
    assert item['paragraph'] == item['reviewed_paragraph'] == 'Reviewed passage.'


def test_legacy_binding_recovers_original_and_exported_current_location(client, artifact_tree):
    from forage.webapp.store import ReviewStore
    store = client.app.state.reviews
    row = store.add(book_id=BOOK_ID, segment_id=SEGMENT_ID, draft_para=0,
              anchor=anchor_hash('Earlier text.'), quote='', severity='minor',
              kind='clarity', body='Fix that.', author='A')
    paras = ['The first source paragraph.', 'The second, compressed.']
    binding = make_binding({**row, 'original_text': 'Earlier text.'}, paras, [1])
    directory = artifact_tree / 'work' / BOOK_ID / 'editorial'
    directory.mkdir()
    (directory / 'review_apply_ledger.json').write_text(json.dumps({'entries': [{
        'comment_id': row['id'], 'segment_id': SEGMENT_ID, 'source_id': store.source_id,
        'reason': 'Corrected passage.', 'action': 'applied', 'comment_binding': binding}]}))
    response = client.get(f'/api/books/{BOOK_ID}/chapters/{SEGMENT_ID}').json()['comments'][0]
    assert response['draft_para'] == 0 and response['current_draft_paras'] == [1]
    assert response['original_text'] == 'Earlier text.' and response['stale']
    exported = client.get(f'/api/books/{BOOK_ID}/edits.json').json()['segments'][0]['comments'][0]
    assert exported['paragraph'] == 'Earlier text.'


def test_duplicate_text_uses_recorded_whole_chapter_not_an_arbitrary_occurrence():
    from forage.review_anchors import chapter_hash
    paras = ['Repeated.', 'Other.', 'Repeated.']
    row = {**note('Repeated.', 2), 'chapter_anchor': chapter_hash(paras)}
    assert locate(row, paras)['current_draft_para'] == 2
    assert locate(row, ['Inserted.', *paras])['current_draft_para'] is None


@pytest.mark.parametrize('targets', [None, [True], [-1], [99], [2, 1], [1, 1]])
def test_bad_generation_target_map_is_rejected(targets):
    with pytest.raises(ValueError):
        make_binding(note(), ['Before.', 'After.', 'End.'], targets)


def test_regeneration_records_split_targets_with_draft_and_ledger(tmp_path, monkeypatch):
    from forage.llm import LLMResponse
    from forage.webapp.store import ArtifactStore, ReviewStore, build_feedback
    book = Book('sample', tmp_path / 'source.txt', {}, tmp_path)
    for directory in ('segments', 'chapters', 'editorial', 'alignments'):
        (tmp_path / directory).mkdir()
    before = 'Before.\n\nHe arrived; she left.\n\nAfter.'
    after = 'Before.\n\nHe arrived.\n\nShe left.\n\nAfter.'
    (tmp_path / 'chapters/001.md').write_text(before)
    (tmp_path / 'segments/001.md').write_text(before)
    comment = note('He arrived; she left.', 1)
    overlay = {'segments': [{'segment_id': '001', 'comments': [comment]}]}
    (tmp_path / 'editorial/edits.json').write_text(json.dumps(overlay))
    planned = review_apply.pending_review_feedback(book)['segments'][0]['pending'][0]
    def provider(**kwargs):
        assert 'He arrived; she left.' in kwargs['prompt']
        return LLMResponse(json.dumps({'segment_id': '001', 'revised_draft': after,
            'decisions': [{'feedback_key': planned['feedback_key'], 'action': 'applied',
                          'reason': 'Split the actions.', 'changed_paragraphs': [1],
                          'target_paragraphs': [1, 2]}]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(review_apply, 'complete', provider)
    result = review_apply.apply_review_feedback(book)
    assert result['segments_applied'] == 1
    ledger = json.loads((tmp_path / 'editorial/review_apply_ledger.json').read_text())
    binding = ledger['entries'][0]['comment_binding']
    assert locate(comment, after.split('\n\n'), binding)['current_draft_paras'] == [1, 2]
    assert review_apply.pending_review_feedback(book)['pending_count'] == 0
    assert (tmp_path / 'segments/001.md').read_text().strip() == after


def test_split_note_displays_at_relevant_part_and_follows_insertions():
    row = note('Tommy nodded. Her eyes misted. "Good sort, Tommy."', 18)
    revised = ['Before.', 'Tommy nodded.', '"Good sort, Tommy," said Tuppence.']
    binding = make_binding(row, revised, [1, 2], display_paragraph=2)
    assert locate(row, revised, binding)['current_draft_para'] == 2
    assert locate(row, ['Inserted.', *revised], binding)['current_draft_para'] == 3
    with pytest.raises(ValueError, match='display paragraph'):
        make_binding(row, revised, [1, 2], display_paragraph=0)
