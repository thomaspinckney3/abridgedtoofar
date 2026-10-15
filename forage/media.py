"""Portable media review index shared by production, publication and hosting."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .production_state import confined_path, sha256_file, digest

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def target_revision(target: dict) -> str:
    return digest({k: v for k, v in target.items() if k not in {"revision", "path", "text_path"}})


def validate_media_manifest(index: dict, root: Path, verify_files: bool = True) -> dict:
    if (not isinstance(index, dict) or index.get("version") != 1
            or not isinstance(index.get("book_id"), str)
            or not _HASH.fullmatch(str(index.get("text_revision", "")))
            or not isinstance(index.get("targets"), list)):
        raise ValueError("invalid media manifest header")
    seen = set()
    for target in index["targets"]:
        if not isinstance(target, dict):
            raise ValueError("invalid media target")
        ident = target.get("id", "")
        if not isinstance(ident, str) or not _ID.fullmatch(ident) or ident in seen:
            raise ValueError("invalid or duplicate media target ID")
        seen.add(ident)
        kind, mime = target.get("kind"), target.get("mime_type", "")
        if kind not in {"audio", "graphic"} or not isinstance(target.get("title"), str):
            raise ValueError("invalid media target kind/title")
        allowed = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/mp4"} if kind == "audio" else {"image/png", "image/jpeg", "image/webp"}
        if mime not in allowed or not _HASH.fullmatch(str(target.get("revision", ""))):
            raise ValueError("invalid media type or revision")
        for path_key, hash_key in [("path", "sha256"), ("text_path", "text_sha256")]:
            if path_key == "text_path" and path_key not in target:
                continue
            path = confined_path(root, target.get(path_key))
            expected = target.get(hash_key, "")
            if not isinstance(expected, str) or not _HASH.fullmatch(expected):
                raise ValueError("invalid asset hash")
            if verify_files and sha256_file(path) != expected:
                raise ValueError(f"media hash mismatch: {target[path_key]}")
        duration = target.get("duration_seconds")
        if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0):
            raise ValueError("invalid media duration")
    return index
