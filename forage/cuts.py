"""Prepass: cuts inventory.

Identifies characters, subplots, and digressions that can be REMOVED
without materially changing the reader's sense of plot, theme, or
principal-character arcs. Inverse framing of the older signature-prepass
which tried to enumerate what to preserve.

One LLM call per book (GPT-5 when source fits context; raises for books
that don't — chunking is not yet supported for cuts because merging
cuts-inventories across chunks is non-trivial).

Writes work/<book>/cuts.json. Not auto-fed to the drafter in this round —
human review first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .llm import complete
from .prompts import load_prompt

TOKENS_PER_WORD = 1.4
MAX_INPUT_TOKENS = 260_000
PROMPT_OVERHEAD_TOKENS = 2000  # spec + synopsis + instructions
MAX_SOURCE_WORDS = int((MAX_INPUT_TOKENS - PROMPT_OVERHEAD_TOKENS) / TOKENS_PER_WORD)

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
    if not isinstance(result, dict):
        raise ValueError(f"expected JSON object, got {type(result).__name__}")
    return result


def generate_cuts(book: Book) -> dict:
    """Enumerate minor characters, subplots, and digressions that can be
    cut from `book`. Writes work/<book>/cuts.json.
    """
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"no chapters.json — run `forage split {book.book_id}` first")
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters", [])

    # Filter by classifier if present — digressions identification only
    # makes sense over diegetic content.
    cls_path = book.work_dir / "chapter_classifications.json"
    classifications = read_json(cls_path) if cls_path.exists() else {}

    blocks: list[str] = []
    total_words = 0
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
        blocks.append(f"{header}\n\n{text}")
        total_words += len(text.split())

    if not blocks:
        raise RuntimeError(f"no diegetic chapters found for {book.book_id}")

    if total_words > MAX_SOURCE_WORDS:
        raise RuntimeError(
            f"book source ({total_words}w) exceeds single-call budget "
            f"(~{MAX_SOURCE_WORDS}w). Chunked cuts inventory not yet "
            f"supported; use Opus via FORAGE_CUTS_MODEL=anthropic:... "
            f"or wait for a chunked implementation."
        )

    synopsis_path = book.work_dir / "book_synopsis.md"
    synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else ""

    prompt = load_prompt("prepass_cuts")
    rendered = prompt.render(
        book={"title": book.metadata.get("title", book.book_id),
              "author": book.metadata.get("author", "?")},
        synopsis=synopsis,
        source="\n\n".join(blocks),
    )

    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-5"),
        max_tokens=prompt.config.get("max_tokens", 12000),
        cache=False,
        work_dir=book.work_dir,
        stage=f"cuts:{book.book_id}",
    )

    data = _parse_json_object(resp.text)

    # Normalize: ensure the three expected keys exist.
    for key in ("minor_characters", "subplots", "digressions"):
        data.setdefault(key, [])

    out_path = book.work_dir / "cuts.json"
    write_json(out_path, data)
    return data
