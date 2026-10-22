"""Rebudget: reallocate per-segment targets so the book total lands near
book_target, instead of forcing each segment to hit a local number.

Pure local operation — no LLM. Mutates plan.json in place, writing new
`target_word_count` and `relative_compression` fields per segment. Callers
then redraft segments flagged `needs_redraft`.

Allocation policy (simple, proportional):
- Segments within ±10% of their current target are left alone.
- Remaining over-budget segments shed proportionally to their overage,
  such that the post-shed book total equals book_target.
- Under-budget segments keep their observed draft_words as their new target
  (no reason to expand them just because we have slack).

If the book is already within ceiling, no changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, write_json
from .assemble import AssemblyResult


@dataclass
class SegmentReallocation:
    id: str
    title: str
    old_target: int
    new_target: int
    draft_words: int
    reason: str               # "unchanged" | "under_kept" | "shed" | "missing"
    needs_redraft: bool


@dataclass
class RebudgetResult:
    book_id: str
    book_target: int
    book_ceiling: int
    total_before: int
    total_after_target: int   # sum of new targets
    applied: bool             # True if plan.json was modified
    reason: str               # why we did or didn't reallocate
    reallocations: list[SegmentReallocation]


SMALL_OVERAGE = 0.10   # within ±10% of target is "fine"


def rebudget(book: Book, plan: dict, assembly: AssemblyResult,
             *, apply: bool = True) -> RebudgetResult:
    book_target = assembly.book_target
    book_ceiling = assembly.book_ceiling
    total = assembly.total_drafted

    # Fast exits.
    if assembly.segments_missing > 0:
        return RebudgetResult(
            book_id=book.book_id,
            book_target=book_target, book_ceiling=book_ceiling,
            total_before=total, total_after_target=total,
            applied=False,
            reason=(f"cannot rebudget: {assembly.segments_missing} segments "
                    f"missing (not drafted or extract-failed). Draft them first."),
            reallocations=[],
        )
    if not assembly.over_ceiling:
        return RebudgetResult(
            book_id=book.book_id,
            book_target=book_target, book_ceiling=book_ceiling,
            total_before=total, total_after_target=total,
            applied=False,
            reason=(f"book within ceiling ({total} ≤ {book_ceiling}); "
                    f"no reallocation needed."),
            reallocations=[],
        )

    # Bucket segments by whether they need to shed.
    #   - skip: drafted and within SMALL_OVERAGE of target
    #   - shed: drafted and over target * (1 + SMALL_OVERAGE)
    #   - under: drafted below target (keep current draft_words as target)
    skip: list[dict] = []
    shed: list[dict] = []
    under: list[dict] = []
    per_seg = {ps.id: ps for ps in assembly.per_segment}

    for s in plan.get("segments", []):
        ps = per_seg[s["id"]]
        if ps.status != "drafted":
            continue  # cut or missing; unchanged
        target = ps.target or 0
        drafted = ps.drafted or 0
        if target <= 0:
            skip.append(s)
        elif drafted > target * (1 + SMALL_OVERAGE):
            shed.append(s)
        elif drafted < target:
            under.append(s)
        else:
            skip.append(s)

    # How much to shed collectively: bring total to book_target (not ceiling,
    # for margin).
    # Budget available to non-shed segments:
    fixed_words = sum((per_seg[s["id"]].drafted or 0) for s in skip + under)
    shed_budget = book_target - fixed_words
    shed_current = sum((per_seg[s["id"]].drafted or 0) for s in shed)

    if shed_budget <= 0 or not shed:
        return RebudgetResult(
            book_id=book.book_id,
            book_target=book_target, book_ceiling=book_ceiling,
            total_before=total, total_after_target=total,
            applied=False,
            reason=("rebudget infeasible: even aggressive cuts on over-budget "
                    "segments can't bring the book under target. "
                    "Consider raising book_target or refusing."),
            reallocations=[],
        )

    # Proportional shed: each over-budget segment keeps its share of the
    # shed_budget weighted by its current draft_words.
    reallocations: list[SegmentReallocation] = []

    for s in plan.get("segments", []):
        ps = per_seg[s["id"]]
        old_target = ps.target or 0
        if ps.status != "drafted":
            reallocations.append(SegmentReallocation(
                id=s["id"], title=s.get("title", ""),
                old_target=old_target, new_target=old_target,
                draft_words=ps.drafted or 0,
                reason="missing" if ps.status != "cut" else "unchanged",
                needs_redraft=False,
            ))
            continue

        drafted = ps.drafted or 0
        if s in skip:
            reallocations.append(SegmentReallocation(
                id=s["id"], title=s.get("title", ""),
                old_target=old_target, new_target=old_target,
                draft_words=drafted, reason="unchanged", needs_redraft=False,
            ))
        elif s in under:
            # Under-budget: lock target to what was actually drafted. No redraft.
            reallocations.append(SegmentReallocation(
                id=s["id"], title=s.get("title", ""),
                old_target=old_target, new_target=drafted,
                draft_words=drafted, reason="under_kept", needs_redraft=False,
            ))
        else:
            # Shed: allocate share of shed_budget.
            share = drafted / shed_current if shed_current else 0.0
            new_target = int(round(shed_budget * share))
            reallocations.append(SegmentReallocation(
                id=s["id"], title=s.get("title", ""),
                old_target=old_target, new_target=new_target,
                draft_words=drafted, reason="shed", needs_redraft=True,
            ))

    total_after = sum(r.new_target for r in reallocations)

    if apply:
        # Update plan.json in place.
        by_id = {r.id: r for r in reallocations}
        avg_ratio = plan.get("overall_compression_ratio") or (
            plan.get("source_word_count", 0) / max(total_after, 1))
        for s in plan.get("segments", []):
            r = by_id[s["id"]]
            s["target_word_count"] = r.new_target
            # Recompute relative_compression for visibility; the drafter uses
            # target_word_count for its actual budget.
            src = int(s.get("source_word_count_est", 0) or 0)
            if src > 0 and r.new_target > 0 and avg_ratio:
                seg_ratio = src / r.new_target
                s["relative_compression"] = round(seg_ratio / avg_ratio, 2)
            if r.needs_redraft:
                s["needs_redraft"] = True
            elif "needs_redraft" in s:
                del s["needs_redraft"]
        write_json(book.work_dir / "plan.json", plan)

    return RebudgetResult(
        book_id=book.book_id,
        book_target=book_target, book_ceiling=book_ceiling,
        total_before=total, total_after_target=total_after,
        applied=apply,
        reason=(f"reallocated {len([r for r in reallocations if r.needs_redraft])} "
                f"over-budget segments; projected total={total_after} "
                f"(target={book_target})"),
        reallocations=reallocations,
    )
