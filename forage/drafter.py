"""Drafter stage: read plan.json, produce segments/NNN.md for one or all segments.

Source-text extraction uses a monotone cursor across the book, so each
segment's text lives at work/<book-id>/segments/NNN.source.md. The drafter
reads that + plan.json and asks the LLM for the compressed draft.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .resources import resource_path
from .artifacts import Book, read_json, segment_source_path, write_json, write_text
from .chapter_split import split_to_disk
from .llm import LLMResponse, complete, resolve_model_for_stage
from .motif_ledger import read_ledger, rebuild_ledger
from .prompts import load_prompt
from .text_norm import fuzzy_contains


@dataclass
class DraftResult:
    segment_id: str
    title: str
    status: str  # "drafted", "cut", "truncated", "skipped_extract_fail", "error"
    source_words: int
    target_words: int
    draft_words: int
    signature_hits: int
    signature_misses: list[dict]  # each has {hint, score, ambiguous}
    message: str = ""


@dataclass
class DraftLLMRequest:
    request_id: str
    prompt_name: str
    prompt: str
    cached_prompt: str | None
    model: str
    active_model: str
    system: str | None
    max_tokens: int
    temperature: float | None
    cache: bool
    thinking: str | None
    stage: str


@dataclass
class DraftGroupBuild:
    request: DraftLLMRequest
    members: list[dict]


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


def _draft_runtime_options(prompt, default_model: str, stage: str = "draft") -> tuple[str, str | None, int]:
    active_model = resolve_model_for_stage(default_model, stage)[0]
    thinking = os.environ.get("FORAGE_DRAFT_THINKING")
    if thinking == "":
        thinking = None
    if thinking is None:
        thinking = "max" if "opus" in active_model.lower() else None
    max_out = max(prompt.config.get("max_tokens", 16000), 128000) if thinking \
              else prompt.config.get("max_tokens", 32000)
    return active_model, thinking, max_out


def _draft_fallback_model(active_model: str) -> str:
    configured = os.environ.get("FORAGE_DRAFT_FALLBACK_MODEL")
    if configured:
        return configured
    if active_model.startswith("anthropic:"):
        return "openai:gpt-6-astra"
    return "anthropic:claude-sonnet-5-5"


def _complete_draft_with_exception_fallback(
    *,
    book: Book,
    prompt: str,
    cached_prompt: str | None,
    model: str,
    active_model: str,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    cache: bool,
    thinking: str | None,
    stage: str,
    fallback_stage: str,
) -> LLMResponse:
    try:
        return complete(
            prompt=prompt,
            cached_prompt=cached_prompt,
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            cache=cache,
            thinking=thinking,
            work_dir=book.work_dir,
            stage=stage,
        )
    except Exception as e:
        import sys as _sys
        fallback_model = _draft_fallback_model(active_model)
        fb_thinking = "max" if "opus" in fallback_model.lower() else None
        fb_max = 128000 if fb_thinking else max_tokens
        print(f"[drafter] {stage}: {type(e).__name__} from {active_model}; "
              f"retrying on {fallback_model}",
              file=_sys.stderr, flush=True)
        return complete(
            prompt=prompt,
            cached_prompt=cached_prompt,
            model=fallback_model,
            system=system,
            max_tokens=fb_max,
            temperature=temperature,
            cache=cache,
            thinking=fb_thinking,
            work_dir=book.work_dir,
            stage=fallback_stage,
        )


_CHAPTER_NOTES_RE = re.compile(
    r"<!--\s*FORAGE_CHAPTER_NOTES\s*(.*?)\s*-->",
    flags=re.DOTALL,
)
_CHAPTER_NOTE_LIST_FIELDS = ("acceptable_changes", "risks", "review_focus")
_CHAPTER_NOTE_TEXT_FIELDS = ("summary",)


def _normalize_chapter_notes(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _CHAPTER_NOTE_TEXT_FIELDS:
        value = str(data.get(key) or "").strip()
        if value:
            out[key] = value[:1200]
    for key in _CHAPTER_NOTE_LIST_FIELDS:
        value = data.get(key)
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            items = []
        cleaned = [str(item).strip()[:800] for item in items if str(item).strip()]
        if cleaned:
            out[key] = cleaned[:8]
    return out


def _extract_chapter_notes(text: str) -> tuple[str, dict[str, Any]]:
    """Remove the reviewer-note sidecar marker from model output.

    The marker is intentionally an HTML comment so a malformed parser cannot
    expose it as prose in most Markdown renderers, but it still must not land
    in segments/*.md or the assembled abridgment.
    """
    notes: dict[str, Any] = {}
    parse_error = ""

    def replace(match: re.Match[str]) -> str:
        nonlocal notes, parse_error
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
            return ""
        normalized = _normalize_chapter_notes(parsed)
        if normalized:
            notes = normalized
        return ""

    cleaned = _CHAPTER_NOTES_RE.sub(replace, text).strip()
    if parse_error and not notes:
        notes = {"parse_error": parse_error[:500]}
    return cleaned, notes


def build_draft_group_request(book: Book, plan: dict, group_id: str) -> DraftGroupBuild:
    groups = plan.get("merged_groups") or {}
    group = groups[group_id]
    member_ids = group["member_ids"]
    members = [next(s for s in plan["segments"] if s["id"] == mid)
               for mid in member_ids]

    source_blocks: list[str] = []
    for i, m in enumerate(members, 1):
        src_path = book.work_dir / "chapters" / f"{m['id']}.md"
        src = src_path.read_text() if src_path.exists() else ""
        title = m.get("title") or f"Chapter {m.get('number') or i}"
        source_blocks.append(
            f"## Sub-chapter {i} — {title}\n"
            f"(id {m['id']}; source {m['source_word_count']}w; "
            f"target {m['target_word_count']}w)\n\n"
            f"{src}"
        )
    merged_source = "\n\n---\n\n".join(source_blocks)

    spec_path = resource_path("spec/ABRIDGMENT_SPEC.md")
    spec_text = spec_path.read_text() if spec_path.exists() else ""

    virtual_segment = {
        "id": group_id,
        "kind": "merged",
        "title": f"merged: {' + '.join(member_ids)}",
        "diegetic_status": "diegetic",
        "role": "narrative",
        "source_word_count": group["combined_source_word_count"],
        "target_word_count": group["combined_target_word_count"],
    }

    prompt = load_prompt("draft_lean")
    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else None
    member_id_set = set(member_ids)
    kernels = []
    if cuts:
        for entry in cuts.get("skippable_chapters", []) or []:
            tgt = (entry.get("relocate_to") or "").strip()
            kernel_text = (entry.get("kernel") or "").strip()
            if tgt in member_id_set and kernel_text:
                kernels.append({
                    "from_chapter": entry.get("chapter_id"),
                    "to_chapter": tgt,
                    "position": entry.get("position"),
                    "kernel": kernel_text,
                })
    cached, body = prompt.render_blocks(
        spec=spec_text,
        book={"title": plan.get("title", book.book_id),
              "author": plan.get("author", "?"),
              "genre": book.metadata.get("genre", "unknown")},
        segment=virtual_segment,
        ceiling=int(round(virtual_segment["target_word_count"] * 1.2)),
        segment_source=merged_source,
        critic_feedback=None,
        previous_draft=None,
        merged_members=members,
        cuts=cuts,
        kernels=kernels,
    )

    default_model = prompt.config.get("model", "openai:gpt-6-astra")
    active_model, thinking, max_out = _draft_runtime_options(prompt, default_model)
    request = DraftLLMRequest(
        request_id=group_id,
        prompt_name="draft_lean",
        prompt=body,
        cached_prompt=cached,
        model=default_model,
        active_model=active_model,
        system=prompt.system,
        max_tokens=max_out,
        temperature=prompt.config.get("temperature"),
        cache=not cached,
        thinking=thinking,
        stage=f"draft:{book.book_id}:{group_id}",
    )
    return DraftGroupBuild(request=request, members=members)


def _disk_draft_result(seg_dir: Path, segment: dict) -> DraftResult:
    """Synthesize a DraftResult by reading a segment's on-disk draft. Used
    when another member of the same merged group already did the LLM work.
    """
    path = seg_dir / f"{segment['id']}.md"
    try:
        text = path.read_text() if path.exists() else ""
        checks = read_json(seg_dir / f"{segment['id']}.checks.json")
        if not isinstance(checks, dict):
            checks = {}
    except (OSError, ValueError):
        text, checks = "", {}
    words = len(text.split())
    status = checks.get("status", "error")
    if not isinstance(status, str) or status not in {"drafted", "cut", "error", "truncated"}:
        status = "error"
    if (status == "drafted" and not words) or (status == "cut" and words):
        status = "error"
    return DraftResult(
        segment_id=segment["id"], title=segment.get("title", ""),
        status=status,
        source_words=segment.get("source_word_count", 0),
        target_words=segment.get("target_word_count", 0),
        draft_words=words, signature_hits=checks.get("signatures_matched", 0),
        signature_misses=checks.get("signatures_missed", []),
        message=f"merged group recorded status: {status}",
    )


def _response_draft_status(resp: LLMResponse, text: str) -> str:
    if resp.is_truncated:
        return "truncated"
    return "drafted" if resp.is_complete and text.strip() else "error"


def build_draft_segment_request(
    book: Book,
    plan: dict,
    segment_id: str,
    segment_source: str,
    source_words: int,
    *,
    critic_feedback: list[dict] | None = None,
    previous_draft: str | None = None,
) -> DraftLLMRequest:
    segment = next((s for s in plan["segments"] if s["id"] == segment_id), None)
    if segment is None:
        raise ValueError(f"no segment {segment_id!r} in plan")

    is_lean = plan.get("_meta", {}).get("builder") == "lean_plan"
    prompt_name = "draft_lean" if is_lean else "draft_segment"
    prompt = load_prompt(prompt_name)

    if is_lean:
        spec_path = resource_path("spec/ABRIDGMENT_SPEC.md")
        spec_text = spec_path.read_text() if spec_path.exists() else ""
        target = int(segment.get("target_word_count", 0) or 0)
        ceiling = int(round(target * 1.2)) if target else 0
        cuts_path = book.work_dir / "cuts.json"
        cuts = (read_json(cuts_path) if cuts_path.exists() else None)
        kernels = []
        if cuts:
            for entry in cuts.get("skippable_chapters", []) or []:
                tgt = (entry.get("relocate_to") or "").strip()
                kernel_text = (entry.get("kernel") or "").strip()
                if tgt == segment["id"] and kernel_text:
                    kernels.append({
                        "from_chapter": entry.get("chapter_id"),
                        "to_chapter": tgt,
                        "position": entry.get("position"),
                        "kernel": kernel_text,
                    })
        cached, rendered = prompt.render_blocks(
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
            cuts=cuts,
            kernels=kernels,
        )
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
    default_model = prompt.config.get("model", "anthropic:claude-opus-5-5")
    active_model, thinking, max_out = _draft_runtime_options(prompt, default_model, stage_label)
    return DraftLLMRequest(
        request_id=segment_id,
        prompt_name=prompt_name,
        prompt=rendered,
        cached_prompt=cached,
        model=default_model,
        active_model=active_model,
        system=prompt.system,
        max_tokens=max_out,
        temperature=prompt.config.get("temperature"),
        cache=not cached,
        thinking=thinking,
        stage=stage_label,
    )


def _draft_group(book: Book, plan: dict, group_id: str) -> None:
    """Draft all segments in a merged group with one LLM call, then split
    the output into per-member segments/<id>.md files.
    """
    import re as _re
    build = build_draft_group_request(book, plan, group_id)
    members = build.members
    request = build.request
    cached = request.cached_prompt
    body = request.prompt
    default_model = request.model
    active_model = request.active_model
    thinking = request.thinking
    max_out = request.max_tokens

    seg_dir = book.work_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    resp = _complete_draft_with_exception_fallback(
        book=book,
        prompt=body,
        cached_prompt=cached,
        model=default_model,
        active_model=active_model,
        system=request.system,
        max_tokens=max_out,
        temperature=request.temperature,
        cache=request.cache,
        thinking=thinking,
        stage=request.stage,
        fallback_stage=f"draft_fallback:{book.book_id}:{group_id}",
    )

    # Cross-provider fallback (same logic as the per-segment drafter path)
    if resp.stop_reason == "content_filter" and active_model.startswith("openai:"):
        import sys as _sys
        fallback_model = _draft_fallback_model(active_model)
        print(f"[drafter] content_filter on {active_model}; "
              f"retrying on {fallback_model}",
              file=_sys.stderr, flush=True)
        fb_thinking = "max" if "opus" in fallback_model.lower() else None
        resp = complete(
            prompt=body, cached_prompt=cached,
            model=fallback_model, system=request.system,
            max_tokens=128000 if fb_thinking else max_out,
            temperature=request.temperature,
            cache=request.cache, thinking=fb_thinking,
            work_dir=book.work_dir,
            stage=f"draft_fallback:{book.book_id}:{group_id}",
        )

    # Failure mode: empty text + stop_reason=max_tokens means thinking
    # consumed the entire output budget. Retry once with reduced thinking
    # effort so visible output gets guaranteed budget.
    if not resp.text.strip() and resp.is_truncated and thinking == "max":
        import sys as _sys
        retry_thinking = "medium"
        print(f"[drafter] {group_id}: empty output after {resp.output_tokens} "
              f"tokens with thinking=max; retrying with thinking={retry_thinking}",
              file=_sys.stderr, flush=True)
        resp = complete(
            prompt=body, cached_prompt=cached,
            model=default_model, system=request.system,
            max_tokens=max_out,
            temperature=request.temperature,
            cache=request.cache, thinking=retry_thinking,
            work_dir=book.work_dir,
            stage=f"draft_thinkretry:{book.book_id}:{group_id}",
        )

    merged_draft = resp.text.strip()
    # Preserve the raw merged output alongside per-chapter splits.
    (seg_dir / f"{group_id}.md").write_text(merged_draft + "\n")

    # Split on `## Chapter N` / `Chapter N` / `## Sub-chapter N` lines and
    # assign sections to members in document order. The LLM uses whatever
    # chapter numbering is natural for the source (Dragon Maiden's
    # "Chapter 4" for the 4th story-chapter, not the 1st group member);
    # we just want "first heading found → first member", etc.
    pieces = _re.split(
        r"(?m)^(?:##\s*)?(?:Sub-)?Chapter\s+(?:\d+|[IVXLCDM]+)\b[^\n]*$",
        merged_draft)
    section_bodies = [p.strip() for p in pieces[1:]]

    for idx, m in enumerate(members):
        body_text = section_bodies[idx] if idx < len(section_bodies) else ""
        body_text, chapter_notes = _extract_chapter_notes(body_text)
        (seg_dir / f"{m['id']}.md").write_text(body_text + "\n")
        draft_words = len(body_text.split())
        _write_checks(seg_dir / f"{m['id']}.checks.json", m,
                      source_words=m["source_word_count"],
                      draft_words=draft_words,
                      signature_hits=0, signature_misses=[],
                      status=_response_draft_status(resp, body_text),
                      chapter_notes=chapter_notes)


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

    # Group-aware initial drafting: if this segment belongs to a merged group
    # AND we're not in a regen pass, route to _draft_group so all members of
    # the group are drafted together (better compression on short adjacent
    # chapters). Regen stays per-segment for now.
    group_id = segment.get("group_id")
    groups = plan.get("merged_groups") or {}
    if group_id and group_id in groups and not critic_feedback:
        member_ids = groups[group_id]["member_ids"]
        members = [s for s in plan["segments"] if s["id"] in member_ids]
        attempted = any((seg_dir / f"{sid}.checks.json").exists()
                        or (seg_dir / f"{sid}.md").exists() for sid in member_ids)
        complete_group = all(_disk_draft_result(seg_dir, s).status in {"drafted", "cut"}
                             for s in members)
        # Retry an incomplete group only at its first member. Subsequent
        # members preserve failure instead of spending once per empty split.
        if not attempted or (segment_id == member_ids[0] and not complete_group):
            _draft_group(book, plan, group_id)
        return _disk_draft_result(seg_dir, segment)

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

    # target_word_count=0 on a narrative segment means prepare-skips marked
    # this chapter for wholesale elision (its kernel, if any, was relocated
    # into an adjacent chapter). Skip the LLM call and emit an empty draft.
    if int(segment.get("target_word_count", 0) or 0) == 0:
        write_text(seg_dir / f"{segment_id}.md", "")
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[], status="cut")
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="cut", source_words=source_words, target_words=0,
            draft_words=0, signature_hits=0, signature_misses=[],
            message="target=0 — skipped by prepare-skips (kernel relocated)",
        )

    request = build_draft_segment_request(
        book, plan, segment_id, segment_source, source_words,
        critic_feedback=critic_feedback,
        previous_draft=previous_draft,
    )
    rendered = request.prompt
    cached = request.cached_prompt
    default_model = request.model
    active_model = request.active_model
    thinking = request.thinking
    max_out = request.max_tokens
    fallback_stage = (("draft_fallback:" if not critic_feedback
                       else "regen_fallback:")
                      + f"{book.book_id}:{segment_id}")
    resp = _complete_draft_with_exception_fallback(
        book=book,
        prompt=rendered,
        cached_prompt=cached,
        model=default_model,
        active_model=active_model,
        system=request.system,
        max_tokens=max_out,
        temperature=request.temperature,
        cache=request.cache,  # if we have a cache prefix, don't double-wrap
        thinking=thinking,
        stage=request.stage,
        fallback_stage=fallback_stage,
    )

    # Cross-provider fallback on OpenAI's content_filter. Happens on
    # classical-lit triggers (Moby Dick's suicide references, etc.). Anthropic
    # moderation is less aggressive on acknowledged literary material, so
    # retry once there. Configurable via FORAGE_DRAFT_FALLBACK_MODEL.
    if resp.stop_reason == "content_filter" and active_model.startswith("openai:"):
        import sys as _sys
        fallback_model = _draft_fallback_model(active_model)
        print(f"[drafter] content_filter on {active_model}; "
              f"retrying on {fallback_model}",
              file=_sys.stderr, flush=True)
        fb_thinking = "max" if "opus" in fallback_model.lower() else None
        fb_max = 128000 if fb_thinking else max_out
        resp = complete(
            prompt=rendered,
            cached_prompt=cached,
            model=fallback_model,
            system=request.system,
            max_tokens=fb_max,
            temperature=request.temperature,
            cache=request.cache,
            thinking=fb_thinking,
            work_dir=book.work_dir,
            stage=fallback_stage,
        )

    draft_text, chapter_notes = _extract_chapter_notes(resp.text.strip())
    # Failure mode: empty text + stop_reason=max_tokens means the model
    # consumed its entire output budget on thinking/reasoning and never
    # emitted any draft. Retry once with reduced thinking effort so visible
    # output gets guaranteed budget. Only kicks in when thinking="max" was
    # used (otherwise there's nothing to dial down).
    if not draft_text and resp.is_truncated and thinking == "max":
        import sys as _sys
        retry_thinking = "medium"
        retry_stage = (f"draft_thinkretry:{book.book_id}:{segment_id}"
                       if not critic_feedback
                       else f"regen_thinkretry:{book.book_id}:{segment_id}")
        print(f"[drafter] {segment_id}: empty output after {resp.output_tokens} "
              f"tokens with thinking=max; retrying with thinking={retry_thinking}",
              file=_sys.stderr, flush=True)
        resp = complete(
            prompt=rendered,
            cached_prompt=cached,
            model=default_model,
            system=request.system,
            max_tokens=max_out,
            temperature=request.temperature,
            cache=request.cache,
            thinking=retry_thinking,
            work_dir=book.work_dir,
            stage=retry_stage,
        )
        draft_text, chapter_notes = _extract_chapter_notes(resp.text.strip())

    if draft_text == "CUT" and resp.is_complete:
        write_text(seg_dir / f"{segment_id}.md", "")
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[], status="cut",
                      chapter_notes=chapter_notes)
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status="cut", source_words=source_words,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message="drafter returned CUT",
        )

    # If still empty after the thinking-retry (or thinking wasn't max to begin
    # with), report error. Don't leave a stale .md around.
    if not draft_text:
        draft_path = seg_dir / f"{segment_id}.md"
        if draft_path.exists():
            draft_path.unlink()
        _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                      source_words=source_words, draft_words=0,
                      signature_hits=0, signature_misses=[],
                      status=_response_draft_status(resp, draft_text),
                      chapter_notes=chapter_notes)
        return DraftResult(
            segment_id=segment_id, title=segment.get("title", ""),
            status=_response_draft_status(resp, draft_text), source_words=source_words,
            target_words=segment.get("target_word_count", 0),
            draft_words=0, signature_hits=0, signature_misses=[],
            message=(f"empty output with stop_reason={resp.stop_reason} after "
                     f"{resp.output_tokens} tokens"),
        )

    (seg_dir / f"{segment_id}.md").write_text(draft_text + "\n")

    draft_words = len(draft_text.split())
    hits, misses = _check_signatures(draft_text, segment.get("signatures", []))

    # Non-empty text with stop_reason=max_tokens means the model was cut
    # off mid-stream. The draft is partial — possibly missing the chapter's
    # ending and later signatures. Mark truncated (not drafted) so assemble
    # treats this as an incomplete segment, not a valid one.
    status = _response_draft_status(resp, draft_text)
    message = ""
    if status == "truncated":
        message = (f"draft truncated at {draft_words} words "
                   f"(target {segment.get('target_word_count', 0)}) due to "
                   f"{resp.stop_reason}. Bump max_tokens or reduce thinking effort.")
    _write_checks(seg_dir / f"{segment_id}.checks.json", segment,
                  source_words=source_words, draft_words=draft_words,
                  signature_hits=hits, signature_misses=misses, status=status,
                  chapter_notes=chapter_notes)

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
                  signature_misses: list[dict] | list[str], status: str,
                  chapter_notes: dict[str, Any] | None = None) -> None:
    target = segment.get("target_word_count", 0)
    delta = (draft_words - target) / target if target else None
    data: dict[str, Any] = {
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
    }
    if chapter_notes:
        data["chapter_notes"] = chapter_notes
    write_json(path, data)


def draft_all(book: Book, plan: dict) -> list[DraftResult]:
    return [draft_segment(book, plan, s["id"]) for s in plan["segments"]]
