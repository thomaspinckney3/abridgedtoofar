"""EPUB support: extract chapters from an EPUB spine, classify, and write
chapters.json + chapters/NNN.md into work/<book>/ — bypassing the regex-based
splitter when the source is structured.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .artifacts import Book

FRONTMATTER_FILENAME_PATTERNS = (
    "cover", "title-page", "titlepage", "contents", "toc",
    "copyright", "dedication", "acknowledg", "author",
    "frontmatter",
)
AFTERMATTER_FILENAME_PATTERNS = (
    "afterword", "appendix", "glossary", "bibliograph", "backmatter",
    "about-the-author", "aboutauthor",
)


def _item_kind(filename: str) -> str:
    """Classify a spine item by its filename."""
    lname = Path(filename).name.lower()
    if any(p in lname for p in FRONTMATTER_FILENAME_PATTERNS):
        return "front"
    if any(p in lname for p in AFTERMATTER_FILENAME_PATTERNS):
        return "front"  # bucket with extradiegetic for lean_plan purposes
    if "preface" in lname or "foreword" in lname or "prologue" in lname:
        # Prologues are debatable. Lean_plan treats "front" as extradiegetic,
        # which matches our earlier decision to cut preface-like material.
        return "front"
    if "epilogue" in lname:
        return "epilogue"
    if "chapter" in lname or re.match(r"^\d+\b", Path(filename).stem):
        return "chapter"
    return "prose"


def _html_to_markdown(html: bytes) -> tuple[str, str]:
    """Convert one HTML file to (title, body_text).

    Title is pulled from the first heading element and stripped from body so
    it isn't duplicated. Body is rendered as paragraph blocks separated by
    blank lines — enough fidelity for prose, no list/table handling yet.
    """
    soup = BeautifulSoup(html, "lxml")
    # Strip script/style early.
    for t in soup(["script", "style", "nav"]):
        t.decompose()

    title = ""
    for h in soup.find_all(["h1", "h2", "h3"]):
        txt = h.get_text(" ", strip=True)
        if txt:
            title = txt
            h.decompose()
            break

    blocks: list[str] = []
    for el in soup.find_all(["p", "blockquote", "pre"]):
        txt = el.get_text(" ", strip=True)
        if txt:
            blocks.append(txt)

    # If no paragraphs found (some EPUBs use <div> wrappers), fall back to
    # the full body text split by blank lines.
    if not blocks:
        body = soup.get_text("\n", strip=True)
        blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]

    return title, "\n\n".join(blocks)


def _parse_number(num_str: str) -> int | None:
    if not num_str:
        return None
    s = num_str.strip().lower()
    # plain integer
    if s.isdigit():
        return int(s)
    # Roman numerals up to L
    roman = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total, prev = 0, 0
    try:
        for ch in reversed(s):
            v = roman[ch]
            total += v if v >= prev else -v
            prev = v
        return total if total > 0 else None
    except KeyError:
        return None


def extract_epub_chapters(epub_path: Path) -> list[dict]:
    """Walk an EPUB's spine and return an ordered list of chapter dicts.

    Each dict carries {id, kind, number, title, raw_heading, text}.
    Empty items are dropped. Order matches spine order.
    """
    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    chapters: list[dict] = []
    chapter_n = 0
    for sid, _ in book.spine:
        item = book.get_item_with_id(sid)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        fname = item.get_name()
        kind = _item_kind(fname)
        title, body = _html_to_markdown(item.get_content())
        if not body.strip():
            continue
        num: int | None = None
        if kind == "chapter":
            chapter_n += 1
            # Prefer a number extracted from the filename (chapter-007 → 7)
            m = re.search(r"(\d+)", Path(fname).stem)
            num = int(m.group(1)) if m else chapter_n
        chapters.append({
            "id": f"{len(chapters) + 1:03d}",
            "kind": kind,
            "number": num,
            "title": title,
            "raw_heading": title,
            "source_filename": fname,
            "text": body,
        })
    return chapters


def split_epub_to_disk(book: Book) -> list[dict]:
    """EPUB analog of chapter_split.split_to_disk(): extract spine items,
    write chapters/NNN.md + chapters.json, return the manifest chapters list.
    """
    if book.source_path.suffix.lower() != ".epub":
        raise ValueError(f"expected .epub source, got {book.source_path}")

    chapters = extract_epub_chapters(book.source_path)
    seg_dir = book.work_dir / "chapters"
    seg_dir.mkdir(parents=True, exist_ok=True)

    manifest_chapters: list[dict] = []
    total_words = 0
    for c in chapters:
        path = seg_dir / f"{c['id']}.md"
        header = f"# {c['title']}\n\n" if c["title"] else ""
        path.write_text(header + c["text"] + "\n")
        words = len(c["text"].split())
        total_words += words
        manifest_chapters.append({
            "id": c["id"],
            "kind": c["kind"],
            "number": c["number"],
            "title": c["title"],
            "raw_heading": c["raw_heading"],
            "source_filename": c["source_filename"],
        })

    manifest = {
        "book_id": book.book_id,
        "source": str(book.source_path),
        "total_chapters": len(manifest_chapters),
        "total_words": total_words,
        "chapters": manifest_chapters,
        "builder": "epub_reader",
    }
    (book.work_dir / "chapters.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    return manifest_chapters
