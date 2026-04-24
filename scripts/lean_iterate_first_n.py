"""Run the lean draft → critic → regen loop on the first N substantive
diegetic chapters of every book under books/.

Usage: python -m scripts.lean_iterate_first_n [N]   (default N=2)
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, read_json
from forage.iterate import iterate_segment
from forage.lean_plan import build_lean_plan

BOOKS_DIR = Path("/Users/tp/forage/books")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
MIN_CHAPTER_WORDS = 300

BOOKS = sorted(p.name for p in BOOKS_DIR.iterdir() if p.is_dir())
print(f"processing first {N} chapter(s) of {len(BOOKS)} books")
print(f"FORAGE_DRAFT_MODEL  = {os.environ.get('FORAGE_DRAFT_MODEL','(unset)')}")
print(f"FORAGE_CRITIC_MODEL = {os.environ.get('FORAGE_CRITIC_MODEL','(unset)')}")
print(f"FORAGE_REGEN_MODEL  = {os.environ.get('FORAGE_REGEN_MODEL','(unset)')}")
print()

results = []
for book_id in BOOKS:
    print(f"=== {book_id} ===", flush=True)
    try:
        book = load_book(book_id)
        plan_path = book.work_dir / "plan.json"
        rebuild = True
        if plan_path.exists():
            existing = read_json(plan_path)
            rebuild = (existing.get("_meta", {}).get("builder") != "lean_plan")
        if rebuild:
            build_lean_plan(book)
        plan = read_json(plan_path)
        if plan.get("refusal"):
            print(f"  REFUSED: {plan['refusal'].get('reason')}")
            results.append({"book": book_id, "error": "refused"})
            print()
            continue

        segs = plan.get("segments", [])
        picks = [s for s in segs
                 if s.get("diegetic_status") == "diegetic"
                 and (s.get("source_word_count") or 0) >= MIN_CHAPTER_WORDS][:N]
        if not picks:
            print(f"  SKIP: no substantive diegetic chapters")
            print()
            continue

        for seg in picks:
            sid = seg["id"]
            t0 = time.time()
            print(f"  -> segment {sid} '{seg.get('title','')[:40]}' "
                  f"src={seg['source_word_count']}w tgt={seg['target_word_count']}w",
                  flush=True)
            r = iterate_segment(book, plan, sid, max_retries=1,
                                redraft_first=False)
            elapsed = time.time() - t0

            # Pull final word count from disk (regen writes segments/NNN.md)
            draft_path = book.work_dir / "segments" / f"{sid}.md"
            final_words = (len(draft_path.read_text().split())
                           if draft_path.exists() else None)

            tally = {"high": 0, "medium": 0, "low": 0}
            for step in r.steps:
                if step.kind == "critic":
                    for f in step.detail.get("findings", []) or []:
                        sev = (f.get("severity") or "").lower()
                        if sev in tally:
                            tally[sev] += 1
            print(f"     verdict={r.final_verdict} attempts={r.attempts} "
                  f"exhausted={r.exhausted} "
                  f"h/m/l={tally['high']}/{tally['medium']}/{tally['low']} "
                  f"final={final_words}w t={elapsed:.0f}s")

            results.append({
                "book": book_id, "segment": sid,
                "title": seg.get("title", ""),
                "verdict": r.final_verdict, "attempts": r.attempts,
                "exhausted": r.exhausted,
                "high": tally["high"], "medium": tally["medium"],
                "low": tally["low"],
                "source_words": seg["source_word_count"],
                "target_words": seg["target_word_count"],
                "final_words": final_words,
                "elapsed_s": round(elapsed, 1),
            })
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        results.append({"book": book_id, "error": str(e)})
    print()

print("=" * 92)
print("SUMMARY")
print("=" * 92)
hdr = (f"{'book':<18} {'seg':<4} {'verdict':<11} {'att':>3} "
       f"{'h/m/l':<7} {'src':>6} {'tgt':>6} {'got':>6} {'Δ%':>5}")
print(hdr)
for r in results:
    if "error" in r:
        print(f"{r['book']:<18} ERROR: {r['error'][:60]}")
        continue
    got = r.get("final_words") or 0
    tgt = r.get("target_words") or 0
    delta = ((got - tgt) / tgt * 100) if tgt else 0
    hml = f"{r['high']}/{r['medium']}/{r['low']}"
    print(f"{r['book']:<18} {r['segment']:<4} {r['verdict']:<11} "
          f"{r['attempts']:>3} {hml:<7} "
          f"{r['source_words']:>6} {tgt:>6} {got:>6} {delta:>+4.0f}%")
