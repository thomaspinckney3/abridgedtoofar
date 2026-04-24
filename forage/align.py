"""Paragraph-level alignment of draft ↔ source for proofreading.

For each diegetic chapter, runs one LLM call to map draft paragraphs back to
their source paragraphs. Writes work/<book>/alignments/<sid>.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .llm import complete
from .prompts import load_prompt

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_array(text: str) -> list:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            from json_repair import loads as repair_loads
            return repair_loads(s)
        except Exception:
            start, end = s.find("["), s.rfind("]")
            if start < 0 or end < 0:
                raise
            return json.loads(s[start:end + 1])


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; strip per-line; drop empties."""
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _numbered(paragraphs: list[str]) -> str:
    return "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs))


def align_chapter(book: Book, segment_id: str) -> dict:
    """Align one chapter's draft to its source. Returns the alignment dict and
    writes work/<book>/alignments/<sid>.json."""
    src_path = book.work_dir / "chapters" / f"{segment_id}.md"
    draft_path = book.work_dir / "segments" / f"{segment_id}.md"
    if not src_path.exists():
        raise FileNotFoundError(f"no source at {src_path}")
    if not draft_path.exists():
        raise FileNotFoundError(f"no draft at {draft_path}")

    source_paras = _split_paragraphs(src_path.read_text())
    draft_paras = _split_paragraphs(draft_path.read_text())

    prompt = load_prompt("align")
    rendered = prompt.render(
        source_paragraphs=_numbered(source_paras),
        draft_paragraphs=_numbered(draft_paras),
    )
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-4-6"),
        max_tokens=prompt.config.get("max_tokens", 8000),
        cache=False,
        work_dir=book.work_dir,
        stage=f"align:{book.book_id}:{segment_id}",
    )
    mapping = _parse_json_array(resp.text)

    # Normalize any nested lists (same defensive pattern we use elsewhere).
    flat: list[dict] = []
    for f in mapping:
        if isinstance(f, list):
            flat.extend(x for x in f if isinstance(x, dict))
        elif isinstance(f, dict):
            flat.append(f)

    out = {
        "segment_id": segment_id,
        "source_paragraphs": source_paras,
        "draft_paragraphs": draft_paras,
        "mapping": flat,
    }
    out_dir = book.work_dir / "alignments"
    out_dir.mkdir(exist_ok=True)
    write_json(out_dir / f"{segment_id}.json", out)
    return out


def align_book(book: Book) -> dict:
    """Align all diegetic chapters. Skips chapters where alignment already
    exists on disk (resumable). Returns summary dict."""
    plan = read_json(book.work_dir / "plan.json")
    diegetic = [s["id"] for s in plan.get("segments", [])
                if s.get("diegetic_status") == "diegetic"
                and (s.get("source_word_count") or 0) >= 100]

    out_dir = book.work_dir / "alignments"
    out_dir.mkdir(exist_ok=True)

    done, skipped, errors = [], [], []
    for sid in diegetic:
        draft_path = book.work_dir / "segments" / f"{sid}.md"
        if not draft_path.exists():
            skipped.append((sid, "no draft"))
            continue
        out_path = out_dir / f"{sid}.json"
        if out_path.exists():
            skipped.append((sid, "already aligned"))
            continue
        try:
            align_chapter(book, sid)
            done.append(sid)
        except Exception as e:
            errors.append((sid, f"{type(e).__name__}: {e}"))

    return {
        "book_id": book.book_id,
        "aligned": done,
        "skipped": skipped,
        "errors": errors,
    }
