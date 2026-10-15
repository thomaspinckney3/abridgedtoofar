"""Alignment reuse follows current prose, including legacy embedded inputs."""
import json
from unittest.mock import Mock

import pytest

from forage import align
from forage.artifacts import Book, write_json
from forage.llm import LLMResponse
from forage.webapp.store import ArtifactStore, ReviewStore, anchor_hash, build_edits


@pytest.fixture
def aligned_book(tmp_path, monkeypatch):
    source = tmp_path / 'books' / 'sample' / 'source.txt'
    source.parent.mkdir(parents=True)
    source.write_text('Original book.')
    work = tmp_path / 'work' / 'sample'
    (work / 'chapters').mkdir(parents=True)
    (work / 'segments').mkdir()
    (work / 'chapters' / '001.md').write_text('The source paragraph.')
    (work / 'segments' / '001.md').write_text('The old paragraph.')
    write_json(work / 'plan.json', {'segments': [dict(id='001', source_word_count=200, diegetic_status='diegetic')]})
    book = Book('sample', source, {}, work)
    fake = Mock(return_value=LLMResponse(json.dumps([dict(draft_para=0, source_paras=[0], note='compressed')]),
                                       'fixture', 1, 1, 0, 'end_turn'))
    monkeypatch.setattr(align, 'complete', fake)
    assert align.align_book(book)['aligned'] == ['001']
    return book, fake


def test_legacy_alignment_reuses_matching_normalized_inputs(aligned_book):
    book, fake = aligned_book
    (book.work_dir / 'segments' / '001.md').write_text('\n The old paragraph. \n\n')
    result = align.align_book(book)
    assert result['skipped'] == [('001', 'already aligned')]
    assert not result['errors']
    assert fake.call_count == 1


@pytest.mark.parametrize('which', ['chapters', 'segments'])
def test_changed_input_regenerates(aligned_book, which):
    book, fake = aligned_book
    (book.work_dir / which / '001.md').write_text('The corrected paragraph.')
    assert align.align_book(book)['aligned'] == ['001']
    assert fake.call_count == 2
    cached = json.loads((book.work_dir / 'alignments' / '001.json').read_text())
    field = 'source_paragraphs' if which == 'chapters' else 'draft_paragraphs'
    assert cached[field] == ['The corrected paragraph.']


def test_regenerated_review_view_marks_old_comment_stale(aligned_book, tmp_path):
    book, _ = aligned_book
    store = ArtifactStore(work_dir=tmp_path / 'work', books_dir=tmp_path / 'books')
    reviews = ReviewStore(db_path=tmp_path / 'reviews.db')
    reviews.add(book_id='sample', segment_id='001', draft_para=0, anchor=anchor_hash('The old paragraph.'),
                quote='', severity='minor', kind='clarity', body='Revise this.', author='reviewer')
    assert build_edits(store, reviews, 'sample')['stale_count'] == 0
    (book.work_dir / 'segments' / '001.md').write_text('The corrected paragraph.')
    assert align.align_book(book)['aligned'] == ['001']
    assert store.chapter_view('sample', '001')['blocks'][0]['draft'] == 'The corrected paragraph.'
    assert build_edits(store, reviews, 'sample')['stale_count'] == 1


@pytest.mark.parametrize('corrupt', ['{', '[]', '{"mapping":null}', None])
def test_corrupt_or_missing_cache_regenerates(aligned_book, corrupt):
    book, fake = aligned_book
    path = book.work_dir / 'alignments' / '001.json'
    if corrupt is None:
        path.unlink()
    else:
        path.write_text(corrupt)
    assert align.align_book(book)['aligned'] == ['001']
    assert fake.call_count == 2


@pytest.mark.parametrize('failure', ['provider', 'invalid_json', 'partial_mapping', 'truncated', 'source_missing', 'draft_read'])
def test_failures_report_error_and_preserve_old_view(aligned_book, monkeypatch, failure):
    book, fake = aligned_book
    path = book.work_dir / 'alignments' / '001.json'
    before = path.read_bytes()
    (book.work_dir / 'segments' / '001.md').write_text('The corrected paragraph.')
    if failure == 'provider':
        fake.side_effect = RuntimeError('offline provider failed')
    elif failure == 'source_missing':
        (book.work_dir / 'chapters' / '001.md').unlink()
    elif failure == 'draft_read':
        (book.work_dir / 'segments' / '001.md').write_bytes(b'\xff')
    else:
        text = {'invalid_json': '{}', 'partial_mapping': '[]', 'truncated': '[{"draft_para":0,"source_paras":[0]}]'}[failure]
        fake.return_value = LLMResponse(text, 'fixture', 1, 1, 0, 'length' if failure == 'truncated' else 'end_turn')
    result = align.align_book(book)
    assert result['errors'] and not result['aligned'] and not result['skipped']
    assert path.read_bytes() == before


def test_invalid_mapping_in_matching_cache_regenerates(aligned_book):
    book, fake = aligned_book
    path = book.work_dir / 'alignments' / '001.json'
    cached = json.loads(path.read_text())
    cached['mapping'] = None
    write_json(path, cached)
    assert align.align_book(book)['aligned'] == ['001']
    assert fake.call_count == 2


def test_alignment_write_failure_preserves_previous_file(aligned_book, monkeypatch):
    book, _ = aligned_book
    path = book.work_dir / 'alignments' / '001.json'
    before = path.read_bytes()
    (book.work_dir / 'segments' / '001.md').write_text('The corrected paragraph.')
    monkeypatch.setattr(align.os, 'replace', Mock(side_effect=OSError('injected publication failure')))
    result = align.align_book(book)
    assert result['errors'] and not result['aligned']
    assert path.read_bytes() == before
    assert not list(path.parent.glob('*.tmp'))
