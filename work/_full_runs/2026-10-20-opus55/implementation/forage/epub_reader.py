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
    """Classify a spine item by its filename alone. Used only as a hint —
    Gutenberg EPUBs use opaque hashed filenames, so real classification lives
    in _classify_from_title below.
    """
    lname = Path(filename).name.lower()
    if any(p in lname for p in FRONTMATTER_FILENAME_PATTERNS):
        return "front"
    if any(p in lname for p in AFTERMATTER_FILENAME_PATTERNS):
        return "front"
    if "preface" in lname or "foreword" in lname or "prologue" in lname:
        return "front"
    if "epilogue" in lname:
        return "epilogue"
    if "chapter" in lname or re.match(r"^\d+\b", Path(filename).stem):
        return "chapter"
    return "prose"


FRONT_HEADING_KEYWORDS = (
    "project gutenberg", "title page", "cover", "table of contents",
    "contents", "preface", "foreword", "introduction", "prologue",
    "dedication", "copyright", "author’s note", "author's note",
    "about the author", "editor’s preface", "editor's preface",
    "translator’s note", "translator's note",
)
AFTER_HEADING_KEYWORDS = (
    "epilogue", "afterword", "appendix", "glossary", "bibliography",
    "about the project gutenberg", "colophon",
)


def _classify_from_title(title: str) -> tuple[str, int | None]:
    """Classify a section by its heading text. Returns (kind, chapter_number)."""
    t = (title or "").strip()
    if not t:
        return "prose", None
    tl = t.lower()
    if any(kw in tl for kw in FRONT_HEADING_KEYWORDS):
        return "front", None
    if any(kw in tl for kw in AFTER_HEADING_KEYWORDS):
        return "epilogue", None
    # "CHAPTER N" / "Chapter N" / "CHAPTER N: Title" / "CHAPTER N. Title"
    m = re.match(r"^(?:CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\b", t)
    if m:
        return "chapter", _parse_number(m.group(1))
    # Roman numeral alone or followed by title (Gatsby's "I", Little Women's
    # "I. Playing Pilgrims.", Treasure Island's "I The Old Sea-dog"). Anchor
    # on end-of-string for bare numerals, or on period/whitespace boundary
    # followed by title text. Capital-N max length 7 = up to LXXIII.
    m = re.match(r"^([IVXLCDM]{1,7})\s*\.\s*(.*)$", t)  # "I. Title" / "I."
    if m:
        return "chapter", _parse_number(m.group(1))
    m = re.match(r"^([IVXLCDM]{1,7})(?:\s+([A-Z].*))?\s*$", t)  # "I Title" / "I"
    if m:
        return "chapter", _parse_number(m.group(1))
    # Arabic alone or followed by title.
    m = re.match(r"^(\d{1,3})\s*[\.\s]\s*(.*)$", t)
    if m:
        return "chapter", int(m.group(1))
    return "prose", None


_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def _split_epub_document(html: bytes) -> list[dict]:
    """Split one EPUB document's HTML into sections.

    A heading tag (h1–h6) creates a new section only when its text classifies
    as a chapter/front/epilogue marker via `_classify_from_title`. Headings
    whose text doesn't match (e.g. Bleak House's "In Chancery" subtitle,
    which is a chapter's theme rather than its number) fold into body text
    instead of creating spurious splits.

    Handles: Gutenberg EPUBs where many chapters live in one HTML file with
    `<h4>CHAPTER I</h4>` tags between them; self-pub EPUBs (Dragon Maiden
    style) with one chapter per file and a single leading h1/h2; and hybrid
    cases where a chapter number heading is followed by a descriptive
    subtitle heading.
    """
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav"]):
        t.decompose()

    blocks = soup.find_all([*_HEADING_TAGS, "p", "blockquote", "pre"])
    sections: list[dict] = []
    current_title = ""
    current_texts: list[str] = []

    def flush():
        body_text = "\n\n".join(current_texts).strip()
        if body_text or current_title:
            sections.append({"title": current_title, "body": body_text})

    for el in blocks:
        if el.name in _HEADING_TAGS:
            heading_text = el.get_text(" ", strip=True)
            if not heading_text:
                continue
            k, _ = _classify_from_title(heading_text)
            if k != "prose":
                # Real section boundary.
                flush()
                current_title = heading_text
                current_texts = []
            else:
                # Non-boundary heading — Bleak House's "In Chancery"
                # chapter-subtitle case. Treat as body text; if the current
                # section has no title yet, promote it to the title.
                if not current_title:
                    current_title = heading_text
                else:
                    current_texts.append(heading_text)
        else:
            txt = el.get_text(" ", strip=True)
            if txt:
                current_texts.append(txt)
    flush()

    # If no heading-delimited sections produced any body text (<div> wrappers
    # or odd structure), fall back to the whole document as one section.
    if not sections or all(not s["body"] for s in sections):
        text = soup.get_text("\n", strip=True)
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        sections = [{"title": "", "body": "\n\n".join(blocks)}]

    return sections


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
    """Walk an EPUB's spine, split each document into heading-delimited
    sections, classify each section, and return a flat ordered list of
    section dicts: {id, kind, number, title, raw_heading, text,
    source_filename}.

    Handles both one-file-per-chapter EPUBs (self-pub) and Gutenberg-style
    many-chapters-per-file EPUBs uniformly.
    """
    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    chapters: list[dict] = []
    for sid, _ in book.spine:
        item = book.get_item_with_id(sid)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        fname = item.get_name()
        filename_hint = _item_kind(fname)
        for section in _split_epub_document(item.get_content()):
            title = section["title"]
            body = section["body"]
            if not body.strip():
                continue
            kind, num = _classify_from_title(title)
            # If the title gave no signal, fall back to the filename hint.
            if kind == "prose" and filename_hint != "prose":
                kind = filename_hint
            chapters.append({
                "id": f"{len(chapters) + 1:03d}",
                "kind": kind,
                "number": num,
                "title": title,
                "raw_heading": title,
                "source_filename": fname,
                "text": body,
            })

    # Position-based reclassification: unclassified "prose" sections that
    # fall BEFORE the first chapter-kind section are front matter;
    # those AFTER the last are back matter (epilogue). This catches Moby
    # Dick's "Etymology" / "Extracts" preambles and Don Quixote's long
    # translator's introduction, whose headings don't match known patterns
    # but whose position-in-spine makes their apparatus-status clear.
    chapter_idxs = [i for i, c in enumerate(chapters) if c["kind"] == "chapter"]
    if chapter_idxs:
        first_i, last_i = chapter_idxs[0], chapter_idxs[-1]
        for i, c in enumerate(chapters):
            if c["kind"] == "prose":
                if i < first_i:
                    c["kind"] = "front"
                elif i > last_i:
                    c["kind"] = "epilogue"
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
