"""Run the full lean pipeline on all diegetic chapters of a book end-to-end.

Usage: python -m scripts.full_pipeline <book_id>

Stages assumed already complete (cached on disk): split, classify, plan,
summarize. This script runs iterate per chapter, then assemble, then the
book-level critic. Writes progress to work/<book>/full_pipeline_progress.jsonl.
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
from forage.coherence import run_coherence
from forage.iterate import iterate_segment

if len(sys.argv) < 2:
    print("usage: python -m scripts.full_pipeline <book_id>")
    sys.exit(2)
BOOK_ID = sys.argv[1]
MIN_CHAPTER_WORDS = 100

book = load_book(BOOK_ID)
plan = read_json(book.work_dir / "plan.json")
segs = plan["segments"]
diegetic = [s for s in segs
            if s.get("diegetic_status") == "diegetic"
            and (s.get("source_word_count") or 0) >= MIN_CHAPTER_WORDS]
print(f"book: {BOOK_ID}")
print(f"total segments: {len(segs)}, diegetic to process: {len(diegetic)}")
meta = plan["_meta"]["computed"]
print(f"book target: {meta['target_word_count']}w "
      f"(source {meta['source_word_count']}w, "
      f"ratio {meta['overall_compression_ratio']}x)")
print()

progress_path = book.work_dir / "full_pipeline_progress.jsonl"
progress_path.write_text("")

def log(entry: dict) -> None:
    with progress_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")

t_pipeline = time.time()

for i, seg in enumerate(diegetic, 1):
    sid = seg["id"]
    title = (seg.get("title") or "")[:40]
    t0 = time.time()
    print(f"[{i:>3}/{len(diegetic)}] iterate {sid} '{title}' "
          f"src={seg['source_word_count']}w tgt={seg['target_word_count']}w "
          f"group={seg.get('group_id') or '—'}", flush=True)
    try:
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
    except Exception as e:
        print(f"      ERROR: {type(e).__name__}: {e}")
        log({"phase": "iterate", "segment_id": sid,
             "error": f"{type(e).__name__}: {e}"})

t_iterate = time.time() - t_pipeline
print()
print(f"iterate phase done in {t_iterate/60:.1f} min")

print()
print("assembling...")
assembly = assemble_book(book, plan)
print(f"  total_drafted={assembly.total_drafted}w (target {assembly.book_target}w, "
      f"ceiling {assembly.book_ceiling}w)")
print(f"  segments drafted/cut/missing: {assembly.segments_drafted}/"
      f"{assembly.segments_cut}/{assembly.segments_missing}")
print(f"  over_budget={assembly.over_budget} over_ceiling={assembly.over_ceiling}")
log({"phase": "assemble",
     "total_drafted": assembly.total_drafted,
     "book_target": assembly.book_target,
     "book_ceiling": assembly.book_ceiling,
     "over_budget": assembly.over_budget,
     "over_ceiling": assembly.over_ceiling,
     "segments_drafted": assembly.segments_drafted,
     "segments_cut": assembly.segments_cut,
     "segments_missing": assembly.segments_missing})

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
