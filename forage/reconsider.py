"""Re-identify signatures for a single segment without re-running the full pre-pass.

Writes the result to work/<book-id>/segments/<id>.signatures.json alongside
the existing source/draft/checks files. Does not touch plan.json; it's up to
the caller (or a future stage) to fold the new signatures back in.
"""

from __future__ import annotations

from .artifacts import Book, read_json, segment_source_path, write_json
from .json_parse import parse_llm_json
from .llm import complete
from .prompts import load_prompt


def reconsider_segment(book: Book, segment_id: str) -> dict:
    plan = read_json(book.work_dir / "plan.json")
    segment = next((s for s in plan["segments"] if s["id"] == segment_id), None)
    if segment is None:
        raise ValueError(f"no segment {segment_id!r} in plan")

    seg_dir = book.work_dir / "segments"
    source_path = segment_source_path(book, segment_id)
    if source_path is None:
        raise FileNotFoundError(f"no chapter source for {segment_id}; "
                                f"run `forage split {book.book_id}` first")
    segment_source = source_path.read_text()

    prompt = load_prompt("reconsider_segment")
    rendered = prompt.render(
        book={
            "title": plan.get("title", book.book_id),
            "author": plan.get("author", "?"),
            "genre": book.metadata.get("genre", "unknown"),
        },
        plan={
            "voice_driven_narrator": plan.get("voice_driven_narrator", "?"),
            "indirection_budget_applies": plan.get("indirection_budget_applies", "?"),
            "modernization_level": plan.get("modernization_level", "?"),
            "overall_compression_ratio": plan.get("overall_compression_ratio", "?"),
            "plan_notes": plan.get("plan_notes", ""),
        },
        segment=segment,
        segment_source=segment_source,
    )

    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-opus-4-7"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 4000),
        temperature=prompt.config.get("temperature"),
        cache=True,
        work_dir=book.work_dir,
        stage=f"reconsider:{segment_id}",
    )

    result = parse_llm_json(resp.text)
    write_json(seg_dir / f"{segment_id}.signatures.json", {
        "previous": segment.get("signatures", []),
        "new": result.get("signatures", []),
        "role_previous": segment.get("role"),
        "role_new": result.get("role"),
        "notes_previous": segment.get("notes", ""),
        "notes_new": result.get("notes", ""),
    })
    return result


