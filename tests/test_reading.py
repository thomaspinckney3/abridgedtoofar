"""Completed reading editions preserve prose, selection and attribution."""
import json

import pytest

from forage import publication, review_package
from forage.production_state import inventory
from forage.reading import completed_text, reading_document
from forage.webapp.app import create_app
from forage.webapp.store import ArtifactStore, ReviewStore
from fastapi.testclient import TestClient

from .conftest import BOOK_ID
from .test_publication import publication_input
from .test_artifact_safety import package_tree


def completed(root, text='Chapter One\n\nThe completed book, including its ending.\n'):
    book = root / 'work' / BOOK_ID
    (book / 'assembly_report.json').write_text(json.dumps({
        'partial': False, 'segments_missing': 0, 'segments_drafted': 1,
        'abridgment_path': '/private/operator/work/abridgment.txt',
    }))
    (book / 'abridgment.txt').write_text(text)
    return book


def test_reader_is_separate_and_does_not_expose_editorial_content(client, artifact_tree):
    complete = 'Chapter One\n\nThe full assembled text.\n\nThe ending absent from the review mapping.\n'
    completed(artifact_tree, complete)
    for url in ['/read', f'/read/{BOOK_ID}']:
        shell = client.get(url)
        assert shell.status_code == 200
        assert '/static/reader.js' in shell.text and '/static/app.js' not in shell.text
        assert 'signin-dialog' not in shell.text
    listing = client.get('/api/books/reading').json()['books']
    assert [b['book_id'] for b in listing] == [BOOK_ID]
    response = client.get(f'/api/books/{BOOK_ID}/reading')
    assert response.status_code == 200
    book = response.json()
    assert book['chapters'][0]['paragraphs'][-1] == 'The ending absent from the review mapping.'
    assert all(f'"{key}":' not in response.text for key in ['source_paragraphs', 'mapping', 'diagnostics', 'comments', 'diff_html'])
    assert 'The second, compressed.' not in response.text
    download = client.get(book['download_url'])
    assert download.status_code == 200
    assert complete.rstrip() in download.text
    assert download.headers['content-type'].startswith('text/plain; charset=utf-8')
    assert download.headers['content-disposition'] == f'attachment; filename="{BOOK_ID}-abridged.txt"'
    assert download.headers['x-content-type-options'] == 'nosniff'
    assert 'Abridged Too Far' in download.text and 'CC BY 4.0' in download.text
    assert 'https://creativecommons.org/licenses/by/4.0/' in download.text
    assert 'including commercially' in download.text
    assert 'original source text' in download.text.lower()
    assert 'public domain' in download.text
    assert book['license']['copyright'] in download.text


@pytest.mark.parametrize('report', [None, {}, {'partial': True, 'segments_missing': 0, 'segments_drafted': 1},
    {'partial': False, 'segments_missing': 1, 'segments_drafted': 1},
    {'partial': False, 'segments_missing': 0, 'segments_drafted': 0}])
def test_partial_or_unproven_assemblies_are_not_offered_as_complete(client, artifact_tree, report):
    root = artifact_tree / 'work' / BOOK_ID
    (root / 'abridgment.txt').write_text('A partial book.')
    if report is not None:
        (root / 'assembly_report.json').write_text(json.dumps(report))
    assert client.get('/api/books/reading').json() == {'books': []}
    assert client.get(f'/api/books/{BOOK_ID}/reading').status_code == 404
    assert client.get(f'/api/books/{BOOK_ID}/reading.txt').status_code == 404


def test_changed_local_book_requires_reload_before_download(client, artifact_tree):
    root = completed(artifact_tree)
    book = client.get(f'/api/books/{BOOK_ID}/reading').json()
    (root / 'abridgment.txt').write_text('A newer completed book.')
    assert client.get(book['download_url']).status_code == 409
    assert client.get(f'/api/books/{BOOK_ID}/reading?version={book["edition_id"]}').status_code == 409
    fresh = client.get(f'/api/books/{BOOK_ID}/reading').json()
    assert fresh['edition_id'] != book['edition_id']
    assert 'A newer completed book.' in client.get(fresh['download_url']).text


def test_reader_reuses_immutable_selection_after_review_moves(publication_input, tmp_path):
    book, options = publication_input
    first = publication.snapshot_revision(book, **options)
    publication.promote_release(book, first['revision'])
    store = ArtifactStore(work_dir=book.work_dir.parent, books_dir=book.source_path.parent.parent)
    app = create_app(artifacts=store, reviews=ReviewStore(tmp_path / 'reader.db'))
    with TestClient(app) as client:
        original = client.get('/api/books/sample/reading').json()
        (book.work_dir / 'abridgment.txt').write_text('A newer book.')
        options['outputs'] = inventory(book.work_dir, [i['path'] for i in options['outputs']])
        second = publication.snapshot_revision(book, **options)
        assert second['revision'] != first['revision']
        assert client.get('/api/books/sample/reading').json()['publication_revision'] == second['revision']
        assert client.get('/api/books/sample/reading?channel=release').json()['publication_revision'] == first['revision']
        historical = client.get(original['download_url'])
        assert 'An abridged book.' in historical.text and 'A newer book.' not in historical.text
        assert client.get('/api/books/sample/reading?revision=' + 'f' * 64).status_code == 404


def test_reader_refuses_corrupt_published_text(publication_input, tmp_path):
    book, options = publication_input
    first = publication.snapshot_revision(book, **options)
    store = ArtifactStore(work_dir=book.work_dir.parent, books_dir=book.source_path.parent.parent)
    app = create_app(artifacts=store, reviews=ReviewStore(tmp_path / 'reader.db'))
    with TestClient(app) as client:
        assert client.get('/api/books/sample/reading').status_code == 200
        (book.work_dir / 'publications' / first['revision'] / 'abridgment.txt').write_text('Corrupted.')
        assert client.get('/api/books/sample/reading').status_code == 400
        assert client.get('/api/books/sample/reading.txt').status_code == 400
        assert client.get('/api/books/reading').status_code == 503


def test_markdown_only_assembly_and_chapters_preserve_complete_text(artifact_tree):
    root = completed(artifact_tree)
    (root / 'abridgment.txt').unlink()
    (root / 'abridgment.md').write_text('## Chapter One\n\nFirst.\n\n## Chapter Two\n\nLast.\n')
    plan = {'segments': [{'id': '001', 'title': 'Chapter One'}, {'id': '002', 'title': 'Chapter Two'}]}
    result = reading_document(root, BOOK_ID, {}, plan)
    assert [c['title'] for c in result['chapters']] == ['Chapter One', 'Chapter Two']
    assert [c['paragraphs'] for c in result['chapters']] == [['First.'], ['Last.']]
    assert result['text'] == 'Chapter One\n\nFirst.\n\nChapter Two\n\nLast.\n'


def test_alignment_can_locate_headless_chapters_but_cannot_replace_assembly(artifact_tree):
    root = completed(artifact_tree, 'First.\n\nLast.\n')
    plan = {'segments': [{'id': '001', 'title': 'One'}, {'id': '002', 'title': 'Two'}]}
    for sid, text in [('001', 'First.'), ('002', 'Last.')]:
        (root / 'alignments' / f'{sid}.json').write_text(json.dumps({'draft_paragraphs': [text]}))
    book = reading_document(root, BOOK_ID, {}, plan)
    assert [c['title'] for c in book['chapters']] == ['One', 'Two']
    (root / 'alignments/002.json').write_text(json.dumps({'draft_paragraphs': ['A changed review draft.']}))
    book = reading_document(root, BOOK_ID, {}, plan)
    assert len(book['chapters']) == 1
    assert book['chapters'][0]['paragraphs'] == ['First.', 'Last.']


def test_reading_text_cannot_follow_symlinks_outside_book(artifact_tree, tmp_path):
    root = completed(artifact_tree)
    secret = tmp_path / 'private.txt'
    secret.write_text('Private secret')
    (root / 'abridgment.txt').unlink()
    (root / 'abridgment.txt').symlink_to(secret)
    with pytest.raises(ValueError):
        completed_text(root)


def test_invalid_alignment_shape_cannot_hide_valid_assembled_text(client, artifact_tree):
    root = completed(artifact_tree)
    (root / 'alignments/001.json').write_text('[]')
    response = client.get(f'/api/books/{BOOK_ID}/reading')
    assert response.status_code == 200
    assert response.json()['chapters'][0]['paragraphs'] == ['The completed book, including its ending.']


def test_invalid_reading_plan_returns_controlled_error(client, artifact_tree):
    root = completed(artifact_tree)
    (root / 'plan.json').write_text('[1]')
    assert client.get(f'/api/books/{BOOK_ID}/reading').status_code == 503
    assert client.get('/api/books/reading').status_code == 503


def test_package_preserves_complete_reader_text_without_private_report_paths(package_tree):
    root = package_tree
    book = completed(root)
    original = (book / 'abridgment.txt').read_bytes()
    out = root / 'deploy/artifacts'
    assert review_package.package([BOOK_ID], out) == 0
    assert (out / BOOK_ID / 'abridgment.txt').read_bytes() == original
    assert json.loads((out / BOOK_ID / 'assembly_report.json').read_text()) == {
        'partial': False, 'segments_missing': 0, 'segments_drafted': 1}
    assert '/private/' not in (out / BOOK_ID / 'assembly_report.json').read_text()
    assert '/private/' in (book / 'assembly_report.json').read_text()
