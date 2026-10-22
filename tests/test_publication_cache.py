"""Cached verification saves hashing while failing closed on changed files."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forage import publication, production_state
from forage.publication_cache import RevisionCache
from forage.webapp.app import create_app
from forage.webapp.store import ArtifactStore, ReviewStore
from .test_publication import publication_input


def snapshot(publication_input):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)['revision']
    return book, revision, book.work_dir / 'publications' / revision


def count_hashes(monkeypatch):
    seen = []
    original = production_state.sha256_file
    def counted(path):
        seen.append(str(path))
        return original(path)
    monkeypatch.setattr(production_state, 'sha256_file', counted)
    return seen


def test_web_missing_asset_never_hashes_and_repeated_valid_reads_hash_once(publication_input, tmp_path, monkeypatch):
    book, revision, _ = snapshot(publication_input)
    client = TestClient(create_app(artifacts=ArtifactStore(work_dir=book.work_dir.parent,
        books_dir=tmp_path/'books'), reviews=ReviewStore(tmp_path/'review.db')))
    seen = count_hashes(monkeypatch)
    base = f'/api/books/sample/revisions/{revision}/assets/'
    for _ in range(2):
        assert client.get(base + 'absent.txt').status_code == 404
        assert not seen
    assert client.get(base + 'abridgment.txt').text == 'An abridged book.'
    assert seen
    seen.clear()
    assert client.get(base + 'abridgment.txt').status_code == 200
    assert client.get('/api/books/sample/media').status_code == 200
    assert not seen


@pytest.mark.parametrize('change', ['content', 'extra', 'deleted', 'symlink', 'manifest'])
def test_cached_snapshot_fails_closed_on_changes(publication_input, change):
    book, revision, root = snapshot(publication_input)
    cache = RevisionCache()
    cache.verify(book, revision)
    target = root / 'abridgment.txt'
    if change == 'content':
        info = target.stat()
        target.write_bytes(b'x' * info.st_size)
        os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
    elif change == 'extra':
        (root / 'extra').write_text('unexpected')
    elif change == 'deleted':
        target.unlink()
    elif change == 'symlink':
        target.unlink()
        target.symlink_to(book.work_dir / 'abridgment.txt')
    else:
        (root / 'revision.json').write_text('{}')
    with pytest.raises(ValueError):
        cache.verify(book, revision)


def test_parallel_readers_share_verification_and_cannot_mutate_cached_manifest(publication_input, monkeypatch):
    book, revision, _ = snapshot(publication_input)
    cache = RevisionCache()
    seen = count_hashes(monkeypatch)
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifests = list(pool.map(lambda _: cache.verify(book, revision), range(8)))
    assert len(seen) == len(manifests[0]['outputs'])
    manifests[0]['outputs'].clear()
    assert cache.verify(book, revision)['outputs']
    seen.clear()
    cache.invalidate()
    cache.verify(book, revision)
    assert seen


def test_eviction_and_changed_during_verification(publication_input, monkeypatch):
    book, revision, root = snapshot(publication_input)
    cache = RevisionCache(max_entries=1)
    cache.verify(book, revision)
    book, options = publication_input
    (book.work_dir/'abridgment.txt').write_text('Second book text.')
    options['outputs'] = production_state.inventory(book.work_dir, [o['path'] for o in options['outputs']])
    second = publication.snapshot_revision(book, **options)['revision']
    cache.verify(book, second)
    seen = count_hashes(monkeypatch)
    cache.verify(book, revision)
    assert seen and len(cache._entries) == 1
    cache.invalidate()
    original = publication.verify_revision
    def race(*args):
        result = original(*args)
        (root/'extra.txt').write_text('changed while verifying')
        return result
    monkeypatch.setattr(publication, 'verify_revision', race)
    with pytest.raises(ValueError, match='changed during verification'):
        cache.verify(book, revision)
    assert not cache._entries


def test_file_hash_streams_without_whole_file_read(tmp_path, monkeypatch):
    payload = b'bounded hashing' * 100000
    target = tmp_path / 'large'
    target.write_bytes(payload)
    def forbidden(*args):
        raise AssertionError('whole file read')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    assert production_state.sha256_file(target) == hashlib.sha256(payload).hexdigest()
