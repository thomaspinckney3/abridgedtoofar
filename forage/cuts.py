"""Prepass: cuts inventory.

Identifies characters, subplots, and digressions that can be REMOVED
without materially changing the reader's sense of plot, theme, or
principal-character arcs. Inverse framing of the older signature-prepass
which tried to enumerate what to preserve.

For books that fit GPT-5's input context, a single LLM call produces the
inventory. For longer books, the source is split into N chunks at chapter
boundaries, each chunk is sent with the same authoritative synopsis, and
the partial inventories are merged deterministically by deduplicating
named entries (characters by name, subplots by name, digressions by
chapter_id+topic).

Writes work/<book>/cuts.json. Not auto-fed to the drafter in this round —
human review first.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .llm import complete
from .prompts import load_prompt

TOKENS_PER_WORD = 1.4
# GPT-5's context fits ~260k tokens, but format adherence degrades at
# very large inputs (it starts returning prose instead of JSON at ~250k).
# Conservative cap forces mid-size books like Uncle Tom's Cabin to chunk.
MAX_INPUT_TOKENS = 200_000
PROMPT_OVERHEAD_TOKENS = 2000  # spec + synopsis + instructions
MAX_CHUNK_WORDS = int((MAX_INPUT_TOKENS - PROMPT_OVERHEAD_TOKENS) / TOKENS_PER_WORD)
# Back-compat alias (older code may import MAX_SOURCE_WORDS).
MAX_SOURCE_WORDS = MAX_CHUNK_WORDS

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_object(text: str) -> dict:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        result = json.loads(s)
    except json.JSONDecodeError:
        try:
            from json_repair import loads as repair_loads
            result = repair_loads(s)
        except Exception:
            start, end = s.find("{"), s.rfind("}")
            if start < 0 or end < 0:
                raise
            result = json.loads(s[start:end + 1])
    # Some models wrap the JSON payload in a quoted string; unwrap once.
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            pass
    if not isinstance(result, dict):
        raise ValueError(f"expected JSON object, got {type(result).__name__}")
    return result


def _build_chapter_blocks(book: Book) -> list[tuple[str, int]]:
    """Return a list of (block_text, word_count) for each diegetic chapter,
    in plan order. Each block is the chapter's source prose with a
    `## Chapter NNN — title` header."""
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"no chapters.json — run `forage split {book.book_id}` first")
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters", [])

    cls_path = book.work_dir / "chapter_classifications.json"
    classifications = read_json(cls_path) if cls_path.exists() else {}

    blocks: list[tuple[str, int]] = []
    for c in chapters:
        status = classifications.get(c["id"], {}).get("status", "diegetic")
        if status in ("extradiegetic", "toc_fragment"):
            continue
        p = book.work_dir / "chapters" / f"{c['id']}.md"
        if not p.exists():
            continue
        text = p.read_text()
        title = c.get("title", "")
        header = (f"## Chapter {c['id']} — {title}"
                  if title else f"## Chapter {c['id']}")
        block = f"{header}\n\n{text}"
        blocks.append((block, len(text.split())))
    return blocks


def _partition_into_chunks(blocks: list[tuple[str, int]],
                            max_words: int) -> list[list[tuple[str, int]]]:
    """Partition chapter blocks into N contiguous chunks, each <= max_words.
    Falls back to a single chunk when blocks fit."""
    total = sum(w for _, w in blocks)
    if total <= max_words:
        return [blocks]
    # Balance chunk sizes: use ceil(total / max_words) chunks.
    n_chunks = max(2, math.ceil(total / max_words))
    target = total / n_chunks
    chunks: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_words = 0
    for block, w in blocks:
        # If adding this block would push well past target AND we already have
        # content, close the chunk. Still allow overshoot if target is tiny
        # relative to a single block.
        if current and current_words + w > max_words:
            chunks.append(current)
            current = []
            current_words = 0
        current.append((block, w))
        current_words += w
    if current:
        chunks.append(current)
    return chunks


def _call_cuts_prepass(book: Book, chunk_blocks: list[tuple[str, int]],
                        synopsis: str, stage: str) -> dict:
    """Issue one LLM call for a chunk of chapters; return parsed JSON object."""
    prompt = load_prompt("prepass_cuts")
    rendered = prompt.render(
        book={"title": book.metadata.get("title", book.book_id),
              "author": book.metadata.get("author", "?")},
        synopsis=synopsis,
        source="\n\n".join(b for b, _ in chunk_blocks),
    )
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-5"),
        max_tokens=prompt.config.get("max_tokens", 12000),
        cache=False,
        work_dir=book.work_dir,
        stage=stage,
    )
    data = _parse_json_object(resp.text)
    for key in ("minor_characters", "subplots", "digressions", "skippable_chapters"):
        data.setdefault(key, [])
    return data


def _merge_cuts(partials: list[dict]) -> dict:
    """Deterministically merge N partial cuts inventories:
    - minor_characters: dedup by lowercase name; keep the first-seen entry.
    - subplots: dedup by lowercase name; keep the first-seen entry.
    - digressions: dedup by (sorted chapter_ids, topic.lower()) tuple.
    - skippable_chapters: dedup by chapter_id; keep the first-seen entry.
    """
    seen_chars: set[str] = set()
    seen_subplots: set[str] = set()
    seen_digressions: set[tuple] = set()
    seen_skippable: set[str] = set()
    merged = {"minor_characters": [], "subplots": [],
              "digressions": [], "skippable_chapters": []}
    for p in partials:
        for c in p.get("minor_characters", []) or []:
            key = str(c.get("name", "")).strip().lower()
            if not key or key in seen_chars:
                continue
            seen_chars.add(key)
            merged["minor_characters"].append(c)
        for s in p.get("subplots", []) or []:
            key = str(s.get("name", "")).strip().lower()
            if not key or key in seen_subplots:
                continue
            seen_subplots.add(key)
            merged["subplots"].append(s)
        for d in p.get("digressions", []) or []:
            ch_ids = tuple(sorted(str(x) for x in (d.get("chapter_ids") or [])))
            topic = str(d.get("topic", "")).strip().lower()
            key = (ch_ids, topic)
            if not topic or key in seen_digressions:
                continue
            seen_digressions.add(key)
            merged["digressions"].append(d)
        for k in p.get("skippable_chapters", []) or []:
            cid = str(k.get("chapter_id", "")).strip()
            if not cid or cid in seen_skippable:
                continue
            seen_skippable.add(cid)
            merged["skippable_chapters"].append(k)
    return merged


def _chapter_id_aliases(value: str) -> set[str]:
    raw = str(value).strip()
    aliases = {raw}
    if raw.isdigit():
        aliases.add(str(int(raw)))
        aliases.add(raw.zfill(3))
    return {a for a in aliases if a}


def _apply_forced_keeps(book: Book, data: dict) -> dict:
    """Remove book-configured must-keep chapters from skippable_chapters.

    This is a deterministic guardrail for cases where the cut prepass marks a
    chapter skippable but downstream coverage requires it. Metadata accepts
    either strings or objects with `chapter_id`/`id` and optional `reason`.
    """
    configured = book.metadata.get("force_keep_chapters") or []
    keep_aliases: set[str] = set()
    keep_notes: list[dict] = []
    for item in configured:
        if isinstance(item, dict):
            cid = str(item.get("chapter_id") or item.get("id") or "").strip()
            reason = str(item.get("reason") or "").strip()
        else:
            cid = str(item).strip()
            reason = ""
        if not cid:
            continue
        keep_aliases.update(_chapter_id_aliases(cid))
        keep_notes.append({"chapter_id": cid, "reason": reason})

    if not keep_aliases:
        return data

    kept_skips = []
    removed_skips = []
    for entry in data.get("skippable_chapters", []) or []:
        cid = str(entry.get("chapter_id", "")).strip()
        if cid in keep_aliases:
            removed_skips.append(entry)
        else:
            kept_skips.append(entry)
    data["skippable_chapters"] = kept_skips
    data.setdefault("_meta", {})
    data["_meta"]["force_keep_chapters"] = keep_notes
    data["_meta"]["force_keep_removed_skips"] = removed_skips
    return data


def generate_cuts(book: Book) -> dict:
    """Enumerate minor characters, subplots, and digressions that can be
    cut from `book`. For books over the single-call budget, splits into
    chunks at chapter boundaries and merges partial inventories. Writes
    work/<book>/cuts.json.
    """
    blocks = _build_chapter_blocks(book)
    if not blocks:
        raise RuntimeError(f"no diegetic chapters found for {book.book_id}")

    synopsis_path = book.work_dir / "book_synopsis.md"
    synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else ""

    chunks = _partition_into_chunks(blocks, MAX_CHUNK_WORDS)
    if len(chunks) == 1:
        data = _call_cuts_prepass(book, chunks[0], synopsis,
                                   stage=f"cuts:{book.book_id}")
    else:
        partials: list[dict] = []
        for i, chunk in enumerate(chunks, 1):
            partial = _call_cuts_prepass(
                book, chunk, synopsis,
                stage=f"cuts:{book.book_id}:part{i}")
            partials.append(partial)
        data = _merge_cuts(partials)

    data = _apply_forced_keeps(book, data)

    out_path = book.work_dir / "cuts.json"
    write_json(out_path, data)
    return data
