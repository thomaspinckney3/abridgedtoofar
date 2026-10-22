"""Paragraph-level alignment of draft ↔ source for proofreading.

For each diegetic chapter, runs one LLM call to map draft paragraphs back to
their source paragraphs. Writes work/<book>/alignments/<sid>.json.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
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


def _valid_mapping(mapping: object, source_count: int, draft_count: int) -> bool:
    if not isinstance(mapping, list):
        return False
    seen = set()
    for item in mapping:
        if not isinstance(item, dict):
            return False
        draft = item.get("draft_para")
        sources = item.get("source_paras")
        if (type(draft) is not int or not 0 <= draft < draft_count
                or draft in seen or not isinstance(sources, list)
                or any(type(i) is not int or not 0 <= i < source_count for i in sources)):
            return False
        seen.add(draft)
    return seen == set(range(draft_count))


def _alignment_current(path: Path, source: list[str], draft: list[str]) -> bool:
    try:
        cached = read_json(path)
    except (OSError, ValueError):
        return False
    return (isinstance(cached, dict)
            and cached.get("source_paragraphs") == source
            and cached.get("draft_paragraphs") == draft
            and _valid_mapping(cached.get("mapping"), len(source), len(draft)))


def align_chapter(book: Book, segment_id: str, *, generate=None) -> dict:
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
    resp = (generate or complete)(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-5-5"),
        max_tokens=prompt.config.get("max_tokens", 8000),
        cache=False,
        work_dir=book.work_dir,
        stage=f"align:{book.book_id}:{segment_id}",
    )
    if not resp.is_complete:
        raise ValueError(f"incomplete alignment response: {resp.stop_reason}")
    mapping = _parse_json_array(resp.text)
    if not isinstance(mapping, list):
        raise ValueError("alignment response must be a JSON array")

    # Normalize any nested lists (same defensive pattern we use elsewhere).
    flat: list[dict] = []
    for f in mapping:
        if isinstance(f, list):
            flat.extend(x for x in f if isinstance(x, dict))
        elif isinstance(f, dict):
            flat.append(f)
    if not _valid_mapping(flat, len(source_paras), len(draft_paras)):
        raise ValueError("alignment response does not map every draft paragraph")

    out = {
        "segment_id": segment_id,
        "source_paragraphs": source_paras,
        "draft_paragraphs": draft_paras,
        "mapping": flat,
    }
    out_dir = book.work_dir / "alignments"
    out_dir.mkdir(exist_ok=True)
    # Keep the previous review view intact until regeneration fully succeeds.
    with tempfile.NamedTemporaryFile(dir=out_dir, suffix=".tmp", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        write_json(temp_path, out)
        os.replace(temp_path, out_dir / f"{segment_id}.json")
    finally:
        temp_path.unlink(missing_ok=True)
    return out


def align_book(book: Book) -> dict:
    """Align diegetic chapters, reusing only mappings of the current inputs."""
    plan = read_json(book.work_dir / "plan.json")
    diegetic = [s["id"] for s in plan.get("segments", [])
                if s.get("diegetic_status") == "diegetic"
                and (s.get("source_word_count") or 0) >= 100]

    out_dir = book.work_dir / "alignments"
    out_dir.mkdir(exist_ok=True)

    done, skipped, errors = [], [], []
    for sid in diegetic:
        try:
            source = _split_paragraphs((book.work_dir / "chapters" / f"{sid}.md").read_text())
            draft = _split_paragraphs((book.work_dir / "segments" / f"{sid}.md").read_text())
            if _alignment_current(out_dir / f"{sid}.json", source, draft):
                skipped.append((sid, "already aligned"))
                continue
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
