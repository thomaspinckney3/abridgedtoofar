"""Drafter stage: read plan.json, produce segments/NNN.md for one or all segments.

Source-text extraction uses a monotone cursor across the book, so each
segment's text lives at work/<book-id>/segments/NNN.source.md. The drafter
reads that + plan.json and asks the LLM for the compressed draft.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, read_json, segment_source_path, write_json, write_text
from .chapter_split import split_to_disk
from .llm import complete
from .motif_ledger import read_ledger, rebuild_ledger
from .prompts import load_prompt
from .text_norm import fuzzy_contains


@dataclass
class DraftResult:
    segment_id: str
    title: str
    status: str  # "drafted", "cut", "skipped_extract_fail", "error"
    source_words: int
    target_words: int
    draft_words: int
    signature_hits: int
    signature_misses: list[dict]  # each has {hint, score, ambiguous}
    message: str = ""


def ensure_chapters(book: Book) -> dict:
    """Ensure the deterministic chapter split has been run. Returns the
    chapters.json manifest. Cheap: a no-op if chapters.json already exists.
    """
    manifest_path = book.work_dir / "chapters.json"
    if manifest_path.exists():
        return read_json(manifest_path)
    split_to_disk(book)
    return read_json(manifest_path)


# Back-compat shim: older call sites expect ensure_extractions(book, plan)
# returning a per-segment dict. Keep it working by delegating to
# ensure_chapters, which is plan-independent.
def ensure_extractions(book: Book, plan: dict) -> dict[str, dict]:
    manifest = ensure_chapters(book)
    return {c["id"]: {"word_count": None, "error": None,
                      "start_offset": c.get("start"),
                      "end_offset": c.get("end")}
            for c in manifest.get("chapters", [])}


def _recent_drafts(book: Book, plan: dict, segment_id: str,
                   n: int = 2, max_words: int = 400) -> list[dict]:
    """Return up to N most recent drafted non-empty segments preceding
    `segment_id` in plan order, as {id, title, excerpt} dicts. Drafter
    prompt uses these for voice continuity — NOT as source material.
    """
    seg_dir = book.work_dir / "segments"
    segs = plan.get("segments", [])
    try:
        idx = next(i for i, s in enumerate(segs) if s["id"] == segment_id)
    except StopIteration:
        return []
    out: list[dict] = []
    for i in range(idx - 1, -1, -1):
        if len(out) >= n:
            break
        prev = segs[i]
        drf_path = seg_dir / f"{prev['id']}.md"
        if not drf_path.exists():
            continue
        text = drf_path.read_text().strip()
        if not text:
            continue
        words = text.split()
        excerpt = (" ".join(words[:max_words]) + " […]"
                   if len(words) > max_words else text)
        out.append({"id": prev["id"],
                    "title": prev.get("title", ""),
                    "excerpt": excerpt})
    return list(reversed(out))  # oldest first


def draft_segment(
    book: Book,
    plan: dict,
    segment_id: str,
    *,
    critic_feedback: list[dict] | None = None,
    previous_draft: str | None = None,
) -> DraftResult:
    segment = next((s for s in plan["segments"] if s["id"] == segment_id), None)
    if segment is None:
        raise ValueError(f"no segment {segment_id!r} in plan")

    seg_dir = book.work_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    source_path = segment_source_path(book, segment_id)
    if source_path is None:
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="skipped_extract_fail", source_words=0,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message=f"no chapter/source file for {segment_id}; run `forage split {book.book_id}`",
        )

    segment_source = source_path.read_text()
    source_words = len(segment_source.split())

    # Extradiegetic segments are cut per the spec.
    if segment.get("diegetic_status") == "extradiegetic":
        write_text(seg_dir / f"{segment_id}.md", "")
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[], status="cut")
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="cut", source_words=source_words,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message="extradiegetic — cut per spec",
        )

    # Lean plans (no prepass) use the spec-as-prompt drafter; fall back to
    # the older tier-based prompt only if the plan has LLM-annotated segments.
    is_lean = plan.get("_meta", {}).get("builder") == "lean_plan"
    prompt_name = "draft_lean" if is_lean else "draft_segment"
    prompt = load_prompt(prompt_name)

    if is_lean:
        spec_path = Path(__file__).resolve().parent.parent / "spec" / "ABRIDGMENT_SPEC.md"
        spec_text = spec_path.read_text() if spec_path.exists() else ""
        target = int(segment.get("target_word_count", 0) or 0)
        ceiling = int(round(target * 1.2)) if target else 0
        cached, body = prompt.render_blocks(
            spec=spec_text,
            book={
                "title": plan.get("title", book.book_id),
                "author": plan.get("author", "?"),
                "genre": book.metadata.get("genre", "unknown"),
            },
            segment={**segment,
                     "source_word_count": segment.get("source_word_count") or source_words},
            ceiling=ceiling,
            segment_source=segment_source,
            critic_feedback=critic_feedback,
            previous_draft=previous_draft,
        )
        rendered = body
    else:
        rendered = prompt.render(
            book={
                "title": plan.get("title", book.book_id),
                "author": plan.get("author", "?"),
                "genre": book.metadata.get("genre", "unknown"),
            },
            plan={
                "modernization_level": plan.get("modernization_level", "L1"),
                "modernization_rationale": plan.get("modernization_rationale", ""),
                "cultural_depth": plan.get("cultural_depth", "?"),
                "voice_driven_narrator": plan.get("voice_driven_narrator", False),
                "indirection_budget_applies": plan.get("indirection_budget_applies", False),
                "overall_compression_ratio": plan.get("overall_compression_ratio", "?"),
                "plan_notes": plan.get("plan_notes", ""),
                "motifs": plan.get("motifs", []),
            },
            segment=segment,
            segment_source=segment_source,
            critic_feedback=critic_feedback,
            previous_draft=previous_draft,
            recent_drafts=_recent_drafts(book, plan, segment_id),
            motif_ledger=read_ledger(book),
        )
        cached = None

    stage_label = (f"draft:{book.book_id}:{segment_id}"
                   if not critic_feedback
                   else f"regen:{book.book_id}:{segment_id}")
    # Extended thinking on Opus improves budget adherence. Enable it only when
    # the resolved model is Opus — GPT-5 and other non-Opus models ignore or
    # reject the param. The per-stage model override (FORAGE_DRAFT_MODEL) wins
    # over FORAGE_MODEL which wins over prompt config default.
    default_model = prompt.config.get("model", "anthropic:claude-opus-4-7")
    active_model = (os.environ.get("FORAGE_DRAFT_MODEL")
                    or os.environ.get("FORAGE_MODEL")
                    or default_model)
    thinking = "max" if "opus" in active_model.lower() else None
    max_out = max(prompt.config.get("max_tokens", 16000), 64000) if thinking \
              else prompt.config.get("max_tokens", 32000)
    resp = complete(
        prompt=rendered,
        cached_prompt=cached,
        model=default_model,
        system=prompt.system,
        max_tokens=max_out,
        temperature=prompt.config.get("temperature"),
        cache=not cached,  # if we have a cache prefix, don't double-wrap
        thinking=thinking,
        work_dir=book.work_dir,
        stage=stage_label,
    )

    # Cross-provider fallback on OpenAI's content_filter. Happens on
    # classical-lit triggers (Moby Dick's suicide references, etc.). Anthropic
    # moderation is less aggressive on acknowledged literary material, so
    # retry once there. Configurable via FORAGE_DRAFT_FALLBACK_MODEL.
    if resp.stop_reason == "content_filter" and active_model.startswith("openai:"):
        import sys as _sys
        fallback_model = os.environ.get("FORAGE_DRAFT_FALLBACK_MODEL",
                                        "anthropic:claude-sonnet-4-6")
        print(f"[drafter] content_filter on {active_model}; "
              f"retrying on {fallback_model}",
              file=_sys.stderr, flush=True)
        fb_thinking = "max" if "opus" in fallback_model.lower() else None
        fb_max = 64000 if fb_thinking else max_out
        fallback_stage = (("draft_fallback:" if not critic_feedback
                           else "regen_fallback:")
                          + f"{book.book_id}:{segment_id}")
        resp = complete(
            prompt=rendered,
            cached_prompt=cached,
            model=fallback_model,
            system=prompt.system,
            max_tokens=fb_max,
            temperature=prompt.config.get("temperature"),
            cache=not cached,
            thinking=fb_thinking,
            work_dir=book.work_dir,
            stage=fallback_stage,
        )

    draft_text = resp.text.strip()
    if draft_text == "CUT":
        write_text(seg_dir / f"{segment_id}.md", "")
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[], status="cut")
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="cut", source_words=source_words,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message="drafter returned CUT",
        )

    # Failure mode: empty text + stop_reason=max_tokens means the model
    # consumed its entire output budget on thinking/reasoning and never
    # emitted any draft. Mark as error. Don't leave a stale .md around.
    if not draft_text and resp.stop_reason == "max_tokens":
        draft_path = seg_dir / f"{segment_id}.md"
        if draft_path.exists():
            draft_path.unlink()
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[], status="error")
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="error", source_words=source_words,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message=(f"empty output with stop_reason=max_tokens after "
                     f"{resp.output_tokens} tokens — thinking likely exhausted "
                     f"the token budget. Bump max_tokens or reduce thinking."),
        )

    (seg_dir / f"{segment_id}.md").write_text(draft_text + "\n")

    draft_words = len(draft_text.split())
    hits, misses = _check_signatures(draft_text, segment.get("signatures", []))

    # Non-empty text with stop_reason=max_tokens means the model was cut
    # off mid-stream. The draft is partial — possibly missing the chapter's
    # ending and later signatures. Mark truncated (not drafted) so assemble
    # treats this as an incomplete segment, not a valid one.
    status = "truncated" if resp.stop_reason == "max_tokens" else "drafted"
    message = ""
    if status == "truncated":
        message = (f"draft truncated at {draft_words} words "
                   f"(target {segment.get('target_word_count', 0)}) due to "
                   f"max_tokens. Bump max_tokens or reduce thinking effort.")
    _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                  source_words=source_words, draft_words=draft_words,
                  signature_hits=hits, signature_misses=misses, status=status)

    # Refresh the cumulative motif ledger so the next segment's drafter sees
    # up-to-date running state.
    rebuild_ledger(book, plan)

    return DraftResult(
        segment_id=segment_id, title=segment.get("title", ""),
        status=status, source_words=source_words,
        target_words=segment.get("target_word_count", 0),
        draft_words=draft_words, signature_hits=hits,
        signature_misses=misses, message=message,
    )


def _check_signatures(draft: str, signatures: list[dict]) -> tuple[int, list[dict]]:
    """Fuzzy-match check respecting signature priority.

    Uses whitespace + punctuation normalization and rapidfuzz partial_ratio.
    A signature marked `optional` that is genuinely absent from the draft
    counts as an intentional drop, NOT a miss, if the draft ends with a
    `<!-- DROPPED-OPTIONAL: ... -->` marker. Verbatim and recognizable
    tiers track as hits/misses as before.

    Returns (hits, misses). Each miss carries {hint, score, ambiguous,
    priority}.
    """
    if not signatures:
        return 0, []
    # Collect intentional drops from the draft's marker, if any.
    import re as _re
    dropped_marker = _re.search(r"<!--\s*DROPPED-OPTIONAL\s*:\s*(.+?)\s*-->",
                                draft, flags=_re.DOTALL)
    dropped_hints: list[str] = []
    if dropped_marker:
        dropped_hints = [s.strip() for s in dropped_marker.group(1).split(";")
                         if s.strip()]

    def _is_intentional_drop(hint: str) -> bool:
        needle = hint.lower()[:40]
        return any(needle in d.lower() for d in dropped_hints)

    hits = 0
    misses: list[dict] = []
    for sig in signatures:
        hint = sig.get("passage_hint", "").strip()
        if not hint:
            continue
        priority = sig.get("priority") or "recognizable"
        r = fuzzy_contains(hint, draft, threshold=85, prefix_words=8)
        if r.present:
            hits += 1
        elif priority == "optional" and _is_intentional_drop(hint):
            # Intentional budget-driven drop; not a miss.
            hits += 1
        else:
            misses.append({
                "hint": hint[:120],
                "score": r.score,
                "ambiguous": r.ambiguous,
                "priority": priority,
            })
    return hits, misses


def _write_checks(path: Path, segment: dict, *, source_words: int,
                  draft_words: int, signature_hits: int,
                  signature_misses: list[dict] | list[str], status: str) -> None:
    target = segment.get("target_word_count", 0)
    delta = (draft_words - target) / target if target else None
    write_json(path, {
        "segment_id": segment["id"],
        "title": segment.get("title", ""),
        "status": status,
        "source_words": source_words,
        "target_words": target,
        "draft_words": draft_words,
        "word_count_delta_pct": round(delta * 100, 1) if delta is not None else None,
        "signatures_total": len(segment.get("signatures", [])),
        "signatures_matched": signature_hits,
        "signatures_missed": signature_misses,
    })


def draft_all(book: Book, plan: dict) -> list[DraftResult]:
    return [draft_segment(book, plan, s["id"]) for s in plan["segments"]]
