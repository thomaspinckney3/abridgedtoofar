"""Deterministic lean plan builder: no LLM, no prime/prepass.

Builds plan.json from chapters.json + book-level compression math alone:
  - book target from compression.plan_compression (strict 2× of full source)
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


# Merge thresholds — empirical from the prototype runs on Bleak House and
# Little Women. GPT-5 compresses well on inputs whose target is >= ~1500w;
# below that it hits a floor around 1.2× regardless of the ask. Grouping
# adjacent short chapters into a super-segment of combined target up to
# ~3000w puts the draft call back in GPT-5's effective zone (3–4× ratio).
MERGE_TARGET_FLOOR = 1500
MERGE_GROUP_CAP = 2000


def _assign_merge_groups(segments: list[dict]) -> dict[str, dict]:
    """Walk diegetic segments in plan order, group adjacent ones whose
    individual targets are below MERGE_TARGET_FLOOR into super-segments
    capped at MERGE_GROUP_CAP combined target.

    Mutates `segments` in place to add `group_id` (None or "g<NNN>") and
    returns a dict: {group_id: {member_ids, combined_target, combined_source}}.
    """
    groups: dict[str, dict] = {}
    current: list[dict] = []
    group_seq = 0

    def flush():
        nonlocal group_seq, current
        if len(current) >= 2:
            group_seq += 1
            gid = f"g{group_seq:03d}"
            for s in current:
                s["group_id"] = gid
            groups[gid] = {
                "member_ids": [s["id"] for s in current],
                "combined_target_word_count": sum(s["target_word_count"] for s in current),
                "combined_source_word_count": sum(s["source_word_count"] for s in current),
            }
        else:
            for s in current:
                s.setdefault("group_id", None)
        current = []

    for s in segments:
        s.setdefault("group_id", None)
        # Extradiegetic and already-large chapters don't participate.
        if (s.get("diegetic_status") != "diegetic"
                or s.get("target_word_count", 0) >= MERGE_TARGET_FLOOR):
            flush()
            continue

        # Candidate for merging — check whether adding it would bust the cap.
        prospective = sum(x["target_word_count"] for x in current) + s["target_word_count"]
        if current and prospective > MERGE_GROUP_CAP:
            flush()
        current.append(s)
        # If the running group's target has already crossed the floor and the
        # next candidate would push over the cap, seal now. Otherwise keep
        # accumulating small chapters.
        if sum(x["target_word_count"] for x in current) >= MERGE_GROUP_CAP:
            flush()
    flush()
    return groups


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

    # LLM chapter classifications override the heuristic. Auto-run the
    # classifier on first `plan` invocation; subsequent `plan` runs reuse
    # the cached file. One LLM call per book, one-time.
    cls_path = book.work_dir / "chapter_classifications.json"
    if not cls_path.exists():
        from .chapter_classifier import classify_chapters
        classify_chapters(book)
    classifications = read_json(cls_path)

    def _role_for_segment(c: dict) -> str:
        verdict = classifications.get(c["id"], {}).get("status")
        if verdict == "diegetic":
            return "narrative"
        if verdict in ("extradiegetic", "toc_fragment"):
            return "extradiegetic"
        # cut_for_review or no classification → heuristic fallback
        return _role_for_kind(c["kind"])

    # Apportion target by diegetic chapter share only — extradiegetic
    # chapters are cut, they shouldn't claim any of the book's target budget.
    diegetic_source_total = sum(
        chapter_words[c["id"]] for c in chapters
        if _role_for_segment(c) != "extradiegetic"
    )

    segments: list[dict] = []
    for c in chapters:
        role = _role_for_segment(c)
        src_w = chapter_words[c["id"]]
        if role == "extradiegetic" or diegetic_source_total == 0:
            target_w = 0
        else:
            raw = src_w * comp.target_words / diegetic_source_total
            # Round up to the nearest 100 for drafter ergonomics — a round
            # target reads as authoritative and gives a few words of slack
            # vs. the exact proportional math.
            target_w = int(-(-raw // 100) * 100)
        seg = {
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
            "group_id": None,  # populated by _assign_merge_groups below
        }
        cls = classifications.get(c["id"])
        if cls:
            seg["classification_status"] = cls.get("status")
            seg["classification_reason"] = cls.get("reason", "")
        segments.append(seg)

    merged_groups = _assign_merge_groups(segments)

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
        "merged_groups": merged_groups,
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
