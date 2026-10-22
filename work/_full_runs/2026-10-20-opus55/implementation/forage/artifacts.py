"""Per-book working directory layout and I/O helpers.

Layout:
  books/<book-id>/<book-id>.txt   -- source text (input)
  books/<book-id>/metadata.json   -- optional metadata (genre, title, ...)
  work/<book-id>/plan.json        -- pre-pass output
  work/<book-id>/plan.raw.md      -- raw LLM response for debugging
  work/<book-id>/segments/NNN.md  -- drafted segments
  work/<book-id>/critics/...      -- critic diagnoses
  work/<book-id>/llm_calls.jsonl  -- per-call log
  work/<book-id>/abridgment.md    -- internal assembled markdown-ish output
  work/<book-id>/abridgment.txt   -- UTF-8 plain-text final assembled output
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .resources import workspace_root, workspace_dirs

ROOT = workspace_root()
BOOKS_DIR, WORK_DIR = workspace_dirs()


@dataclass
class Book:
    book_id: str
    source_path: Path
    metadata: dict[str, Any]
    work_dir: Path

    @property
    def source_text(self) -> str:
        if self.source_path.suffix.lower() == ".epub":
            from .epub_reader import extract_epub_chapters

            parts: list[str] = []
            for section in extract_epub_chapters(self.source_path):
                title = (section.get("title") or "").strip()
                text = (section.get("text") or "").strip()
                if title and text:
                    parts.append(f"# {title}\n\n{text}")
                elif title:
                    parts.append(f"# {title}")
                elif text:
                    parts.append(text)
            return "\n\n".join(parts)
        return self.source_path.read_text(encoding="utf-8", errors="replace")


def load_book(book_id: str, *, workspace=None, create: bool = True) -> Book:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", book_id):
        raise ValueError("invalid book ID")
    books_dir, work_root = (workspace_dirs(workspace) if workspace is not None or any(
        os.environ.get(k) for k in ("FORAGE_WORKSPACE", "FORAGE_BOOKS_DIR", "FORAGE_WORK_DIR"))
        else (BOOKS_DIR, WORK_DIR))
    book_dir = books_dir / book_id
    if not book_dir.is_dir():
        raise FileNotFoundError(f"no book directory at {book_dir}")

    meta_path = book_dir / "metadata.json"
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    # Source file resolution, in priority order:
    #   1. metadata["source"] if set (any extension — .txt, .epub, ...)
    #   2. source.txt / <book-id>.txt
    #   3. source.epub / <book-id>.epub
    #   4. largest .txt, else largest .epub
    source_path: Path | None = None
    if "source" in metadata:
        source_path = book_dir / metadata["source"]
    elif (book_dir / "source.txt").exists():
        source_path = book_dir / "source.txt"
    elif (book_dir / f"{book_id}.txt").exists():
        source_path = book_dir / f"{book_id}.txt"
    elif (book_dir / "source.epub").exists():
        source_path = book_dir / "source.epub"
    elif (book_dir / f"{book_id}.epub").exists():
        source_path = book_dir / f"{book_id}.epub"
    else:
        epubs = list(book_dir.glob("*.epub"))
        txts = list(book_dir.glob("*.txt"))
        if txts:
            source_path = max(txts, key=lambda p: p.stat().st_size)
        elif epubs:
            source_path = max(epubs, key=lambda p: p.stat().st_size)
        else:
            raise FileNotFoundError(f"no .txt or .epub source in {book_dir}")

    if not source_path.resolve().is_relative_to(book_dir.resolve()) or not source_path.is_file():
        raise ValueError("source must be a file inside its book directory")
    work_dir = work_root / book_id
    if create:
        work_dir.mkdir(parents=True, exist_ok=True)
    return Book(book_id=book_id, source_path=source_path,
                metadata=metadata, work_dir=work_dir)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def segment_source_path(book: "Book", segment_id: str) -> Path | None:
    """Return the path to a segment's source text, or None if not found.

    Prefers the new chapter-split output (`chapters/NNN.md`); falls back to
    the legacy LLM-hint-based extraction (`segments/NNN.source.md`) so old
    work directories still function.
    """
    chapters_path = book.work_dir / "chapters" / f"{segment_id}.md"
    if chapters_path.exists():
        return chapters_path
    legacy_path = book.work_dir / "segments" / f"{segment_id}.source.md"
    if legacy_path.exists():
        return legacy_path
    return None
