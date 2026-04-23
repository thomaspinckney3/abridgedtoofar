"""LLM chapter classifier: decides whether each candidate segment from the
splitter is diegetic (keep) or extradiegetic (cut).

Runs between `split` and `plan`. One LLM call per book (all candidates
classified in a single prompt). Output cached in
`work/<book>/chapter_classifications.json`.

The lean planner reads this file if present and uses it to override the
coarse kind-based heuristic in `_role_for_kind`; falls back to the heuristic
if the file is missing, so the pipeline still works without this stage.
"""

from __future__ import annotations

from pathlib import Path

import json
import re

from .artifacts import Book, read_json, write_json
from .chapter_split import split_to_disk
from .llm import complete
from .prompts import load_prompt

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_array(text: str) -> list:
    """Tolerant parser for a JSON array response wrapped in optional markdown
    fences. Falls back to slicing between the outermost [ and ].
    """
    stripped = text.strip()
    fence = _FENCE_RE.match(stripped)
    if fence:
        stripped = fence.group(1).strip()
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start < 0 or end < 0:
            raise
        result = json.loads(stripped[start:end + 1])
    if not isinstance(result, list):
        raise ValueError(f"expected JSON array, got {type(result).__name__}")
    return result

# Words of per-candidate prose to include in the prompt. Enough to tell a
# real chapter from a TOC fragment or editorial preface without inflating
# the prompt to book scale.
SAMPLE_WORDS = 200

# Expected classification strings — anything outside this set is coerced to
# "cut_for_review" so downstream stages never see junk values.
VALID_STATUS = {"diegetic", "extradiegetic", "toc_fragment", "cut_for_review"}


def classify_chapters(book: Book) -> dict[str, dict]:
    """Classify every chapter candidate for `book`.

    Returns `{chapter_id: {"status": ..., "reason": ...}}` and writes the
    same structure to `work/<book>/chapter_classifications.json`.
    """
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        # Respect source type: EPUB vs text both flow through split_to_disk.
        split_to_disk(book)
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters", [])
    if not chapters:
        raise RuntimeError(f"no chapters in {manifest_path}")

    candidates = []
    for c in chapters:
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
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-4-6"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 12000),
        temperature=prompt.config.get("temperature"),
        cache=False,
        work_dir=book.work_dir,
        stage=f"classify:{book.book_id}",
    )

    entries = _parse_json_array(resp.text)

    result: dict[str, dict] = {}
    for entry in entries:
        cid = entry.get("id")
        if not cid:
            continue
        status = entry.get("status", "cut_for_review")
        if status not in VALID_STATUS:
            status = "cut_for_review"
        result[cid] = {
            "status": status,
            "reason": (entry.get("reason") or "").strip(),
        }

    # Any candidate the model didn't respond about gets marked for review
    # so we don't silently accept the coarse heuristic for it.
    missing = [c["id"] for c in candidates if c["id"] not in result]
    for cid in missing:
        result[cid] = {
            "status": "cut_for_review",
            "reason": "classifier did not return a verdict",
        }

    write_json(book.work_dir / "chapter_classifications.json", result)
    return result
