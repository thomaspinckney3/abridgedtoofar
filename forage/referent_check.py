"""Referent-integrity check.

For each chapter, split the draft into overlapping 2-paragraph windows,
present them to the LLM in scrambled order (so the LLM can't fill in
context from sequential reading), and flag any window whose meaning
depends on material not inside it.

Three runs with different shuffles per chapter. Findings that appear in
fewer than 2 of 3 runs are dropped (noise filtering).
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from .artifacts import Book, read_json, write_json
from .llm import complete
from .prompts import load_prompt

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

WINDOW_SIZE = 2
STRIDE = 1
RUNS = 3
MAJORITY = 2


def _parse_json_array(text: str) -> list:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            from json_repair import loads as repair_loads
            return repair_loads(s)
        except Exception:
            start, end = s.find("["), s.rfind("]")
            if start < 0 or end < 0:
                raise
            return json.loads(s[start:end + 1])


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _build_windows(paragraphs: list[str]) -> list[dict]:
    """Build overlapping WINDOW_SIZE-paragraph windows (stride=STRIDE).
    Each window has an id W1/W2/... and joined text."""
    windows = []
    for i in range(0, max(1, len(paragraphs) - WINDOW_SIZE + 1), STRIDE):
        chunk = paragraphs[i:i + WINDOW_SIZE]
        if not chunk:
            continue
        windows.append({
            "id": f"W{len(windows) + 1}",
            "text": "\n\n".join(chunk),
            "start_para": i,
        })
    return windows


def check_chapter(book: Book, segment_id: str, seed_base: int = 17) -> dict:
    """Run the referent check on one chapter's draft. Returns a dict with
    `findings` (consensus) and `runs` (per-run raw findings)."""
    draft_path = book.work_dir / "segments" / f"{segment_id}.md"
    if not draft_path.exists():
        raise FileNotFoundError(f"no draft at {draft_path}")
    paragraphs = _split_paragraphs(draft_path.read_text())
    windows = _build_windows(paragraphs)
    if not windows:
        return {"segment_id": segment_id, "paragraphs": len(paragraphs),
                "windows": 0, "findings": [], "runs": []}

    prompt = load_prompt("referent_check")

    runs_raw: list[list[dict]] = []
    for run_idx in range(RUNS):
        rng = random.Random(seed_base + run_idx * 101 + hash(segment_id) % 10000)
        shuffled = list(windows)
        rng.shuffle(shuffled)
        rendered = prompt.render(windows=shuffled)
        resp = complete(
            prompt=rendered,
            model=prompt.config.get("model", "anthropic:claude-sonnet-4-6"),
            max_tokens=prompt.config.get("max_tokens", 12000),
            cache=False,
            work_dir=book.work_dir,
            stage=f"referent:{book.book_id}:{segment_id}:run{run_idx}",
        )
        try:
            findings = _parse_json_array(resp.text)
        except Exception as e:
            findings = [{"parse_error": str(e)}]
        # Flatten nested lists if any.
        flat: list[dict] = []
        for f in findings:
            if isinstance(f, list):
                flat.extend(x for x in f if isinstance(x, dict))
            elif isinstance(f, dict):
                flat.append(f)
        runs_raw.append(flat)

    # Consensus: a finding appears in majority of runs iff the same
    # (window_id, nature) pair appears >= MAJORITY times.
    counts: Counter[tuple[str, str]] = Counter()
    by_key: dict[tuple[str, str], dict] = {}
    for run_findings in runs_raw:
        seen_in_run: set[tuple[str, str]] = set()
        for f in run_findings:
            wid = str(f.get("window_id", "") or "")
            nat = str(f.get("nature", "") or "")
            key = (wid, nat)
            if key in seen_in_run:
                continue
            seen_in_run.add(key)
            counts[key] += 1
            # Keep the first instance's descriptive fields.
            by_key.setdefault(key, f)

    consensus: list[dict] = []
    for key, n in counts.items():
        if n >= MAJORITY:
            f = dict(by_key[key])
            f["agreement"] = n
            # Attach paragraph indices for navigation back to the draft.
            wid = key[0]
            for w in windows:
                if w["id"] == wid:
                    f["start_para"] = w["start_para"]
                    break
            consensus.append(f)

    consensus.sort(key=lambda f: f.get("start_para", 0))
    return {
        "segment_id": segment_id,
        "paragraphs": len(paragraphs),
        "windows": len(windows),
        "findings": consensus,
        "runs": runs_raw,
    }


def run_referent_check(book: Book) -> dict:
    """Run the referent check on every diegetic chapter. Writes
    work/<book>/referent_report.json."""
    plan = read_json(book.work_dir / "plan.json")
    diegetic = [s["id"] for s in plan.get("segments", [])
                if s.get("diegetic_status") == "diegetic"
                and (s.get("source_word_count") or 0) >= 100]

    per_chapter: list[dict] = []
    all_findings: list[dict] = []
    for sid in diegetic:
        draft_path = book.work_dir / "segments" / f"{sid}.md"
        if not draft_path.exists():
            per_chapter.append({"segment_id": sid, "skipped": "no draft"})
            continue
        result = check_chapter(book, sid)
        per_chapter.append({
            "segment_id": sid,
            "paragraphs": result["paragraphs"],
            "windows": result["windows"],
            "findings_count": len(result["findings"]),
            "findings": result["findings"],
        })
        for f in result["findings"]:
            f = dict(f)
            f["segment_id"] = sid
            all_findings.append(f)

    nature_counts = Counter(f.get("nature", "?") for f in all_findings)
    report = {
        "book_id": book.book_id,
        "chapters_checked": sum(1 for c in per_chapter if "windows" in c),
        "findings_total": len(all_findings),
        "nature_counts": dict(nature_counts),
        "per_chapter": per_chapter,
        "findings": all_findings,
    }
    write_json(book.work_dir / "referent_report.json", report)
    return report
