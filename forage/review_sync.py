"""Atomic full-feed reconciliation and explicit, revision-aware prose repair."""
from __future__ import annotations

from collections import Counter
from contextlib import nullcontext
import copy
import hashlib
import json
import math
from pathlib import Path
import re

from .review_anchors import locate, anchor_hash, binding_is_current
from .revision_review import actionable, request_for, request_matches
from .production_state import (atomic_json, book_lock, canonical_json, digest,
                               load_state, text_revision, matches_published_text)

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_STATUSES = {"open", "accepted", "resolved", "wontfix", "deleted"}


def import_path(book):
    return book.work_dir / "editorial" / "feedback_import.json"


def imported_edits_path(book):
    return book.work_dir / "editorial" / "imported_edits.json"


def validate_feed(feed, book_id: str) -> dict:
    if (not isinstance(feed, dict) or type(feed.get("version")) is not int or feed["version"] != 1
            or feed.get("book_id") != book_id or feed.get("complete") is not True):
        raise ValueError("feedback requires a complete version-1 feed for this book")
    source = feed.get("source_id")
    if not isinstance(source, str) or not source.strip() or len(source) > 200:
        raise ValueError("feedback requires a stable source_id")
    comments = feed.get("comments")
    if not isinstance(comments, list) or len(comments) > 100000:
        raise ValueError("invalid feedback comments collection")
    seen = set()
    for item in comments:
        if not isinstance(item, dict):
            raise ValueError("invalid feedback comment")
        identifier = item.get("id")
        if (not isinstance(identifier, str) or not identifier or len(identifier) > 200 or identifier in seen):
            raise ValueError("feedback IDs must be unique nonempty strings")
        seen.add(identifier)
        if item.get("book_id", book_id) != book_id:
            raise ValueError("comment book identity mismatch")
        if not isinstance(item.get("status"), str) or item["status"] not in _STATUSES:
            raise ValueError("invalid feedback status")
        for key in ("body", "author"):
            if not isinstance(item.get(key), str):
                raise ValueError(f"feedback {key} must be text")
        for key in ("created_at", "updated_at"):
            value = item.get(key)
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise ValueError(f"feedback requires original {key}")
        for key in ("publication_revision", "text_revision", "target_revision"):
            value = item.get(key)
            if value not in (None, "") and (not isinstance(value, str) or not _HASH.fullmatch(value)):
                raise ValueError(f"invalid feedback {key}")
        if item.get("scope") not in (None, "", "book", "chapter", "paragraph", "audio", "graphic"):
            raise ValueError("unknown feedback scope")
        if item.get("target_kind") not in (None, "", "text", "audio", "graphic"):
            raise ValueError("unknown feedback target kind")
        sid = item.get("segment_id")
        media_segment = sid == "__media__" and item.get("scope") in {"audio", "graphic"}
        if not media_segment and sid not in (None, "", "__book__") and (not isinstance(sid, str) or not _SEGMENT.fullmatch(sid)):
            raise ValueError("invalid feedback segment")
        para = item.get("draft_para")
        if para is not None and (type(para) is not int or para < 0):
            raise ValueError("invalid feedback paragraph index")
        timestamp = item.get("timestamp_seconds")
        if timestamp is not None:
            try:
                finite = type(timestamp) in (int, float) and math.isfinite(timestamp) and timestamp >= 0
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError("invalid feedback timestamp")
        for key in ("anchor", "original_text", "target_id"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ValueError(f"invalid feedback {key}")
        review = item.get('revision_review')
        if review is not None:
            if (not isinstance(review, dict) or not isinstance(review.get('state'), str)
                    or review['state'] not in {'pending', 'accepted', 'rejected', 'reopened'}
                    or type(review.get('current')) is not bool):
                raise ValueError('invalid revision review')
            if review['state'] == 'rejected':
                request = review.get('request')
                if (not isinstance(request, dict) or not isinstance(request.get('id'), str) or not request['id']
                        or not isinstance(request.get('body'), str) or not request['body'].strip()
                        or not isinstance(request.get('segment_id'), str) or not _SEGMENT.fullmatch(request['segment_id'])
                        or not isinstance(request.get('chapter_anchor'), str) or not _HASH.fullmatch(request['chapter_anchor'])):
                    raise ValueError('invalid revision request')
    canonical_json(feed)  # Reject NaN/Infinity anywhere before state changes.
    return feed


def current_text_revision(book) -> str | None:
    """Match the production text identity from current plan and draft bytes."""
    try:
        return text_revision(book)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def imported_eligibility(book, comment: dict) -> str:
    """Freshness comes from live local prose, never a remote stale flag."""
    if comment.get("removed") or comment.get("status") not in {"open", "accepted"}:
        return "inactive"
    if not actionable(comment):
        return 'inactive'
    scope = comment.get("scope")
    if scope in {"audio", "graphic"} or comment.get("target_kind") in {"audio", "graphic"}:
        return "media"
    if scope not in {"book", "chapter", "paragraph"}:
        return "unanchored"
    request = request_for(comment)
    if not request and (not comment.get("publication_revision") or not comment.get("text_revision")):
        return "unanchored"
    if scope == "book" and not request:
        current = current_text_revision(book)
        matches = current and (current == comment.get('text_revision') or matches_published_text(
            book, comment['publication_revision'], comment['text_revision']))
        return 'eligible' if matches else 'stale'
    sid = request['segment_id'] if request else comment.get("segment_id")
    if not isinstance(sid, str) or not _SEGMENT.fullmatch(sid):
        return "unanchored"
    try:
        plan = json.loads((book.work_dir / "plan.json").read_text(encoding="utf-8"))
        active = {s["id"] for s in plan["segments"] if s.get("diegetic_status") == "diegetic"
                  and not s.get("skipped") and int(s.get("target_word_count", 0)) > 0}
        if sid not in active:
            return "orphaned"
    except (OSError, ValueError, KeyError, TypeError):
        return "unanchored"
    path = book.work_dir / "segments" / f"{sid}.md"
    if not path.is_file():
        return "orphaned"
    try:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()) if p.strip()]
    except (OSError, UnicodeError):
        return "orphaned"
    if request:
        if not request_matches(request, sid, paragraphs):
            return 'stale'
        if scope in {'book', 'chapter'}:
            return 'eligible'
        # A remote request cannot certify an old-to-new mapping. Use only the
        # pipeline's own durable binding, or an exact original passage match.
        from .review_apply import load_review_ledger, default_ledger_path
        binding = None
        for entry in load_review_ledger(default_ledger_path(book)).get('entries', []):
            if (entry.get('comment_id') == (comment.get('remote_id') or comment.get('id'))
                    and entry.get('source_id') == comment.get('source_id')
                    and entry.get('segment_id') == sid and entry.get('comment_binding')):
                binding = entry['comment_binding']
        located = locate(comment, paragraphs, binding)
        original = located.get('original_text')
        present = located['current_draft_para'] is not None or binding_is_current(comment, paragraphs, binding)
        return ('eligible' if present and original
                and anchor_hash(original) == comment.get('anchor') else 'stale')
    original = comment.get("original_text")
    anchor = comment.get("anchor")
    if not isinstance(original, str) or not original or not isinstance(anchor, str) or not anchor:
        return "unanchored"
    if scope == "paragraph":
        position = comment.get("draft_para")
        if type(position) is not int or position < 0:
            return "unanchored"
        target = locate(comment, paragraphs)
        if target["current_draft_para"] is None:
            return "orphaned" if not paragraphs else "stale"
        current = paragraphs[target["current_draft_para"]]
    else:
        current = "\n\n".join(paragraphs)
    expected = hashlib.sha1(" ".join(current.split()).encode("utf-8")).hexdigest()[:16]
    return "eligible" if original == current and anchor == expected else "stale"


def filter_imported_overlay(book, overlay: dict) -> dict:
    """Recheck at application time, while keeping trusted legacy overlays intact."""
    if not overlay.get("imported_feedback"):
        return overlay
    if import_path(book).exists():
        # A failed cache replacement must not resurrect a comment resolved or
        # removed in the already committed authoritative import.
        return _projection(book, _load_import(book))[0]
    result = {**overlay, "book_comments": [], "segments": []}
    result["book_comments"] = [c for c in overlay.get("book_comments", [])
                               if imported_eligibility(book, c) == "eligible"]
    for segment in overlay.get("segments", []):
        comments = [c for c in segment.get("comments", [])
                    if imported_eligibility(book, c) == "eligible"]
        if comments:
            result["segments"].append({**segment, "comments": comments})
    return result


def _load_import(book):
    path = import_path(book)
    if not path.exists():
        return {"version": 1, "book_id": book.book_id, "sources": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or state.get("version") != 1
            or state.get("book_id") != book.book_id or not isinstance(state.get("sources"), dict)):
        raise ValueError("invalid local feedback import state")
    return state


def _projection(book, state):
    counts = Counter()
    rows = []
    segments = {}
    books = []
    media = []
    for source_id, source in state["sources"].items():
        for remote_id, record in source["comments"].items():
            comment = {**record["comment"], "source_id": source_id,
                       "removed": record.get("removed", False)}
            reason = imported_eligibility(book, comment)
            counts[reason] += 1
            identity = digest([source_id, book.book_id, remote_id])
            projected = {**comment, "id": identity, "source_id": source_id,
                         "remote_id": remote_id, "note": comment["body"],
                         "paragraph": comment.get("original_text"), "eligibility": reason}
            rows.append({"source_id": source_id, "comment_id": remote_id, "eligibility": reason})
            if reason == "media":
                media.append(projected)
            if reason != "eligible":
                continue
            if comment["scope"] == "book":
                books.append(projected)
            else:
                segments.setdefault(comment["segment_id"], []).append(projected)
    overlay = {"book_id": book.book_id, "imported_feedback": True,
               "book_comments": books, "media_comments": media,
               "segments": [{"segment_id": sid, "comments": comments} for sid, comments in sorted(segments.items())]}
    return overlay, dict(counts), rows


def pull_feedback(book, transport, *, lock_held: bool = False) -> dict:
    with nullcontext() if lock_held else book_lock(book):
        from .review_recovery import recover_review_applications
        recover_review_applications(book, lock_held=True)
        feed = validate_feed(transport.fetch_feedback(book.book_id), book.book_id)
        previous = _load_import(book)
        state = copy.deepcopy(previous)
        source = state["sources"].setdefault(feed["source_id"], {"comments": {}})
        active = set()
        changed = 0
        for comment in feed["comments"]:
            identifier = comment["id"]
            active.add(identifier)
            # Decoration is not source identity; republishing alone must not make
            # an unchanged feedback body into a new application decision.
            comment = {k: v for k, v in comment.items() if k not in {"stale", "orphaned", "responses", "current_revision", "current_draft_para",
                        "current_draft_paras", "attachment_status", "llm_responses", "llm_response_count"}}
            old = source["comments"].get(identifier)
            if old is None or old["comment"] != comment or old.get("removed"):
                history = list(old.get("history", [])) if old else []
                if old:
                    history.append({"comment": old["comment"], "removed": old.get("removed", False)})
                source["comments"][identifier] = {"comment": comment, "removed": False, "history": history}
                changed += 1
        for identifier, record in source["comments"].items():
            if identifier not in active and not record.get("removed"):
                record["history"].append({"comment": record["comment"], "removed": False})
                record["removed"] = True
                changed += 1
        overlay, counts, rows = _projection(book, state)
        if state != previous:
            atomic_json(import_path(book), state)
        # A derived cache: authoritative state is always the complete atomic import.
        path = imported_edits_path(book)
        if not path.exists() or json.loads(path.read_text()) != overlay:
            atomic_json(path, overlay)
        return {"success": True, "book_id": book.book_id, "source_id": feed["source_id"],
                "changed_comments": changed, "counts": counts, "comments": rows,
                "import_path": str(import_path(book)), "edits_path": str(path)}


def sync_feedback(book, transport, *, apply: bool = False, republish: bool = False,
                  production_options: dict | None = None, segment_ids=None) -> dict:
    if republish and not apply:
        raise ValueError("republish requires explicit apply")
    with book_lock(book):
        report = {"success": True, "book_id": book.book_id,
                  "pull": pull_feedback(book, transport, lock_held=True)}
        if not apply:
            return report
        # Heavy pipeline dependencies are only imported after the explicit paid
        # boundary; pulling and all hosted storage remain provider-free.
        from .review_apply import apply_review_feedback
        from .production import run_production, plan_production, validate_refresh_inputs
        from .publication import verify_revision
        state = load_state(book)
        options = dict(state.get("requested_production_options") or state.get("production_options") or {})
        pointer_path = book.work_dir / "review_current.json"
        pointer = json.loads(pointer_path.read_text()) if pointer_path.exists() else None
        if pointer:
            manifest = verify_revision(book, pointer["revision"])
            options.setdefault("outputs", manifest["selected_outputs"])
            if (set(options["outputs"]) - {"text"} and not state.get("requested_production_options")
                    and not state.get("production_options") and production_options is None):
                raise ValueError("legacy media run has no saved settings; supply production_options explicitly")
        options.update(production_options or {})
        # Invalid explicit settings must fail even when the feed has no new
        # prose. Validate before any provider call can apply feedback.
        validate_refresh_inputs(book, options)
        result = apply_review_feedback(book, edits_path=imported_edits_path(book),
                                       segment_ids=segment_ids, lock_held=True)
        report["apply"] = result
        if result.get("segments_failed", 0):
            report.update(success=False, failed_stage="apply")
            return report
        # The common free planner checks the whole dependency graph, selected
        # settings and output bytes. A text hash (including an acknowledged
        # checkpoint) alone cannot certify successful media or a snapshot.
        planned = plan_production(book, options)
        needs_refresh = not planned["success"]
        if needs_refresh:
            production = run_production(book, options, lock_held=True)
            report["production"] = production
            if not production.get("success"):
                report.update(success=False, failed_stage="production")
                return report
            revision = production.get("review_revision")
        else:
            report["production"] = {"status": "unchanged"}
            revision = planned.get("review_revision")
        if republish:
            if not revision:
                raise ValueError("no complete review revision to republish")
            report["publication"] = transport.publish(book, revision, channel="review")
        return report
