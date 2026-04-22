"""Per-book working directory layout and I/O helpers.

Layout:
  books/<book-id>/<book-id>.txt   -- source text (input)
  books/<book-id>/metadata.json   -- optional metadata (genre, title, ...)
  work/<book-id>/plan.json        -- pre-pass output
  work/<book-id>/plan.raw.md      -- raw LLM response for debugging
  work/<book-id>/segments/NNN.md  -- drafted segments
  work/<book-id>/critics/...      -- critic diagnoses
  work/<book-id>/llm_calls.jsonl  -- per-call log
  work/<book-id>/abridgment.md    -- final assembled output
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "books"
WORK_DIR = ROOT / "work"


@dataclass
class Book:
    book_id: str
    source_path: Path
    metadata: dict[str, Any]
    work_dir: Path

    @property
    def source_text(self) -> str:
        return self.source_path.read_text(encoding="utf-8", errors="replace")


def load_book(book_id: str) -> Book:
    book_dir = BOOKS_DIR / book_id
    if not book_dir.is_dir():
        raise FileNotFoundError(f"no book directory at {book_dir}")

    meta_path = book_dir / "metadata.json"
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    # Source file resolution, in priority order:
    #   1. metadata["source"] if set (any extension — .txt, .epub, ...)
    #   2. source.txt / source.epub
    #   3. <book-id>.txt / <book-id>.epub
    #   4. largest .epub, else largest .txt
    source_path: Path | None = None
    if "source" in metadata:
        source_path = book_dir / metadata["source"]
    elif (book_dir / "source.txt").exists():
        source_path = book_dir / "source.txt"
    elif (book_dir / "source.epub").exists():
        source_path = book_dir / "source.epub"
    elif (book_dir / f"{book_id}.txt").exists():
        source_path = book_dir / f"{book_id}.txt"
    elif (book_dir / f"{book_id}.epub").exists():
        source_path = book_dir / f"{book_id}.epub"
    else:
        epubs = list(book_dir.glob("*.epub"))
        txts = list(book_dir.glob("*.txt"))
        if epubs:
            source_path = max(epubs, key=lambda p: p.stat().st_size)
        elif txts:
            source_path = max(txts, key=lambda p: p.stat().st_size)
        else:
            raise FileNotFoundError(f"no .txt or .epub source in {book_dir}")

    work_dir = WORK_DIR / book_id
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
