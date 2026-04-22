"""Deterministic lean plan builder: no LLM, no prime/prepass.

Builds plan.json from chapters.json + book-level compression math alone:
  - book target from compression.plan_compression (log-scaled reading time)
  - per-chapter target apportioned by chapter source share
  - extradiegetic chapters (front-matter, toc, translator notes, epilogue
    apparatus) marked and excluded from target apportionment
"""

from __future__ import annotations

from .artifacts import Book, read_json, write_json
from .chapter_split import split_to_disk
from .compression import count_words, plan_compression

EXTRADIEGETIC_KINDS = {
    # Splitter's actual kind names
    "front",            # prefaces, etymologies, prologues, editor's notes
    "part",             # "Part One" dividers between sections
    "epilogue",         # after-story apparatus — NOT diegetic endings
    # Legacy/alt kind names (kept for defensiveness)
    "frontmatter", "toc", "translator_notes", "preface_editor",
    "afterword", "critical_afterword", "biography", "appendix",
    "bibliography", "index",
}


def _role_for_kind(kind: str) -> str:
    """Heuristic chapter-role from the splitter's structural kind.

    Lean plan has no LLM judgment, so we can only guess from surface shape.
    Everything that isn't clearly apparatus gets "narrative"; the drafter
    itself decides whether a chapter is voice-heavy vs digression-heavy.
    """
    if kind in EXTRADIEGETIC_KINDS:
        return "extradiegetic"
    return "narrative"


def build_lean_plan(book: Book) -> dict:
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        if book.source_path.suffix.lower() == ".epub":
            from .epub_reader import split_epub_to_disk
            split_epub_to_disk(book)
        else:
            split_to_disk(book)
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters", [])

    # For EPUB sources we can't read the raw bytes as text; compute source
    # word count by summing the already-split chapter files instead.
    if book.source_path.suffix.lower() == ".epub":
        source_words = sum(
            len((book.work_dir / "chapters" / f"{c['id']}.md").read_text().split())
            for c in chapters
            if (book.work_dir / "chapters" / f"{c['id']}.md").exists()
        )
    else:
        source_words = count_words(book.source_text)
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

    # Word counts per chapter (already split to disk).
    chapter_words = {}
    for c in chapters:
        p = book.work_dir / "chapters" / f"{c['id']}.md"
        chapter_words[c["id"]] = len(p.read_text().split()) if p.exists() else 0

    # Apportion target by diegetic chapter share only — extradiegetic
    # chapters are cut, they shouldn't claim any of the book's target budget.
    diegetic_source_total = sum(
        chapter_words[c["id"]] for c in chapters
        if _role_for_kind(c["kind"]) != "extradiegetic"
    )

    segments: list[dict] = []
    for c in chapters:
        role = _role_for_kind(c["kind"])
        src_w = chapter_words[c["id"]]
        if role == "extradiegetic" or diegetic_source_total == 0:
            target_w = 0
        else:
            raw = src_w * comp.target_words / diegetic_source_total
            # Round up to the nearest 100 for drafter ergonomics — a round
            # target reads as authoritative and gives a few words of slack
            # vs. the exact proportional math.
            target_w = int(-(-raw // 100) * 100)
        segments.append({
            "id": c["id"],
            "kind": c["kind"],
            "number": c.get("number"),
            "title": c.get("title", ""),
            "raw_heading": c.get("raw_heading", ""),
            "source_word_count": src_w,
            "diegetic_status": "extradiegetic" if role == "extradiegetic" else "diegetic",
            "role": role,
            "target_word_count": target_w,
            "relative_compression": 1.0,
            "signatures": [],  # no prepass — drafter identifies in-line
            "notes": "",
        })

    plan = {
        "book_id": book.book_id,
        "title": book.metadata.get("title", book.book_id),
        "author": book.metadata.get("author", "?"),
        "structural_classification": "lean",
        "modernization_level": book.metadata.get("modernization_level", "L1"),
        "cultural_depth": book.metadata.get("cultural_depth", "unknown"),
        "voice_driven_narrator": book.metadata.get("voice_driven_narrator"),
        "indirection_budget_applies": book.metadata.get("indirection_budget_applies"),
        "overall_compression_ratio": round(comp.ratio, 2),
        "plan_notes": ("Lean deterministic plan: per-chapter targets apportioned "
                       "by source-word share; extradiegetic chapters excluded. "
                       "No prepass, no signature enumeration."),
        "motifs": [],
        "segments": segments,
        "_meta": {
            "computed": {
                "source_word_count": source_words,
                "diegetic_source_word_count": diegetic_source_total,
                "target_word_count": comp.target_words,
                "target_hours": round(comp.target_hours, 2),
                "overall_compression_ratio": round(comp.ratio, 2),
            },
            "builder": "lean_plan",
        },
    }
    write_json(book.work_dir / "plan.json", plan)
    return plan
