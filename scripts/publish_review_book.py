#!/usr/bin/env python3
"""Publish one review-app book artifact without rebuilding the app image.

The deployed web app serves baked artifacts from /app, but can override any
single book from a writable volume:

    /data/artifacts/<book_id>
    /data/books/<book_id>

This tool builds the same slim artifact shape as package_review_artifacts.py,
uploads it to Fly, and swaps just that book directory into the volume. The app
will pick it up on the next request because ArtifactStore stats JSON files on
read and falls back to baked artifacts when no overlay exists.

Examples:

    python scripts/publish_review_book.py secret_adversary
    python scripts/publish_review_book.py secret_adversary --dry-run
    python scripts/publish_review_book.py secret_adversary --package-only /tmp/secret_adversary-review.tgz
    python scripts/publish_review_book.py secret_adversary --local-root /tmp/review-volume
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.package_review_artifacts import package  # noqa: E402


BOOK_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _valid_book_id(book_id: str) -> bool:
    return bool(BOOK_RE.fullmatch(book_id))


def _touch_files(root: Path) -> None:
    now = time.time()
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (now, now))


def _archive_book(book_id: str, archive_path: Path) -> dict[str, int]:
    if not _valid_book_id(book_id):
        raise ValueError(f"invalid book id: {book_id!r}")

    with tempfile.TemporaryDirectory(prefix=f"forage-review-{book_id}-") as tmp_raw:
        tmp = Path(tmp_raw)
        artifacts_dir = tmp / "artifacts"
        code = package([book_id], artifacts_dir)
        if code != 0:
            raise RuntimeError(f"packaging failed for {book_id}")

        artifact_book = artifacts_dir / book_id
        metadata_book = tmp / "books" / book_id
        if not artifact_book.is_dir():
            raise RuntimeError(f"packaging produced no artifact directory for {book_id}")

        _touch_files(tmp)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            archive_path.unlink()
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(artifact_book, arcname=f"artifacts/{book_id}")
            if metadata_book.is_dir():
                tar.add(metadata_book, arcname=f"books/{book_id}")

        return {
            "chapters": len(list((artifact_book / "alignments").glob("*.json"))),
            "artifact_files": sum(1 for p in artifact_book.rglob("*") if p.is_file()),
            "metadata_files": sum(1 for p in metadata_book.rglob("*") if p.is_file())
            if metadata_book.is_dir() else 0,
        }


def _run(cmd: list[str], *, dry_run: bool = False) -> None:
    print("$ " + shlex.join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def _remote_swap_script(remote_root: str, archive_path: str, book_id: str) -> str:
    root = shlex.quote(remote_root.rstrip("/") or "/data")
    archive = shlex.quote(archive_path)
    book = shlex.quote(book_id)
    return f"""
set -eu
root={root}
archive={archive}
book={book}
stage="$root/incoming/review-book-$book.$$"
rm -rf "$stage"
mkdir -p "$stage" "$root/artifacts" "$root/books"
tar -xzf "$archive" -C "$stage"
test -d "$stage/artifacts/$book"
rm -rf "$root/artifacts/$book.next" "$root/books/$book.next"
mv "$stage/artifacts/$book" "$root/artifacts/$book.next"
if [ -d "$stage/books/$book" ]; then
  mv "$stage/books/$book" "$root/books/$book.next"
fi
rm -rf "$root/artifacts/$book.prev" "$root/books/$book.prev"
if [ -d "$root/artifacts/$book" ]; then
  mv "$root/artifacts/$book" "$root/artifacts/$book.prev"
fi
mv "$root/artifacts/$book.next" "$root/artifacts/$book"
if [ -d "$root/books/$book.next" ]; then
  if [ -d "$root/books/$book" ]; then
    mv "$root/books/$book" "$root/books/$book.prev"
  fi
  mv "$root/books/$book.next" "$root/books/$book"
else
  rm -rf "$root/books/$book"
fi
rm -rf "$stage" "$archive" "$root/artifacts/$book.prev" "$root/books/$book.prev"
""".strip()


def publish_to_fly(book_id: str, archive_path: Path, *, app: str,
                   remote_root: str, dry_run: bool = False) -> None:
    remote_root = remote_root.rstrip("/") or "/data"
    remote_archive = f"{remote_root}/incoming/{archive_path.name}"
    swap_script = _remote_swap_script(remote_root, remote_archive, book_id)
    _run([
        "fly", "ssh", "console",
        "--app", app,
        "-C", f"mkdir -p {shlex.quote(remote_root + '/incoming')}",
    ], dry_run=dry_run)
    _run([
        "fly", "ssh", "sftp", "put",
        "--app", app,
        str(archive_path),
        remote_archive,
    ], dry_run=dry_run)
    _run([
        "fly", "ssh", "console",
        "--app", app,
        "-C", "sh -lc " + shlex.quote(swap_script),
    ], dry_run=dry_run)


def _safe_extract(archive_path: Path, dest: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(dest, filter="data")


def _replace_dir(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    next_dir = dest.parent / f"{dest.name}.next"
    prev_dir = dest.parent / f"{dest.name}.prev"
    shutil.rmtree(next_dir, ignore_errors=True)
    shutil.rmtree(prev_dir, ignore_errors=True)
    shutil.move(str(src), str(next_dir))
    if dest.exists():
        shutil.move(str(dest), str(prev_dir))
    shutil.move(str(next_dir), str(dest))
    shutil.rmtree(prev_dir, ignore_errors=True)


def publish_to_local_root(book_id: str, archive_path: Path, local_root: Path,
                          *, dry_run: bool = False) -> None:
    print(f"publish {archive_path} into {local_root}")
    if dry_run:
        return
    with tempfile.TemporaryDirectory(prefix=f"forage-review-local-{book_id}-") as tmp_raw:
        stage = Path(tmp_raw)
        _safe_extract(archive_path, stage)
        artifact_src = stage / "artifacts" / book_id
        metadata_src = stage / "books" / book_id
        if not artifact_src.is_dir():
            raise RuntimeError(f"archive is missing artifacts/{book_id}")
        _replace_dir(artifact_src, local_root / "artifacts" / book_id)
        if metadata_src.is_dir():
            _replace_dir(metadata_src, local_root / "books" / book_id)
        else:
            shutil.rmtree(local_root / "books" / book_id, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("book_id", help="book id to publish")
    parser.add_argument("--app", default=os.environ.get("FLY_APP_NAME") or "forage-review",
                        help="Fly app name (default: FLY_APP_NAME or forage-review)")
    parser.add_argument("--remote-root", default="/data",
                        help="Fly volume root (default: /data)")
    parser.add_argument("--local-root",
                        help="publish into a local volume-shaped directory instead of Fly")
    parser.add_argument("--package-only",
                        help="write the one-book tarball here and do not publish")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the package and print publish commands without running them")
    args = parser.parse_args()

    if not _valid_book_id(args.book_id):
        print(f"invalid book id: {args.book_id!r}", file=sys.stderr)
        return 2

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.package_only:
        archive_path = Path(args.package_only)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix=f"forage-review-{args.book_id}-")
        stamp = f"{int(time.time())}-{os.getpid()}"
        archive_path = Path(temp_dir.name) / f"{args.book_id}-review-{stamp}.tgz"

    try:
        summary = _archive_book(args.book_id, archive_path)
        size_mb = archive_path.stat().st_size / 1e6
        print(
            f"packaged {args.book_id}: {summary['chapters']} chapters, "
            f"{summary['artifact_files']} artifact files, "
            f"{summary['metadata_files']} metadata files, {size_mb:.2f} MB"
        )

        if args.package_only:
            print(f"wrote {archive_path}")
            return 0

        if args.local_root:
            publish_to_local_root(args.book_id, archive_path, Path(args.local_root),
                                  dry_run=args.dry_run)
            print(f"{'would publish' if args.dry_run else 'published'} {args.book_id} locally")
            return 0

        publish_to_fly(args.book_id, archive_path, app=args.app,
                       remote_root=args.remote_root, dry_run=args.dry_run)
        print(
            f"{'would publish' if args.dry_run else 'published'} {args.book_id} "
            f"to {args.app}:{args.remote_root}"
        )
        return 0
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    sys.exit(main())
