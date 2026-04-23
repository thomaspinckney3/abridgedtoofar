"""Assembly stage: concatenate segment drafts into a single abridgment +
budget report.

Pure local operation — no LLM. Runs any time after the drafter has produced
at least some segment files. Missing, extract-failed, or cut segments are
reported and skipped in the final text.

Always writes abridgment.md when any drafted content exists, and writes
assembly_report.json with per-stage stats: segments drafted/cut/missing,
total drafted words, book target/ceiling, overage (words and %),
over_target/over_ceiling flags. Budget adherence is reported, not
enforced — downstream stages (book critic, validate) decide whether
the produced abridgment is acceptable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, write_json


@dataclass
class SegmentStatus:
    id: str
    title: str
    role: str
    diegetic_status: str
    target: int
    drafted: int | None  # None when no draft on disk
    status: str           # "drafted" | "cut" | "not_drafted" | "extract_fail"


@dataclass
class AssemblyResult:
    book_id: str
    book_target: int
    book_ceiling: int          # target * 1.2
    total_drafted: int
    segments_total: int
    segments_drafted: int
    segments_cut: int
    segments_missing: int
    over_budget: bool          # total_drafted > book_target
    over_ceiling: bool         # total_drafted > book_ceiling
    per_segment: list[SegmentStatus]


def assemble_book(book: Book, plan: dict) -> AssemblyResult:
    seg_dir = book.work_dir / "segments"

    # Extraction status tells us which segments failed source extraction.
    ext_index_path = seg_dir / "_extractions.json"
    ext_errors: dict[str, str] = {}
    if ext_index_path.exists():
        import json
        data = json.loads(ext_index_path.read_text())
        ext_errors = {sid: r.get("error")
                      for sid, r in data.items() if r.get("error")}

    parts: list[str] = []
    per_segment: list[SegmentStatus] = []
    total_drafted = 0
    drafted = cut = missing = 0

    for s in plan.get("segments", []):
        sid = s["id"]
        title = s.get("title", "")
        role = s.get("role", "")
        diegetic = s.get("diegetic_status", "")
        target = int(s.get("target_word_count", 0) or 0)

        draft_path = seg_dir / f"{sid}.md"
        checks_path = seg_dir / f"{sid}.checks.json"
        draft_words: int | None = None
        status: str

        # Consult checks.json for the drafter's recorded status. If it says
        # "error" or "truncated", trust that over the file's mere presence.
        checks_status: str | None = None
        if checks_path.exists():
            try:
                import json
                checks_status = json.loads(checks_path.read_text()).get("status")
            except Exception:
                checks_status = None

        if sid in ext_errors:
            status = "extract_fail"
            missing += 1
        elif checks_status in ("error", "truncated"):
            # Drafter failure or truncation — count as missing, not a valid draft.
            status = checks_status
            missing += 1
        elif not draft_path.exists():
            status = "not_drafted"
            missing += 1
        else:
            text = draft_path.read_text()
            if text.strip() == "":
                # Empty draft == extradiegetic cut by drafter.
                status = "cut"
                draft_words = 0
                cut += 1
            else:
                draft_words = len(text.split())
                total_drafted += draft_words
                drafted += 1
                parts.append(text.rstrip() + "\n")
                status = "drafted"

        per_segment.append(SegmentStatus(
            id=sid, title=title, role=role, diegetic_status=diegetic,
            target=target, drafted=draft_words, status=status,
        ))

    meta = plan.get("_meta", {}).get("computed", {})
    book_target = int(meta.get("target_word_count",
                               plan.get("target_word_count", 0)) or 0)
    book_ceiling = int(book_target * 1.2)
    over_ceiling = total_drafted > book_ceiling
    over_budget = total_drafted > book_target
    partial = missing > 0

    # Write abridgment.md whenever we have any drafted content. Budget
    # adherence is reported (overage_pct, over_ceiling) but does not gate
    # output — the book critic and validate stages decide whether the
    # produced abridgment is acceptable.
    abridgment_path = book.work_dir / "abridgment.md"
    budget_report_path = book.work_dir / "assembly_report.json"
    if parts:
        abridgment_path.write_text("\n".join(parts))
    overage = total_drafted - book_target
    over_ceiling_by = total_drafted - book_ceiling
    overage_pct = (overage / book_target * 100) if book_target else 0
    write_json(budget_report_path, {
        "book_id": book.book_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "book_target": book_target,
        "book_ceiling": book_ceiling,
        "total_drafted": total_drafted,
        "over_target": over_budget,
        "over_ceiling": over_ceiling,
        "partial": partial,
        "segments_total": len(plan.get("segments", [])),
        "segments_drafted": drafted,
        "segments_cut": cut,
        "segments_missing": missing,
        "overage_words": overage,
        "over_ceiling_words": over_ceiling_by,
        "overage_pct": round(overage_pct, 1),
    })
    # Remove any stale halt.json left over from the previous fail-loud
    # regime so downstream tooling doesn't read obsolete state.
    halt_path = book.work_dir / "halt.json"
    if halt_path.exists():
        halt_path.unlink()

    return AssemblyResult(
        book_id=book.book_id,
        book_target=book_target,
        book_ceiling=book_ceiling,
        total_drafted=total_drafted,
        segments_total=len(plan.get("segments", [])),
        segments_drafted=drafted,
        segments_cut=cut,
        segments_missing=missing,
        over_budget=total_drafted > book_target,
        over_ceiling=over_ceiling,
        per_segment=per_segment,
    )
