#!/usr/bin/env python3
"""Collect just what the review app needs into deploy/artifacts/.

Copy review text, metadata and only the verified media assets referenced by
the current media index. Private drafts, caches and obsolete media are excluded.
Zero LLM cost; also available from an installed package.

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
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from .artifacts import BOOKS_DIR, WORK_DIR, ROOT, Book
from .media import validate_media_manifest
from .production_state import confined_path


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
ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def is_internal_variant(book_id: str) -> bool:
    return any(marker in book_id for marker in INTERNAL_VARIANT_MARKERS)


def _validate_id(value: str) -> None:
    if not isinstance(value, str) or value in {".", ".."} or not ID_RE.fullmatch(value):
        raise ValueError(f"invalid artifact id: {value!r}")


def _overlap(first: Path, second: Path) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _output_paths(out_dir: Path) -> tuple[Path, Path]:
    requested = (out_dir, out_dir.parent / "books")
    outputs = tuple(path.resolve() for path in requested)
    for output in outputs:
        for source in (WORK_DIR.resolve(), BOOKS_DIR.resolve()):
            if _overlap(output, source):
                raise ValueError(f"output overlaps input root: {output} and {source}")
    if _overlap(*outputs):
        raise ValueError("artifact and metadata output directories must be separate")
    for path in requested:
        # A linked parent is safe after resolution, but replacing a linked
        # output itself would make the requested layout ambiguous.
        if path.is_symlink():
            raise ValueError(f"output directory must not be a symlink: {path}")
        if path.exists() and not path.is_dir():
            raise ValueError(f"output is not a directory: {path}")
    return outputs


def _confined(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"input escapes selected root: {path}")
    return resolved


def _input_file(path: Path, root: Path, *, optional: bool = False) -> Path | None:
    resolved = _confined(path, root)
    if optional and not path.exists() and not path.is_symlink():
        return None
    if not resolved.is_file():
        raise FileNotFoundError(f"missing input file: {path}")
    return resolved


def _read_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return data


def _copy_json(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    # Validate the actual staged bytes, including JSON we otherwise only copy.
    _read_object(destination)


def _stage_media(work_book: Path, dest: Path, book_id: str) -> None:
    from .publication import _allowed_output
    index_path = _input_file(work_book / "media_manifest.json", work_book, optional=True)
    if index_path is None:
        return
    index = validate_media_manifest(_read_object(index_path), work_book)
    if index["book_id"] != book_id:
        raise ValueError("media index book identity mismatch")
    _copy_json(index_path, dest / "media_manifest.json")
    for target in index["targets"]:
        for key in ("path", "text_path"):
            if key not in target:
                continue
            relative = target[key]
            _allowed_output(relative)
            source = confined_path(work_book, relative)
            output = confined_path(dest, relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    # Catch source replacement during the staged copy before replacing outputs.
    validate_media_manifest(_read_object(dest / "media_manifest.json"), dest)


def _stage_publications(work_book: Path, dest: Path, book_id: str) -> None:
    from .publication import verify_revision, _read_pointer

    book = Book(book_id, work_book / "unused-source", {}, work_book)
    revisions = set()
    pointers = {}
    for channel in ("review", "release"):
        pointer = _read_pointer(book, channel)
        if pointer is None:
            continue
        pointers[channel] = pointer
        revisions.add(pointer["revision"])
        revisions.update(event["revision"] for event in pointer["history"])
    for revision in sorted(revisions):
        manifest = verify_revision(book, revision)
        source_root = work_book / "publications" / revision
        output_root = dest / "publications" / revision
        for item in manifest["outputs"] + [{"path": "revision.json"}]:
            source = confined_path(source_root, item["path"])
            output = confined_path(output_root, item["path"])
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
        verify_revision(Book(book_id, dest / "unused-source", {}, dest), revision)
    for channel, pointer in pointers.items():
        (dest / f"{channel}_current.json").write_text(
            json.dumps(pointer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _stage_book(book_id: str, artifacts_out: Path, books_out: Path) -> tuple[int, int]:
    work_book = _confined(WORK_DIR.resolve() / book_id, WORK_DIR.resolve())
    src_align = _confined(work_book / "alignments", work_book)
    alignments = sorted(src_align.glob("*.json")) if src_align.is_dir() else []
    if not alignments:
        raise FileNotFoundError(f"no alignments for selected book: {book_id}")

    dest = artifacts_out / book_id
    for alignment in alignments:
        _validate_id(alignment.stem)
        source = _input_file(alignment, work_book)
        _copy_json(source, dest / "alignments" / alignment.name)

        checks_name = f"{alignment.stem}.checks.json"
        checks = _input_file(work_book / "segments" / checks_name, work_book, optional=True)
        if checks is not None:
            _copy_json(checks, dest / "segments" / checks_name)

    # plan.json supplies chapter titles, and title/author when books/ is
    # not shipped. Trim it to the fields the app reads.
    plan_path = _input_file(work_book / "plan.json", work_book, optional=True)
    if plan_path is not None:
        plan = _read_object(plan_path)
        _validate_id(plan.get("book_id", book_id))
        segments = plan.get("segments", [])
        if not isinstance(segments, list) or any(not isinstance(s, dict) for s in segments):
            raise ValueError(f"invalid plan segments: {plan_path}")
        for segment in segments:
            _validate_id(segment.get("id"))
        slim = {
            "book_id": plan.get("book_id", book_id),
            "title": plan.get("title", book_id),
            "author": plan.get("author", ""),
            "segments": [{k: s.get(k) for k in ("id", "title")} for s in segments],
        }
        (dest / "plan.json").write_text(json.dumps(slim, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")

    for relative in [Path(name) for name in REVIEW_REPORTS] + [
            Path("editorial") / name for name in EDITORIAL_ARTIFACTS]:
        source = _input_file(work_book / relative, work_book, optional=True)
        if source is not None:
            _copy_json(source, dest / relative)

    _stage_media(work_book, dest, book_id)
    _stage_publications(work_book, dest, book_id)

    books_book = _confined(BOOKS_DIR.resolve() / book_id, BOOKS_DIR.resolve())
    meta_path = _input_file(books_book / "metadata.json", books_book, optional=True)
    if meta_path is not None:
        meta = _read_object(meta_path)
        books_dest = books_out / book_id
        books_dest.mkdir(parents=True)
        (books_dest / "metadata.json").write_text(
            json.dumps({k: meta[k] for k in ("title", "author", "genre") if k in meta},
                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    return size, len(alignments)


def _publish(stage: Path, out_dir: Path, books_out: Path) -> None:
    """Replace both directories, restoring the previous pair on exceptions.

    The sibling renames are not a crash-atomic filesystem transaction. Backups
    remain under the stage directory if rollback itself cannot finish.
    """
    replacements = [(stage / "artifacts", out_dir, stage / "previous-artifacts"),
                    (stage / "books", books_out, stage / "previous-books")]
    backed_up = []
    installed = []
    try:
        for _, destination, backup in replacements:
            if destination.exists():
                os.replace(destination, backup)
                backed_up.append((destination, backup))
        for source, destination, _ in replacements:
            os.replace(source, destination)
            installed.append((source, destination))
    except BaseException as error:
        rollback_errors = []
        for source, destination in reversed(installed):
            try:
                os.replace(destination, source)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        for destination, backup in reversed(backed_up):
            try:
                os.replace(backup, destination)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        if rollback_errors:
            raise RuntimeError(f"package rollback failed; recover previous output from {stage}") from error
        raise


def package(book_ids: list[str], out_dir: Path) -> int:
    out_dir, books_out = _output_paths(Path(out_dir))

    if not book_ids:
        book_ids = sorted(p.parent.name for p in WORK_DIR.glob("*/alignments")
                          if any(p.glob("*.json"))
                          and not is_internal_variant(p.parent.name))
    if not book_ids:
        print("no aligned books under work/ — run: forage proofread <book>")
        return 1
    for book_id in book_ids:
        _validate_id(book_id)
    book_ids = list(dict.fromkeys(book_ids))

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".forage-package-", dir=out_dir.parent))
    published = False
    summaries = []
    try:
        (stage / "artifacts").mkdir()
        (stage / "books").mkdir()
        for book_id in book_ids:
            size, chapters = _stage_book(book_id, stage / "artifacts", stage / "books")
            summaries.append((book_id, size, chapters))
        # Atomic pipeline writes are owner-only. These selected public copies
        # must also be readable when the web server runs under a different uid
        # from the operator who builds/uploads the package.
        for public_root in (stage / "artifacts", stage / "books"):
            public_root.chmod(0o755)
            for path in public_root.rglob("*"):
                path.chmod(0o755 if path.is_dir() else 0o644)
        _publish(stage, out_dir, books_out)
        published = True
    finally:
        if published or not any((stage / name).exists()
                                for name in ("previous-artifacts", "previous-books")):
            shutil.rmtree(stage, ignore_errors=True)

    for book_id, size, chapters in summaries:
        print(f"  ok    {book_id}  {chapters} chapters  {size / 1e6:.1f} MB")
    total_bytes = sum(size for _, size, _ in summaries)
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
