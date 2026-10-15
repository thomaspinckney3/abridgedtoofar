"""Replay-cache audit helpers.

This module renders current LLM requests without issuing API calls and checks
whether the replay cache contains an exact response for the request key.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .artifacts import Book, read_json, segment_source_path
from .book_critic import _read_abridgment, _split_synopsis_sentences
from .chapter_classifier import SAMPLE_WORDS
from .coherence import _coherence_segment_ids
from .cuts import (_build_chapter_blocks, _partition_into_chunks,
                   MAX_CHUNK_WORDS as CUTS_MAX_CHUNK_WORDS)
from .drafter import (_draft_fallback_model, build_draft_group_request,
                      build_draft_segment_request)
from .llm import replay_cache_root, replay_cache_path, replay_key_for_request, resolve_model_for_stage
from .prompts import load_prompt
from .source_fingerprint import compare_source_fingerprint
from .summarizer import (MAX_CHUNK_WORDS as SYNOPSIS_MAX_CHUNK_WORDS,
                         TARGET_SENTENCES, _chunk_chapters)


@dataclass
class AuditRow:
    stage: str
    request: str
    status: str
    key: str = ""
    model: str = ""
    note: str = ""
    fingerprint: str = ""


@dataclass
class StageVerdict:
    stage: str
    cache: str
    pipeline: str
    source: str
    counts: dict[str, int]
    note: str = ""


PIPELINE_STAGE_ORDER = [
    "classify",
    "summarize",
    "cuts",
    "draft",
    "coherence",
    "coherence-fix",
    "critic:book",
]


def _row_stage(row: AuditRow) -> str:
    if row.stage.startswith("critic:book"):
        return "critic:book"
    if row.stage.startswith("draft:") or row.stage.startswith("draft_"):
        return "draft"
    if row.stage.startswith("regen:") or row.stage.startswith("regen_"):
        return "draft"
    if row.stage.startswith("coherence-fix"):
        return "coherence-fix"
    return row.stage.split(":", 1)[0]


def _stage_cache_verdict(rows: list[AuditRow]) -> str:
    if not rows:
        return "missing"
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    llm_rows = [row for row in rows if row.status != "no-call"]
    if not llm_rows:
        return "no-call"
    if any(row.status == "miss" for row in llm_rows):
        return "miss"
    if any(row.status == "blocked" for row in llm_rows):
        return "blocked"
    if any(row.status == "unsupported" for row in llm_rows):
        return "unsupported"
    if all(row.status == "hit" for row in llm_rows):
        return "hit"
    return "mixed"


def _stage_source_verdict(rows: list[AuditRow]) -> str:
    statuses = [row.fingerprint for row in rows if row.status == "hit" and row.fingerprint]
    if not statuses:
        return "n/a"
    if "stale" in statuses:
        return "stale"
    if "missing" in statuses:
        return "missing"
    if all(status == "current" for status in statuses):
        return "current"
    return "mixed"


def summarize_stage_verdicts(rows: list[AuditRow]) -> list[StageVerdict]:
    grouped: dict[str, list[AuditRow]] = {}
    for row in rows:
        grouped.setdefault(_row_stage(row), []).append(row)

    ordered_stages = [s for s in PIPELINE_STAGE_ORDER if s in grouped]
    ordered_stages.extend(sorted(s for s in grouped if s not in ordered_stages))

    verdicts: list[StageVerdict] = []
    upstream_issue: tuple[str, str] | None = None
    for stage in ordered_stages:
        stage_rows = grouped[stage]
        counts: dict[str, int] = {}
        for row in stage_rows:
            counts[row.status] = counts.get(row.status, 0) + 1

        cache = _stage_cache_verdict(stage_rows)
        source = _stage_source_verdict(stage_rows)
        pipeline = cache
        notes: list[str] = []
        if upstream_issue and cache in ("hit", "no-call", "mixed"):
            pipeline = "stale-risk"
            notes.append(f"upstream {upstream_issue[0]} is {upstream_issue[1]}")
        elif upstream_issue and cache == "miss":
            notes.append(f"also downstream of upstream {upstream_issue[0]} {upstream_issue[1]}")
        elif upstream_issue and cache == "blocked":
            notes.append(f"also downstream of upstream {upstream_issue[0]} {upstream_issue[1]}")

        if cache in ("hit", "mixed") and source == "stale" and pipeline == cache:
            pipeline = "source-stale"
        elif cache in ("hit", "mixed") and source == "missing" and pipeline == cache:
            pipeline = "source-untracked"
        if source == "stale":
            notes.append("cached response was produced under a different source fingerprint")
        elif source == "missing":
            notes.append("cached response has no source fingerprint metadata")

        if upstream_issue is None and cache in ("miss", "blocked"):
            upstream_issue = (stage, cache)

        verdicts.append(StageVerdict(
            stage=stage,
            cache=cache,
            pipeline=pipeline,
            source=source,
            counts=counts,
            note="; ".join(notes),
        ))
    return verdicts


def _cache_data_for_key(key: str) -> Optional[dict]:
    path = replay_cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _cache_text_for_key(key: str) -> Optional[str]:
    response = _cache_response_for_key(key)
    return (response.get("text") or "") if response else None


def _cache_response_for_key(key: str) -> Optional[dict]:
    data = _cache_data_for_key(key)
    if not data:
        return None
    response = data.get("response")
    return response if isinstance(response, dict) else None


def _row_for_request(
    *,
    stage: str,
    request: str,
    prompt: str,
    model: str,
    system: str | None = None,
    max_tokens: int,
    temperature: float | None = None,
    cached_prompt: str | None = None,
    tools: list | None = None,
    thinking: str | None = None,
) -> AuditRow:
    resolved, override = resolve_model_for_stage(model, stage)
    key = replay_key_for_request(
        resolved, system, cached_prompt, prompt, max_tokens, temperature,
        tools=tools, thinking=thinking,
    )
    status = "hit" if replay_cache_path(key).exists() else "miss"
    notes = [f"model overridden by {override}"] if override else []
    fingerprint = ""
    if status == "hit":
        data = _cache_data_for_key(key)
        comparison = compare_source_fingerprint(
            stage, data.get("source_fingerprint") if data else None)
        fingerprint = comparison["status"]
        if fingerprint == "stale":
            reason = comparison.get("reason", "source fingerprint changed")
            notes.append(f"source fingerprint stale: {reason}")
        elif fingerprint == "missing":
            notes.append("source fingerprint missing")
    return AuditRow(stage=stage, request=request, status=status,
                    key=key, model=resolved, note="; ".join(notes),
                    fingerprint=fingerprint)


def _classification_rows(book: Book) -> list[AuditRow]:
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        return [AuditRow("classify", "book", "blocked",
                         note="missing chapters.json")]
    manifest = read_json(manifest_path)
    candidates = []
    for c in manifest.get("chapters", []):
        text_path = book.work_dir / "chapters" / f"{c['id']}.md"
        if text_path.exists():
            words = text_path.read_text().split()
            wc = len(words)
            sample = " ".join(words[:SAMPLE_WORDS])
            if wc > SAMPLE_WORDS:
                sample += " […]"
        else:
            sample, wc = "", 0
        candidates.append({
            "id": c["id"],
            "kind": c["kind"],
            "number": c.get("number"),
            "title": c.get("title", ""),
            "word_count": wc,
            "sample": sample,
        })
    prompt = load_prompt("classify_chapters")
    rendered = prompt.render(
        book={
            "title": book.metadata.get("title", book.book_id),
            "author": book.metadata.get("author", "?"),
            "genre": book.metadata.get("genre", "novel"),
        },
        candidates=candidates,
    )
    return [_row_for_request(
        stage=f"classify:{book.book_id}",
        request="book",
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-5-5"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 12000),
        temperature=prompt.config.get("temperature"),
    )]


def _synopsis_chapter_sources(book: Book) -> list[dict]:
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        return []
    manifest = read_json(manifest_path)
    classifications_path = book.work_dir / "chapter_classifications.json"
    classifications = (read_json(classifications_path)
                       if classifications_path.exists() else {})
    chapter_sources = []
    for c in manifest.get("chapters", []):
        status = classifications.get(c["id"], {}).get("status", "diegetic")
        if status in ("extradiegetic", "toc_fragment"):
            continue
        path = book.work_dir / "chapters" / f"{c['id']}.md"
        if not path.exists():
            continue
        text = path.read_text()
        chapter_sources.append({
            "id": c["id"],
            "text": text,
            "words": len(text.split()),
        })
    return chapter_sources


def _single_synopsis_row(book: Book, chapter_sources: list[dict], *,
                         n_sentences: int, note: str = "",
                         stage_suffix: str = "") -> tuple[AuditRow, str | None]:
    source_block = "\n\n".join(c["text"] for c in chapter_sources)
    prompt = load_prompt("summarize_synopsis")
    rendered = prompt.render(n_sentences=n_sentences, note=note,
                             source=source_block)
    stage = f"summarize:{book.book_id}"
    request = "book"
    if stage_suffix:
        stage = f"{stage}:{stage_suffix}"
        request = stage_suffix
    row = _row_for_request(
        stage=stage,
        request=request,
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-6-astra"),
        max_tokens=prompt.config.get("max_tokens", 8000),
    )
    return row, _cache_text_for_key(row.key) if row.status == "hit" else None


def _summarize_rows(book: Book) -> list[AuditRow]:
    chapter_sources = _synopsis_chapter_sources(book)
    if not chapter_sources:
        return [AuditRow("summarize", "book", "blocked",
                         note="missing chapters or no diegetic chapters")]
    total_words = sum(c["words"] for c in chapter_sources)
    n_chunks = max(1, math.ceil(total_words / SYNOPSIS_MAX_CHUNK_WORDS))
    if n_chunks == 1:
        row, _ = _single_synopsis_row(
            book, chapter_sources, n_sentences=TARGET_SENTENCES)
        return [row]

    rows: list[AuditRow] = []
    chunks = _chunk_chapters(chapter_sources, n_chunks)
    per_chunk = max(3, math.ceil(TARGET_SENTENCES / n_chunks) + 1)
    partial_texts: list[str] = []
    blocked = False
    for i, chunk in enumerate(chunks, 1):
        row, text = _single_synopsis_row(
            book, chunk, n_sentences=per_chunk,
            note=f"(part {i} of {n_chunks})",
            stage_suffix=f"part{i}",
        )
        rows.append(row)
        if text is None:
            blocked = True
        else:
            partial_texts.append(text)
    if blocked:
        rows.append(AuditRow(f"summarize:{book.book_id}:merge", "merge",
                             "blocked",
                             note="merge prompt depends on missing partial synopsis cache hit(s)"))
        return rows

    prompt = load_prompt("summarize_merge")
    rendered = prompt.render(
        partials=partial_texts,
        target_sentences=TARGET_SENTENCES,
        book={"title": book.metadata.get("title", book.book_id),
              "author": book.metadata.get("author", "?")},
    )
    rows.append(_row_for_request(
        stage=f"summarize:{book.book_id}:merge",
        request="merge",
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-6-astra"),
        max_tokens=prompt.config.get("max_tokens", 4000),
    ))
    return rows


def _cuts_rows(book: Book) -> list[AuditRow]:
    try:
        blocks = _build_chapter_blocks(book)
    except Exception as e:
        return [AuditRow("cuts", "book", "blocked",
                         note=f"{type(e).__name__}: {e}")]
    if not blocks:
        return [AuditRow("cuts", "book", "blocked",
                         note="no diegetic chapter blocks")]
    synopsis_path = book.work_dir / "book_synopsis.md"
    synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else ""
    chunks = _partition_into_chunks(blocks, CUTS_MAX_CHUNK_WORDS)
    rows = []
    prompt = load_prompt("prepass_cuts")
    for i, chunk in enumerate(chunks, 1):
        stage = f"cuts:{book.book_id}" if len(chunks) == 1 else f"cuts:{book.book_id}:part{i}"
        rendered = prompt.render(
            book={"title": book.metadata.get("title", book.book_id),
                  "author": book.metadata.get("author", "?")},
            synopsis=synopsis,
            source="\n\n".join(b for b, _ in chunk),
        )
        rows.append(_row_for_request(
            stage=stage,
            request="book" if len(chunks) == 1 else f"part{i}",
            prompt=rendered,
            model=prompt.config.get("model", "openai:gpt-6-astra"),
            max_tokens=prompt.config.get("max_tokens", 12000),
        ))
    return rows


def _append_note(row: AuditRow, note: str) -> AuditRow:
    row.note = f"{row.note}; {note}" if row.note else note
    return row


def _draft_row_for_request(request, label: str) -> AuditRow:
    row = _row_for_request(
        stage=request.stage,
        request=label,
        prompt=request.prompt,
        model=request.model,
        system=request.system,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        cached_prompt=request.cached_prompt,
        thinking=request.thinking,
    )
    _append_note(row, request.prompt_name)
    if request.cached_prompt:
        _append_note(row, "uses prompt prefix cache break")
    if request.thinking:
        _append_note(row, f"thinking={request.thinking}")
    return row


def _conditional_draft_rows(book: Book, request, label: str,
                            primary: AuditRow) -> list[AuditRow]:
    if primary.status != "hit":
        return []
    response = _cache_response_for_key(primary.key)
    if not response:
        return []
    stop_reason = response.get("stop_reason")
    text = (response.get("text") or "").strip()
    kind = "regen" if request.stage.startswith("regen:") else "draft"
    rows: list[AuditRow] = []

    if stop_reason == "content_filter" and request.active_model.startswith("openai:"):
        fallback_model = _draft_fallback_model(request.active_model)
        fallback_thinking = "max" if "opus" in fallback_model.lower() else None
        fallback_max = 128000 if fallback_thinking else request.max_tokens
        row = _row_for_request(
            stage=f"{kind}_fallback:{book.book_id}:{label}",
            request=f"{label} fallback",
            prompt=request.prompt,
            model=fallback_model,
            system=request.system,
            max_tokens=fallback_max,
            temperature=request.temperature,
            cached_prompt=request.cached_prompt,
            thinking=fallback_thinking,
        )
        _append_note(row, "conditional: primary cached response is content_filter")
        if fallback_thinking:
            _append_note(row, f"thinking={fallback_thinking}")
        rows.append(row)

    if not text and stop_reason == "max_tokens" and request.thinking == "max":
        row = _row_for_request(
            stage=f"{kind}_thinkretry:{book.book_id}:{label}",
            request=f"{label} thinking retry",
            prompt=request.prompt,
            model=request.model,
            system=request.system,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            cached_prompt=request.cached_prompt,
            thinking="medium",
        )
        _append_note(row, "conditional: primary cached response is empty max_tokens")
        _append_note(row, "thinking=medium")
        rows.append(row)

    return rows


def _draft_rows(book: Book) -> list[AuditRow]:
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        return [AuditRow("draft", "all", "blocked", note="missing plan.json")]
    plan = read_json(plan_path)
    rows: list[AuditRow] = []
    groups = plan.get("merged_groups") or {}
    seen_groups: set[str] = set()

    for segment in plan.get("segments", []):
        sid = segment["id"]
        group_id = segment.get("group_id")
        if group_id and group_id in groups:
            if group_id in seen_groups:
                continue
            seen_groups.add(group_id)
            try:
                build = build_draft_group_request(book, plan, group_id)
            except Exception as e:
                rows.append(AuditRow(f"draft:{book.book_id}:{group_id}",
                                     group_id, "blocked",
                                     note=f"{type(e).__name__}: {e}"))
                continue
            row = _draft_row_for_request(build.request, group_id)
            _append_note(row, "merged group")
            rows.append(row)
            rows.extend(_conditional_draft_rows(book, build.request, group_id, row))
            continue

        source_path = segment_source_path(book, sid)
        if source_path is None:
            rows.append(AuditRow(f"draft:{book.book_id}:{sid}", sid, "no-call",
                                 note="no chapter/source file; draft would skip_extract_fail"))
            continue
        segment_source = source_path.read_text()
        source_words = len(segment_source.split())
        if segment.get("diegetic_status") == "extradiegetic":
            rows.append(AuditRow(f"draft:{book.book_id}:{sid}", sid, "no-call",
                                 note="extradiegetic segment is cut locally"))
            continue
        if int(segment.get("target_word_count", 0) or 0) == 0:
            rows.append(AuditRow(f"draft:{book.book_id}:{sid}", sid, "no-call",
                                 note="target=0 segment is cut locally"))
            continue

        try:
            request = build_draft_segment_request(
                book, plan, sid, segment_source, source_words)
        except Exception as e:
            rows.append(AuditRow(f"draft:{book.book_id}:{sid}", sid, "blocked",
                                 note=f"{type(e).__name__}: {e}"))
            continue
        row = _draft_row_for_request(request, sid)
        rows.append(row)
        rows.extend(_conditional_draft_rows(book, request, sid, row))

    return rows


def _book_critic_rows(book: Book) -> list[AuditRow]:
    synopsis_path = book.work_dir / "book_synopsis.md"
    if not synopsis_path.exists():
        return [AuditRow("critic:book", "book", "blocked",
                         note="missing book_synopsis.md")]
    sentences = _split_synopsis_sentences(synopsis_path.read_text())
    if not sentences:
        return [AuditRow("critic:book", "book", "blocked",
                         note="no synopsis sentences parsed")]
    abridgment, is_partial = _read_abridgment(book)
    if not abridgment.strip():
        return [AuditRow("critic:book", "book", "blocked",
                         note="missing abridgment or segment content")]
    partial_note = (
        "**Note:** the abridgment is PARTIAL — some chapters may not "
        "yet be drafted. Missing material in the partial may reflect "
        "incompleteness rather than preservation failures; note this in "
        "the `note` field for any missing sentence whose content would "
        "plausibly appear in an undrafted chapter."
        if is_partial else "")
    prompt = load_prompt("critic_book")
    rendered = prompt.render(
        sentences=sentences,
        partial_note=partial_note,
        abridgment=abridgment,
    )
    return [_row_for_request(
        stage=f"critic:book:{book.book_id}",
        request="book",
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-5-5"),
        max_tokens=prompt.config.get("max_tokens", 8000),
    )]


def _coherence_rows(book: Book) -> list[AuditRow]:
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        return [AuditRow("coherence", "pairs", "blocked",
                         note="missing plan.json")]
    plan = read_json(plan_path)
    final_ids = _coherence_segment_ids(plan)
    if len(final_ids) < 2:
        return [AuditRow("coherence", "pairs", "blocked",
                         note="need at least two diegetic segments")]
    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else None
    prompt = load_prompt("critic_coherence")
    rows: list[AuditRow] = []
    for sid_n, sid_np1 in zip(final_ids, final_ids[1:]):
        src_n_path = book.work_dir / "chapters" / f"{sid_n}.md"
        src_np1_path = book.work_dir / "chapters" / f"{sid_np1}.md"
        draft_n_path = book.work_dir / "segments" / f"{sid_n}.md"
        draft_np1_path = book.work_dir / "segments" / f"{sid_np1}.md"
        pair = f"{sid_n}-{sid_np1}"
        if not all(p.exists() and p.read_text().strip()
                   for p in (src_n_path, src_np1_path,
                             draft_n_path, draft_np1_path)):
            rows.append(AuditRow(f"coherence:{book.book_id}:{pair}",
                                 pair, "blocked",
                                 note="source or draft missing"))
            continue
        rendered = prompt.render(
            n=sid_n, n_plus_1=sid_np1,
            src_n=src_n_path.read_text(),
            draft_n=draft_n_path.read_text(),
            src_np1=src_np1_path.read_text(),
            draft_np1=draft_np1_path.read_text(),
            cuts=cuts,
        )
        rows.append(_row_for_request(
            stage=f"coherence:{book.book_id}:{pair}",
            request=pair,
            prompt=rendered,
            model=prompt.config.get("model", "anthropic:claude-sonnet-5-5"),
            max_tokens=prompt.config.get("max_tokens", 12000),
        ))
    return rows


def audit_replay_cache_files() -> dict:
    """Integrity check for existing replay-cache files."""
    root = replay_cache_root()
    result = {
        "total": 0,
        "valid": 0,
        "fingerprinted": 0,
        "unfingerprinted": 0,
        "stale_fingerprint": 0,
        "invalid": [],
    }
    if not root.exists():
        return result
    for path in sorted(root.glob("*.json")):
        result["total"] += 1
        try:
            data = json.loads(path.read_text())
            response = data.get("response")
            if data.get("key") != path.stem:
                raise ValueError("stored key does not match filename")
            if not isinstance(response, dict):
                raise ValueError("missing response object")
            if "text" not in response or "stop_reason" not in response:
                raise ValueError("response missing required fields")
            result["valid"] += 1
            source_fingerprint = data.get("source_fingerprint")
            if isinstance(source_fingerprint, dict):
                result["fingerprinted"] += 1
                group = source_fingerprint.get("group") or "unknown"
                comparison = compare_source_fingerprint(group, source_fingerprint)
                if comparison["status"] == "stale":
                    result["stale_fingerprint"] += 1
            else:
                result["unfingerprinted"] += 1
        except Exception as e:
            result["invalid"].append({"path": str(path),
                                      "error": f"{type(e).__name__}: {e}"})
    return result


def audit_book_cache(book: Book, *, include_coherence: bool = False) -> list[AuditRow]:
    rows: list[AuditRow] = []
    rows.extend(_classification_rows(book))
    rows.extend(_summarize_rows(book))
    rows.extend(_cuts_rows(book))
    rows.extend(_draft_rows(book))
    rows.extend(_book_critic_rows(book))
    if include_coherence:
        rows.extend(_coherence_rows(book))
    rows.append(AuditRow("coherence-fix", "all", "unsupported",
                         note="coherence-fix prompt audit is not implemented yet"))
    return rows
