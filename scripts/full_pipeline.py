"""Compatibility CLI over forage.production; default is a free plan.

Pass --execute to permit generation. --resume-drafts is accepted because resume
is always enabled. Legacy adoption is explicit via --adopt-existing. No separate
stage loop lives here; every argument maps to the shared runner.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from forage.artifacts import load_book
from forage.production import plan_production, run_production


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book_id")
    parser.add_argument("--execute", action="store_true", help="Permit potentially paid generation (default: preview)")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--outputs", default="text")
    parser.add_argument("--iterate", action="store_true")
    parser.add_argument("--coherence", action="store_true")
    parser.add_argument("--resume-drafts", action="store_true", help="Compatibility alias: resume is always enabled")
    parser.add_argument("--adopt-existing", action="store_true")
    repairs = parser.add_mutually_exclusive_group()
    repairs.add_argument("--coherence-fix", action="store_true")
    repairs.add_argument("--skip-coherence-fix", action="store_true")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--coherence-fix-all-findings", action="store_true")
    scope.add_argument("--coherence-fix-selected-pairs", action="store_true")
    parser.add_argument("--coherence-fix-pair", action="append", default=[])
    args = parser.parse_args(argv)
    if args.coherence_fix_selected_pairs and not args.coherence_fix_pair:
        parser.error("--coherence-fix-selected-pairs requires --coherence-fix-pair")
    if args.coherence_fix_all_findings and args.coherence_fix_pair:
        parser.error("all-findings is incompatible with pair targeting")
    if args.skip_coherence_fix and (args.coherence_fix_pair or args.coherence_fix_all_findings):
        parser.error("repair options are incompatible with --skip-coherence-fix")
    load_dotenv()
    options = {"outputs": args.outputs, "iterate": args.iterate, "coherence": args.coherence,
               "coherence_fix": not args.skip_coherence_fix, "coherence_fix_pairs": args.coherence_fix_pair,
               "adopt_existing": args.adopt_existing}
    try:
        book = load_book(args.book_id, workspace=args.workspace, create=False)
        result = (run_production if args.execute else plan_production)(book, options)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result, indent=2))
    return int(args.execute and not result["success"])


if __name__ == "__main__":
    raise SystemExit(main())
