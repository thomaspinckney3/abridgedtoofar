"""Provider-free, recoverable commit of prose repairs and their decisions.

A durable intent precedes every artifact change. Recovery accepts only the
recorded before/after bytes; an intervening human edit blocks rather than being
overwritten. The intent is removed only after all final bytes are durable.
"""
from __future__ import annotations

import base64
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from .production_state import atomic_json, book_lock, canonical_json, confined_path


def pending_path(book) -> Path:
    return book.work_dir / "editorial" / "review_apply_pending.json"


def assert_review_applications_resolved(book) -> None:
    path = pending_path(book)
    if path.exists() or path.is_symlink():
        raise RuntimeError("unresolved review application; run review-apply or production to recover before publication")


def _hash(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _read(path: Path) -> bytes | None:
    if path.is_symlink():
        raise RuntimeError(f"review recovery refuses symlink: {path}")
    return path.read_bytes() if path.exists() else None


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _finalize_intent(path: Path) -> None:
    path.unlink()
    _sync_directory(path.parent)


def _change(book, path: Path, role: str, after: bytes) -> dict:
    path = path.absolute()
    root = book.work_dir.absolute()
    if path.is_relative_to(root):
        name, absolute = path.relative_to(root).as_posix(), False
    elif role == "ledger":
        # Explicit standalone --ledger paths remain supported. Other outputs
        # are always confined to this book's own working directory.
        name, absolute = str(path), True
    else:
        raise ValueError("review artifact must be inside its book")
    before = _read(path)
    return {"role": role, "path": name, "absolute": absolute,
            "before_sha256": _hash(before), "after_sha256": _hash(after),
            "after": base64.b64encode(after).decode("ascii")}


def commit_review_application(book, *, segment_id: str, run_id: str,
                              draft_before: bytes,
                              draft_after: bytes | None, checks_after: dict | None,
                              ledger_path: Path, ledger_before: bytes | None,
                              ledger_after: dict) -> Path | None:
    """Called under book_lock after a validated provider response, exactly once."""
    assert_review_applications_resolved(book)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment_id):
        raise ValueError("invalid review segment ID")
    identifier = uuid.uuid4().hex
    changes = []
    snapshot = None
    draft = confined_path(book.work_dir, f"segments/{segment_id}.md")
    if _read(draft) != draft_before:
        raise RuntimeError("review draft changed while feedback was being evaluated; no repair committed")
    if _read(ledger_path) != ledger_before:
        raise RuntimeError("review ledger changed while feedback was being evaluated; no repair committed")
    if draft_after is not None:
        before = _read(draft)
        if before is None:
            raise ValueError("review draft disappeared before commit")
        snapshot = confined_path(book.work_dir, f"segments/{segment_id}.review_apply.{identifier}.before.md")
        changes.append(_change(book, snapshot, "snapshot", before))
        changes.append(_change(book, draft, "draft", draft_after))
        if checks_after is None:
            raise ValueError("changed review prose requires updated checks")
        checks = confined_path(book.work_dir, f"segments/{segment_id}.checks.json")
        changes.append(_change(book, checks, "checks", canonical_json(checks_after) + b"\n"))
    changes.append(_change(book, ledger_path, "ledger", canonical_json(ledger_after) + b"\n"))
    intent = {"version": 1, "book_id": book.book_id, "transaction_id": identifier,
              "segment_id": segment_id, "run_id": run_id, "changes": changes,
              "draft_before_sha256": _hash(draft_before),
              "draft_after_sha256": _hash(draft_after if draft_after is not None else draft_before)}
    # All decisions and their exact prospective ledger are durable before prose
    # changes. A failure here has no accepted-prose or ledger side effects.
    atomic_json(pending_path(book), intent)
    recover_review_applications(book, lock_held=True)
    return snapshot


def _validated_changes(book, intent: dict) -> list[tuple[Path, dict, bytes]]:
    if (not isinstance(intent, dict) or intent.get("version") != 1
            or intent.get("book_id") != book.book_id
            or not isinstance(intent.get("changes"), list)):
        raise RuntimeError("invalid pending review application")
    sid, identifier = intent.get("segment_id"), intent.get("transaction_id")
    if (not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid)
            or not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier)):
        raise RuntimeError("invalid pending review application identity")
    for name in ("draft_before_sha256", "draft_after_sha256"):
        if not isinstance(intent.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", intent[name]):
            raise RuntimeError("invalid pending review prose checksum")
    expected = {"snapshot": f"segments/{sid}.review_apply.{identifier}.before.md",
                "draft": f"segments/{sid}.md", "checks": f"segments/{sid}.checks.json"}
    result, roles, paths = [], [], set()
    for change in intent["changes"]:
        if not isinstance(change, dict) or change.get("role") not in {*expected, "ledger"}:
            raise RuntimeError("invalid pending review change")
        role, name = change["role"], change.get("path")
        if role != "ledger" and (name != expected[role] or change.get("absolute") is not False):
            raise RuntimeError("unexpected pending review artifact")
        if change.get("absolute") is True and role == "ledger":
            if not isinstance(name, str) or not Path(name).is_absolute():
                raise RuntimeError("invalid pending review ledger path")
            path = Path(name)
        elif change.get("absolute") is False:
            path = confined_path(book.work_dir, name)
        else:
            raise RuntimeError("invalid pending review artifact path")
        if path in paths:
            raise RuntimeError("duplicate pending review artifact")
        paths.add(path)
        roles.append(role)
        try:
            after = base64.b64decode(change["after"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("invalid pending review artifact bytes") from exc
        if _hash(after) != change.get("after_sha256"):
            raise RuntimeError("pending review artifact checksum mismatch")
        before = change.get("before_sha256")
        if before is not None and (not isinstance(before, str) or not re.fullmatch(r"[0-9a-f]{64}", before)):
            raise RuntimeError("invalid pending review original checksum")
        result.append((path, change, after))
    if roles not in (["ledger"], ["snapshot", "draft", "checks", "ledger"]):
        raise RuntimeError("incomplete pending review transaction")
    if roles != ["ledger"]:
        by_role = {change["role"]: change for _, change, _ in result}
        if (by_role["snapshot"]["after_sha256"] != intent["draft_before_sha256"]
                or by_role["draft"]["before_sha256"] != intent["draft_before_sha256"]
                or by_role["draft"]["after_sha256"] != intent["draft_after_sha256"]):
            raise RuntimeError("inconsistent pending review prose checksums")
    return result


def recover_review_applications(book, *, lock_held: bool = False) -> list[str]:
    """Finish a durable decision without providers; refuse conflicting edits."""
    with nullcontext() if lock_held else book_lock(book):
        path = pending_path(book)
        raw = _read(path)
        if raw is None:
            return []
        try:
            intent = json.loads(raw)
            changes = _validated_changes(book, intent)
        except (ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("invalid pending review application; recovery refused") from exc
        draft = confined_path(book.work_dir, f"segments/{intent['segment_id']}.md")
        if _hash(_read(draft)) not in {intent.get("draft_before_sha256"), intent.get("draft_after_sha256")}:
            raise RuntimeError(f"review recovery conflict at {draft}; preserve the pending intent and reconcile the intervening edit")
        # Check *every* artifact before writing another one. This includes a
        # pre-existing ledger, so recovery cannot discard later decisions.
        for target, change, _ in changes:
            current = _hash(_read(target))
            if current not in {change["before_sha256"], change["after_sha256"]}:
                raise RuntimeError(f"review recovery conflict at {target}; preserve the pending intent and reconcile the intervening edit")
        for target, change, after in changes:
            current = _hash(_read(target))
            if current == change["after_sha256"]:
                continue
            if current != change["before_sha256"]:
                raise RuntimeError(f"review recovery conflict at {target}")
            atomic_write_bytes(target, after)
        # Recheck all committed bytes before retiring the recovery instruction.
        if any(_hash(_read(target)) != change["after_sha256"] for target, change, _ in changes):
            raise RuntimeError("review commit changed during recovery")
        _finalize_intent(path)
        return [intent["transaction_id"]]
