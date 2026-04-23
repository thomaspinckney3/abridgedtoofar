"""Coherence critic stage: per-adjacent-chapter-pair structural damage check.

For each pair of adjacent diegetic chapters (Ch N, Ch N+1), sends source
and draft for both to Sonnet with a strict structural gate. Flags only
cases where the draft fails one of these tests:

  - non-parseable on its own
  - dangling pronoun/demonstrative with no antecedent
  - broken logical pivot (but/yet/because with cut side)
  - missing definitional gloss
  - unattributed dialogue
  - mid-scene jump

Explicitly does NOT flag stylistic compression. Empirically ~100% precision
at ~55% recall on dense callback material. Complementary to the signature
critic (absence-hunting) and the book critic (synopsis verification).

Writes work/<book>/coherence_report.json. Zero downstream coupling —
findings are reported only, not auto-fed to regen, because even true
findings can propagate damage through budget-neutral regen's compensating
cuts. Human review is the intended consumer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .llm import complete
from .prompts import load_prompt

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_array(text: str) -> list:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        result = json.loads(s)
    except json.JSONDecodeError:
        try:
            from json_repair import loads as repair_loads
            result = repair_loads(s)
        except Exception:
            start, end = s.find("["), s.rfind("]")
            if start < 0 or end < 0:
                raise
            result = json.loads(s[start:end + 1])
    if not isinstance(result, list):
        raise ValueError(f"expected JSON array, got {type(result).__name__}")
    return result


def _pair_has_drafts(book: Book, sid_n: str, sid_np1: str) -> bool:
    return all((book.work_dir / "segments" / f"{s}.md").exists()
               and (book.work_dir / "segments" / f"{s}.md").read_text().strip()
               for s in (sid_n, sid_np1))


def run_coherence(book: Book) -> dict:
    """Walk all adjacent pairs of diegetic chapters with drafts on disk,
    run the v3 structural coherence critic on each, write a combined
    report to work/<book>/coherence_report.json.
    """
    plan = read_json(book.work_dir / "plan.json")
    # Take ids of diegetic segments in plan order.
    diegetic = [s["id"] for s in plan.get("segments", [])
                if s.get("diegetic_status") == "diegetic"
                and (s.get("source_word_count") or 0) >= 300]
    if len(diegetic) < 2:
        raise RuntimeError(
            f"need at least 2 diegetic drafts to form a pair "
            f"(found {len(diegetic)})")

    pairs = list(zip(diegetic, diegetic[1:]))
    all_findings: list[dict] = []
    per_pair: list[dict] = []
    prompt = load_prompt("critic_coherence")

    for sid_n, sid_np1 in pairs:
        if not _pair_has_drafts(book, sid_n, sid_np1):
            per_pair.append({"pair": f"{sid_n}-{sid_np1}",
                             "skipped": "draft(s) missing", "count": 0})
            continue
        src_n = (book.work_dir / "chapters" / f"{sid_n}.md").read_text()
        src_np1 = (book.work_dir / "chapters" / f"{sid_np1}.md").read_text()
        draft_n = (book.work_dir / "segments" / f"{sid_n}.md").read_text()
        draft_np1 = (book.work_dir / "segments" / f"{sid_np1}.md").read_text()

        rendered = prompt.render(
            n=sid_n, n_plus_1=sid_np1,
            src_n=src_n, draft_n=draft_n,
            src_np1=src_np1, draft_np1=draft_np1,
        )
        resp = complete(
            prompt=rendered,
            model=prompt.config.get("model", "anthropic:claude-sonnet-4-6"),
            max_tokens=prompt.config.get("max_tokens", 12000),
            cache=False,
            work_dir=book.work_dir,
            stage=f"coherence:{book.book_id}:{sid_n}-{sid_np1}",
        )
        try:
            findings = _parse_json_array(resp.text)
        except Exception as e:
            per_pair.append({"pair": f"{sid_n}-{sid_np1}",
                             "skipped": f"parse error: {e}", "count": 0})
            continue

        # Resolve the "chapter" field ("N" or "N+1") to an actual segment id.
        for f in findings:
            ch = str(f.get("chapter", "")).upper().replace("+", "")
            if ch == "N":
                f["segment_id"] = sid_n
            elif ch == "N1":
                f["segment_id"] = sid_np1
            else:
                f["segment_id"] = sid_np1  # default to later chapter
            f["pair"] = f"{sid_n}-{sid_np1}"
        all_findings.extend(findings)
        per_pair.append({"pair": f"{sid_n}-{sid_np1}", "count": len(findings)})

    from collections import Counter
    class_counts = Counter(f.get("class", "?") for f in all_findings)
    seg_counts = Counter(f.get("segment_id", "?") for f in all_findings)

    report = {
        "book_id": book.book_id,
        "pairs_checked": len(pairs),
        "findings_total": len(all_findings),
        "class_counts": dict(class_counts),
        "per_segment_counts": dict(seg_counts),
        "per_pair": per_pair,
        "findings": all_findings,
    }
    write_json(book.work_dir / "coherence_report.json", report)
    return report
