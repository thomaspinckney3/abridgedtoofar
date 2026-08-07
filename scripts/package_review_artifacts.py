#!/usr/bin/env python3
"""Collect just what the review app needs into deploy/artifacts/.

work/ holds gigabytes the review app never reads — drafts, replay caches,
rendered graphic-novel pages. This copies only the alignment JSON, the plan,
and the book metadata for the books you name, so the deployed image carries
megabytes instead. Zero LLM cost.

    python scripts/package_review_artifacts.py                # every aligned public candidate
    python scripts/package_review_artifacts.py gatsby dragon_maiden
    python scripts/package_review_artifacts.py --out deploy/artifacts

The Dockerfile copies deploy/artifacts to /app/artifacts and deploy/books to
/app/books inside the image, matching FORAGE_WORK_DIR and FORAGE_BOOKS_DIR.
For a mounted one-book refresh on Fly, use scripts/publish_review_book.py
instead; it packages the same slim shape and swaps only that book under /data.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forage.artifacts import BOOKS_DIR, WORK_DIR  # noqa: E402


INTERNAL_VARIANT_MARKERS = (
    "_nontrial_",
    "_namefix_trial",
)
REVIEW_REPORTS = (
    "name_lint_report.json",
)
EDITORIAL_ARTIFACTS = (
    "review_apply_ledger.json",
)


def is_internal_variant(book_id: str) -> bool:
    return any(marker in book_id for marker in INTERNAL_VARIANT_MARKERS)


def package(book_ids: list[str], out_dir: Path) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    books_out = out_dir.parent / "books"
    if books_out.exists():
        shutil.rmtree(books_out)

    if not book_ids:
        book_ids = sorted(p.parent.name for p in WORK_DIR.glob("*/alignments")
                          if any(p.glob("*.json"))
                          and not is_internal_variant(p.parent.name))
    if not book_ids:
        print("no aligned books under work/ — run: forage proofread <book>")
        return 1

    total_bytes = 0
    for book_id in book_ids:
        src_align = WORK_DIR / book_id / "alignments"
        if not src_align.is_dir() or not any(src_align.glob("*.json")):
            print(f"  skip  {book_id}  (no alignments)")
            continue

        dest = out_dir / book_id
        dest.mkdir(parents=True)
        shutil.copytree(src_align, dest / "alignments")

        alignment_ids = {p.stem for p in src_align.glob("*.json")}
        src_segments = WORK_DIR / book_id / "segments"
        checks = []
        if src_segments.is_dir():
            checks = sorted(
                src_segments / f"{sid}.checks.json"
                for sid in alignment_ids
                if (src_segments / f"{sid}.checks.json").exists()
            )
        if checks:
            checks_dest = dest / "segments"
            checks_dest.mkdir()
            for checks_path in checks:
                shutil.copy2(checks_path, checks_dest / checks_path.name)

        # plan.json supplies chapter titles, and title/author when books/ is
        # not shipped. Trim it to the fields the app reads.
        plan_path = WORK_DIR / book_id / "plan.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text())
            slim = {
                "book_id": plan.get("book_id", book_id),
                "title": plan.get("title", book_id),
                "author": plan.get("author", ""),
                "segments": [{k: s.get(k) for k in ("id", "title")}
                             for s in plan.get("segments", [])],
            }
            (dest / "plan.json").write_text(json.dumps(slim, indent=2, ensure_ascii=False) + "\n")

        for report_name in REVIEW_REPORTS:
            report_path = WORK_DIR / book_id / report_name
            if report_path.exists():
                shutil.copy2(report_path, dest / report_name)

        editorial_src = WORK_DIR / book_id / "editorial"
        for artifact_name in EDITORIAL_ARTIFACTS:
            artifact_path = editorial_src / artifact_name
            if artifact_path.exists():
                editorial_dest = dest / "editorial"
                editorial_dest.mkdir(exist_ok=True)
                shutil.copy2(artifact_path, editorial_dest / artifact_name)

        meta_path = BOOKS_DIR / book_id / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            books_dest = out_dir.parent / "books" / book_id
            books_dest.mkdir(parents=True, exist_ok=True)
            (books_dest / "metadata.json").write_text(
                json.dumps({k: meta[k] for k in ("title", "author", "genre") if k in meta},
                           indent=2, ensure_ascii=False) + "\n")

        size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
        total_bytes += size
        chapters = len(list((dest / "alignments").glob("*.json")))
        print(f"  ok    {book_id}  {chapters} chapters  {size / 1e6:.1f} MB")

    print(f"\npackaged {total_bytes / 1e6:.1f} MB into {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("books", nargs="*", help="book ids; default is every aligned book")
    parser.add_argument("--out", default=str(ROOT / "deploy" / "artifacts"),
                        help="output directory (default: deploy/artifacts)")
    args = parser.parse_args()
    return package(args.books, Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
