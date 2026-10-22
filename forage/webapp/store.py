"""Storage layer for the editorial review app.

Two stores, deliberately separated so the app can be hosted:

* `ArtifactStore` — read-only view of the pipeline's output on disk
  (`work/<book>/alignments/*.json`, `plan.json`, `books/<book>/metadata.json`).
  Nothing here is ever written by the web app, so the artifact tree can be
  baked into an image or mounted read-only.

* `ReviewStore` — the review queue (comments), in SQLite. This is the only
  mutable state the app owns, so a deployment needs exactly one writable
  volume for the database file.

Roots are overridable via FORAGE_WORK_DIR / FORAGE_BOOKS_DIR so a container
can mount artifacts anywhere. FORAGE_ARTIFACT_OVERLAY_DIR /
FORAGE_BOOKS_OVERLAY_DIR optionally point at a writable volume whose per-book
directories override the baked artifact tree, enabling one-book refreshes
without rebuilding or restarting the app.
"""

from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from ..artifacts import BOOKS_DIR, WORK_DIR
from ..proofread import should_word_diff, word_diff_html
from ..review_anchors import anchor_hash, locate, binding_is_current
from ..revision_review import response_id
from ..review_anchors import chapter_hash

NOTE_KEYS = ("verbatim", "paraphrased", "compressed", "unsupported")
DIAGNOSTIC_CLASSES = (
    "non_parseable",
    "dangling_reference",
    "broken_pivot",
    "missing_gloss",
    "unattributed_dialogue",
    "mid_scene_jump",
    "unglossed_name",
)
DIAGNOSTIC_SEVERITY = {
    "non_parseable": "blocker",
    "dangling_reference": "blocker",
    "unattributed_dialogue": "blocker",
    "mid_scene_jump": "blocker",
    "broken_pivot": "major",
    "missing_gloss": "major",
    "unglossed_name": "major",
}

SEVERITIES = ("blocker", "major", "minor", "nit", "praise")
KINDS = ("fidelity", "voice", "continuity", "clarity", "style", "typo", "other")
STATUSES = ("open", "accepted", "resolved", "wontfix")
BOOK_COMMENT_SEGMENT = "__book__"

MAX_BODY = 4000
MAX_AUTHOR = 80
MAX_QUOTE = 600
MAX_LLM_RESPONSE = 2400

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_BOOK_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
# The character class admits "." and ".." on its own. Every id becomes a path
# component, so a bare dot-segment resolves outside the directory it names.
_RESERVED_IDS = frozenset({".", ".."})

_CHAPTER_NOTE_METRICS = (
    "status",
    "source_words",
    "target_words",
    "draft_words",
    "word_count_delta_pct",
    "signatures_total",
    "signatures_matched",
)


def valid_book_id(book_id: str) -> bool:
    return bool(_BOOK_RE.match(book_id)) and book_id not in _RESERVED_IDS


def valid_segment_id(segment_id: str) -> bool:
    return bool(_SEGMENT_RE.match(segment_id)) and segment_id not in _RESERVED_IDS


def mutable_path(path: Path) -> Path:
    """A configuration mistake must not put a DB/export inside a snapshot."""
    parts = path.resolve().parts
    for index, part in enumerate(parts[:-1]):
        if part == "publications" and re.fullmatch(r"[0-9a-f]{64}", parts[index + 1]):
            raise ValueError("Mutable review state must be outside immutable publications.")
    return path


_DIAG_TEXT_NORMALIZE = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u00a0": " ",
})
_DIAG_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "but", "by", "for", "from", "had",
    "has", "he", "her", "his", "i", "in", "is", "it", "its", "me", "my",
    "not", "of", "on", "or", "she", "that", "the", "their", "them", "this",
    "to", "was", "we", "were", "with", "you",
}
_DIALOGUE_QUOTE_START = ("\"", "\u201c", "'")
_DIALOGUE_ATTRIBUTION_RE = re.compile(
    r"\b("
    r"said|asked|cried|replied|answered|murmured|whispered|called|returned|"
    r"continued|remarked|exclaimed|shouted|protested|explained|began|resumed|"
    r"observed|suggested|declared|added|told|interrupted|ejaculated|"
    r"hinted|pressed|retorted|inquired|demanded|insisted|admitted"
    r")\b",
    re.IGNORECASE,
)


def _diag_text_key(text: Any) -> str:
    normalized = str(text or "").translate(_DIAG_TEXT_NORMALIZE)
    normalized = normalized.replace("...", " ").replace("\u2026", " ")
    normalized = re.sub(r"[^a-zA-Z0-9']+", " ", normalized.lower())
    return " ".join(normalized.split())


def _diag_tokens(text: Any) -> set[str]:
    return {
        token for token in _diag_text_key(text).split()
        if len(token) > 2 and token not in _DIAG_STOPWORDS
    }


def _diagnostic_id(diag: dict[str, Any]) -> str:
    raw = "|".join(str(diag.get(k, ""))
                   for k in ("source", "segment_id", "class", "draft_passage",
                             "alias", "name"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _diagnostic_dedupe_key(diag: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(diag.get("segment_id") or ""),
        str(diag.get("class") or ""),
        _diag_text_key(diag.get("draft_passage"))[:220],
        _diag_text_key(diag.get("alias") or diag.get("name")),
    )


def _dedupe_diagnostics(diagnostics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    source_rank = {"coherence": 0, "dialogue-lint": 1, "name-lint": 2}
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for diag in diagnostics:
        key = _diagnostic_dedupe_key(diag)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = diag
            continue
        if source_rank.get(str(diag.get("source")), 9) < source_rank.get(
            str(existing.get("source")), 9
        ):
            by_key[key] = diag
    out = []
    for diag in by_key.values():
        diag = dict(diag)
        diag["id"] = _diagnostic_id(diag)
        out.append(diag)
    return sorted(out, key=lambda d: (
        str(d.get("segment_id") or ""),
        str(d.get("class") or ""),
        str(d.get("draft_passage") or ""),
    ))


def _match_diagnostic_block(blocks: list[dict], diagnostic: dict[str, Any]) -> int | None:
    passage = str(diagnostic.get("draft_passage") or "").strip()
    if not passage:
        return None
    passage_key = _diag_text_key(passage)
    if not passage_key:
        return None

    block_keys = [_diag_text_key(b.get("draft", "")) for b in blocks]
    for idx, block_key in enumerate(block_keys):
        if passage_key in block_key or block_key in passage_key:
            return idx

    passage_tokens = _diag_tokens(passage)
    if len(passage_tokens) < 4:
        return None

    best_idx: int | None = None
    best_score = 0.0
    for idx, block in enumerate(blocks):
        block_tokens = _diag_tokens(block.get("draft", ""))
        if not block_tokens:
            continue
        score = len(passage_tokens & block_tokens) / len(passage_tokens)
        if score > best_score:
            best_idx = idx
            best_score = score
    return best_idx if best_score >= 0.65 else None


def _attach_diagnostics(blocks: list[dict], diagnostics: list[dict]) -> list[dict]:
    unmatched: list[dict] = []
    for diagnostic in diagnostics:
        idx = _match_diagnostic_block(blocks, diagnostic)
        if idx is None:
            unmatched.append(diagnostic)
        else:
            blocks[idx].setdefault("diagnostics", []).append(diagnostic)
    return unmatched


def _quote_span_count(text: str) -> int:
    straight = text.count("\"") // 2
    curly = min(text.count("\u201c"), text.count("\u201d"))
    return max(straight, curly)


def _looks_like_unattributed_dialogue(text: Any) -> bool:
    s = str(text or "").strip()
    if not s or not s.startswith(_DIALOGUE_QUOTE_START):
        return False
    if _DIALOGUE_ATTRIBUTION_RE.search(s):
        return False
    if _quote_span_count(s) >= 2:
        return True
    return len(s.split()) <= 45


def _dialogue_lint_diagnostics(book_id: str, segment_id: str,
                               draft_paras: list[str],
                               source_by_draft: dict[int, str]) -> list[dict[str, Any]]:
    quote_only = [
        idx for idx, text in enumerate(draft_paras)
        if _looks_like_unattributed_dialogue(text)
    ]
    quote_set = set(quote_only)
    runs: list[list[int]] = []
    current: list[int] = []
    for idx in range(len(draft_paras)):
        if idx in quote_set:
            current.append(idx)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    findings: list[dict[str, Any]] = []
    for run in runs:
        if len(run) < 3:
            continue
        source_contexts = [source_by_draft.get(idx, "") for idx in run]
        if not any(_DIALOGUE_ATTRIBUTION_RE.search(src) for src in source_contexts):
            continue
        severity = "blocker"
        first = run[0]
        excerpt = "\n\n".join(draft_paras[idx].strip() for idx in run[:3])
        source_excerpt = "\n\n".join(src.strip() for src in source_contexts if src.strip())
        findings.append({
            "source": "dialogue-lint",
            "class": "unattributed_dialogue",
            "severity": severity,
            "segment_id": segment_id,
            "pair": "",
            "draft_passage": excerpt[:600],
            "source_has": source_excerpt[:600],
            "reason": (
                f"Draft paragraphs {first}-{run[-1]} form a run of {len(run)} "
                    f"adjacent quote-led dialogue turns with no explicit speaker "
                    f"attribution, while the aligned source has attribution or "
                    f"action beats. Add compact tags or action beats where speaker "
                    f"identity is not obvious."
            ),
            "name": "",
            "alias": "",
            "book_id": book_id,
            "draft_para_start": first,
            "draft_para_end": run[-1],
        })
    return findings


def _note_text(data: dict[str, Any], *keys: str, limit: int = 1200) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:limit]
    return ""


def _note_list(data: dict[str, Any], *keys: str, limit: int = 800) -> list[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return [value.strip()[:limit]]
        if isinstance(value, list):
            cleaned = [str(item).strip()[:limit]
                       for item in value if str(item).strip()]
            if cleaned:
                return cleaned[:8]
    return []


def _signature_miss_label(item: Any) -> str:
    if isinstance(item, dict):
        hint = str(item.get("hint") or item.get("passage_hint") or "").strip()
        if hint:
            return hint[:800]
    value = str(item or "").strip()
    return value[:800]


def _chapter_notes_from_checks(checks: Any) -> dict[str, Any]:
    if not isinstance(checks, dict):
        return {}

    out: dict[str, Any] = {}
    for key in _CHAPTER_NOTE_METRICS:
        value = checks.get(key)
        if value is not None:
            out[key] = value

    raw = (checks.get("chapter_notes")
           or checks.get("editorial_notes")
           or checks.get("llm_commentary"))
    if isinstance(raw, str) and raw.strip():
        out["summary"] = raw.strip()[:1200]
    elif isinstance(raw, dict):
        summary = _note_text(raw, "summary", "editorial_summary", "rationale")
        if summary:
            out["summary"] = summary
        acceptable = _note_list(raw, "acceptable_changes", "why_acceptable", "why_ok")
        if not acceptable:
            rationale = _note_text(raw, "rationale")
            if rationale and rationale != summary:
                acceptable = [rationale]
        risks = _note_list(raw, "risks", "known_risks", "tradeoff_risks")
        review_focus = _note_list(raw, "review_focus", "reviewer_focus", "needs_review")
        if acceptable:
            out["acceptable_changes"] = acceptable
        if risks:
            out["risks"] = risks
        if review_focus:
            out["review_focus"] = review_focus
        parse_error = _note_text(raw, "parse_error", limit=500)
        if parse_error:
            out["parse_error"] = parse_error

    misses = checks.get("signatures_missed")
    if isinstance(misses, list):
        labels = [_signature_miss_label(item) for item in misses]
        labels = [label for label in labels if label]
        if labels:
            out["signature_misses"] = labels[:8]

    out["has_rich_notes"] = any(out.get(key) for key in (
        "summary", "acceptable_changes", "risks", "review_focus"
    ))
    return out


# --------------------------------------------------------------------------
# Artifacts (read-only)
# --------------------------------------------------------------------------


@dataclass
class BookSummary:
    book_id: str
    title: str
    author: str
    chapters: int
    counts: dict[str, int]
    diagnostics: dict[str, int]


class ArtifactStore:
    def __init__(self, work_dir: Path | None = None,
                 books_dir: Path | None = None,
                 overlay_work_dir: Path | None = None,
                 overlay_books_dir: Path | None = None,
                 hosted_dir: Path | None = None) -> None:
        self.work_dir = Path(os.environ.get("FORAGE_WORK_DIR") or work_dir or WORK_DIR)
        self.books_dir = Path(os.environ.get("FORAGE_BOOKS_DIR") or books_dir or BOOKS_DIR)
        self.overlay_work_dir = self._optional_root(
            "FORAGE_ARTIFACT_OVERLAY_DIR", overlay_work_dir)
        self.overlay_books_dir = self._optional_root(
            "FORAGE_BOOKS_OVERLAY_DIR", overlay_books_dir)
        self._cache: dict[str, tuple[tuple[int, int], Any]] = {}
        root = (os.environ.get("FORAGE_HOSTED_ROOT")
                or os.environ.get("FORAGE_PUBLICATION_DIR") or hosted_dir)
        self.hosted = None
        if root:
            from ..hosted_publication import HostedPublications
            limits = {}
            for env, parameter in (("FORAGE_MAX_UPLOAD_BYTES", "max_archive_bytes"),
                                   ("FORAGE_MAX_EXPANDED_BYTES", "max_expanded_bytes"),
                                   ("FORAGE_MAX_UPLOAD_FILES", "max_files")):
                if os.environ.get(env):
                    value = int(os.environ[env])
                    if value <= 0:
                        raise ValueError(f"{env} must be a positive integer")
                    limits[parameter] = value
            self.hosted = HostedPublications(Path(root), **limits)
        self._pinned: dict[str, Path] = {}
        self._revisions: dict[str, dict] = {}
        self._channels: dict[str, str] = {}

    @staticmethod
    def _resolve_hosted(hosted, book_id: str, revision: str | None = None,
                        channel: str | None = None):
        # Default reading/feedback uses review-current when it exists. A book
        # may legitimately have only a public release, which is then current.
        # Explicit selectors stay strict and never change either pointer.
        selected_channel = channel or "review"
        if channel is None and revision is None:
            pointers = hosted.status(book_id)
            if pointers["review"] is None and pointers["release"] is not None:
                selected_channel = "release"
        root, manifest = hosted.resolve(book_id, revision, selected_channel)
        label = "revision" if revision is not None and channel is None else selected_channel
        return root, manifest, label

    def selected(self, book_id: str, revision: str | None = None,
                 channel: str | None = None) -> "ArtifactStore":
        """Pin a whole book once, so pointer changes cannot mix a response."""
        if not valid_book_id(book_id) or channel not in {None, "review", "release"}:
            raise ValueError("Bad book or publication channel.")
        selected = copy.copy(self)
        selected._pinned = dict(self._pinned)
        selected._revisions = dict(self._revisions)
        selected._channels = dict(self._channels)
        hosted = self.hosted
        if hosted is None or book_id not in hosted.book_ids():
            from ..hosted_publication import HostedPublications
            for candidate in (self.overlay_work_dir, self.work_dir):
                if candidate and (candidate / book_id / "publications").is_dir():
                    hosted = HostedPublications(candidate)
                    break
                if candidate and (candidate / book_id / "alignments").is_dir():
                    break  # A whole-book overlay replaces the baked book.
        if hosted is not None:
            try:
                root, manifest, label = self._resolve_hosted(hosted, book_id, revision, channel)
            except FileNotFoundError:
                if revision or channel == "release" or book_id in hosted.book_ids():
                    raise
            else:
                selected._pinned[book_id] = root
                selected._revisions[book_id] = manifest
                selected._channels[book_id] = label
                return selected
        if revision or channel == "release":
            raise FileNotFoundError("No such published revision.")
        selected._pinned[book_id] = self._book_work_dir(book_id)
        return selected

    def revision_info(self, book_id: str) -> dict:
        manifest = self._revisions.get(book_id, {})
        return {"publication_revision": manifest.get("revision"),
                "text_revision": manifest.get("text_revision")}

    def media(self, book_id: str) -> dict:
        from ..media import validate_media_manifest
        root = self._book_work_dir(book_id)
        index = self._read_json_cached(root / "media_manifest.json")
        if index is None:
            return {"version": 1, "book_id": book_id, "targets": []}
        if not isinstance(index, dict) or index.get("book_id") != book_id:
            raise ValueError("Media manifest belongs to a different book.")
        return validate_media_manifest(index, root, verify_files=True)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _optional_root(env_name: str, fallback: Path | None) -> Path | None:
        raw = os.environ.get(env_name)
        if raw:
            return Path(raw)
        return Path(fallback) if fallback is not None else None

    def _read_json_cached(self, path: Path) -> Any:
        """Read + parse JSON, re-reading only when mtime changes. Alignment
        files are large and every page view touches them."""
        try:
            stat = path.stat()
        except OSError:
            self._cache.pop(str(path), None)
            return None
        signature = (stat.st_mtime_ns, stat.st_size)
        hit = self._cache.get(str(path))
        if hit and hit[0] == signature:
            return hit[1]
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        self._cache[str(path)] = (signature, data)
        return data

    def _book_work_dir(self, book_id: str) -> Path:
        if book_id in self._pinned:
            return self._pinned[book_id]
        if self.hosted is not None:
            try:
                return self._resolve_hosted(self.hosted, book_id)[0]
            except FileNotFoundError:
                pass
        for candidate in (self.overlay_work_dir, self.work_dir):
            if candidate and (candidate / book_id / "publications").is_dir():
                from ..hosted_publication import HostedPublications
                return self._resolve_hosted(HostedPublications(candidate), book_id)[0]
            if candidate and (candidate / book_id / "alignments").is_dir():
                break
        if self.overlay_work_dir and valid_book_id(book_id):
            candidate = self.overlay_work_dir / book_id
            alignments = candidate / "alignments"
            if alignments.is_dir() and any(alignments.glob("*.json")):
                return candidate
        return self.work_dir / book_id

    def _book_books_dir(self, book_id: str) -> Path:
        if self.overlay_books_dir and valid_book_id(book_id):
            candidate = self.overlay_books_dir / book_id
            if (candidate / "metadata.json").is_file():
                return candidate
        return self.books_dir / book_id

    def _align_dir(self, book_id: str) -> Path:
        return self._book_work_dir(book_id) / "alignments"

    def _segments_dir(self, book_id: str) -> Path:
        return self._book_work_dir(book_id) / "segments"

    def _editorial_dir(self, book_id: str) -> Path:
        return self._book_work_dir(book_id) / "editorial"

    def _metadata(self, book_id: str) -> dict:
        if book_id in self._revisions:
            plan = self._read_json_cached(self._book_work_dir(book_id) / "plan.json") or {}
            return {k: plan[k] for k in ("title", "author") if plan.get(k)}
        meta = self._read_json_cached(self._book_books_dir(book_id) / "metadata.json")
        if isinstance(meta, dict) and meta:
            return meta
        # Hosted deploys may ship work/ without books/ — plan.json carries the
        # same title/author fields.
        plan = self._read_json_cached(self._book_work_dir(book_id) / "plan.json")
        if isinstance(plan, dict):
            return {k: plan[k] for k in ("title", "author") if plan.get(k)}
        return {}

    def _segment_titles(self, book_id: str) -> dict[str, str]:
        plan = self._read_json_cached(self._book_work_dir(book_id) / "plan.json")
        if not isinstance(plan, dict):
            return {}
        return {str(s.get("id")): str(s.get("title") or "")
                for s in plan.get("segments", []) if s.get("id") is not None}

    def _book_ids_under(self, root: Path | None) -> set[str]:
        out: set[str] = set()
        if root is None or not root.is_dir():
            return out
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if not valid_book_id(child.name):
                continue
            alignments = child / "alignments"
            if ((alignments.is_dir() and any(alignments.glob("*.json")))
                    or (child / "review_current.json").is_file()
                    or (child / "release_current.json").is_file()):
                out.add(child.name)
        return out

    # -- public ------------------------------------------------------------

    def book_ids(self) -> list[str]:
        return sorted(self._book_ids_under(self.work_dir)
                      | self._book_ids_under(self.overlay_work_dir)
                      | (set(self.hosted.book_ids()) if self.hosted else set()))

    def has_book(self, book_id: str) -> bool:
        return (valid_book_id(book_id)
                and self._align_dir(book_id).is_dir()
                and any(self._align_dir(book_id).glob("*.json")))

    def segment_ids(self, book_id: str) -> list[str]:
        if not valid_book_id(book_id):
            return []
        return sorted(p.stem for p in self._align_dir(book_id).glob("*.json"))

    def alignment(self, book_id: str, segment_id: str) -> Optional[dict]:
        if not (valid_book_id(book_id) and valid_segment_id(segment_id)):
            return None
        data = self._read_json_cached(self._align_dir(book_id) / f"{segment_id}.json")
        return data if isinstance(data, dict) else None

    def segment_checks(self, book_id: str, segment_id: str) -> Optional[dict]:
        if not (valid_book_id(book_id) and valid_segment_id(segment_id)):
            return None
        data = self._read_json_cached(self._segments_dir(book_id)
                                      / f"{segment_id}.checks.json")
        return data if isinstance(data, dict) else None

    def chapter_notes(self, book_id: str, segment_id: str) -> dict[str, Any]:
        return _chapter_notes_from_checks(self.segment_checks(book_id, segment_id))

    def review_apply_responses(
        self,
        book_id: str,
        segment_id: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """LLM decisions recorded after processing human review comments.

        The review-apply stage writes these into the artifact tree rather than
        the review SQLite DB, so hosted read paths can display the response
        after a redeploy or artifact refresh.
        """
        if not valid_book_id(book_id):
            return {}
        if segment_id is not None and not valid_segment_id(segment_id):
            return {}
        root = self._book_work_dir(book_id)
        snapshot = root.parent.name == 'publications'
        ledger = self._read_json_cached(root / "review_responses.json") if snapshot else None
        if ledger is None and snapshot:
            root = root.parent.parent
        if ledger is None:
            ledger = self._read_json_cached(root / "editorial" / "review_apply_ledger.json")
        out: dict[str, list[dict[str, Any]]] = {}
        from ..pipeline_review import response_entry
        package = self.pipeline_review(book_id)
        for item in package.get('items', []):
            if segment_id is None or item['segment_id'] == segment_id:
                out[item['id']] = [_review_apply_response(response_entry(package, item))]
        applied: dict[str, list[dict[str, Any]]] = {}
        for entry in (ledger.get("entries", []) or []) if isinstance(ledger, dict) else []:
            if not isinstance(entry, dict):
                continue
            if source_id is not None and entry.get("source_id") and entry["source_id"] != source_id:
                continue
            target_segment = str(entry.get("segment_id") or "").strip()
            if segment_id is not None and target_segment != segment_id:
                continue
            comment_id = str(entry.get("comment_id") or "").strip()
            if not comment_id:
                continue
            response = _review_apply_response(entry)
            if response:
                applied.setdefault(comment_id, []).append(response)
        for comment_id, items in applied.items():
            items.sort(key=lambda r: str(r.get("processed_at") or ""))
            out[comment_id] = items[-1:]
        return out

    def pipeline_review(self, book_id: str) -> dict:
        from ..pipeline_review import FILENAME, validate_package
        data = self._read_json_cached(self._book_work_dir(book_id) / FILENAME)
        return validate_package(data, book_id) if data is not None else {}

    def book_summary(self, book_id: str) -> Optional[BookSummary]:
        if not self.has_book(book_id):
            return None
        meta = self._metadata(book_id)
        counts = {k: 0 for k in NOTE_KEYS}
        sids = self.segment_ids(book_id)
        for sid in sids:
            for k, v in self.chapter_counts(book_id, sid).items():
                counts[k] = counts.get(k, 0) + v
        return BookSummary(
            book_id=book_id,
            title=str(meta.get("title") or book_id),
            author=str(meta.get("author") or ""),
            chapters=len(sids),
            counts=counts,
            diagnostics=self.diagnostic_counts(book_id),
        )

    def chapter_counts(self, book_id: str, segment_id: str) -> dict[str, int]:
        alignment = self.alignment(book_id, segment_id)
        if not alignment:
            return {k: 0 for k in NOTE_KEYS}
        counts = {k: 0 for k in NOTE_KEYS}
        for m in alignment.get("mapping", []):
            counts[_note_key(m.get("note"))] += 1
        return counts

    def diagnostics(self, book_id: str,
                    segment_id: str | None = None) -> list[dict[str, Any]]:
        if not valid_book_id(book_id):
            return []
        if segment_id is not None and not valid_segment_id(segment_id):
            return []
        found: list[dict[str, Any]] = []

        book_work_dir = self._book_work_dir(book_id)

        name_lint = self._read_json_cached(book_work_dir / "name_lint_report.json")
        if isinstance(name_lint, dict):
            for f in name_lint.get("findings", []) or []:
                if not isinstance(f, dict):
                    continue
                sid = str(f.get("segment_id") or "").strip()
                if not valid_segment_id(sid) or (segment_id and sid != segment_id):
                    continue
                found.append({
                    "source": "name-lint",
                    "class": "unglossed_name",
                    "severity": str(f.get("severity") or "major"),
                    "segment_id": sid,
                    "pair": "",
                    "draft_passage": str(f.get("draft_passage") or "").strip(),
                    "source_has": str(f.get("appearances_summary") or "").strip(),
                    "reason": str(f.get("reason") or "").strip(),
                    "name": str(f.get("name") or "").strip(),
                    "alias": str(f.get("alias") or "").strip(),
                    "occurrence_type": str(f.get("occurrence_type") or "").strip(),
                })

        dialogue_segment_ids = [segment_id] if segment_id else self.segment_ids(book_id)
        for sid in dialogue_segment_ids:
            alignment = self.alignment(book_id, sid)
            if not alignment:
                continue
            draft_paras = alignment.get("draft_paragraphs", [])
            if isinstance(draft_paras, list):
                src_paras = alignment.get("source_paragraphs", [])
                source_by_draft: dict[int, str] = {}
                if isinstance(src_paras, list):
                    for m in alignment.get("mapping", []):
                        idx = m.get("draft_para")
                        if not isinstance(idx, int):
                            continue
                        source_idxs = [
                            i for i in (m.get("source_paras") or [])
                            if isinstance(i, int) and 0 <= i < len(src_paras)
                        ]
                        if source_idxs:
                            source_by_draft[idx] = "\n\n".join(
                                str(src_paras[i]) for i in source_idxs)
                found.extend(_dialogue_lint_diagnostics(
                    book_id, sid, draft_paras, source_by_draft))

        return _dedupe_diagnostics(found)

    def diagnostic_counts(self, book_id: str,
                          segment_id: str | None = None) -> dict[str, int]:
        counts = {k: 0 for k in DIAGNOSTIC_CLASSES}
        counts["total"] = 0
        for diagnostic in self.diagnostics(book_id, segment_id):
            cls = str(diagnostic.get("class") or "")
            counts[cls] = counts.get(cls, 0) + 1
            counts["total"] += 1
        return counts

    def chapter_index(self, book_id: str) -> list[dict]:
        titles = self._segment_titles(book_id)
        out = []
        for sid in self.segment_ids(book_id):
            alignment = self.alignment(book_id, sid) or {}
            out.append({
                "segment_id": sid,
                "title": titles.get(sid, ""),
                "draft_paragraphs": len(alignment.get("draft_paragraphs", [])),
                "source_paragraphs": len(alignment.get("source_paragraphs", [])),
                "counts": self.chapter_counts(book_id, sid),
                "diagnostics": self.diagnostic_counts(book_id, sid),
            })
        return out

    def chapter_view(self, book_id: str, segment_id: str) -> Optional[dict]:
        """Alignment rendered into the block shape the UI consumes — same
        bucketing and word-diff decisions the static proofread.html makes."""
        alignment = self.alignment(book_id, segment_id)
        if not alignment:
            return None
        src_paras: list[str] = alignment.get("source_paragraphs", [])
        draft_paras: list[str] = alignment.get("draft_paragraphs", [])
        titles = self._segment_titles(book_id)

        blocks: list[dict] = []
        used_src: set[int] = set()
        for m in alignment.get("mapping", []):
            idx = m.get("draft_para")
            if not isinstance(idx, int) or not (0 <= idx < len(draft_paras)):
                continue
            note_raw = str(m.get("note", "")).strip()
            note_key = _note_key(note_raw)
            src_idxs = [i for i in (m.get("source_paras") or [])
                        if isinstance(i, int) and 0 <= i < len(src_paras)]
            used_src.update(src_idxs)

            draft_text = draft_paras[idx]
            concat_src = "\n\n".join(src_paras[i] for i in src_idxs)
            diff = None
            if len(src_idxs) == 1 and should_word_diff(note_key, concat_src, draft_text):
                diff = word_diff_html(concat_src, draft_text)

            blocks.append({
                "draft_para": idx,
                "note": note_raw or note_key,
                "note_key": note_key,
                "draft": draft_text,
                "anchor": anchor_hash(draft_text),
                "sources": [{"index": i, "text": src_paras[i]} for i in src_idxs],
                "diff_html": diff,
                "diagnostics": [],
            })

        diagnostics = self.diagnostics(book_id, segment_id)
        unmatched_diagnostics = _attach_diagnostics(blocks, diagnostics)
        unused = [{"index": i, "text": t} for i, t in enumerate(src_paras)
                  if i not in used_src]

        return {
            "book_id": book_id,
            "segment_id": segment_id,
            "title": titles.get(segment_id, ""),
            "counts": self.chapter_counts(book_id, segment_id),
            "chapter_notes": self.chapter_notes(book_id, segment_id),
            "diagnostic_counts": self.diagnostic_counts(book_id, segment_id),
            "diagnostics": diagnostics,
            "diagnostics_unmatched": unmatched_diagnostics,
            "blocks": blocks,
            "unused": unused,
        }


def _note_key(note: Any) -> str:
    key = str(note or "").split("—")[0].strip().lower()
    return key if key in NOTE_KEYS else "unsupported"


def _review_apply_response(entry: dict[str, Any]) -> dict[str, Any] | None:
    raw_response = entry.get("comment_response")
    response = raw_response if isinstance(raw_response, dict) else {}
    body = str(response.get("body") or entry.get("reason") or "").strip()
    if not body:
        return None
    raw_changed = (response.get("changed_paragraphs")
                   if "changed_paragraphs" in response
                   else entry.get("changed_paragraphs"))
    changed = [
        i for i in (raw_changed or [])
        if isinstance(i, int) and i >= 0
    ] if isinstance(raw_changed, list) else []
    action = str(response.get("action") or entry.get("action") or "").strip().lower()
    if action not in {"applied", "skipped"}:
        action = "processed"
    return {
        "id": response_id(entry),
        "source": str(response.get("source") or "review_apply"),
        "action": action,
        "body": body[:MAX_LLM_RESPONSE],
        "processed_at": response.get("processed_at") or entry.get("used_at"),
        "segment_id": str(response.get("segment_id") or entry.get("segment_id") or ""),
        "run_id": str(response.get("run_id") or entry.get("run_id") or ""),
        "feedback_key": str(entry.get("feedback_key") or ""),
        "draft_changed": bool(response.get("draft_changed", entry.get("draft_changed"))),
        "changed_paragraphs": changed,
        "model": str(response.get("model") or entry.get("model") or ""),
        "draft_after_hash": entry.get("draft_after_hash"),
        **({"comment_binding": entry["comment_binding"]} if isinstance(entry.get("comment_binding"), dict) else {}),
    }


# --------------------------------------------------------------------------
# Review queue (read-write)
# --------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
    id          TEXT PRIMARY KEY,
    book_id     TEXT NOT NULL,
    segment_id  TEXT NOT NULL,
    draft_para  INTEGER,
    anchor      TEXT NOT NULL DEFAULT '',
    quote       TEXT NOT NULL DEFAULT '',
    severity    TEXT NOT NULL DEFAULT 'minor',
    kind        TEXT NOT NULL DEFAULT 'other',
    status      TEXT NOT NULL DEFAULT 'open',
    body        TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_book ON comments (book_id, segment_id);
CREATE TABLE IF NOT EXISTS revision_reviews (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    comment_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    action TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at REAL NOT NULL,
    context TEXT NOT NULL,
    response TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revision_reviews_comment ON revision_reviews (comment_id, sequence);
"""


class ReviewStore:
    """SQLite-backed comment queue. One connection per call keeps this safe
    under uvicorn's threadpool without a global lock."""

    def __init__(self, db_path: Path | None = None) -> None:
        env = os.environ.get("FORAGE_REVIEW_DB")
        self.db_path = Path(env) if env else (db_path or WORK_DIR / "_review" / "review.db")
        mutable_path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Serialize schema upgrades across app workers; existing comments
            # retain their original anchors and receive nullable new metadata.
            conn.execute("BEGIN IMMEDIATE")
            columns = {r[1] for r in conn.execute("PRAGMA table_info(comments)")}
            for name, definition in {
                "scope": "TEXT", "target_kind": "TEXT NOT NULL DEFAULT 'text'",
                "target_id": "TEXT", "publication_revision": "TEXT",
                "text_revision": "TEXT", "target_revision": "TEXT",
                "timestamp_seconds": "REAL", "original_text": "TEXT", "chapter_anchor": "TEXT",
                "review_version": "INTEGER NOT NULL DEFAULT 0",
                "pipeline_item_id": "TEXT",
                "author_user_id": "TEXT",
            }.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE comments ADD COLUMN {name} {definition}")
            conn.execute("CREATE TABLE IF NOT EXISTS review_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO review_metadata VALUES ('source_id', ?)",
                         (uuid.uuid4().hex,))

    @property
    def source_id(self) -> str:
        with self._connect() as conn:
            return conn.execute("SELECT value FROM review_metadata WHERE key='source_id'").fetchone()[0]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # -- reads -------------------------------------------------------------

    def list_comments(self, book_id: str, segment_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM comments WHERE book_id = ?"
        args: list[Any] = [book_id]
        if segment_id is not None:
            sql += " AND segment_id = ?"
            args.append(segment_id)
        sql += " ORDER BY segment_id, draft_para IS NULL, draft_para, created_at"
        with self._connect() as conn:
            return self._with_reviews(conn, [dict(r) for r in conn.execute(sql, args)])

    def get(self, comment_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM comments WHERE id = ?",
                               (comment_id,)).fetchone()
            return self._with_reviews(conn, [dict(row)])[0] if row else None

    def _with_reviews(self, conn, rows):
        by_id = {row['id']: row for row in rows}
        for row in rows:
            row['revision_reviews'] = []
        if rows:
            # One history query per book, avoiding a query for every comment.
            for event in conn.execute('SELECT * FROM revision_reviews WHERE comment_id IN '
                    '(SELECT id FROM comments WHERE book_id = ?) ORDER BY sequence', (rows[0]['book_id'],)):
                if event['comment_id'] in by_id:
                    data = dict(event)
                    data['context'] = json.loads(data['context'])
                    data['response'] = json.loads(data['response'])
                    by_id[event['comment_id']]['revision_reviews'].append(data)
        return rows

    def counts_by_chapter(self, book_id: str) -> dict[str, dict[str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT segment_id, status, COUNT(*) AS n FROM comments "
                "WHERE book_id = ? GROUP BY segment_id, status", (book_id,))
            out: dict[str, dict[str, int]] = {}
            for r in rows:
                bucket = out.setdefault(r["segment_id"], {"total": 0})
                bucket[r["status"]] = r["n"]
                bucket["total"] += r["n"]
        return out

    def counts_by_book(self) -> dict[str, dict[str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT book_id, status, COUNT(*) AS n FROM comments "
                "GROUP BY book_id, status")
            out: dict[str, dict[str, int]] = {}
            for r in rows:
                bucket = out.setdefault(r["book_id"], {"total": 0})
                bucket[r["status"]] = r["n"]
                bucket["total"] += r["n"]
        return out

    # -- writes ------------------------------------------------------------

    def import_pipeline_review(self, artifacts: ArtifactStore, book_id: str) -> None:
        """Idempotent publication import; never replace reviewer decisions."""
        package = artifacts.pipeline_review(book_id)
        info = artifacts.revision_info(book_id)
        now = time.time()
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for item in package.get('items', []):
                original = '\n\n'.join(package['chapters'][item['segment_id']]['paragraphs'])
                existing = conn.execute('SELECT pipeline_item_id FROM comments WHERE id = ?', (item['id'],)).fetchone()
                if existing is not None:
                    if existing['pipeline_item_id'] != item['id']:
                        raise ValueError('Pipeline review ID conflicts with an existing comment')
                    continue
                conn.execute('INSERT INTO comments '
                    '(id, book_id, segment_id, draft_para, anchor, quote, severity, kind, status, body, '
                    'author, created_at, updated_at, scope, target_kind, original_text, chapter_anchor, '
                    'publication_revision, text_revision, pipeline_item_id) '
                    'VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (item['id'], book_id, item['segment_id'], anchor_hash(original), '',
                     'blocker' if item['priority'] == 'must_fix' else 'minor', 'continuity', 'open',
                     item['body'], 'Pipeline critic' if item['kind'] == 'finding' else 'Pipeline repairs',
                     now, now, 'chapter', 'text', original, item['chapter_anchor'],
                     info['publication_revision'], info['text_revision'], item['id']))

    def add(self, *, book_id: str, segment_id: str, draft_para: int | None,
            anchor: str, quote: str, severity: str, kind: str, body: str,
            author: str, scope: str | None = None, target_kind: str = "text",
            target_id: str | None = None, publication_revision: str | None = None,
            text_revision: str | None = None, target_revision: str | None = None,
            timestamp_seconds: float | None = None,
            original_text: str | None = None, chapter_anchor: str | None = None,
            author_user_id: str | None = None) -> dict:
        now = time.time()
        row = {
            "id": uuid.uuid4().hex[:12],
            "book_id": book_id,
            "segment_id": segment_id,
            "draft_para": draft_para,
            "anchor": anchor[:64],
            "quote": quote[:MAX_QUOTE],
            "severity": severity if severity in SEVERITIES else "minor",
            "kind": kind if kind in KINDS else "other",
            "status": "open",
            "body": body[:MAX_BODY],
            "author": author[:MAX_AUTHOR],
            "author_user_id": author_user_id,
            "created_at": now,
            "updated_at": now,
            "scope": scope or ("book" if segment_id == BOOK_COMMENT_SEGMENT
                               else "chapter" if draft_para is None else "paragraph"),
            "target_kind": target_kind, "target_id": target_id,
            "publication_revision": publication_revision, "text_revision": text_revision,
            "target_revision": target_revision, "timestamp_seconds": timestamp_seconds,
            "original_text": original_text, "chapter_anchor": chapter_anchor,
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO comments (id, book_id, segment_id, draft_para, anchor,"
                " quote, severity, kind, status, body, author, created_at, updated_at,"
                " scope, target_kind, target_id, publication_revision, text_revision,"
                " target_revision, timestamp_seconds, original_text, chapter_anchor, author_user_id)"
                " VALUES (:id, :book_id, :segment_id, :draft_para, :anchor, :quote,"
                " :severity, :kind, :status, :body, :author, :created_at, :updated_at,"
                " :scope, :target_kind, :target_id, :publication_revision, :text_revision,"
                " :target_revision, :timestamp_seconds, :original_text, :chapter_anchor, :author_user_id)",
                row)
        return row

    @staticmethod
    def _require_owner(conn, row, actor_id, *, pipeline_decision=False):
        actor = conn.execute('SELECT role FROM users WHERE id=?', (actor_id,)).fetchone()
        if actor is None or actor['role'] not in {'admin', 'reviewer'}:
            raise PermissionError('Sign in again before changing notes.')
        if row['pipeline_item_id'] and not pipeline_decision:
            raise PermissionError('Use the pipeline review decision controls.')
        if (actor['role'] == 'admin' or row['author_user_id'] == actor_id
                or (pipeline_decision and row['pipeline_item_id'])):
            return
        raise PermissionError('You can only change your own notes.')

    def update(self, comment_id: str, *, actor_id: str, **fields: Any) -> Optional[dict]:
        allowed = {"body", "severity", "kind", "status"}
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "severity" in sets and sets["severity"] not in SEVERITIES:
            sets.pop("severity")
        if "kind" in sets and sets["kind"] not in KINDS:
            sets.pop("kind")
        if "status" in sets and sets["status"] not in STATUSES:
            sets.pop("status")
        if "body" in sets:
            sets["body"] = str(sets["body"])[:MAX_BODY]
        sets["updated_at"] = time.time()
        clause = ", ".join(f"{k} = :{k}" for k in sets)
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM comments WHERE id=?', (comment_id,)).fetchone()
            if row is None:
                return None
            self._require_owner(conn, row, actor_id)
            conn.execute(f"UPDATE comments SET {clause}, review_version = review_version + 1 WHERE id = :id",
                         {**sets, "id": comment_id})
        return self.get(comment_id)

    def delete(self, comment_id: str, *, actor_id: str) -> bool:
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM comments WHERE id=?', (comment_id,)).fetchone()
            if row is None:
                return False
            self._require_owner(conn, row, actor_id)
            conn.execute('DELETE FROM revision_reviews WHERE comment_id = ?', (comment_id,))
            cur = conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        return cur.rowcount > 0

    def review_revision(self, comment_id: str, *, response: dict, action: str,
                        body: str, author: str, context: dict, expected_version: int,
                        actor_id: str) -> dict:
        """Save a reviewer decision and queue status as one serialized mutation."""
        if action not in {'accepted', 'rejected', 'reopened'}:
            raise ValueError('Unknown revision decision.')
        if not isinstance(body, str) or len(body) > MAX_BODY or (action == 'rejected' and not body.strip()):
            raise ValueError('Explain what should change before requesting another revision.')
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM comments WHERE id = ?', (comment_id,)).fetchone()
            if row is None:
                raise ValueError('No such comment.')
            self._require_owner(conn, row, actor_id, pipeline_decision=True)
            if type(expected_version) is not int or row['review_version'] != expected_version:
                raise RuntimeError('This review changed. Reload before deciding.')
            last = conn.execute('SELECT action FROM revision_reviews WHERE comment_id = ? '
                'AND response_id = ? ORDER BY sequence DESC LIMIT 1', (comment_id, response['id'])).fetchone()
            state = last['action'] if last else 'pending'
            if (action == 'reopened' and state != 'accepted') or (action != 'reopened' and state == 'accepted'):
                raise RuntimeError('Reopen an accepted revision before changing its decision.')
            now = time.time()
            conn.execute('INSERT INTO revision_reviews '
                '(id, comment_id, response_id, action, body, author, created_at, context, response) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (uuid.uuid4().hex, comment_id, response['id'], action, body.strip(), author[:MAX_AUTHOR],
                 now, json.dumps(context), json.dumps(response)))
            conn.execute('UPDATE comments SET status = ?, updated_at = ?, review_version = review_version + 1 WHERE id = ?',
                ('resolved' if action == 'accepted' else 'open', now, comment_id))
        return self.get(comment_id)


# --------------------------------------------------------------------------
# Publish
# --------------------------------------------------------------------------


def decorate_comments(artifacts: ArtifactStore, book_id: str, rows: list[dict],
                      responses: dict | None = None) -> list[dict]:
    """Decorate against one pinned revision without changing stored context."""
    targets = {t["id"]: t for t in artifacts.media(book_id)["targets"]}
    info = artifacts.revision_info(book_id)
    out = []
    pipeline_items = {i['id']: i for i in artifacts.pipeline_review(book_id).get('items', [])}
    for row in rows:
        if row.get('pipeline_item_id') and row['pipeline_item_id'] not in pipeline_items:
            continue  # Historical editions show only their own immutable review items.
        item = dict(row)
        if row.get('pipeline_item_id'):
            item['pipeline_review'] = pipeline_items[row['pipeline_item_id']]
        scope = row.get("scope") or ("book" if row["segment_id"] == BOOK_COMMENT_SEGMENT
                                    else "chapter" if row["draft_para"] is None else "paragraph")
        item.update(scope=scope, stale=False, orphaned=False)
        if scope in {"audio", "graphic"}:
            target = targets.get(row.get("target_id"))
            item["orphaned"] = target is None
            item["stale"] = target is not None and target["revision"] != row.get("target_revision")
        elif scope == "book":
            item["stale"] = bool(row.get("text_revision") and
                                 row["text_revision"] != info.get("text_revision"))
        else:
            alignment = artifacts.alignment(book_id, row["segment_id"])
            paras = (alignment or {}).get("draft_paragraphs", [])
            if scope == "chapter":
                current = "\n\n".join(paras)
                item["orphaned"] = alignment is None
                item["stale"] = alignment is not None and row.get("original_text") is not None and current != row["original_text"]
            else:
                response = (responses or {}).get(row["id"], [])
                binding = response[-1].get("comment_binding") if response else None
                item.update(locate(row, paras, binding))
        response = (responses or {}).get(row["id"], [])
        if response:
            item.update(llm_responses=response, llm_response_count=len(response))
            latest = response[-1]
            sid = latest['segment_id']
            paragraphs = (artifacts.alignment(book_id, sid) or {}).get('draft_paragraphs', [])
            binding = latest.get('comment_binding')
            if scope == 'paragraph':
                # A return to the original chapter can locate the old note,
                # but must not make a discarded LLM correction reviewable.
                current = binding_is_current(row, paragraphs, binding)
            else:
                digest = hashlib.sha256(('\n\n'.join(paragraphs).strip() + '\n').encode()).hexdigest()[:24]
                current = bool(paragraphs) and digest == latest.get('draft_after_hash')
            history = row.get('revision_reviews', [])
            decisions = [e for e in history if e['response_id'] == latest['id']]
            decision = decisions[-1] if decisions else None
            state = decision['action'] if decision else 'pending'
            item['revision_review'] = {
                'response_id': latest['id'], 'state': state, 'current': current,
                'version': row.get('review_version', 0), 'chapter_anchor': chapter_hash(paragraphs),
                'segment_id': sid, **info,
                'request': ({'id': decision['id'], 'body': decision['body'], **decision['context']}
                            if state == 'rejected' else None),
            }
            if history and not decision:
                item['status'] = 'open'  # An old acceptance never approves a new response.
        out.append(item)
    return out


def build_feedback(artifacts: ArtifactStore, reviews: ReviewStore, book_id: str) -> dict:
    return {"version": 1, "source_id": reviews.source_id, "book_id": book_id,
            "complete": True,
            "comments": decorate_comments(artifacts, book_id, reviews.list_comments(book_id),
                artifacts.review_apply_responses(book_id, source_id=reviews.source_id))}


def build_edits(artifacts: ArtifactStore, reviews: ReviewStore, book_id: str,
                statuses: Iterable[str] = ("open", "accepted")) -> dict:
    """Keep prose overlay compatibility while exporting media separately."""
    wanted = set(statuses)
    comments = decorate_comments(artifacts, book_id,
                                reviews.list_comments(book_id),
                                artifacts.review_apply_responses(book_id, source_id=reviews.source_id))
    comments = [c for c in comments if c['status'] in wanted]
    by_segment: dict[str, list[dict]] = {}
    book_items, media_items = [], []
    for c in comments:
        item = {**c, "note": c["body"], "source_id": reviews.source_id}
        if c["scope"] in {"audio", "graphic"}:
            media_items.append(item)
        elif c["scope"] == "book":
            book_items.append(item)
        else:
            paras = (artifacts.alignment(book_id, c["segment_id"]) or {}).get("draft_paragraphs", [])
            # Never substitute today's text at an old numeric position.
            original = c.get("original_text")
            if original is None and c.get("attachment_status") == "exact":
                original = paras[c["current_draft_para"]]
            if original is None and c.get("scope") == "chapter" and not c.get("stale"):
                original = "\n\n".join(paras)
            item["paragraph"] = original
            by_segment.setdefault(c["segment_id"], []).append(item)
    return {"book_id": book_id, "generated_at": time.time(), "statuses": sorted(wanted),
            "comment_count": len(comments), "stale_count": sum(c["stale"] for c in comments),
            "book_comments": book_items, "media_comments": media_items,
            "segments": [{"segment_id": sid, "comments": by_segment[sid]} for sid in sorted(by_segment)]}


def edits_path(artifacts: ArtifactStore, book_id: str) -> Path:
    """Where a published overlay lands.

    Locally that's alongside the book's other artifacts. A hosted deployment
    reads artifacts from a read-only image, so FORAGE_EDITS_DIR redirects the
    write to the one volume that is actually writable.
    """
    override = os.environ.get("FORAGE_EDITS_DIR")
    if override:
        return mutable_path(Path(override) / book_id / "edits.json")
    return mutable_path(artifacts.work_dir / book_id / "editorial" / "edits.json")


def publish_edits(artifacts: ArtifactStore, reviews: ReviewStore,
                  book_id: str) -> tuple[Path, dict]:
    """Write the overlay to disk. Returns (path, document)."""
    doc = build_edits(artifacts, reviews, book_id)
    out_path = edits_path(artifacts, book_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return out_path, doc
