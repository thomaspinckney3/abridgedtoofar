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


def anchor_hash(text: str) -> str:
    """Stable fingerprint of a draft paragraph.

    Comments anchor to (segment, paragraph index, anchor hash). When the draft
    is redrafted the index may still exist but the hash won't match — that's
    how the UI knows a comment has gone stale rather than silently pointing at
    different prose.
    """
    normalized = " ".join(text.split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


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
                 overlay_books_dir: Path | None = None) -> None:
        self.work_dir = Path(os.environ.get("FORAGE_WORK_DIR") or work_dir or WORK_DIR)
        self.books_dir = Path(os.environ.get("FORAGE_BOOKS_DIR") or books_dir or BOOKS_DIR)
        self.overlay_work_dir = self._optional_root(
            "FORAGE_ARTIFACT_OVERLAY_DIR", overlay_work_dir)
        self.overlay_books_dir = self._optional_root(
            "FORAGE_BOOKS_OVERLAY_DIR", overlay_books_dir)
        self._cache: dict[str, tuple[tuple[int, int], Any]] = {}

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
            if alignments.is_dir() and any(alignments.glob("*.json")):
                out.add(child.name)
        return out

    # -- public ------------------------------------------------------------

    def book_ids(self) -> list[str]:
        return sorted(self._book_ids_under(self.work_dir)
                      | self._book_ids_under(self.overlay_work_dir))

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
        ledger = self._read_json_cached(
            self._editorial_dir(book_id) / "review_apply_ledger.json")
        if not isinstance(ledger, dict):
            return {}
        out: dict[str, list[dict[str, Any]]] = {}
        for entry in ledger.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            target_segment = str(entry.get("segment_id") or "").strip()
            if segment_id is not None and target_segment != segment_id:
                continue
            comment_id = str(entry.get("comment_id") or "").strip()
            if not comment_id:
                continue
            response = _review_apply_response(entry)
            if response:
                out.setdefault(comment_id, []).append(response)
        for comment_id, items in list(out.items()):
            items.sort(key=lambda r: str(r.get("processed_at") or ""))
            out[comment_id] = items[-1:]
        return out

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
"""


class ReviewStore:
    """SQLite-backed comment queue. One connection per call keeps this safe
    under uvicorn's threadpool without a global lock."""

    def __init__(self, db_path: Path | None = None) -> None:
        env = os.environ.get("FORAGE_REVIEW_DB")
        self.db_path = Path(env) if env else (db_path or WORK_DIR / "_review" / "review.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

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
            return [dict(r) for r in conn.execute(sql, args)]

    def get(self, comment_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM comments WHERE id = ?",
                               (comment_id,)).fetchone()
        return dict(row) if row else None

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

    def add(self, *, book_id: str, segment_id: str, draft_para: int | None,
            anchor: str, quote: str, severity: str, kind: str, body: str,
            author: str) -> dict:
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
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO comments (id, book_id, segment_id, draft_para, anchor,"
                " quote, severity, kind, status, body, author, created_at, updated_at)"
                " VALUES (:id, :book_id, :segment_id, :draft_para, :anchor, :quote,"
                " :severity, :kind, :status, :body, :author, :created_at, :updated_at)",
                row)
        return row

    def update(self, comment_id: str, **fields: Any) -> Optional[dict]:
        allowed = {"body", "severity", "kind", "status", "author"}
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not sets:
            return self.get(comment_id)
        if "severity" in sets and sets["severity"] not in SEVERITIES:
            sets.pop("severity")
        if "kind" in sets and sets["kind"] not in KINDS:
            sets.pop("kind")
        if "status" in sets and sets["status"] not in STATUSES:
            sets.pop("status")
        if "body" in sets:
            sets["body"] = str(sets["body"])[:MAX_BODY]
        if "author" in sets:
            sets["author"] = str(sets["author"])[:MAX_AUTHOR]
        sets["updated_at"] = time.time()
        clause = ", ".join(f"{k} = :{k}" for k in sets)
        with self._connect() as conn:
            conn.execute(f"UPDATE comments SET {clause} WHERE id = :id",
                         {**sets, "id": comment_id})
        return self.get(comment_id)

    def delete(self, comment_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        return cur.rowcount > 0


# --------------------------------------------------------------------------
# Publish
# --------------------------------------------------------------------------


def build_edits(artifacts: ArtifactStore, reviews: ReviewStore, book_id: str,
                statuses: Iterable[str] = ("open", "accepted")) -> dict:
    """Materialize the review queue into the overlay document that a fix stage
    consumes: comments grouped by chapter, each carrying the paragraph text it
    was written against and whether that text has since changed."""
    wanted = set(statuses)
    comments = [c for c in reviews.list_comments(book_id)
                if c["status"] in wanted]

    by_segment: dict[str, list[dict]] = {}
    book_comments: list[dict] = []
    for c in comments:
        if c["segment_id"] == BOOK_COMMENT_SEGMENT:
            book_comments.append(c)
            continue
        by_segment.setdefault(c["segment_id"], []).append(c)

    segments = []
    stale_total = 0
    book_items = [
        {
            "id": c["id"],
            "scope": "book",
            "severity": c["severity"],
            "kind": c["kind"],
            "status": c["status"],
            "note": c["body"],
            "quote": c["quote"],
            "author": c["author"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        }
        for c in book_comments
    ]
    for sid in sorted(by_segment):
        alignment = artifacts.alignment(book_id, sid) or {}
        draft_paras = alignment.get("draft_paragraphs", [])
        items = []
        for c in by_segment[sid]:
            idx = c["draft_para"]
            current = draft_paras[idx] if isinstance(idx, int) and 0 <= idx < len(draft_paras) else None
            stale = bool(c["anchor"]) and current is not None and anchor_hash(current) != c["anchor"]
            if stale:
                stale_total += 1
            items.append({
                "id": c["id"],
                "scope": "chapter" if idx is None else "paragraph",
                "draft_para": idx,
                "severity": c["severity"],
                "kind": c["kind"],
                "status": c["status"],
                "note": c["body"],
                "quote": c["quote"],
                "author": c["author"],
                "paragraph": current,
                "stale": stale,
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
            })
        segments.append({"segment_id": sid, "comments": items})

    return {
        "book_id": book_id,
        "generated_at": time.time(),
        "statuses": sorted(wanted),
        "comment_count": len(comments),
        "stale_count": stale_total,
        "book_comments": book_items,
        "segments": segments,
    }


def edits_path(artifacts: ArtifactStore, book_id: str) -> Path:
    """Where a published overlay lands.

    Locally that's alongside the book's other artifacts. A hosted deployment
    reads artifacts from a read-only image, so FORAGE_EDITS_DIR redirects the
    write to the one volume that is actually writable.
    """
    override = os.environ.get("FORAGE_EDITS_DIR")
    if override:
        return Path(override) / book_id / "edits.json"
    return artifacts.work_dir / book_id / "editorial" / "edits.json"


def publish_edits(artifacts: ArtifactStore, reviews: ReviewStore,
                  book_id: str) -> tuple[Path, dict]:
    """Write the overlay to disk. Returns (path, document)."""
    doc = build_edits(artifacts, reviews, book_id)
    out_path = edits_path(artifacts, book_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return out_path, doc
