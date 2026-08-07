"""Apply published human review feedback as minimal draft repairs.

This stage consumes the public review overlay (`editorial/edits.json`) and
asks the LLM to revise one chapter at a time. Every feedback item that the LLM
considers is recorded in `editorial/review_apply_ledger.json`, including
skipped feedback, so unchanged comments are not reprocessed in later rounds.
"""

from __future__ import annotations

import hashlib
import difflib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .artifacts import Book, read_json, segment_source_path, write_json
from .json_parse import parse_llm_json
from .llm import complete
from .prompts import load_prompt


_DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"
_LEDGER_VERSION = 1
_PROMPT_NAME = "review_apply_segment"
_SAFE_TERMINALS = set(".!?)]}\"'")
_MAX_REVIEW_WORD_DELTA = 600
_MAX_REVIEW_REL_DELTA = 0.25
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


def default_edits_path(book: Book) -> Path:
    return book.work_dir / "editorial" / "edits.json"


def default_ledger_path(book: Book) -> Path:
    return book.work_dir / "editorial" / "review_apply_ledger.json"


def default_report_path(book: Book) -> Path:
    return book.work_dir / "editorial" / "review_apply_report.json"


def load_review_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ledger_version": _LEDGER_VERSION,
            "entries": [],
        }
    data = read_json(path)
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    return {
        **data,
        "ledger_version": data.get("ledger_version", _LEDGER_VERSION),
        "entries": entries,
    }


def pending_review_feedback(
    book: Book,
    *,
    overlay: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
    segment_ids: Iterable[str] | None = None,
    include_book_comments: bool = True,
    edits_path: Path | None = None,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Return feedback items not yet recorded in the review-apply ledger.

    Book-level comments are evaluated per target chapter. Without an explicit
    segment list, candidates are the chapters that already have chapter or
    paragraph feedback in the overlay.
    """
    edits_path = edits_path or default_edits_path(book)
    ledger_path = ledger_path or default_ledger_path(book)
    overlay = overlay if overlay is not None else read_json(edits_path)
    ledger = ledger if ledger is not None else load_review_ledger(ledger_path)

    candidates = _candidate_segment_ids(book, overlay, segment_ids)
    entries = ledger.get("entries", []) or []
    used_keys = {
        str(e.get("feedback_key"))
        for e in entries
        if e.get("feedback_key")
    }
    segment_rows = []
    for sid in candidates:
        all_items = _feedback_for_segment(
            book_id=book.book_id,
            overlay=overlay,
            segment_id=sid,
            include_book_comments=include_book_comments,
        )
        pending = [item for item in all_items
                   if item["feedback_key"] not in used_keys]
        segment_rows.append({
            "segment_id": sid,
            "pending": pending,
            "pending_count": len(pending),
            "used_count": len(all_items) - len(pending),
            "total_count": len(all_items),
        })

    return {
        "book_id": book.book_id,
        "edits_path": str(edits_path),
        "ledger_path": str(ledger_path),
        "overlay_generated_at": overlay.get("generated_at"),
        "include_book_comments": include_book_comments,
        "book_comment_count": len(overlay.get("book_comments", []) or []),
        "segments": segment_rows,
        "pending_count": sum(row["pending_count"] for row in segment_rows),
        "used_count": sum(row["used_count"] for row in segment_rows),
        "total_count": sum(row["total_count"] for row in segment_rows),
        "needs_segment_for_book_comments": (
            include_book_comments
            and bool(overlay.get("book_comments"))
            and not _overlay_segment_ids(overlay)
            and segment_ids is None
        ),
    }


def apply_review_feedback(
    book: Book,
    *,
    segment_ids: Iterable[str] | None = None,
    edits_path: Path | None = None,
    ledger_path: Path | None = None,
    report_path: Path | None = None,
    include_book_comments: bool = True,
    max_segments: int | None = None,
    plan_only: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply pending human feedback.

    `plan_only` performs no LLM calls and writes no files. `dry_run` does call
    the LLM but does not update drafts or the ledger.
    """
    edits_path = edits_path or default_edits_path(book)
    ledger_path = ledger_path or default_ledger_path(book)
    report_path = report_path or default_report_path(book)
    if not edits_path.exists():
        raise FileNotFoundError(f"no published review overlay at {edits_path}")

    overlay = read_json(edits_path)
    ledger = load_review_ledger(ledger_path)
    plan = pending_review_feedback(
        book,
        overlay=overlay,
        ledger=ledger,
        segment_ids=segment_ids,
        include_book_comments=include_book_comments,
        edits_path=edits_path,
        ledger_path=ledger_path,
    )
    planned_segments = [row for row in plan["segments"] if row["pending_count"]]
    if max_segments is not None:
        planned_segments = planned_segments[:max(0, max_segments)]

    report: dict[str, Any] = {
        "book_id": book.book_id,
        "run_id": _run_id(),
        "plan_only": plan_only,
        "dry_run": dry_run,
        "edits_path": str(edits_path),
        "ledger_path": str(ledger_path),
        "overlay_generated_at": overlay.get("generated_at"),
        "include_book_comments": include_book_comments,
        "segments_considered": len(plan["segments"]),
        "segments_planned": len(planned_segments),
        "pending_feedback": sum(row["pending_count"] for row in planned_segments),
        "already_used_feedback": plan["used_count"],
        "needs_segment_for_book_comments": plan.get(
            "needs_segment_for_book_comments", False),
        "segments": [],
    }
    if plan_only:
        report["segments"] = planned_segments
        return report

    prompt = load_prompt(_PROMPT_NAME)
    for row in planned_segments:
        result = _apply_segment_feedback(
            book=book,
            segment_id=row["segment_id"],
            feedback=row["pending"],
            overlay=overlay,
            ledger=ledger,
            ledger_path=ledger_path,
            prompt=prompt,
            run_id=report["run_id"],
            dry_run=dry_run,
        )
        report["segments"].append(result)

    report["segments_applied"] = sum(1 for r in report["segments"]
                                     if r.get("status") == "applied")
    report["segments_no_change"] = sum(1 for r in report["segments"]
                                       if r.get("status") == "no_change")
    report["segments_failed"] = sum(1 for r in report["segments"]
                                    if r.get("status") in {"failed", "rejected"})
    if not dry_run:
        write_json(report_path, report)
    return report


def _apply_segment_feedback(
    *,
    book: Book,
    segment_id: str,
    feedback: list[dict[str, Any]],
    overlay: dict[str, Any],
    ledger: dict[str, Any],
    ledger_path: Path,
    prompt: Any,
    run_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    source_path = segment_source_path(book, segment_id)
    if source_path is None:
        return _segment_error(segment_id, "failed", "missing source chapter")
    draft_path = book.work_dir / "segments" / f"{segment_id}.md"
    if not draft_path.exists():
        return _segment_error(segment_id, "failed", "missing draft chapter")

    source_text = source_path.read_text()
    draft_text = draft_path.read_text()
    if not draft_text.strip():
        return _segment_error(segment_id, "failed", "empty draft chapter")

    cached, body = prompt.render_blocks(
        book={
            "id": book.book_id,
            "title": book.metadata.get("title") or book.book_id,
            "author": book.metadata.get("author") or "",
        },
        segment_id=segment_id,
        source_text=source_text,
        draft_text=draft_text,
        feedback_json=json.dumps(feedback, indent=2, ensure_ascii=False),
    )

    response = complete(
        prompt=body,
        cached_prompt=cached,
        model=prompt.config.get("model", _DEFAULT_MODEL),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 16000),
        temperature=prompt.config.get("temperature"),
        cache=not cached,
        work_dir=book.work_dir,
        stage=f"review_apply:{book.book_id}:{segment_id}",
    )

    try:
        parsed = _parse_apply_response(response.text)
        _validate_apply_response(parsed, segment_id=segment_id,
                                 expected_keys={f["feedback_key"] for f in feedback})
        revised = parsed["revised_draft"].strip()
        original = draft_text.strip()
        _validate_revision_consistency(
            decisions=parsed["decisions"], original=original, revised=revised)
        _validate_revised_draft(segment_id, original=original, revised=revised)
    except Exception as e:
        return _segment_error(segment_id, "rejected", str(e),
                              model=response.model,
                              input_tokens=response.input_tokens,
                              output_tokens=response.output_tokens)

    changed = revised != draft_text.strip()
    before_hash = _text_hash(draft_text.strip() + "\n")
    after_hash = _text_hash(revised + "\n")
    if changed and not dry_run:
        snapshot = _snapshot_segment(draft_path, run_id)
        draft_path.write_text(revised + "\n")
        _update_checks(
            book=book,
            segment_id=segment_id,
            source_words=len(source_text.split()),
            draft_words=len(revised.split()),
            run_id=run_id,
        )
    else:
        snapshot = None

    if not dry_run:
        _record_feedback_use(
            ledger=ledger,
            ledger_path=ledger_path,
            book=book,
            segment_id=segment_id,
            feedback=feedback,
            decisions=parsed["decisions"],
            run_id=run_id,
            overlay_generated_at=overlay.get("generated_at"),
            before_hash=before_hash,
            after_hash=after_hash,
            draft_changed=changed,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    status = "applied" if changed else "no_change"
    return {
        "segment_id": segment_id,
        "status": status,
        "feedback_count": len(feedback),
        "decisions": parsed["decisions"],
        "changed": changed,
        "snapshot": str(snapshot) if snapshot else None,
        "before_words": len(draft_text.split()),
        "after_words": len(revised.split()),
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "dry_run": dry_run,
    }


def _candidate_segment_ids(
    book: Book,
    overlay: dict[str, Any],
    segment_ids: Iterable[str] | None,
) -> list[str]:
    if segment_ids is not None:
        return [_normalize_segment_id(sid) for sid in segment_ids]
    overlay_ids = _overlay_segment_ids(overlay)
    if overlay_ids:
        return overlay_ids
    return []


def _overlay_segment_ids(overlay: dict[str, Any]) -> list[str]:
    return sorted({
        _normalize_segment_id(str(seg.get("segment_id")))
        for seg in overlay.get("segments", []) or []
        if seg.get("segment_id") and seg.get("comments")
    })


def _feedback_for_segment(
    *,
    book_id: str,
    overlay: dict[str, Any],
    segment_id: str,
    include_book_comments: bool,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if include_book_comments:
        for comment in overlay.get("book_comments", []) or []:
            items.append(_normalise_feedback(
                book_id=book_id,
                segment_id=segment_id,
                source_segment_id="__book__",
                comment=comment,
            ))
    for seg in overlay.get("segments", []) or []:
        if _normalize_segment_id(str(seg.get("segment_id", ""))) != segment_id:
            continue
        for comment in seg.get("comments", []) or []:
            items.append(_normalise_feedback(
                book_id=book_id,
                segment_id=segment_id,
                source_segment_id=segment_id,
                comment=comment,
            ))
    return items


def _normalise_feedback(
    *,
    book_id: str,
    segment_id: str,
    source_segment_id: str,
    comment: dict[str, Any],
) -> dict[str, Any]:
    scope = comment.get("scope") or (
        "chapter" if comment.get("draft_para") is None else "paragraph")
    item = {
        "feedback_key": "",
        "comment_id": str(comment.get("id") or ""),
        "scope": scope,
        "target_segment_id": segment_id,
        "source_segment_id": source_segment_id,
        "draft_para": comment.get("draft_para"),
        "severity": comment.get("severity") or "minor",
        "kind": comment.get("kind") or "other",
        "status": comment.get("status") or "open",
        "note": comment.get("note") or "",
        "quote": comment.get("quote") or "",
        "paragraph": comment.get("paragraph"),
        "stale": bool(comment.get("stale")),
        "author": comment.get("author") or "",
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
    }
    item["feedback_key"] = feedback_fingerprint(
        book_id=book_id,
        segment_id=segment_id,
        comment=item,
    )
    return item


def feedback_fingerprint(
    *,
    book_id: str,
    segment_id: str,
    comment: dict[str, Any],
) -> str:
    """Stable key for a comment considered against one target chapter.

    The current paragraph text and staleness flag are intentionally excluded:
    applying feedback changes the draft, and that should not by itself make the
    same unchanged comment pending again.
    """
    basis = {
        "book_id": book_id,
        "segment_id": segment_id,
        "comment_id": comment.get("comment_id") or comment.get("id") or "",
        "scope": comment.get("scope") or "",
        "source_segment_id": comment.get("source_segment_id") or "",
        "draft_para": comment.get("draft_para"),
        "severity": comment.get("severity") or "",
        "kind": comment.get("kind") or "",
        "status": comment.get("status") or "",
        "note": comment.get("note") or comment.get("body") or "",
        "quote": comment.get("quote") or "",
        "author": comment.get("author") or "",
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
    }
    raw = json.dumps(basis, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_apply_response(text: str) -> dict[str, Any]:
    parsed = parse_llm_json(text)
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("response must include a decisions list")
    revised = parsed.get("revised_draft")
    if not isinstance(revised, str):
        raise ValueError("response must include string field revised_draft")
    return {
        "segment_id": str(parsed.get("segment_id") or ""),
        "decisions": decisions,
        "revised_draft": revised,
    }


def _validate_apply_response(
    parsed: dict[str, Any],
    *,
    segment_id: str,
    expected_keys: set[str],
) -> None:
    if parsed.get("segment_id") != segment_id:
        raise ValueError(
            f"response segment_id {parsed.get('segment_id')!r} "
            f"did not match {segment_id!r}")

    seen: set[str] = set()
    normalised: list[dict[str, Any]] = []
    for raw in parsed["decisions"]:
        if not isinstance(raw, dict):
            raise ValueError("every decision must be an object")
        key = str(raw.get("feedback_key") or "")
        if not key:
            raise ValueError("every decision must include feedback_key")
        if key in seen:
            raise ValueError(f"duplicate decision for feedback_key {key}")
        action = str(raw.get("action") or "").strip().lower()
        if action not in {"applied", "skipped"}:
            raise ValueError(
                f"decision for {key} has invalid action {raw.get('action')!r}")
        changed = raw.get("changed_paragraphs", [])
        if changed is None:
            changed = []
        if not isinstance(changed, list):
            raise ValueError(
                f"decision for {key} changed_paragraphs must be a list")
        if any(not isinstance(i, int) or i < 0 for i in changed):
            raise ValueError(
                f"decision for {key} changed_paragraphs must contain paragraph indexes")
        reason = str(raw.get("reason") or "").strip()
        if not reason:
            raise ValueError(f"decision for {key} must include a reason")
        if action == "skipped" and changed:
            raise ValueError(
                f"decision for {key} is skipped but lists changed paragraphs")
        normalised.append({
            "feedback_key": key,
            "comment_id": str(raw.get("comment_id") or ""),
            "action": action,
            "reason": reason,
            "changed_paragraphs": changed,
        })
        seen.add(key)

    missing = expected_keys - seen
    extra = seen - expected_keys
    if missing:
        raise ValueError(
            "response omitted decisions for feedback_key(s): "
            + ", ".join(sorted(missing)))
    if extra:
        raise ValueError(
            "response included unexpected feedback_key(s): "
            + ", ".join(sorted(extra)))
    parsed["decisions"] = normalised


def _validate_revised_draft(
    segment_id: str,
    *,
    original: str,
    revised: str,
) -> None:
    if original and not revised:
        raise ValueError(f"{segment_id} revision erased a non-empty draft")
    original_words = len(original.split())
    revised_words = len(revised.split())
    delta = abs(revised_words - original_words)
    relative = (delta / original_words) if original_words else 0.0
    if delta > _MAX_REVIEW_WORD_DELTA and relative > _MAX_REVIEW_REL_DELTA:
        raise ValueError(
            f"{segment_id} revision changed word count from {original_words} "
            f"to {revised_words}; review-apply only allows local edits")
    if _has_safe_terminal(original) and not _has_safe_terminal(revised):
        raise ValueError(f"{segment_id} revision appears truncated at the end")


def _validate_revision_consistency(
    *,
    decisions: list[dict[str, Any]],
    original: str,
    revised: str,
) -> None:
    if not any(d["action"] == "applied" for d in decisions) and revised != original:
        raise ValueError(
            "response changed the draft while all feedback decisions were skipped")
    _validate_declared_changed_paragraphs(
        decisions=decisions, original=original, revised=revised)
    introduced = _introduced_unattributed_dialogue_runs(
        original=original, revised=revised)
    if introduced:
        first = introduced[0]
        location = f" near paragraphs {first[0]}-{first[-1]}"
        raise ValueError(
            "response introduced or increased unattributed dialogue"
            f"{location}; review-apply must not create new unclear speakers")


def _validate_declared_changed_paragraphs(
    *,
    decisions: list[dict[str, Any]],
    original: str,
    revised: str,
) -> None:
    original_paragraphs = _draft_paragraphs(original)
    revised_paragraphs = _draft_paragraphs(revised)
    if len(original_paragraphs) != len(revised_paragraphs):
        return
    actual_changed = {
        idx for idx, (before, after)
        in enumerate(zip(original_paragraphs, revised_paragraphs))
        if before != after
    }
    declared_changed = {
        idx
        for decision in decisions
        for idx in (decision.get("changed_paragraphs") or [])
        if isinstance(idx, int) and idx >= 0
    }
    undeclared = sorted(actual_changed - declared_changed)
    if undeclared:
        preview = ", ".join(str(i) for i in undeclared[:8])
        raise ValueError(
            "response changed paragraph(s) not listed in changed_paragraphs: "
            f"{preview}")


def _draft_paragraphs(text: str) -> list[str]:
    return [para.strip() for para in re.split(r"\n\s*\n", text) if para.strip()]


def _looks_like_unattributed_dialogue(text: str) -> bool:
    s = text.strip()
    if not s or not s.startswith(_DIALOGUE_QUOTE_START):
        return False
    return not _DIALOGUE_ATTRIBUTION_RE.search(s)


def _unattributed_dialogue_runs(text: str) -> list[list[int]]:
    paragraphs = _draft_paragraphs(text)
    runs: list[list[int]] = []
    current: list[int] = []
    for idx, paragraph in enumerate(paragraphs):
        if _looks_like_unattributed_dialogue(paragraph):
            current.append(idx)
        elif current:
            if len(current) >= 3:
                runs.append(current)
            current = []
    if len(current) >= 3:
        runs.append(current)
    return runs


def _introduced_unattributed_dialogue_runs(
    *,
    original: str,
    revised: str,
) -> list[list[int]]:
    original_paragraphs = _draft_paragraphs(original)
    revised_paragraphs = _draft_paragraphs(revised)
    original_unattributed = [
        original_paragraphs[idx]
        for run in _unattributed_dialogue_runs(original)
        for idx in run
    ]
    introduced: list[list[int]] = []
    for run in _unattributed_dialogue_runs(revised):
        new_turns = [
            idx for idx in run
            if not _matches_existing_unattributed_turn(
                revised_paragraphs[idx], original_unattributed)
        ]
        if new_turns:
            introduced.append(run)
    return introduced


def _matches_existing_unattributed_turn(
    paragraph: str,
    candidates: list[str],
) -> bool:
    normalized = _dialogue_turn_key(paragraph)
    if not normalized:
        return False
    for candidate in candidates:
        candidate_key = _dialogue_turn_key(candidate)
        if not candidate_key:
            continue
        if normalized == candidate_key:
            return True
        if difflib.SequenceMatcher(None, normalized, candidate_key).ratio() >= 0.9:
            return True
    return False


def _dialogue_turn_key(text: str) -> str:
    s = text.strip().translate({
        ord("\u2018"): "'",
        ord("\u2019"): "'",
        ord("\u201c"): '"',
        ord("\u201d"): '"',
        ord("\u2014"): "-",
        ord("\u2013"): "-",
    })
    s = re.sub(r"[^a-zA-Z0-9']+", " ", s.lower())
    return " ".join(s.split())


def _record_feedback_use(
    *,
    ledger: dict[str, Any],
    ledger_path: Path,
    book: Book,
    segment_id: str,
    feedback: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    run_id: str,
    overlay_generated_at: Any,
    before_hash: str,
    after_hash: str,
    draft_changed: bool,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    now = _now_iso()
    feedback_by_key = {item["feedback_key"]: item for item in feedback}
    entries = ledger.setdefault("entries", [])
    for decision in decisions:
        item = feedback_by_key[decision["feedback_key"]]
        changed_paragraphs = decision.get("changed_paragraphs") or []
        comment_response = {
            "source": "review_apply",
            "processed_at": now,
            "run_id": run_id,
            "segment_id": segment_id,
            "action": decision["action"],
            "body": decision["reason"],
            "draft_changed": draft_changed,
            "changed_paragraphs": changed_paragraphs,
            "model": model,
        }
        entries.append({
            "run_id": run_id,
            "used_at": now,
            "book_id": book.book_id,
            "segment_id": segment_id,
            "feedback_key": decision["feedback_key"],
            "comment_id": item["comment_id"],
            "scope": item["scope"],
            "source_segment_id": item["source_segment_id"],
            "draft_para": item.get("draft_para"),
            "comment_updated_at": item.get("updated_at") or item.get("created_at"),
            "action": decision["action"],
            "reason": decision["reason"],
            "changed_paragraphs": changed_paragraphs,
            "comment_response": comment_response,
            "draft_before_hash": before_hash,
            "draft_after_hash": after_hash,
            "draft_changed": draft_changed,
            "overlay_generated_at": overlay_generated_at,
            "prompt": _PROMPT_NAME,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })
    ledger["ledger_version"] = _LEDGER_VERSION
    ledger["last_updated_at"] = now
    write_json(ledger_path, ledger)


def _snapshot_segment(draft_path: Path, run_id: str) -> Path:
    snapshot = draft_path.with_name(
        f"{draft_path.stem}.review_apply.{run_id}.before{draft_path.suffix}")
    shutil.copy2(draft_path, snapshot)
    return snapshot


def _update_checks(
    *,
    book: Book,
    segment_id: str,
    source_words: int,
    draft_words: int,
    run_id: str,
) -> None:
    path = book.work_dir / "segments" / f"{segment_id}.checks.json"
    data: dict[str, Any] = read_json(path) if path.exists() else {}
    target = data.get("target_words")
    data["source_words"] = data.get("source_words") or source_words
    data["draft_words"] = draft_words
    if isinstance(target, (int, float)) and target:
        data["word_count_delta_pct"] = round((draft_words - target) / target, 3)
    data["review_apply"] = {
        "run_id": run_id,
        "updated_at": _now_iso(),
    }
    write_json(path, data)


def _segment_error(
    segment_id: str,
    status: str,
    error: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "status": status,
        "error": error,
        **extra,
    }


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _normalize_segment_id(value: str) -> str:
    raw = str(value).strip()
    return raw.zfill(3) if raw.isdigit() else raw


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_safe_terminal(text: str) -> bool:
    return bool(text) and text[-1] in _SAFE_TERMINALS
