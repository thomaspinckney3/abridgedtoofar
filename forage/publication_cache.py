"""Bounded web cache of verified snapshots, invalidated by filesystem changes."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import stat
import threading

from . import publication


class RevisionCache:
    def __init__(self, max_entries: int = 32):
        if max_entries < 1:
            raise ValueError("revision cache capacity must be positive")
        self.max_entries = max_entries
        self._entries = OrderedDict()
        # Serialize cold verification so concurrent reads cannot multiply hashing.
        self._lock = threading.RLock()

    @staticmethod
    def _fingerprint(directory):
        entries = []
        for path in [directory, *sorted(directory.rglob("*"))]:
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError("immutable publication files must be regular files or directories")
            entries.append((path.relative_to(directory).as_posix(), info.st_dev,
                            info.st_ino, info.st_mode, info.st_size,
                            info.st_mtime_ns, info.st_ctime_ns))
        return tuple(entries)

    def invalidate(self):
        with self._lock:
            self._entries.clear()

    def verify(self, book, revision_id, *, asset_path=None):
        with self._lock:
            directory, manifest = publication.read_revision_manifest(book, revision_id)
            if asset_path is not None and not any(
                    item["path"] == asset_path for item in manifest["outputs"]):
                raise FileNotFoundError("Asset is absent from this revision.")
            key = str(directory)
            fingerprint = self._fingerprint(directory)
            hit = self._entries.get(key)
            if hit is not None and hit[0] == fingerprint:
                self._entries.move_to_end(key)
                return deepcopy(hit[1])
            self._entries.pop(key, None)
            checked = publication.verify_revision(book, revision_id)
            if self._fingerprint(directory) != fingerprint:
                raise ValueError("publication changed during verification")
            self._entries[key] = (fingerprint, checked)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            return deepcopy(checked)
