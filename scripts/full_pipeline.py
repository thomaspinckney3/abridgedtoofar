"""Run the full lean pipeline on all diegetic chapters of a book end-to-end.

Usage: python -m scripts.full_pipeline <book_id> [--iterate] [--coherence] [--resume-drafts]
       [--skip-coherence-fix|--coherence-fix [--coherence-fix-all-findings|--coherence-fix-selected-pairs --coherence-fix-pair NNN-NNN ...]]

Runs the required upstream stages first: split, classify, summarize, cuts,
plan, prepare-skips. LLM calls still use the normal replay cache, so reruns
reuse cached responses when the prompt has not changed. Then this script
drafts each chapter, runs a fresh coherence pass, applies coherence-fix to
the resulting findings, then assembles and runs the book-level critic. The
iterate loop (critic + regen) and the post-hoc coherence pass are OPT-IN —
pass `--iterate` and/or `--coherence` to include them.
Coherence-fix is now ON by default (repairs findings from the fresh
`coherence_report.json` after drafting and before assemble). Use
`--skip-coherence-fix` to disable it in a run. Use
`--coherence-fix-selected-pairs --coherence-fix-pair ...` to limit repairs to
specific pairs; use `--coherence-fix-all-findings` to be explicit.

Rationale: empirically, the iterate loop whack-a-moles on voice-dense prose
(most chapters exhaust with mediums accumulated), and coherence has low
recall on the worst compression-induced breaks (dangling antecedents), but
fresh adjacent-pair findings are useful as bounded repair inputs. The
proofread tool + human review remain the final quality surface. Both checks
remain available as `forage iterate` / `forage coherence` for spot-checking.

Writes progress to work/<book>/full_pipeline_progress.jsonl.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, read_json
from forage.assemble import assemble_book
from forage.book_critic import run_book_critic
from forage.chapter_classifier import classify_chapters
from forage.chapter_split import split_to_disk
from forage.coherence import run_coherence
from forage.coherence_fix import run_coherence_fixes
from forage.cuts import generate_cuts
from forage.drafter import draft_segment
from forage.iterate import iterate_segment
from forage.lean_plan import build_lean_plan
from forage.prepare_skips import apply_skips
from forage.summarizer import summarize_book

if len(sys.argv) < 2:
    print("usage: python -m scripts.full_pipeline <book_id> [--iterate] [--coherence] [--resume-drafts] [--skip-coherence-fix|--coherence-fix] [--coherence-fix-all-findings|--coherence-fix-selected-pairs ...]")
    sys.exit(2)
BOOK_ID = sys.argv[1]
ARGS = sys.argv[2:]
RUN_ITERATE = "--iterate" in ARGS
RUN_COHERENCE = "--coherence" in ARGS
RESUME_DRAFTS = "--resume-drafts" in ARGS
RUN_COHERENCE_FIX_EXPLICIT = "--coherence-fix" in ARGS
RUN_COHERENCE_FIX_SKIP = "--skip-coherence-fix" in ARGS
RUN_COHERENCE_FIX = not RUN_COHERENCE_FIX_SKIP
RUN_COHERENCE_FIX_ALL = "--coherence-fix-all-findings" in ARGS
RUN_COHERENCE_FIX_SELECTED = "--coherence-fix-selected-pairs" in ARGS

if RUN_COHERENCE_FIX_EXPLICIT and RUN_COHERENCE_FIX_SKIP:
    print("usage: cannot use both --coherence-fix and --skip-coherence-fix")
    sys.exit(2)
if RUN_COHERENCE_FIX_SELECTED and not RUN_COHERENCE_FIX:
    if RUN_COHERENCE_FIX_SKIP:
        print("usage: --coherence-fix-selected-pairs is incompatible with --skip-coherence-fix")
        sys.exit(2)
if RUN_COHERENCE_FIX_ALL and RUN_COHERENCE_FIX_SELECTED:
    print("usage: cannot use both --coherence-fix-all-findings and --coherence-fix-selected-pairs together")
    sys.exit(2)


def _extract_flag_values(args: list[str], flag: str) -> list[str]:
    vals: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == flag:
            if i + 1 >= len(args):
                print(f"usage: {flag} requires a value")
                sys.exit(2)
            vals.append(args[i + 1])
            i += 2
            continue
        if a.startswith(f"{flag}="):
            vals.append(a.split("=", 1)[1])
        i += 1
    return vals


COHERENCE_FIX_PAIRS = _extract_flag_values(ARGS, "--coherence-fix-pair")

if RUN_COHERENCE_FIX_SELECTED and not COHERENCE_FIX_PAIRS:
    print("usage: --coherence-fix-selected-pairs requires one or more --coherence-fix-pair values")
    sys.exit(2)
if RUN_COHERENCE_FIX_ALL and not RUN_COHERENCE_FIX_SELECTED and COHERENCE_FIX_PAIRS:
    print("usage: --coherence-fix-pair requires --coherence-fix-selected-pairs")
    sys.exit(2)
if COHERENCE_FIX_PAIRS and not RUN_COHERENCE_FIX_SELECTED:
    # Backward compatible default: treat explicit pair args as selected pairs.
    RUN_COHERENCE_FIX_SELECTED = True
    RUN_COHERENCE_FIX = True

if RUN_COHERENCE_FIX_SKIP and RUN_COHERENCE_FIX_SELECTED:
    print("usage: explicit pair targeting requires coherence-fix; remove --skip-coherence-fix")
    sys.exit(2)
MIN_CHAPTER_WORDS = 100

book = load_book(BOOK_ID)
book.work_dir.mkdir(parents=True, exist_ok=True)

progress_path = book.work_dir / "full_pipeline_progress.jsonl"


def _load_resumable_draft_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    for line in path.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("phase") != "draft":
            continue
        if entry.get("status") not in ("drafted", "cut"):
            continue
        sid = entry.get("segment_id")
        if sid:
            ids.add(str(sid))
    return ids


resumable_draft_ids = (_load_resumable_draft_ids(progress_path)
                       if RESUME_DRAFTS and not RUN_ITERATE else set())
if RESUME_DRAFTS:
    progress_path.touch()
else:
    progress_path.write_text("")

def log(entry: dict) -> None:
    with progress_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _requires_draft(segment: dict) -> bool:
    return (
        segment.get("diegetic_status") == "diegetic"
        and (segment.get("source_word_count") or 0) >= MIN_CHAPTER_WORDS
        and not segment.get("skipped")
        and int(segment.get("target_word_count", 0) or 0) > 0
    )


def _find_incomplete_required_drafts(plan: dict) -> list[dict]:
    seg_dir = book.work_dir / "segments"
    failures: list[dict] = []
    for segment in plan.get("segments", []):
        if not _requires_draft(segment):
            continue
        sid = segment["id"]
        draft_path = seg_dir / f"{sid}.md"
        checks_path = seg_dir / f"{sid}.checks.json"
        checks_status = None
        if checks_path.exists():
            try:
                checks_status = json.loads(checks_path.read_text()).get("status")
            except Exception:
                checks_status = None
        if checks_status in ("error", "truncated", "skipped_extract_fail"):
            failures.append({"segment_id": sid, "status": checks_status})
            continue
        if not draft_path.exists():
            failures.append({"segment_id": sid, "status": "missing"})
            continue
        if not draft_path.read_text().strip():
            failures.append({"segment_id": sid, "status": "empty"})
    return failures


def _resume_draft(segment: dict) -> dict | None:
    sid = segment["id"]
    if sid not in resumable_draft_ids:
        return None
    seg_dir = book.work_dir / "segments"
    draft_path = seg_dir / f"{sid}.md"
    checks_path = seg_dir / f"{sid}.checks.json"
    if not draft_path.exists() or not checks_path.exists():
        return None
    try:
        checks = json.loads(checks_path.read_text())
    except Exception:
        return None
    status = checks.get("status")
    text = draft_path.read_text()

    # Resume is keyed by the previous progress log, but the required upstream
    # stages may rebuild the plan before drafting. Do not let an old cut survive
    # when the current plan now requires a real draft, and do not let an old
    # non-empty draft survive when the current plan now cuts the segment.
    if _requires_draft(segment):
        if status != "drafted" or not text.strip():
            return None
    elif status != "cut":
        return None

    source_words = checks.get("source_words")
    if source_words is not None and source_words != segment.get("source_word_count"):
        return None

    target_words = checks.get("target_words")
    if target_words is not None and target_words != segment.get("target_word_count"):
        return None

    return {
        "status": status,
        "final_words": len(text.split()),
    }


t_pipeline = time.time()

print(f"book: {BOOK_ID}")
print()
print("running required upstream stages...")

for phase, fn in (
    ("split", lambda: split_to_disk(book)),
    ("classify", lambda: classify_chapters(book)),
    ("summarize", lambda: summarize_book(book)),
    ("cuts", lambda: generate_cuts(book)),
    ("plan", lambda: build_lean_plan(book)),
):
    t0 = time.time()
    print(f"  {phase}...", flush=True)
    try:
        fn()
        elapsed = time.time() - t0
        print(f"    done t={elapsed:.0f}s")
        log({"phase": phase, "elapsed_s": round(elapsed, 1)})
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")
        log({"phase": phase, "error": f"{type(e).__name__}: {e}"})
        sys.exit(1)

print("  prepare-skips...", flush=True)
try:
    t0 = time.time()
    skips = apply_skips(book)
    elapsed = time.time() - t0
    print(f"    done skipped={len(skips.skipped)} "
          f"kernels={len(skips.kernels_inserted)} t={elapsed:.0f}s")
    log({"phase": "prepare-skips",
         "skipped": skips.skipped,
         "kernels_inserted": skips.kernels_inserted,
         "not_found": skips.not_found,
         "elapsed_s": round(elapsed, 1)})
except Exception as e:
    print(f"    ERROR: {type(e).__name__}: {e}")
    log({"phase": "prepare-skips", "error": f"{type(e).__name__}: {e}"})
    sys.exit(1)

plan = read_json(book.work_dir / "plan.json")
segs = plan["segments"]
diegetic = [s for s in segs
            if s.get("diegetic_status") == "diegetic"
            and (s.get("source_word_count") or 0) >= MIN_CHAPTER_WORDS]
print()
print(f"total segments: {len(segs)}, diegetic to process: {len(diegetic)}")
meta = plan["_meta"]["computed"]
print(f"book target: {meta['target_word_count']}w "
      f"(source {meta['source_word_count']}w, "
      f"ratio {meta['overall_compression_ratio']}x)")
print()

phase_name = "iterate" if RUN_ITERATE else "draft"
draft_failures: list[dict] = []
for i, seg in enumerate(diegetic, 1):
    sid = seg["id"]
    title = (seg.get("title") or "")[:40]
    t0 = time.time()
    print(f"[{i:>3}/{len(diegetic)}] {phase_name} {sid} '{title}' "
          f"src={seg['source_word_count']}w tgt={seg['target_word_count']}w "
          f"group={seg.get('group_id') or '—'}", flush=True)
    resumed = None if RUN_ITERATE else _resume_draft(seg)
    if resumed is not None:
        elapsed = time.time() - t0
        print(f"      resumed got={resumed['final_words']}w "
              f"status={resumed['status']} t={elapsed:.0f}s")
        log({
            "phase": "draft", "segment_id": sid, "title": title,
            "source_words": seg["source_word_count"],
            "target_words": seg["target_word_count"],
            "final_words": resumed["final_words"],
            "status": resumed["status"],
            "resumed": True,
            "elapsed_s": round(elapsed, 1),
        })
        continue
    try:
        if RUN_ITERATE:
            r = iterate_segment(book, plan, sid, max_retries=1,
                                redraft_first=False)
            draft_path = book.work_dir / "segments" / f"{sid}.md"
            final_words = (len(draft_path.read_text().split())
                           if draft_path.exists() else 0)
            elapsed = time.time() - t0
            print(f"      verdict={r.final_verdict} attempts={r.attempts} "
                  f"exhausted={r.exhausted} got={final_words}w t={elapsed:.0f}s")
            log({
                "phase": "iterate", "segment_id": sid, "title": title,
                "source_words": seg["source_word_count"],
                "target_words": seg["target_word_count"],
                "final_words": final_words,
                "verdict": r.final_verdict,
                "attempts": r.attempts,
                "exhausted": r.exhausted,
                "elapsed_s": round(elapsed, 1),
            })
            if _requires_draft(seg) and r.final_verdict in (
                    "cut", "error", "truncated", "skipped_extract_fail"):
                draft_failures.append({
                    "segment_id": sid,
                    "status": r.final_verdict,
                    "message": "iterate did not produce a valid required draft",
                })
        else:
            # Draft-only: skip the critic + regen loop. Empirically most
            # iterate runs exhaust with medium findings that the critic
            # keeps whack-a-moling, so we default to no-iterate and let the
            # proofread tool + human review surface any real issues.
            d = draft_segment(book, plan, sid)
            elapsed = time.time() - t0
            print(f"      {d.status} got={d.draft_words}w "
                  f"(target {d.target_words}w) t={elapsed:.0f}s")
            log({
                "phase": "draft", "segment_id": sid, "title": title,
                "source_words": seg["source_word_count"],
                "target_words": seg["target_word_count"],
                "final_words": d.draft_words,
                "status": d.status,
                "elapsed_s": round(elapsed, 1),
            })
            if _requires_draft(seg) and d.status != "drafted":
                draft_failures.append({
                    "segment_id": sid,
                    "status": d.status,
                    "message": d.message,
                })
    except Exception as e:
        print(f"      ERROR: {type(e).__name__}: {e}")
        log({"phase": phase_name, "segment_id": sid,
             "error": f"{type(e).__name__}: {e}"})
        if _requires_draft(seg):
            draft_failures.append({
                "segment_id": sid,
                "status": "exception",
                "message": f"{type(e).__name__}: {e}",
            })

t_draft = time.time() - t_pipeline
print()
print(f"{phase_name} phase done in {t_draft/60:.1f} min")

incomplete_required = _find_incomplete_required_drafts(plan)
if draft_failures or incomplete_required:
    by_segment: dict[str, dict] = {}
    for item in incomplete_required + draft_failures:
        by_segment.setdefault(item["segment_id"], item)
    failures = list(by_segment.values())
    print()
    print("ERROR: required drafts are incomplete; refusing coherence/assemble")
    for item in failures[:12]:
        msg = f"  {item['segment_id']}: {item.get('status', 'unknown')}"
        if item.get("message"):
            msg += f" — {item['message']}"
        print(msg)
    if len(failures) > 12:
        print(f"  ... {len(failures) - 12} more")
    log({"phase": "draft-verify",
         "status": "failed",
         "failures": failures})
    sys.exit(1)

log({"phase": "draft-verify", "status": "passed"})

if RUN_COHERENCE_FIX:
    print()
    print("applying coherence repairs...")
    try:
        print("  running fresh coherence report...")
        coh = run_coherence(book)
        print(f"  generated: pairs={coh['pairs_checked']} findings={coh['findings_total']} "
              f"classes={coh.get('class_counts', {})}")
        log({"phase": "coherence-pre-fix",
             "pairs_checked": coh["pairs_checked"],
             "findings_total": coh["findings_total"],
             "class_counts": coh.get("class_counts", {})})
        fixes = run_coherence_fixes(
            book,
            all_findings=not RUN_COHERENCE_FIX_SELECTED,
            pairs=COHERENCE_FIX_PAIRS if RUN_COHERENCE_FIX_SELECTED else None,
            max_retries=1,
            dry_run=False,
        )
        print(f"  pairs={fixes['pairs_processed']} applied={fixes['pairs_applied']} "
              f"no_change={fixes['pairs_no_change']} "
              f"rejected={fixes.get('pairs_rejected', 0)} "
              f"failed={fixes['pairs_failed']}")
        log({"phase": "coherence-fix",
             "pairs_processed": fixes["pairs_processed"],
             "pairs_applied": fixes["pairs_applied"],
             "pairs_no_change": fixes["pairs_no_change"],
             "pairs_rejected": fixes.get("pairs_rejected", 0),
             "pairs_failed": fixes["pairs_failed"],
             "pairs_no_findings": fixes["pairs_no_findings"]})
        if fixes["pairs_failed"]:
            print("  ERROR: coherence-fix failed; refusing to assemble")
            sys.exit(1)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        log({"phase": "coherence-fix",
             "error": f"{type(e).__name__}: {e}"})
        sys.exit(1)

print()
print("assembling...")
assembly = assemble_book(book, plan)
print(f"  total_drafted={assembly.total_drafted}w (target {assembly.book_target}w, "
      f"ceiling {assembly.book_ceiling}w)")
print(f"  segments drafted/cut/missing: {assembly.segments_drafted}/"
      f"{assembly.segments_cut}/{assembly.segments_missing}")
print(f"  over_budget={assembly.over_budget} over_ceiling={assembly.over_ceiling}")
if assembly.plain_text_path:
    print(f"  plain_text={assembly.plain_text_path}")
if assembly.published_plain_text_path:
    print(f"  published_text={assembly.published_plain_text_path}")
log({"phase": "assemble",
     "total_drafted": assembly.total_drafted,
     "book_target": assembly.book_target,
     "book_ceiling": assembly.book_ceiling,
     "over_budget": assembly.over_budget,
     "over_ceiling": assembly.over_ceiling,
     "segments_drafted": assembly.segments_drafted,
     "segments_cut": assembly.segments_cut,
     "segments_missing": assembly.segments_missing,
     "plain_text_path": str(assembly.plain_text_path) if assembly.plain_text_path else None,
     "published_plain_text_path": (
         str(assembly.published_plain_text_path)
         if assembly.published_plain_text_path else None
     )})

if RUN_COHERENCE:
    print()
    print("running coherence (post-hoc; does not feed regen)...")
    try:
        coh = run_coherence(book)
        print(f"  pairs={coh['pairs_checked']} findings={coh['findings_total']} "
              f"classes={coh.get('class_counts', {})}")
        log({"phase": "coherence",
             "pairs_checked": coh["pairs_checked"],
             "findings_total": coh["findings_total"],
             "class_counts": coh.get("class_counts", {}),
             "per_segment_counts": coh.get("per_segment_counts", {})})
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        log({"phase": "coherence",
             "error": f"{type(e).__name__}: {e}"})

print()
print("running book critic...")
try:
    bc = run_book_critic(book)
    print(f"  verdict={bc['verdict']} "
          f"{'[PARTIAL]' if bc['is_partial'] else ''}")
    print(f"  counts={bc['counts']}")
    log({"phase": "book_critique",
         "verdict": bc["verdict"],
         "is_partial": bc["is_partial"],
         "counts": bc["counts"]})
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")
    log({"phase": "book_critique",
         "error": f"{type(e).__name__}: {e}"})

total = time.time() - t_pipeline
print()
print(f"TOTAL RUNTIME: {total/60:.1f} min")
