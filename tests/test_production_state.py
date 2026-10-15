import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace

import pytest

from forage.production_state import (atomic_json, book_lock, canonical_json, confined_path,
                                      digest, inventory, load_state, verify_inventory)
from forage.media import target_revision, validate_media_manifest


def test_identity_is_content_ordered_and_rejects_nonfinite():
    assert digest({'a': 1, 'b': 2}) == digest({'b': 2, 'a': 1})
    assert digest('same') != digest('sAme')
    with pytest.raises(ValueError):
        canonical_json(float('nan'))


@pytest.mark.parametrize('path', ['', '../bad', '/tmp/bad', 'a/../b', 'a/./b', 'a\\b'])
def test_confined_paths(tmp_path, path):
    with pytest.raises(ValueError):
        confined_path(tmp_path, path)


def test_symlink_cannot_escape(tmp_path):
    (tmp_path / 'out').symlink_to(tmp_path.parent)
    with pytest.raises(ValueError):
        confined_path(tmp_path, 'out/file')


def test_inventory_detects_same_length_changes_and_missing(tmp_path):
    p = tmp_path / 'a'; p.write_bytes(b'aaa')
    files = inventory(tmp_path, [p])
    assert verify_inventory(tmp_path, files)
    p.write_bytes(b'bbb')
    assert not verify_inventory(tmp_path, files)
    p.unlink()
    assert not verify_inventory(tmp_path, files)
    assert not verify_inventory(tmp_path, [])


def test_atomic_failure_preserves_previous(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    atomic_json(path, {'good': True})
    def fail(*args):
        raise OSError('rename failure')
    monkeypatch.setattr('forage.production_state.os.replace', fail)
    with pytest.raises(OSError):
        atomic_json(path, {'good': False})
    assert json.loads(path.read_text()) == {'good': True}
    assert list(tmp_path.iterdir()) == [path]


def _contend(root, queue):
    try:
        with book_lock(SimpleNamespace(book_id='book', work_dir=Path(root))):
            queue.put('acquired')
    except RuntimeError:
        queue.put('locked')


def test_book_lock_is_process_safe_and_releases(tmp_path):
    book = SimpleNamespace(book_id='book', work_dir=tmp_path)
    context = multiprocessing.get_context('spawn')
    with book_lock(book):
        queue = context.Queue()
        process = context.Process(target=_contend, args=(str(tmp_path), queue))
        process.start(); process.join(10)
        assert process.exitcode == 0
        assert queue.get(timeout=2) == 'locked'
    with book_lock(book):
        pass


def test_invalid_state_fails_closed(tmp_path):
    book = SimpleNamespace(book_id='book', work_dir=tmp_path)
    (tmp_path / 'production_state.json').write_text('{}')
    with pytest.raises(ValueError, match='state'):
        load_state(book)


def test_media_binding_and_asset_validation(tmp_path):
    (tmp_path / 'a.mp3').write_bytes(b'fake audio')
    target = {'id': 'audio-0001', 'kind': 'audio', 'title': 'Chunk 1', 'path': 'a.mp3',
              'sha256': inventory(tmp_path, ['a.mp3'])[0]['sha256'], 'mime_type': 'audio/mpeg', 'duration_seconds': None}
    target['revision'] = target_revision(target)
    index = {'version': 1, 'book_id': 'book', 'text_revision': 'a' * 64, 'targets': [target]}
    assert validate_media_manifest(index, tmp_path) is index
    changed = {**target, 'text_revision': 'b' * 64}
    assert target_revision(changed) != target['revision']
    (tmp_path / 'a.mp3').write_bytes(b'tamper')
    with pytest.raises(ValueError, match='hash'):
        validate_media_manifest(index, tmp_path)


@pytest.mark.parametrize('duration', [-1, float('inf'), float('nan'), True, '1'])
def test_media_bad_duration(tmp_path, duration):
    target = {'id': 'audio-1', 'kind': 'audio', 'title': 'Chunk', 'path': 'a.mp3', 'sha256': 'a'*64,
              'revision': 'b'*64, 'mime_type': 'audio/mpeg', 'duration_seconds': duration}
    with pytest.raises(ValueError):
        validate_media_manifest({'version': 1, 'book_id': 'book', 'text_revision': 'c'*64, 'targets': [target]}, tmp_path, False)


def test_workspace_environment_controls_late_loaded_replay_cache(tmp_path, monkeypatch):
    from forage.llm import replay_cache_path
    monkeypatch.setenv('FORAGE_WORKSPACE', str(tmp_path))
    assert replay_cache_path('key') == tmp_path / 'work/.replay_cache/key.json'
    monkeypatch.setenv('FORAGE_WORK_DIR', str(tmp_path / 'custom-work'))
    assert replay_cache_path('key') == tmp_path / 'custom-work/.replay_cache/key.json'
