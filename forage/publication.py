"""Verified, immutable local review snapshots and explicit release promotion.

These operations prepare local artifacts; they never upload or publish a website.
Each current-pointer file also contains its history, so advancing a pointer and
recording the event is one atomic write. Snapshot files are copied, never linked
to mutable production files.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

from .artifacts import Book
from .media import validate_media_manifest
from .production_state import (
    atomic_json, book_lock, canonical_json, confined_path, digest, sha256_file,
    verify_inventory,
)

VERSION = 1
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUTS = {"text", "audio", "graphic"}
_VOLATILE = {
    "created_at", "updated_at", "started_at", "completed_at", "finished_at",
    "timestamp", "timestamps", "duration", "duration_seconds", "elapsed",
    "elapsed_seconds", "request_duration", "request_duration_seconds",
    "diagnostic_counts", "counts",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("publication paths must be nonempty relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError(f"unsafe publication path: {value!r}")
    if ":" in path.parts[0]:
        raise ValueError(f"unsafe publication path: {value!r}")
    return value


def _allowed_output(path: str) -> None:
    parts = PurePosixPath(path).parts
    forbidden = {
        "publications", ".replay_cache", "editorial", "books", "revision.json",
        "review_current.json", "release_current.json", "production_state.json",
        "llm_calls.jsonl",
    }
    if any(p in forbidden or p.startswith(".env") for p in parts):
        raise ValueError(f"private/runtime artifact cannot enter a snapshot: {path}")
    if any("credential" in p.lower() for p in parts) or any(
        p.lower().endswith((".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
                           ".sqlite-wal", ".sqlite-shm"))
        for p in parts
    ):
        raise ValueError(f"private/runtime artifact cannot enter a snapshot: {path}")


def _outputs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("a snapshot requires an explicit nonempty file inventory")
    files: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("invalid publication inventory entry")
        path = _relative(item.get("path"))
        _allowed_output(path)
        checksum = _hash(item.get("sha256"), f"output hash for {path}")
        if path in files:
            raise ValueError(f"duplicate publication output: {path}")
        files[path] = checksum
    if not {"abridgment.txt", "abridgment.md"}.intersection(files):
        raise ValueError("a complete snapshot requires assembled abridgment text")
    if "plan.json" not in files or not any(
        path.startswith("alignments/") and path.endswith(".json") for path in files
    ):
        raise ValueError("a review snapshot requires its plan and paragraph alignments")
    return [{"path": path, "sha256": files[path]} for path in sorted(files)]


def _stable(value: Any) -> Any:
    """Remove execution timing/counts; reuse is the same completed result."""
    if isinstance(value, dict):
        return {
            key: ("complete" if key == "status" and child == "reused" else _stable(child))
            for key, child in value.items() if key not in _VOLATILE
        }
    if isinstance(value, list):
        return [_stable(child) for child in value]
    return value


def _summary(value: Any) -> dict:
    if not isinstance(value, dict) or value.get("status") != "complete":
        raise ValueError("only a complete production run can be snapshotted")
    selected = value.get("selected_outputs")
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(item, str) or item not in _OUTPUTS for item in selected)
            or len(set(selected)) != len(selected) or "text" not in selected):
        raise ValueError("selected_outputs must include text and only text/audio/graphic")
    stages = value.get("stages")
    if not isinstance(stages, dict) or not stages:
        raise ValueError("complete stage results are required for a snapshot")
    for name, result in stages.items():
        if not isinstance(result, dict) or result.get("status") not in {"complete", "reused"}:
            raise ValueError(f"stage {name!r} is not complete")
    required = {"assembly", "alignment"} | (set(selected) - {"text"})
    missing = required - stages.keys()
    if missing:
        raise ValueError(f"missing completed publication stages: {', '.join(sorted(missing))}")
    normalized = _stable(value)
    normalized["selected_outputs"] = sorted(selected)
    # Validate finite, serializable JSON before touching publication state.
    canonical_json(normalized)
    return normalized


def _media(index: Any, root: Path, book_id: str, text_revision: str,
           selected: list[str], outputs: list[dict]) -> dict:
    checked = validate_media_manifest(index, root, verify_files=True)
    if checked.get("book_id") != book_id or checked.get("text_revision") != text_revision:
        raise ValueError("media index does not match the book/text revision")
    files = {item["path"]: item["sha256"] for item in outputs}
    kinds = set()
    for target in checked["targets"]:
        kinds.add(target["kind"])
        if files.get(target["path"]) != target["sha256"]:
            raise ValueError(f"media target is absent from the selected inventory: {target['id']}")
        if target.get("text_path") is not None:
            if files.get(target["text_path"]) != target.get("text_sha256"):
                raise ValueError(f"media narration text is absent from the inventory: {target['id']}")
    if kinds != set(selected) - {"text"}:
        raise ValueError("media targets must exactly cover the selected media output kinds")
    return checked


def _identity(record: dict) -> dict:
    return {key: record[key] for key in (
        "version", "book_id", "text_revision", "selected_outputs", "stage_summary", "outputs",
    )}


def _publication_root(book: Book) -> Path:
    root = Path(book.work_dir)
    if (root / "publications").is_symlink():
        raise ValueError("publication storage cannot be a symlink")
    return confined_path(root, "publications")


def _review_text(root: Path, outputs: list[dict]) -> None:
    for item in outputs:
        if item["path"] in {"abridgment.txt", "abridgment.md"}:
            if not confined_path(root, item["path"]).read_text(encoding="utf-8").strip():
                raise ValueError("assembled publication text cannot be empty")


def verify_revision(book: Book, revision_id: str) -> dict:
    """Validate a stored revision and every referenced file without changing it."""
    _hash(revision_id, "revision")
    directory = _publication_root(book) / revision_id
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"missing or unsafe publication revision: {revision_id}")
    manifest = directory / "revision.json"
    if manifest.is_symlink():
        raise ValueError("revision manifest cannot be a symlink")
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("invalid revision manifest")
        if record.get("version") != VERSION or record.get("book_id") != book.book_id:
            raise ValueError("revision schema/book identity mismatch")
        if record.get("revision") != revision_id:
            raise ValueError("revision identity mismatch")
        _hash(record.get("text_revision"), "text_revision")
        summary = _summary(record.get("stage_summary"))
        if summary != record["stage_summary"] or record.get("selected_outputs") != summary["selected_outputs"]:
            raise ValueError("revision stage summary is not canonical")
        outputs = _outputs(record.get("outputs"))
        if outputs != record["outputs"] or digest(_identity(record)) != revision_id:
            raise ValueError("revision content identity mismatch")
        expected = {item["path"] for item in outputs} | {"revision.json"}
        actual = set()
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("immutable publication files cannot be symlinks")
            if path.is_file():
                actual.add(path.relative_to(directory).as_posix())
        if actual != expected or not verify_inventory(directory, outputs):
            raise ValueError("publication file inventory is missing, changed or contains extra files")
        _review_text(directory, outputs)
        index = json.loads((directory / "media_manifest.json").read_text(encoding="utf-8"))
        _media(index, directory, book.book_id, record["text_revision"], record["selected_outputs"], outputs)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid publication revision {revision_id}: {exc}") from exc
    return record


def _read_pointer(book: Book, channel: str) -> dict | None:
    path = confined_path(book.work_dir, f"{channel}_current.json")
    if Path(book.work_dir, f"{channel}_current.json").is_symlink():
        raise ValueError("publication pointer cannot be a symlink")
    if not path.exists():
        return None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(previous, dict) or previous.get("version") != VERSION
                or previous.get("book_id") != book.book_id or previous.get("channel") != channel
                or not isinstance(previous.get("history"), list) or not previous["history"]):
            raise ValueError("invalid existing publication pointer")
        for event in [previous, *previous["history"]]:
            if not isinstance(event, dict):
                raise ValueError("invalid existing publication history")
            revision = _hash(event.get("revision"), "current revision")
            _hash(event.get("text_revision"), "current text revision")
            selected = event.get("selected_outputs")
            if (event.get("path") != f"publications/{revision}"
                    or not isinstance(event.get("at"), str)
                    or not isinstance(selected, list) or "text" not in selected
                    or any(not isinstance(item, str) or item not in _OUTPUTS for item in selected)
                    or selected != sorted(set(selected))):
                raise ValueError("invalid existing publication history")
        if any(previous.get(key) != value for key, value in previous["history"][-1].items()):
            raise ValueError("publication pointer does not match its history")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read existing {channel} pointer") from exc
    return previous


def _advance_pointer(book: Book, channel: str, record: dict) -> dict:
    path = confined_path(book.work_dir, f"{channel}_current.json")
    previous = _read_pointer(book, channel)
    history = list(previous["history"]) if previous else []
    if previous and previous["revision"] == record["revision"]:
        return previous
    event = {
        "revision": record["revision"], "text_revision": record["text_revision"],
        "path": f"publications/{record['revision']}", "selected_outputs": record["selected_outputs"],
        "at": _now(),
    }
    pointer = {
        "version": VERSION, "book_id": book.book_id, "channel": channel,
        **event, "history": [*history, event],
    }
    atomic_json(path, pointer)
    return pointer


def snapshot_revision(book: Book, *, text_revision: str, outputs: list[dict],
                      media_index: dict, stage_summary: dict,
                      lock_held: bool = False) -> dict:
    """Copy a complete selected inventory and advance the local review pointer.

    The runner passes ``lock_held=True`` while it owns the per-book lock. Other
    callers acquire that same lock here. A failed operation never advances the
    prior pointer; an already exposed valid snapshot can safely remain unpointed.
    """
    with nullcontext() if lock_held else book_lock(book):
        from .review_recovery import assert_review_applications_resolved
        assert_review_applications_resolved(book)
        _hash(text_revision, "text_revision")
        summary = _summary(stage_summary)
        selected = summary["selected_outputs"]
        files = _outputs(outputs)
        root = Path(book.work_dir)
        for item in files:
            source = confined_path(root, item["path"])
            _allowed_output(source.relative_to(root.resolve()).as_posix())
            if source.resolve() == book.source_path.resolve() or (
                source.exists() and book.source_path.exists() and source.samefile(book.source_path)
            ):
                raise ValueError("original source books cannot enter a publication snapshot")
        if not verify_inventory(root, files):
            raise ValueError("selected publication files are missing or changed")
        _review_text(root, files)
        index = _media(media_index, root, book.book_id, text_revision, selected, files)
        if any(item["path"] == "media_manifest.json" for item in files):
            current = json.loads((root / "media_manifest.json").read_text(encoding="utf-8"))
            if current != index:
                raise ValueError("selected media manifest differs from supplied media index")
        parent = _publication_root(book)
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=parent) as staging_name:
            staging = Path(staging_name)
            copied = []
            for item in files:
                if item["path"] == "media_manifest.json":
                    continue
                source = confined_path(root, item["path"])
                target = confined_path(staging, item["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if sha256_file(target) != item["sha256"]:
                    raise ValueError(f"publication source changed while copying: {item['path']}")
                copied.append(item)
            atomic_json(staging / "media_manifest.json", index)
            copied.append({"path": "media_manifest.json", "sha256": sha256_file(staging / "media_manifest.json")})
            copied.sort(key=lambda item: item["path"])
            record = {
                "version": VERSION, "book_id": book.book_id, "text_revision": text_revision,
                "selected_outputs": selected, "stage_summary": summary, "outputs": copied,
            }
            revision = digest(_identity(record))
            record.update(revision=revision, created_at=_now())
            atomic_json(staging / "revision.json", record)
            if not verify_inventory(staging, copied):
                raise ValueError("staged publication did not pass verification")
            _media(index, staging, book.book_id, text_revision, selected, copied)
            destination = parent / revision
            if destination.exists() or destination.is_symlink():
                record = verify_revision(book, revision)
            else:
                staging.rename(destination)
                record = verify_revision(book, revision)
        release_pointer = _read_pointer(book, "release")
        pointer = _advance_pointer(book, "review", record)
        return {**record, "path": str(parent / revision), "review_current": pointer,
                "release_current": release_pointer}


def promote_release(book: Book, revision_id: str) -> dict:
    """Explicitly promote a verified immutable snapshot, including a visible hold.

    A critic hold is preserved in ``stage_summary``. Promotion is the operator's
    release decision, not an automatic guarantee of creative quality.
    """
    with book_lock(book):
        record = verify_revision(book, revision_id)
        pointer = _advance_pointer(book, "release", record)
        return {**record, "path": str(_publication_root(book) / revision_id),
                "release_current": pointer}
