"""Pre-pass stage: read a book, produce the global plan."""

from __future__ import annotations

import json
import re

from .artifacts import Book, read_json, write_json, write_text
from .chapter_split import split_to_disk
from .compression import count_words, plan_compression
from .json_parse import parse_llm_json
from .llm import complete
from .prompts import load_prompt


def run_prepass(book: Book) -> dict:
    source = book.source_text
    source_words = count_words(source)
    comp = plan_compression(source_words)

    if comp.refusal is not None:
        plan = {
            "book_id": book.book_id,
            "source_word_count": source_words,
            "refusal": {
                "reason": f"input-length-incompatibility: {comp.refusal}",
                "detail": f"source has {source_words} words; limit triggered",
            },
        }
        write_json(book.work_dir / "plan.json", plan)
        return plan

    # Ensure the deterministic chapter split has run; the pre-pass annotates
    # these pre-identified chapters rather than emitting start/end hints of
    # its own.
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        split_to_disk(book)
    manifest = read_json(manifest_path)
    chapters = [
        {
            "id": c["id"],
            "kind": c["kind"],
            "number": c.get("number"),
            "title": c.get("title", ""),
            "raw_heading": c.get("raw_heading", ""),
            "word_count": _chapter_word_count(book, c["id"]),
        }
        for c in manifest.get("chapters", [])
    ]

    # Pull in primed examples if a prime pass has been run.
    prime_path = book.work_dir / "prime.json"
    primed_examples = []
    if prime_path.exists():
        primed = read_json(prime_path)
        primed_examples = primed.get("examples", [])

    prompt = load_prompt("prepass")
    cached, body = prompt.render_blocks(
        book_id=book.book_id,
        genre=book.metadata.get("genre", "unknown"),
        source_text=source,
        source_word_count=source_words,
        target_word_count=comp.target_words,
        compression_ratio=round(comp.ratio, 2),
        primed_examples=primed_examples,
        chapters=chapters,
    )

    resp = complete(
        prompt=body,
        cached_prompt=cached,
        model=prompt.config.get("model", "anthropic:claude-opus-4-7"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 16000),
        temperature=prompt.config.get("temperature"),
        work_dir=book.work_dir,
        stage="prepass",
    )

    write_text(book.work_dir / "plan.raw.md", resp.text)
    plan = _parse_plan_json(resp.text)

    # Merge the splitter's structural metadata into the LLM's annotation —
    # the LLM doesn't need to re-emit ids/titles/kinds that the splitter
    # already produced deterministically.
    plan = _merge_chapters_into_plan(plan, manifest, chapters)

    plan.setdefault("_meta", {})
    plan["_meta"]["model"] = resp.model
    plan["_meta"]["stop_reason"] = resp.stop_reason
    plan["_meta"]["computed"] = {
        "source_word_count": source_words,
        "target_word_count": comp.target_words,
        "target_hours": round(comp.target_hours, 2),
        "overall_compression_ratio": round(comp.ratio, 2),
    }
    write_json(book.work_dir / "plan.json", plan)
    return plan


def _chapter_word_count(book: Book, chapter_id: str) -> int:
    path = book.work_dir / "chapters" / f"{chapter_id}.md"
    if not path.exists():
        return 0
    return len(path.read_text().split())


def _merge_chapters_into_plan(plan: dict, manifest: dict,
                              chapters: list[dict]) -> dict:
    """Fold structural chapter metadata (id, title, kind, number,
    word_count) from the splitter into the plan's per-segment entries that
    the LLM emitted. The LLM is expected to output segments keyed by the
    same ids the splitter produced; if any ids don't line up, the plan
    falls back to chapter structure alone for the missing ones.
    """
    chapter_by_id = {c["id"]: c for c in chapters}
    llm_by_id = {s.get("id"): s for s in plan.get("segments", [])}

    merged: list[dict] = []
    for c in chapters:
        ls = llm_by_id.get(c["id"], {})
        # Normalize each signature: default priority to "recognizable" if
        # the LLM omits it, so downstream code can rely on the field.
        signatures = []
        for sig in ls.get("signatures", []):
            signatures.append({
                **sig,
                "priority": sig.get("priority") or "recognizable",
            })
        merged.append({
            "id": c["id"],
            "kind": c["kind"],
            "number": c.get("number"),
            "title": c.get("title", ""),
            "raw_heading": c.get("raw_heading", ""),
            "source_word_count": c["word_count"],
            "diegetic_status": ls.get("diegetic_status"),
            "role": ls.get("role"),
            "target_word_count": ls.get("target_word_count"),
            "relative_compression": ls.get("relative_compression"),
            "signatures": signatures,
            "notes": ls.get("notes", ""),
        })
    plan["segments"] = merged
    return plan


_parse_plan_json = parse_llm_json
