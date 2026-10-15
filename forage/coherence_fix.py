"""Apply coherence findings as minimal repairs to adjacent draft pairs.

This stage reads `coherence_report.json`, optionally merges mechanical
`name_lint_report.json` findings, selects the affected pairs, and asks the LLM
to make the smallest local changes needed to fix structural continuity breaks
while preserving paragraph order and unaffected prose. It writes repaired drafts
back to `segments/NNN.md` and records an audit trail artifact at
`coherence_fix_report.json`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from .artifacts import Book, read_json, segment_source_path, write_json
from .coherence import _coherence_segment_ids
from .coherence_filter import (
    finding_dedupe_key,
    normalize_finding_validity,
)
from .json_parse import parse_llm_json
from .llm import complete, require_complete_response
from .name_lint import run_name_lint
from .prompts import load_prompt


_DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"
_DEFAULT_FALLBACK_MODEL = "openai:gpt-6-astra"
_MAX_REPAIR_WORD_DELTA = 250
_MAX_REPAIR_REL_DELTA = 0.15
_SAFE_TERMINALS = set(".!?)]}\"'”’")


def run_coherence_fixes(
    book: Book,
    *,
    all_findings: bool = True,
    pairs: list[str] | None = None,
    segment: str | None = None,
    include_name_lint: bool = False,
    name_lint_only: bool = False,
    use_adjudication: bool = False,
    max_retries: int = 1,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the coherence repair stage for selected pairs.

    Args:
        all_findings: if True (default), process all findings in the report.
            If False, only process findings in `pairs`.
        pairs: one or more pair IDs in the form "NNN-NNN". Ignored when
            all_findings=True; required when all_findings=False.
        segment: optional segment ID filter. Keeps only findings whose target
            segment is this ID or whose pair includes this ID.
        include_name_lint: merge deterministic name-lint findings into the
            repair input set.
        name_lint_only: ignore coherence_report.json findings and repair only
            deterministic name-lint findings.
        use_adjudication: read coherence_adjudication_report.json and repair
            only findings marked as repair candidates.
        max_retries: retry attempts on parse/validation errors per pair.
        dry_run: render repaired drafts without writing side effects.
    """
    if name_lint_only:
        include_name_lint = True

    if use_adjudication and not name_lint_only:
        report_path = book.work_dir / "coherence_adjudication_report.json"
        missing_hint = f"run `forage coherence-adjudicate {book.book_id}` first"
    else:
        report_path = book.work_dir / "coherence_report.json"
        missing_hint = f"run `forage coherence {book.book_id}` first"
    if not report_path.exists() and not include_name_lint:
        raise FileNotFoundError(f"no coherence report at {report_path}; {missing_hint}")

    report = read_json(report_path) if report_path.exists() and not name_lint_only else {"findings": []}
    plan = read_json(book.work_dir / "plan.json")
    segments = {s["id"]: s for s in plan.get("segments", [])}
    seg_lookup = _build_segment_lookup(plan)

    requested_pairs: list[str] = []
    if not all_findings:
        if not pairs:
            raise ValueError("selected-pairs mode requires at least one --pair")
        for raw in pairs:
            requested_pairs.append(_normalize_pair(raw, seg_lookup))

    if segment:
        segment = _normalize_segment_id(segment, seg_lookup)

    name_lint_report = None
    name_lint_findings: list[dict[str, Any]] = []
    if include_name_lint:
        name_lint_report = run_name_lint(book)
        name_lint_findings = _name_lint_as_coherence_findings(
            name_lint_report,
            plan=plan,
        )

    raw_findings = list(report.get("findings", []) or [])
    if use_adjudication and not name_lint_only:
        raw_findings = [
            f for f in raw_findings
            if isinstance(f, dict) and f.get("repair_candidate")
        ]
    raw_findings.extend(name_lint_findings)

    selected_raw = _select_findings(
        raw_findings,
        requested_pairs=requested_pairs,
        segment_filter=segment,
        seg_lookup=seg_lookup,
    )
    selected, filtered_findings = _filter_selected_findings(selected_raw)

    # Preserve explicit order: user-requested order first, then report order
    # for any additional pairs that came through without a filter.
    pair_order: list[str] = []
    for p in requested_pairs:
        if p not in pair_order:
            pair_order.append(p)
    for p in selected.keys():
        if p not in pair_order:
            pair_order.append(p)

    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else None
    prompt = load_prompt("coherence_fix_pair")

    pair_results: list[dict[str, Any]] = []
    for pair in pair_order:
        findings = selected.get(pair, [])
        if not findings:
            pair_results.append({
                "pair": pair,
                "status": "no_findings",
                "findings": 0,
                "attempts": 0,
                "changed": [],
            })
            continue

        result = _repair_pair(
            book=book,
            pair=pair,
            findings=findings,
            segments=segments,
            prompt=prompt,
            cuts=cuts,
            max_retries=max_retries,
            dry_run=dry_run,
        )
        pair_results.append(result)

    report_out = {
        "book_id": book.book_id,
        "requested_pairs": requested_pairs,
        "include_name_lint": include_name_lint,
        "name_lint_only": name_lint_only,
        "use_adjudication": use_adjudication,
        "name_lint_findings_seen": (
            name_lint_report.get("findings_total", 0)
            if name_lint_report else 0
        ),
        "adjudication_findings_seen": (
            report.get("findings_seen", len(report.get("findings", []) or []))
            if use_adjudication and not name_lint_only else 0
        ),
        "adjudication_repair_candidates": (
            report.get("repair_candidates", len(raw_findings))
            if use_adjudication and not name_lint_only else 0
        ),
        "name_lint_findings_mapped": len(name_lint_findings),
        "findings_seen": sum(len(v) for v in selected_raw.values()),
        "findings_selected": sum(len(v) for v in selected.values()),
        "findings_filtered": len(filtered_findings),
        "filtered_findings": filtered_findings,
        "pairs_processed": len(pair_results),
        "pairs_applied": sum(1 for r in pair_results if r["status"] == "applied"),
        "pairs_no_change": sum(1 for r in pair_results
                               if r["status"] == "no_change"),
        "pairs_rejected": sum(1 for r in pair_results
                              if r["status"] == "rejected"),
        "pairs_failed": sum(1 for r in pair_results
                            if r["status"] == "failed"),
        "pairs_no_findings": sum(1 for r in pair_results
                                 if r["status"] == "no_findings"),
        "pairs": pair_results,
    }
    write_json(book.work_dir / "coherence_fix_report.json", report_out)
    return report_out


def _name_lint_as_coherence_findings(
    report: dict[str, Any],
    *,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    final_ids = _coherence_segment_ids(plan)
    index = {sid: i for i, sid in enumerate(final_ids)}
    mapped: list[dict[str, Any]] = []
    for finding in report.get("findings", []) or []:
        sid = str(finding.get("segment_id") or "").strip()
        if sid not in index:
            continue
        i = index[sid]
        if i > 0:
            sid_n = final_ids[i - 1]
            sid_np1 = sid
            chapter = "N+1"
        elif i + 1 < len(final_ids):
            sid_n = sid
            sid_np1 = final_ids[i + 1]
            chapter = "N"
        else:
            continue
        alias = finding.get("alias") or finding.get("name") or "the name"
        canonical = finding.get("name") or alias
        mapped.append({
            "valid": True,
            "class": "unglossed_name",
            "chapter": chapter,
            "segment_id": sid,
            "pair": f"{sid_n}-{sid_np1}",
            "draft_passage": finding.get("draft_passage", ""),
            "name": canonical,
            "alias": alias,
            "source_has": (
                f"Deterministic name-lint found {alias!r}, a minor/cut "
                f"character name ({canonical}), without a local role or "
                "relationship gloss. If the name survives, add a compact "
                "source-supported gloss; otherwise replace it with a clear "
                "descriptor or remove the name while preserving the sentence's "
                "meaning. "
                f"Cut inventory context: {finding.get('appearances_summary', '')}"
            ).strip(),
            "gate_test_answer": finding.get("reason", ""),
            "name_lint": True,
            "name_lint_occurrence_type": finding.get("occurrence_type"),
            "name_lint_line": finding.get("line"),
        })
    return mapped


def _repair_pair(
    *,
    book: Book,
    pair: str,
    findings: list[dict],
    segments: dict[str, dict],
    prompt,
    cuts: dict | None,
    max_retries: int,
    dry_run: bool,
) -> dict[str, Any]:
    sid_n, sid_np1 = pair.split("-", 1)
    seg_dir = book.work_dir / "segments"

    segment_n = segments.get(sid_n)
    segment_np1 = segments.get(sid_np1)
    if segment_n is None or segment_np1 is None:
        return {
            "pair": pair,
            "status": "failed",
            "findings": len(findings),
            "attempts": 0,
            "error": f"pair segments not in plan: {pair}",
            "changed": [],
        }
    blocked = [s["id"] for s in (segment_n, segment_np1)
               if _segment_blocks_repair(s)]
    if blocked:
        return {
            "pair": pair,
            "status": "failed",
            "findings": len(findings),
            "attempts": 0,
            "error": ("coherence-fix refuses to edit skipped/target-zero "
                      f"segment(s): {', '.join(blocked)}; regenerate "
                      "coherence on the current assembled draft sequence"),
            "changed": [],
        }

    source_n_path = segment_source_path(book, sid_n)
    source_np1_path = segment_source_path(book, sid_np1)
    if source_n_path is None or source_np1_path is None:
        return {
            "pair": pair,
            "status": "failed",
            "findings": len(findings),
            "attempts": 0,
            "error": f"missing source path for one or both segments in {pair}",
            "changed": [],
        }

    source_n = source_n_path.read_text()
    source_np1 = source_np1_path.read_text()
    draft_n_path = seg_dir / f"{sid_n}.md"
    draft_np1_path = seg_dir / f"{sid_np1}.md"
    if not draft_n_path.exists() or not draft_np1_path.exists():
        return {
            "pair": pair,
            "status": "failed",
            "findings": len(findings),
            "attempts": 0,
            "error": f"missing draft for one or both segments in {pair}",
            "changed": [],
        }
    draft_n = draft_n_path.read_text()
    draft_np1 = draft_np1_path.read_text()
    if not draft_n.strip() or not draft_np1.strip():
        return {
            "pair": pair,
            "status": "failed",
            "findings": len(findings),
            "attempts": 0,
            "error": f"empty draft for one or both segments in {pair}",
            "changed": [],
        }

    rendered_findings = [{
        "finding_index": item.get("_finding_index"),
        "valid": item.get("valid", True),
        "class": item.get("class", ""),
        "chapter": item.get("chapter", ""),
        "draft_passage": (item.get("draft_passage") or "").strip(),
        "source_has": (item.get("source_has") or "").strip(),
        "gate_test_answer": (item.get("gate_test_answer") or "").strip(),
    } for item in findings]
    cached, body = prompt.render_blocks(
        book={
            "id": book.book_id,
        },
        pair=pair,
        sid_n=sid_n,
        sid_np1=sid_np1,
        src_n=source_n,
        draft_n=draft_n,
        src_np1=source_np1,
        draft_np1=draft_np1,
        findings=rendered_findings,
        findings_count=len(findings),
        cuts=cuts,
    )

    last_error = None
    last_attempt = 0
    parsed = None
    for attempt in range(max_retries + 1):
        resp = _complete_with_anthropic_fallback(
            prompt=body,
            cached_prompt=cached,
            model=prompt.config.get("model", _DEFAULT_MODEL),
            system=prompt.system,
            max_tokens=prompt.config.get("max_tokens", 12000),
            temperature=prompt.config.get("temperature"),
            cache=not cached,
            work_dir=book.work_dir,
            stage=f"coherence_fix:{book.book_id}:{pair}:attempt{attempt + 1}",
            fallback_stage=(f"coherence_fix_fallback:{book.book_id}:{pair}:"
                            f"attempt{attempt + 1}"),
        )
        try:
            require_complete_response(resp, "coherence repair")
            parsed = _parse_repair_response(resp.text)
            parsed_n = parsed.get("draft_n")
            parsed_np1 = parsed.get("draft_np1")
            if not isinstance(parsed_n, str) or not isinstance(parsed_np1, str):
                raise ValueError("response must include string fields draft_n and draft_np1")
            _validate_repair_output(
                pair=pair,
                sid_n=sid_n,
                sid_np1=sid_np1,
                draft_n=draft_n,
                draft_np1=draft_np1,
                repaired_n=parsed_n,
                repaired_np1=parsed_np1,
            )
            parsed = {"draft_n": parsed_n, "draft_np1": parsed_np1,
                      "edits": parsed.get("edits", [])}
            last_attempt = attempt + 1
            break
        except Exception as e:  # pragma: no cover - runtime resilience path
            last_error = str(e)
            parsed = None
            continue

    if parsed is None:
        return {
            "pair": pair,
            "status": "rejected",
            "findings": len(findings),
            "attempts": max_retries + 1,
            "error": last_error or "invalid repair response",
            "changed_segments": [],
        }

    repaired_n = parsed["draft_n"].strip()
    repaired_np1 = parsed["draft_np1"].strip()

    changed_segments: list[str] = []
    if repaired_n != draft_n.strip():
        changed_segments.append(sid_n)
    if repaired_np1 != draft_np1.strip():
        changed_segments.append(sid_np1)

    if not dry_run and changed_segments:
        _snapshot_pair(seg_dir, sid_n, pair, prefix="cohfix_pre")
        _snapshot_pair(seg_dir, sid_np1, pair, prefix="cohfix_pre")
        (seg_dir / f"{sid_n}.md").write_text(repaired_n + "\n")
        (seg_dir / f"{sid_np1}.md").write_text(repaired_np1 + "\n")
        source_n_words = len(source_n.split())
        source_np1_words = len(source_np1.split())
        _update_checks(
            seg_dir / f"{sid_n}.checks.json",
            segment=segment_n,
            source_words=source_n_words,
            draft_words=len(repaired_n.split()),
        )
        _update_checks(
            seg_dir / f"{sid_np1}.checks.json",
            segment=segment_np1,
            source_words=source_np1_words,
            draft_words=len(repaired_np1.split()),
        )
    elif not dry_run and not changed_segments:
        # Keep checks in place; the content is effectively unchanged.
        changed_segments = []

    status = "applied" if changed_segments else "no_change"

    return {
        "pair": pair,
        "status": status,
        "findings": len(findings),
        "attempts": last_attempt,
        "changed_segments": changed_segments,
        "before_words": {
            sid_n: len(draft_n.split()),
            sid_np1: len(draft_np1.split()),
        },
        "after_words": {
            sid_n: len(repaired_n.split()),
            sid_np1: len(repaired_np1.split()),
        },
        "edits": parsed.get("edits", []),
        "dry_run": dry_run,
    }


def _complete_with_anthropic_fallback(
    *,
    prompt: str,
    cached_prompt: str | None,
    model: str,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    cache: bool,
    work_dir: Path,
    stage: str,
    fallback_stage: str,
):
    try:
        return complete(
            prompt=prompt,
            cached_prompt=cached_prompt,
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            cache=cache,
            work_dir=work_dir,
            stage=stage,
        )
    except Exception as e:
        if not _is_anthropic_exception(e):
            raise
        fallback_model = os.environ.get(
            "FORAGE_COHERENCE_FIX_FALLBACK_MODEL",
            _DEFAULT_FALLBACK_MODEL,
        )
        print(
            f"[coherence-fix] Anthropic failure on {stage}: {e}; "
            f"retrying on {fallback_model}",
            file=sys.stderr,
            flush=True,
        )
        return complete(
            prompt=prompt,
            cached_prompt=cached_prompt,
            model=fallback_model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            cache=cache,
            work_dir=work_dir,
            stage=fallback_stage,
        )


def _segment_blocks_repair(segment: dict) -> bool:
    if segment.get("skipped"):
        return True
    if segment.get("diegetic_status") == "extradiegetic":
        return True
    return int(segment.get("target_word_count", 0) or 0) == 0


def _validate_repair_output(
    *,
    pair: str,
    sid_n: str,
    sid_np1: str,
    draft_n: str,
    draft_np1: str,
    repaired_n: str,
    repaired_np1: str,
) -> None:
    _validate_repaired_segment(pair, sid_n, draft_n, repaired_n)
    _validate_repaired_segment(pair, sid_np1, draft_np1, repaired_np1)


def _validate_repaired_segment(
    pair: str,
    segment_id: str,
    original: str,
    repaired: str,
) -> None:
    original_stripped = original.strip()
    repaired_stripped = repaired.strip()
    original_words = len(original_stripped.split())
    repaired_words = len(repaired_stripped.split())

    if original_words > 0 and repaired_words == 0:
        raise ValueError(
            f"{pair} repair for {segment_id} erased a non-empty draft")
    if original_words == 0 and repaired_words > 0:
        raise ValueError(
            f"{pair} repair for {segment_id} wrote into an empty draft")

    delta = abs(repaired_words - original_words)
    relative = (delta / original_words) if original_words else 0.0
    if delta > _MAX_REPAIR_WORD_DELTA and relative > _MAX_REPAIR_REL_DELTA:
        raise ValueError(
            f"{pair} repair for {segment_id} changed word count from "
            f"{original_words} to {repaired_words}; coherence-fix only "
            "allows local edits")

    if (_has_safe_terminal(original_stripped)
            and not _has_safe_terminal(repaired_stripped)):
        raise ValueError(
            f"{pair} repair for {segment_id} appears truncated at the end")


def _has_safe_terminal(text: str) -> bool:
    return bool(text) and text[-1] in _SAFE_TERMINALS


def _is_anthropic_exception(e: Exception) -> bool:
    try:
        import anthropic
    except ImportError:
        return e.__class__.__module__.startswith("anthropic")
    return isinstance(e, anthropic.APIError)


def _select_findings(
    findings: list[dict],
    *,
    requested_pairs: list[str],
    segment_filter: str | None,
    seg_lookup: dict[str, str],
) -> dict[str, list[dict]]:
    selected: dict[str, list[dict]] = defaultdict(list)
    requested_set = set(requested_pairs) if requested_pairs else None

    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        raw_pair = (f.get("pair") or "").strip()
        if not raw_pair:
            continue
        try:
            norm_pair = _normalize_pair(raw_pair, seg_lookup)
        except ValueError:
            continue

        if requested_set and norm_pair not in requested_set:
            continue
        segment_id = str(f.get("segment_id") or "").strip()
        if segment_filter and segment_filter:
            seg_in_pair = segment_filter in norm_pair.split("-", 1) if "-" in norm_pair else False
            if segment_filter != segment_id and not seg_in_pair:
                continue

        enriched = dict(f)
        enriched["_finding_index"] = idx
        selected[norm_pair].append(enriched)

    return selected


def _filter_selected_findings(
    selected: dict[str, list[dict]],
) -> tuple[dict[str, list[dict]], list[dict[str, Any]]]:
    filtered_selected: dict[str, list[dict]] = defaultdict(list)
    filtered_findings: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}

    for pair, findings in selected.items():
        for finding in findings:
            normalized = normalize_finding_validity(finding)
            if not normalized.get("valid", True):
                filtered_findings.append(_filtered_finding_summary(
                    normalized,
                    pair=pair,
                    reason=normalized.get("invalid_reason") or "invalid",
                ))
                continue

            key = finding_dedupe_key(normalized)
            if key[1] and key in seen:
                filtered_findings.append(_filtered_finding_summary(
                    normalized,
                    pair=pair,
                    reason="duplicate",
                    duplicate_of=seen[key],
                ))
                continue

            seen[key] = {
                "pair": pair,
                "finding_index": normalized.get("_finding_index"),
                "segment_id": normalized.get("segment_id"),
                "draft_passage": (normalized.get("draft_passage") or "").strip(),
            }
            filtered_selected[pair].append(normalized)

    return dict(filtered_selected), filtered_findings


def _filtered_finding_summary(
    finding: dict[str, Any],
    *,
    pair: str,
    reason: str,
    duplicate_of: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "pair": pair,
        "finding_index": finding.get("_finding_index"),
        "segment_id": finding.get("segment_id"),
        "valid": finding.get("valid", True),
        "reason": reason,
        "class": finding.get("class", ""),
        "draft_passage": (finding.get("draft_passage") or "").strip(),
        "gate_test_answer": (finding.get("gate_test_answer") or "").strip(),
    }
    if duplicate_of is not None:
        summary["duplicate_of"] = duplicate_of
    return summary


def _normalize_pair(raw: str, seg_lookup: dict[str, str]) -> str:
    if "-" not in raw:
        raise ValueError(f"invalid pair format: {raw!r}")
    a, b = [x.strip() for x in raw.split("-", 1)]
    if not a or not b:
        raise ValueError(f"invalid pair format: {raw!r}")
    a = _normalize_segment_id(a, seg_lookup)
    b = _normalize_segment_id(b, seg_lookup)
    return f"{a}-{b}"


def _build_segment_lookup(plan: dict) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for s in plan.get("segments", []):
        sid = str(s["id"])
        lookup[sid] = sid
        if sid.isdigit():
            lookup[str(int(sid))] = sid
            lookup[sid.lstrip("0") or "0"] = sid
    return lookup


def _normalize_segment_id(value: str, seg_lookup: dict[str, str]) -> str:
    sid = value.strip()
    normalized = seg_lookup.get(sid)
    if normalized is not None:
        return normalized
    lowered = sid.strip().lower()
    if lowered in seg_lookup:
        return seg_lookup[lowered]
    raise ValueError(f"unknown segment id {sid!r}")


def _snapshot_pair(seg_dir: Path, segment_id: str, pair: str, prefix: str) -> None:
    src = seg_dir / f"{segment_id}.md"
    if not src.exists():
        return
    dst = seg_dir / f"{segment_id}.{prefix}.{pair.replace('-', '_')}.md"
    if not dst.exists():
        shutil.copy2(src, dst)


def _parse_repair_response(text: str) -> dict[str, Any]:
    data = parse_llm_json(text)
    if isinstance(data, dict):
        return data
    raise ValueError(f"expected JSON object, got {type(data).__name__}")


def _update_checks(path: Path, *, segment: dict, source_words: int, draft_words: int) -> None:
    target = int(segment.get("target_word_count", 0) or 0)
    delta = (draft_words - target) / target if target else None
    try:
        old = json.loads(path.read_text())
    except Exception:
        old = {}
    sig_total = len(segment.get("signatures", []))
    sig_hits = old.get("signatures_matched", 0)
    sig_misses = old.get("signatures_missed", [])
    if not isinstance(sig_hits, int):
        sig_hits = 0
    if not isinstance(sig_misses, list):
        sig_misses = []
    status = "drafted" if draft_words > 0 else old.get("status", "drafted")
    updated = dict(old) if isinstance(old, dict) else {}
    updated.update({
        "segment_id": segment["id"],
        "title": segment.get("title", ""),
        "status": status,
        "source_words": source_words,
        "target_words": target,
        "draft_words": draft_words,
        "word_count_delta_pct": round(delta * 100, 1) if delta is not None else None,
        "signatures_total": sig_total,
        "signatures_matched": sig_hits,
        "signatures_missed": sig_misses,
    })
    write_json(path, updated)
