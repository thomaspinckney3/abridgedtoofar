"""Apply cuts.json's `skippable_chapters` directives to a book's source.

For each entry in `cuts.skippable_chapters`:
  1. If a `kernel` is provided AND `relocate_to` names a surviving chapter,
     insert the kernel at the specified position (start/end) of the target
     chapter's source file.
  2. Set `target_word_count = 0` on the skipped chapter in `plan.json`,
     so the drafter and assemble step skip it cleanly.
  3. Recompute `combined_target_word_count` for any merge-group containing
     the skipped chapter so the drafter calls land at the right size.

The original chapter source is preserved as `<id>.md.orig` for `revert_skips`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, read_json, write_json


@dataclass
class SkipApply:
    skipped: list[str]            # chapter ids whose target was zeroed
    kernels_inserted: list[dict]  # [{from, to, position, kernel_words}]
    not_found: list[str]          # chapter ids in cuts but not in plan
    backup_paths: list[str]       # source files backed up


def apply_skips(book: Book) -> SkipApply:
    """Apply skippable_chapters from work/<book>/cuts.json. Returns summary.

    Idempotent-ish: if `<id>.md.orig` already exists, the original source is
    re-used as the base before re-applying kernels. This means re-running
    after editing cuts.json yields the expected diff.
    """
    cuts_path = book.work_dir / "cuts.json"
    plan_path = book.work_dir / "plan.json"
    if not cuts_path.exists():
        raise FileNotFoundError(
            f"no cuts.json — run `forage cuts {book.book_id}` first")
    if not plan_path.exists():
        raise FileNotFoundError(
            f"no plan.json — run `forage plan {book.book_id}` first")

    cuts = read_json(cuts_path)
    plan = read_json(plan_path)
    chapters_dir = book.work_dir / "chapters"
    seg_by_id = {s["id"]: s for s in plan.get("segments", [])}

    skipped: list[str] = []
    kernels: list[dict] = []
    not_found: list[str] = []
    backup_paths: list[str] = []

    for entry in cuts.get("skippable_chapters", []) or []:
        cid = str(entry.get("chapter_id", "")).strip()
        if not cid:
            continue
        if cid not in seg_by_id:
            not_found.append(cid)
            continue

        # 1. Insert kernel into the relocate_to chapter, if any.
        kernel = (entry.get("kernel") or "").strip()
        relocate_to = str(entry.get("relocate_to", "") or "").strip()
        position = (entry.get("position") or "").strip().lower()

        if kernel and relocate_to and relocate_to in seg_by_id and position in ("start", "end"):
            target_path = chapters_dir / f"{relocate_to}.md"
            if target_path.exists():
                # Backup once (.orig) so subsequent re-runs operate on the
                # pristine source, not stacked-kernel output.
                orig_path = chapters_dir / f"{relocate_to}.md.orig"
                if not orig_path.exists():
                    orig_path.write_text(target_path.read_text())
                    backup_paths.append(str(orig_path))
                base = orig_path.read_text()
                # Pull all kernels destined for this target so they appear
                # in stable order (deterministic re-application).
                kernels_for_target = [
                    e for e in cuts.get("skippable_chapters", []) or []
                    if str(e.get("relocate_to", "") or "").strip() == relocate_to
                    and (e.get("kernel") or "").strip()
                    and (e.get("position") or "").strip().lower() in ("start", "end")
                ]
                start_kernels = [e["kernel"].strip() for e in kernels_for_target
                                 if (e.get("position") or "").lower() == "start"]
                end_kernels = [e["kernel"].strip() for e in kernels_for_target
                               if (e.get("position") or "").lower() == "end"]
                # Compose: start_kernels + base + end_kernels, separated by
                # blank lines so paragraph boundaries are preserved.
                blocks: list[str] = []
                blocks.extend(start_kernels)
                blocks.append(base.strip())
                blocks.extend(end_kernels)
                target_path.write_text("\n\n".join(blocks) + "\n")
                kernels.append({
                    "from": cid, "to": relocate_to, "position": position,
                    "kernel_words": len(kernel.split()),
                })

        # 2. Zero the skipped chapter's target_word_count.
        seg = seg_by_id[cid]
        seg["source_word_count_original"] = seg.get(
            "source_word_count_original", seg.get("source_word_count", 0))
        seg["target_word_count_original"] = seg.get(
            "target_word_count_original", seg.get("target_word_count", 0))
        seg["target_word_count"] = 0
        seg["skipped"] = True
        skipped.append(cid)

    # 3. Recompute merge_groups' combined_target_word_count.
    for g, info in (plan.get("merged_groups") or {}).items():
        members = [seg_by_id[m] for m in info.get("member_ids", []) if m in seg_by_id]
        info["combined_target_word_count"] = sum(s.get("target_word_count", 0)
                                                  for s in members)

    write_json(plan_path, plan)

    return SkipApply(
        skipped=skipped,
        kernels_inserted=kernels,
        not_found=not_found,
        backup_paths=backup_paths,
    )


def revert_skips(book: Book) -> int:
    """Restore chapters/<id>.md from chapters/<id>.md.orig backups, and
    restore plan.json target_word_count from `target_word_count_original`.
    Returns the number of chapters restored."""
    chapters_dir = book.work_dir / "chapters"
    plan_path = book.work_dir / "plan.json"
    restored = 0

    for orig in list(chapters_dir.glob("*.md.orig")):
        target = chapters_dir / orig.name[:-len(".orig")]
        target.write_text(orig.read_text())
        orig.unlink()
        restored += 1

    if plan_path.exists():
        plan = read_json(plan_path)
        for s in plan.get("segments", []):
            if "target_word_count_original" in s:
                s["target_word_count"] = s.pop("target_word_count_original")
            s.pop("source_word_count_original", None)
            s.pop("skipped", None)
        for g, info in (plan.get("merged_groups") or {}).items():
            members = [m for m in info.get("member_ids", [])
                       if any(s["id"] == m for s in plan.get("segments", []))]
            seg_by_id = {s["id"]: s for s in plan.get("segments", [])}
            info["combined_target_word_count"] = sum(
                seg_by_id[m].get("target_word_count", 0)
                for m in members if m in seg_by_id)
        write_json(plan_path, plan)

    return restored
