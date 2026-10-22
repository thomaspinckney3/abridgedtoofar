"""Cumulative motif preservation ledger.

Walks drafted segments in plan order and counts indicative-phrase
occurrences per motif against the source total. The drafter reads the
ledger so it knows which motifs have slack and which are at risk as it
progresses through the book.

Rebuilt idempotently from disk state each time — no incremental updates,
no stale-state risk if segments are re-drafted out of order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import Book, segment_source_path
from .text_norm import count_phrases


def rebuild_ledger(book: Book, plan: dict) -> dict:
    """Walk all drafted segments in plan order; compute per-motif cumulative
    state. Writes work/<book>/motif_ledger.json and returns the ledger dict.
    """
    motifs = plan.get("motifs", [])
    seg_dir = book.work_dir / "segments"
    source_text = book.source_text

    # Count each motif's total occurrences in the full source once.
    source_total = {
        m["name"]: sum(count_phrases(p, source_text)
                       for p in m.get("indicative_phrases", []))
        for m in motifs
    }

    segments_in_plan_order = plan.get("segments", [])
    # Track occurrences in source up to each segment (cumulative), so the
    # ledger can express "of the N source occurrences you've seen so far,
    # you've preserved M." We re-count per-segment source phrases to avoid
    # relying on an earlier extraction pass.
    cumulative_draft = {m["name"]: 0 for m in motifs}
    cumulative_source_so_far = {m["name"]: 0 for m in motifs}
    segments_processed: list[str] = []

    for seg in segments_in_plan_order:
        sid = seg["id"]
        src_path = segment_source_path(book, sid)
        drf_path = seg_dir / f"{sid}.md"

        # Count source occurrences in this segment's source, if extracted
        if src_path is not None:
            seg_source = src_path.read_text()
            for m in motifs:
                cumulative_source_so_far[m["name"]] += sum(
                    count_phrases(p, seg_source)
                    for p in m.get("indicative_phrases", []))

        if not drf_path.exists():
            continue
        draft = drf_path.read_text()
        if draft.strip() == "":
            segments_processed.append(sid)
            continue
        for m in motifs:
            cumulative_draft[m["name"]] += sum(
                count_phrases(p, draft)
                for p in m.get("indicative_phrases", []))
        segments_processed.append(sid)

    ledger = {
        "segments_processed": segments_processed,
        "segments_processed_count": len(segments_processed),
        "segments_total": len(segments_in_plan_order),
        "motifs": [],
    }
    for m in motifs:
        name = m["name"]
        src_total = source_total[name]
        src_so_far = cumulative_source_so_far[name]
        drf_so_far = cumulative_draft[name]
        ledger["motifs"].append({
            "name": name,
            "source_total": src_total,
            "source_seen_so_far": src_so_far,
            "preserved_so_far": drf_so_far,
            "retention_so_far": (drf_so_far / src_so_far
                                 if src_so_far else None),
            "retention_vs_total": (drf_so_far / src_total
                                   if src_total else None),
        })

    (book.work_dir / "motif_ledger.json").write_text(
        json.dumps(ledger, indent=2) + "\n")
    return ledger


def read_ledger(book: Book) -> dict | None:
    p = book.work_dir / "motif_ledger.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())
