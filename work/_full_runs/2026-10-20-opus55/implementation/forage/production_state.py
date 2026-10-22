"""Content identity, verified inventories and process-safe production records."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def confined_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("asset path must be a nonempty relative POSIX path")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(p in (".", "..") for p in relative.split("/")):
        raise ValueError(f"unsafe asset path: {relative}")
    resolved = (Path(root) / relative).resolve()
    if not resolved.is_relative_to(Path(root).resolve()) or resolved == Path(root).resolve():
        raise ValueError(f"asset escapes artifact root: {relative}")
    return resolved


def inventory(root: Path, paths) -> list[dict]:
    result = []
    for path in paths:
        relative = (Path(path).relative_to(root).as_posix()
                    if isinstance(path, Path) and path.is_absolute() else str(path))
        target = confined_path(root, relative)
        if not target.is_file():
            raise ValueError(f"missing output: {relative}")
        result.append({"path": relative, "sha256": sha256_file(target)})
    return sorted({item["path"]: item for item in result}.values(), key=lambda x: x["path"])


def verify_inventory(root: Path, outputs) -> bool:
    if not isinstance(outputs, list) or not outputs:
        return False
    seen = set()
    try:
        for item in outputs:
            path, expected = item["path"], item["sha256"]
            if path in seen or not isinstance(expected, str) or len(expected) != 64:
                return False
            seen.add(path)
            if sha256_file(confined_path(root, path)) != expected:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def atomic_json(path: Path, value) -> None:
    data = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(book) -> dict:
    path = book.work_dir / "production_state.json"
    if not path.exists():
        return {"version": 1, "book_id": book.book_id, "stages": {}}
    try:
        state = json.loads(path.read_text())
        if (state.get("version") != 1 or state.get("book_id") != book.book_id
                or not isinstance(state.get("stages"), dict)):
            raise ValueError("unsupported state schema or book identity")
        for record in state["stages"].values():
            if not isinstance(record, dict) or record.get("status") not in {"running", "complete", "failed"}:
                raise ValueError("invalid stage record")
        return state
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(f"invalid production state at {path}: {error}") from error


def save_state(book, state) -> None:
    atomic_json(book.work_dir / "production_state.json", state)


@contextmanager
def book_lock(book):
    """Nonblocking advisory lock, released by the OS after a crash."""
    book.work_dir.mkdir(parents=True, exist_ok=True)
    with (book.work_dir / ".production.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"production is already running for {book.book_id}") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
