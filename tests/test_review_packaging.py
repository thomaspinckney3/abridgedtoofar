"""Media packaging uses exact validated inventories and keeps M1 rollback safety."""
import json
from pathlib import Path

import pytest

from forage import publication, review_package
from forage.production_state import atomic_json
from .test_artifact_safety import _snapshot, package_tree
from .test_publication import publication_input, _add_media, _refresh
from .conftest import BOOK_ID


def _media(root):
    from forage.production_state import sha256_file
    asset = root / 'audio' / '001.mp3'
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'audio bytes')
    target = {'id': 'audio-001', 'kind': 'audio', 'title': 'Chapter one',
              'path': 'audio/001.mp3', 'sha256': sha256_file(asset),
              'mime_type': 'audio/mpeg', 'revision': 'b' * 64,
              'duration_seconds': None}
    text = root / 'audio/001.txt'
    text.write_text('The spoken passage.')
    target.update(text_path='audio/001.txt', text_sha256=sha256_file(text))
    index = {'version': 1, 'book_id': BOOK_ID, 'text_revision': 'a' * 64, 'targets': [target]}
    atomic_json(root / 'media_manifest.json', index)
    return index


def test_package_includes_only_current_verified_media(package_tree):
    root = package_tree
    book = root / 'work' / BOOK_ID
    index = _media(book)
    (book / 'audio' / 'obsolete.mp3').write_bytes(b'obsolete')
    (book / 'audio' / 'private.json').write_text('{"token":"secret"}')
    out = root / 'deploy' / 'artifacts'
    assert review_package.package([BOOK_ID], out) == 0
    assert json.loads((out / BOOK_ID / 'media_manifest.json').read_text()) == index
    assert sorted(p.name for p in (out / BOOK_ID / 'audio').iterdir()) == ['001.mp3', '001.txt']


@pytest.mark.parametrize('bad', ['hash', 'escape', 'missing', 'identity'])
def test_invalid_media_preserves_previous_package(package_tree, bad):
    root = package_tree
    book = root / 'work' / BOOK_ID
    index = _media(book)
    if bad == 'hash':
        (book / 'audio/001.mp3').write_bytes(b'changed')
    elif bad == 'escape':
        index['targets'][0]['path'] = '../other/secret.mp3'
    elif bad == 'missing':
        (book / 'audio/001.mp3').unlink()
    else:
        index['book_id'] = 'otherbook'
    atomic_json(book / 'media_manifest.json', index)
    before = _snapshot(root)
    with pytest.raises((ValueError, OSError)):
        review_package.package([BOOK_ID], root / 'deploy/artifacts')
    assert _snapshot(root) == before


def test_package_keeps_verified_revision_and_release_history(publication_input, monkeypatch, tmp_path):
    book, kwargs = publication_input
    _add_media(book, kwargs, 'audio')
    first = publication.snapshot_revision(book, **kwargs)
    publication.promote_release(book, first['revision'])
    (book.work_dir / 'abridgment.txt').write_text('A later abridgment.')
    _refresh(book, kwargs)
    from forage.production_state import sha256_file
    from forage.media import target_revision
    target = kwargs['media_index']['targets'][0]
    target['text_sha256'] = sha256_file(book.work_dir / 'abridgment.txt')
    target['revision'] = target_revision(target)
    second = publication.snapshot_revision(book, **kwargs)
    monkeypatch.setattr(review_package, 'WORK_DIR', book.work_dir.parent)
    monkeypatch.setattr(review_package, 'BOOKS_DIR', book.source_path.parent.parent)
    out = tmp_path / 'deployment/artifacts'
    assert review_package.package([book.book_id], out) == 0
    from forage.artifacts import Book
    copied = Book(book.book_id, Path('unused'), {}, out / book.book_id)
    for revision in [first['revision'], second['revision']]:
        assert publication.verify_revision(copied, revision)['revision'] == revision
    assert json.loads((copied.work_dir / 'release_current.json').read_text())['revision'] == first['revision']
    assert json.loads((copied.work_dir / 'review_current.json').read_text())['revision'] == second['revision']
    assert not (copied.work_dir / '.production.lock').exists()
