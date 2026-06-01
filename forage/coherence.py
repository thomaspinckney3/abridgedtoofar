"""Coherence critic stage: per-adjacent-chapter-pair structural damage check.

For each pair of adjacent drafted chapters in the final reading sequence
(Ch N, Ch N+1), sends source and draft for both to Sonnet with a strict
structural gate. Flags only
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
from collections import Counter
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .coherence_filter import normalize_finding_validity
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


def _coherence_segment_ids(plan: dict) -> list[str]:
    """Return segment ids in the same sequence the assembled abridgment reads.

    Target-zero/skipped chapters are omitted because their drafts must not
    participate in adjacent-pair repair. If a chapter's kernel was relocated,
    the receiving draft carries that context and should be checked directly
    against the next included draft.
    """
    ids: list[str] = []
    for s in plan.get("segments", []):
        if s.get("diegetic_status") != "diegetic":
            continue
        if (s.get("source_word_count") or 0) < 300:
            continue
        if s.get("skipped"):
            continue
        if int(s.get("target_word_count", 0) or 0) == 0:
            continue
        ids.append(s["id"])
    return ids


def _resolve_finding_segment_id(chapter: object, sid_n: str, sid_np1: str) -> str:
    """Map a critic `chapter` field to the real segment id for a pair.

    The prompt asks for "N" or "N+1", but models sometimes return the
    visible chapter/segment number ("2", "002", "3"). Treat those as
    recoverable instead of defaulting every malformed value to N+1.
    """
    raw = str(chapter or "").strip()
    compact = raw.upper().replace(" ", "").replace("_", "").replace("+", "")
    if compact == "N":
        return sid_n
    if compact in {"N1", "NPLUS1"}:
        return sid_np1

    if raw == sid_n:
        return sid_n
    if raw == sid_np1:
        return sid_np1

    if raw.isdigit():
        try:
            number = int(raw)
            if sid_n.isdigit() and number == int(sid_n):
                return sid_n
            if sid_np1.isdigit() and number == int(sid_np1):
                return sid_np1
        except ValueError:
            pass

    return sid_np1


def run_coherence(book: Book) -> dict:
    """Walk all adjacent pairs of final drafted chapters with drafts on disk,
    run the v3 structural coherence critic on each, write a combined
    report to work/<book>/coherence_report.json.
    """
    plan = read_json(book.work_dir / "plan.json")
    final_ids = _coherence_segment_ids(plan)
    if len(final_ids) < 2:
        raise RuntimeError(
            f"need at least 2 diegetic drafts to form a pair "
            f"(found {len(final_ids)})")

    pairs = list(zip(final_ids, final_ids[1:]))
    all_findings: list[dict] = []
    per_pair: list[dict] = []
    prompt = load_prompt("critic_coherence")

    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else None

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
            cuts=cuts,
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

        # Flatten nested list responses (critic sometimes returns [[...]]).
        flat: list[dict] = []
        for f in findings:
            if isinstance(f, list):
                flat.extend(x for x in f if isinstance(x, dict))
            elif isinstance(f, dict):
                flat.append(f)
        findings = flat

        # Resolve the "chapter" field ("N" or "N+1") to an actual segment id.
        normalized_findings: list[dict] = []
        for f in findings:
            f["segment_id"] = _resolve_finding_segment_id(
                f.get("chapter"), sid_n, sid_np1)
            f["pair"] = f"{sid_n}-{sid_np1}"
            normalized_findings.append(normalize_finding_validity(f))
        findings = normalized_findings
        all_findings.extend(findings)
        valid_count = sum(1 for f in findings if f.get("valid", True))
        invalid_count = len(findings) - valid_count
        pair_row = {"pair": f"{sid_n}-{sid_np1}", "count": valid_count}
        if invalid_count:
            pair_row["invalid_count"] = invalid_count
        per_pair.append(pair_row)

    valid_findings = [f for f in all_findings if f.get("valid", True)]
    invalid_findings = [f for f in all_findings if not f.get("valid", True)]
    class_counts = Counter(f.get("class", "?") for f in valid_findings)
    seg_counts = Counter(f.get("segment_id", "?") for f in valid_findings)

    report = {
        "book_id": book.book_id,
        "pairs_checked": len(pairs),
        "findings_total": len(valid_findings),
        "findings_raw_total": len(all_findings),
        "findings_invalid": len(invalid_findings),
        "class_counts": dict(class_counts),
        "per_segment_counts": dict(seg_counts),
        "per_pair": per_pair,
        "findings": all_findings,
    }
    write_json(book.work_dir / "coherence_report.json", report)
    return report
