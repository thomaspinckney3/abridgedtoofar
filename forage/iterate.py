"""Iterate loop: draft → critique → (regenerate with feedback → critique) until
the critic verdict is 'pass' or the retry budget is exhausted.

Preserves a simple trail per attempt:
  work/<book>/segments/NNN.iter<k>.md
  work/<book>/segments/NNN.iter<k>.critic.json
The final pass (or the last attempt on budget exhaustion) is copied to
  work/<book>/segments/NNN.md
  work/<book>/segments/NNN.critic_signature.json
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, read_json
from .critics import run_critic, CriticResult
from .drafter import draft_segment


@dataclass
class IterationStep:
    kind: str  # "draft", "regen", "critic"
    attempt: int
    summary: str
    detail: dict


@dataclass
class IterateResult:
    segment_id: str
    final_verdict: str
    attempts: int
    exhausted: bool
    steps: list[IterationStep]


def iterate_segment(
    book: Book,
    plan: dict,
    segment_id: str,
    *,
    max_retries: int = 1,
    redraft_first: bool = False,
) -> IterateResult:
    """Run the regeneration loop on one segment.

    If a draft already exists and `redraft_first` is False, the loop starts
    with the existing draft (runs critic first). Otherwise a fresh draft is
    produced before the first critic run.
    """
    seg_dir = book.work_dir / "segments"
    draft_path = seg_dir / f"{segment_id}.md"
    steps: list[IterationStep] = []

    # Attempt 0: initial draft (either the existing one or a fresh one).
    if redraft_first or not draft_path.exists():
        d = draft_segment(book, plan, segment_id)
        _snapshot(seg_dir, segment_id, attempt=0, kind="draft")
        steps.append(IterationStep(
            kind="draft", attempt=0,
            summary=f"{d.draft_words} words ({_pct(d.draft_words, d.target_words)} vs target), status={d.status}",
            detail={"draft_words": d.draft_words, "target_words": d.target_words,
                    "source_words": d.source_words, "status": d.status},
        ))
        if d.status != "drafted":
            return IterateResult(segment_id=segment_id, final_verdict=d.status,
                                 attempts=1, exhausted=False, steps=steps)

    for attempt in range(1, max_retries + 2):
        # Skip the would-be verification critic once the regen budget is
        # exhausted — its findings are never acted on downstream, so running
        # it just wastes money and noise. Attempt 1 always runs so we get at
        # least one critic pass even with max_retries=0.
        if attempt > 1 and attempt > max_retries:
            break
        c = run_critic(book, segment_id, "signature")
        _snapshot_critic(seg_dir, segment_id, attempt=attempt)
        # Compute regen trigger from findings directly — the critic's own
        # `verdict` field has proven noisy (same findings → different verdict
        # across runs). Findings list is more stable than the verdict call.
        effective_verdict = _verdict_from_findings(c.findings)
        steps.append(IterationStep(
            kind="critic", attempt=attempt,
            summary=f"{effective_verdict} [critic said {c.verdict}]: {_tally(c.findings)}",
            detail={"verdict_claimed": c.verdict,
                    "verdict_effective": effective_verdict,
                    "findings": c.findings, "summary": c.summary},
        ))
        if effective_verdict == "pass":
            return IterateResult(segment_id=segment_id, final_verdict="pass",
                                 attempts=attempt, exhausted=False, steps=steps)
        if attempt > max_retries:
            break

        previous_draft = draft_path.read_text() if draft_path.exists() else None
        actionable = [f for f in c.findings
                      if f.get("severity") in ("high", "medium")]
        d = draft_segment(book, plan, segment_id,
                          critic_feedback=actionable,
                          previous_draft=previous_draft)
        _snapshot(seg_dir, segment_id, attempt=attempt, kind="regen")
        steps.append(IterationStep(
            kind="regen", attempt=attempt,
            summary=f"{d.draft_words} words ({_pct(d.draft_words, d.target_words)} vs target)",
            detail={"draft_words": d.draft_words, "target_words": d.target_words,
                    "source_words": d.source_words, "status": d.status,
                    "feedback_items": len(actionable),
                    "feedback_items_dropped_low": len(c.findings) - len(actionable)},
        ))
        if d.status != "drafted":
            return IterateResult(segment_id=segment_id, final_verdict=d.status,
                                 attempts=attempt, exhausted=False, steps=steps)

    return IterateResult(segment_id=segment_id, final_verdict="regenerate",
                         attempts=max_retries + 1, exhausted=True, steps=steps)


def _snapshot(seg_dir: Path, segment_id: str, *, attempt: int, kind: str) -> None:
    """Copy current draft to an iter-numbered snapshot for reconstructibility."""
    src = seg_dir / f"{segment_id}.md"
    dst = seg_dir / f"{segment_id}.iter{attempt}.md"
    if src.exists():
        shutil.copy2(src, dst)


def _snapshot_critic(seg_dir: Path, segment_id: str, *, attempt: int) -> None:
    src = seg_dir / f"{segment_id}.critic_signature.json"
    dst = seg_dir / f"{segment_id}.iter{attempt}.critic.json"
    if src.exists():
        shutil.copy2(src, dst)


def _verdict_from_findings(findings: list[dict]) -> str:
    """Compute regen trigger from findings list alone, ignoring the critic's
    self-declared verdict.

    Rules (aligned with spec's severity buckets):
      - Any high-severity finding → regenerate (high-stakes failures).
      - Three or more medium-severity findings → regenerate.
      - Otherwise → pass.
    """
    highs = sum(1 for f in findings if f.get("severity") == "high")
    mediums = sum(1 for f in findings if f.get("severity") == "medium")
    if highs >= 1 or mediums >= 3:
        return "regenerate"
    return "pass"


def _tally(findings: list[dict]) -> str:
    h = sum(1 for f in findings if f.get("severity") == "high")
    m = sum(1 for f in findings if f.get("severity") == "medium")
    l = sum(1 for f in findings if f.get("severity") == "low")
    return f"{h}h/{m}m/{l}l"


def _pct(got: int, target: int) -> str:
    if not target:
        return "—"
    return f"{(got - target) / target * 100:+.0f}%"
