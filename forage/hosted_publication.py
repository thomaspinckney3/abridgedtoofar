"""Small, provider-free receiver for verified immutable publication archives."""
from __future__ import annotations

import gzip
import io
import json
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile

from .artifacts import Book
from . import publication
from .production_state import book_lock, confined_path

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_FILES = 10000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def valid_book_id(value: str) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _relative(value: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or PurePosixPath(value).is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("unsafe archive member path")
    return value


def _context(root: Path, book_id: str) -> Book:
    return Book(book_id, root / "__no_source__", {}, root)


def archive_snapshot(book: Book, revision: str) -> bytes:
    """Return exactly a verified snapshot, without source/runtime material."""
    manifest = publication.verify_revision(book, revision)
    root = book.work_dir / "publications" / revision
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name in ["revision.json", *[item["path"] for item in manifest["outputs"]]]:
            path = confined_path(root, name)
            # verify_revision rejects links; recheck while reading to catch edits.
            if path.is_symlink() or not path.is_file():
                raise ValueError("snapshot changed during archive creation")
            archive.add(path, arcname=name, recursive=False)
    publication.verify_revision(book, revision)
    return stream.getvalue()


class HostedPublications:
    """Publication roots contain only per-book snapshots and channel pointers.

    Upload never advances a pointer. A failed request can leave an unreferenced,
    verified revision, but cannot replace the revision readers are using.
    """

    def __init__(self, root: Path | str, *, max_archive_bytes=MAX_ARCHIVE_BYTES,
                 max_expanded_bytes=MAX_EXPANDED_BYTES, max_files=MAX_FILES):
        if any(type(value) is not int or value <= 0
               for value in (max_archive_bytes, max_expanded_bytes, max_files)):
            raise ValueError("publication limits must be positive integers")
        self.root = Path(root).expanduser().resolve()
        self.max_archive_bytes = max_archive_bytes
        self.max_expanded_bytes = max_expanded_bytes
        self.max_files = max_files

    def _book(self, book_id: str) -> Book:
        if not valid_book_id(book_id):
            raise ValueError("invalid book ID")
        candidate = self.root / book_id
        if candidate.is_symlink():
            raise ValueError("hosted book storage cannot be a symlink")
        root = confined_path(self.root, book_id)
        if (root / ".production.lock").is_symlink():
            raise ValueError("hosted lock cannot be a symlink")
        return _context(root, book_id)

    def book_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(path.name for path in self.root.iterdir()
                      if valid_book_id(path.name) and path.is_dir() and not path.is_symlink()
                      and any((path / f"{c}_current.json").exists() for c in ("review", "release")))

    def upload(self, book_id: str, archive: bytes) -> dict:
        book = self._book(book_id)
        if not isinstance(archive, bytes) or not archive or len(archive) > self.max_archive_bytes:
            raise ValueError("empty or oversized publication archive")
        book.work_dir.mkdir(parents=True, exist_ok=True)
        with book_lock(book), tempfile.TemporaryDirectory(prefix=".upload-", dir=book.work_dir) as tmp:
            stage = Path(tmp)
            incoming = stage / "incoming"
            incoming.mkdir()
            count = total = 0
            names = set()
            try:
                # Tar parsers consume PAX/GNU metadata before yielding a member.
                # Bound every expanded byte first, including metadata, headers,
                # padding and concatenated gzip/trailing tar content.
                expanded = stage / "expanded.tar"
                expanded_bytes = 0
                with gzip.GzipFile(fileobj=io.BytesIO(archive), mode="rb") as compressed, expanded.open("xb") as output:
                    while chunk := compressed.read(min(1024 * 1024, self.max_expanded_bytes + 1 - expanded_bytes)):
                        expanded_bytes += len(chunk)
                        if expanded_bytes > self.max_expanded_bytes:
                            raise ValueError("publication archive exceeds expanded stream limit")
                        output.write(chunk)
                with tarfile.open(expanded, mode="r:") as tar:
                    for member in tar:
                        name = _relative(member.name)
                        if name in names or not member.isfile() or member.linkname:
                            raise ValueError("archive requires unique regular files only")
                        names.add(name)
                        count += 1
                        total += member.size
                        if member.size < 0 or count > self.max_files or total > self.max_expanded_bytes:
                            raise ValueError("publication archive exceeds expanded/file limits")
                        destination = confined_path(incoming, name)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        source = tar.extractfile(member)
                        if source is None:
                            raise ValueError("unreadable archive member")
                        with source, destination.open("xb") as output:
                            shutil.copyfileobj(source, output, length=1024 * 1024)
                        if destination.stat().st_size != member.size:
                            raise ValueError("truncated archive member")
                record = json.loads((incoming / "revision.json").read_text(encoding="utf-8"))
                revision = record.get("revision") if isinstance(record, dict) else None
                if not isinstance(revision, str) or not _HASH.fullmatch(revision):
                    raise ValueError("archive lacks a valid revision manifest")
                staged_root = stage / "publications"
                staged_root.mkdir()
                incoming.rename(staged_root / revision)
                checked = publication.verify_revision(_context(stage, book_id), revision)
            except (tarfile.TarError, OSError, EOFError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid publication archive: {exc}") from exc
            storage = publication._publication_root(book)
            storage.mkdir(parents=True, exist_ok=True)
            target = storage / revision
            if target.exists() or target.is_symlink():
                return publication.verify_revision(book, revision)
            (staged_root / revision).rename(target)
            return checked

    def promote(self, book_id: str, revision: str, channel: str = "review", *,
                lock_held: bool = False) -> dict:
        if channel not in {"review", "release"}:
            raise ValueError("publication channel must be review or release")
        book = self._book(book_id)
        with nullcontext() if lock_held else book_lock(book):
            manifest = publication.verify_revision(book, revision)
            return publication._advance_pointer(book, channel, manifest)

    def status(self, book_id: str) -> dict:
        book = self._book(book_id)
        return {channel: publication._read_pointer(book, channel) for channel in ("review", "release")}

    def resolve(self, book_id: str, revision: str | None = None,
                channel: str = "review", *, verification_cache=None,
                asset_path: str | None = None) -> tuple[Path, dict]:
        if channel not in {"review", "release"}:
            raise ValueError("publication channel must be review or release")
        book = self._book(book_id)
        if revision is None:
            pointer = publication._read_pointer(book, channel)
            if pointer is None:
                raise FileNotFoundError(f"no {channel} publication for {book_id}")
            revision = pointer["revision"]
        if not isinstance(revision, str) or not _HASH.fullmatch(revision):
            raise ValueError("invalid revision ID")
        root = book.work_dir / "publications" / revision
        if not root.exists() and not root.is_symlink():
            raise FileNotFoundError(f"no publication revision {revision}")
        if verification_cache is not None:
            return root, verification_cache.verify(book, revision, asset_path=asset_path)
        if asset_path is not None:
            _, manifest = publication.read_revision_manifest(book, revision)
            if not any(item["path"] == asset_path for item in manifest["outputs"]):
                raise FileNotFoundError("Asset is absent from this revision.")
        return root, publication.verify_revision(book, revision)
