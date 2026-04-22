"""Deterministic chapter splitter for clearly-structured books.

Replaces the LLM's hint-based segmentation for the common case (chaptered
novels and biographies with consistent heading formats). The pre-pass then
receives a structural skeleton and annotates it, rather than identifying
chapter boundaries from source text.

Heuristics handle:
- Project Gutenberg boilerplate stripping (start/end markers).
- Table-of-contents detection and skipping (heading clusters with tiny
  gaps are TOC; real chapters are separated by thousands of characters).
- Chapter headings in multiple common forms (`CHAPTER I`, `CHAPTER 1.
  Loomings.`, etc.).
- Named front-matter sections (ETYMOLOGY, EXTRACTS, PREFACE, etc.).

Per-book overrides live in `books/<id>/split_config.json` if needed.
The default config handles both Moby Dick and Education correctly.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .artifacts import Book, write_json

# A "real" chapter heading has substantial prose after it before the next
# heading. TOC entries cluster much more tightly than this.
MIN_REAL_CHAPTER_GAP_CHARS = 800


@dataclass
class Chapter:
    id: str                  # "001", "002", ...
    kind: str                # "front" | "chapter" | "epilogue" | "part" | "prose"
    number: str | None       # "1" or "I" or None
    title: str               # heading text after the number (if any)
    raw_heading: str         # the heading line as it appears in source
    start: int               # char offset in stripped source
    end: int                 # char offset in stripped source
    text: str                # the chapter body (with heading line stripped)


@dataclass
class SplitConfig:
    # Project Gutenberg markers — everything before the start and after the
    # end is stripped as boilerplate.
    gutenberg_start: str = r"\*\*\*\s*START OF.*?\*\*\*"
    gutenberg_end: str = r"\*\*\*\s*END OF.*?\*\*\*"

    # Regex patterns for structural headings. Each must capture (number, title)
    # where number can be None. Flags: MULTILINE so ^/$ match line boundaries.
    # Leading whitespace tolerated (some books indent headings).
    heading_patterns: list[tuple[str, str]] = field(default_factory=lambda: [
        # `CHAPTER N. Title` (UPPERCASE) or `Chapter N Title` (Title case).
        # Lowercase-starting is prose line-wrap, never a heading.
        ("chapter",
         r"^[ \t]*(?:CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\.?[ \t]*(.*)$"),
        # Bare Roman-numeral chapters (The Great Gatsby, Treasure Island
        # within-part). Must be the whole line alone.
        ("chapter",
         r"^[ \t]*([IVXLCDM]{1,7})\.?[ \t]*$"),
        # Bare-number chapters.
        ("chapter",
         r"^[ \t]*(\d{1,3})\.?[ \t]*$"),
        # Front matter and epilogue: UPPERCASE or Title Case only.
        ("front",
         r"^[ \t]*(ETYMOLOGY|Etymology|EXTRACTS|Extracts|PREFACE|Preface|EDITOR'S PREFACE|Editor's Preface|FOREWORD|Foreword|INTRODUCTION|Introduction|PROLOGUE|Prologue)\b\.?[ \t]*(.*)$"),
        ("epilogue",
         r"^[ \t]*(EPILOGUE|Epilogue|AFTERWORD|Afterword|CONCLUSION|Conclusion)\b\.?[ \t]*(.*)$"),
        # PART/BOOK structural headings. Allows descriptive titles following
        # separators like `--` or `—` or `:` — e.g. "PART ONE--The Old
        # Buccaneer". Rejects inline prose references like "BOOK I.
        # (_Folio_), CHAPTER I. (_Sperm Whale_).—This whale..." by
        # disallowing commas and parentheses in the tail.
        ("part",
         r"^[ \t]*(BOOK|PART|Book|Part)\s+([IVXLCDM]+|\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\b[^,()\n]{0,60}$"),
    ])


def load_config(book_dir: Path) -> SplitConfig:
    """Load split config for a book. Looks for book_dir/split_config.json."""
    cfg_path = book_dir / "split_config.json"
    if not cfg_path.exists():
        return SplitConfig()
    overrides = json.loads(cfg_path.read_text())
    cfg = SplitConfig()
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def split_to_disk(book: Book) -> list[Chapter]:
    """Split a book and persist results to work/<book>/chapters.json and
    chapters/<id>.md files. Returns the chapters list.

    For .epub sources, delegates to `epub_reader.split_epub_to_disk` (which
    uses the EPUB spine directly and skips the regex splitter).
    """
    if book.source_path.suffix.lower() == ".epub":
        from .epub_reader import split_epub_to_disk
        manifest_chapters = split_epub_to_disk(book)
        # Shape a return value compatible with the text-path: build Chapter
        # objects from the on-disk chapter files.
        chapters: list[Chapter] = []
        for mc in manifest_chapters:
            cpath = book.work_dir / "chapters" / f"{mc['id']}.md"
            text = cpath.read_text() if cpath.exists() else ""
            chapters.append(Chapter(
                id=mc["id"], kind=mc["kind"], number=mc.get("number"),
                title=mc.get("title", ""),
                raw_heading=mc.get("raw_heading", ""),
                start=0, end=0, text=text,
            ))
        return chapters

    books_dir = book.source_path.parent
    config = load_config(books_dir)
    chapters = split_book(book.source_text, config=config)

    chapters_dir = book.work_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    # Write body-only per-chapter files. Heading/title metadata lives in
    # chapters.json so downstream stages (drafter, critic, reconsider,
    # validate) can read a chapter's source text without parsing a heading.
    for c in chapters:
        (chapters_dir / f"{c.id}.md").write_text(c.text + "\n")

    # Write the structural manifest with offsets + metadata.
    manifest = {
        "book_id": book.book_id,
        "total_chapters": len(chapters),
        "total_words": sum(len(c.text.split()) for c in chapters),
        "chapters": [
            {k: v for k, v in asdict(c).items() if k != "text"}
            for c in chapters
        ],
    }
    write_json(book.work_dir / "chapters.json", manifest)
    return chapters


def split_book(source: str, config: SplitConfig | None = None) -> list[Chapter]:
    """Split a book's source text into chapters."""
    if config is None:
        config = SplitConfig()

    stripped, strip_offset = _strip_gutenberg(source, config)
    matches = _find_heading_matches(stripped, config)
    matches = _drop_toc(matches)

    chapters: list[Chapter] = []
    for i, m in enumerate(matches):
        start = m["start"]
        end = matches[i + 1]["start"] if i + 1 < len(matches) else len(stripped)
        heading_line_end = stripped.find("\n", start)
        body_start = heading_line_end + 1 if heading_line_end != -1 else end
        title = m.get("title", "") or ""
        # If the heading line had no title (common in two-line chapter
        # formats), look forward for a probable title on the next non-empty
        # line. Bumps body_start past the title line so it doesn't end up in
        # the chapter body.
        if not title and m["kind"] == "chapter":
            title = _extract_title_from_next_lines(stripped, body_start)
            if title:
                idx = stripped.find(title, body_start, end)
                if idx != -1:
                    title_line_end = stripped.find("\n", idx)
                    body_start = (title_line_end + 1 if title_line_end != -1
                                  else body_start)
        body = stripped[body_start:end].strip()
        chapters.append(Chapter(
            id=f"{i + 1:03d}",
            kind=m["kind"],
            number=m.get("number"),
            title=title,
            raw_heading=m["raw"],
            start=start + strip_offset,
            end=end + strip_offset,
            text=body,
        ))

    # Drop chapters with negligible body — likely truncation artifacts
    # (e.g. a TOC entry for a chapter whose real content is missing) or
    # spurious matches. Real chapters can be as short as one speech
    # (e.g. Moby Dick Ch 122 "Midnight Aloft" is ~54 words), so keep the
    # threshold low; dedup-keep-last already handles most TOC residues.
    MIN_CHAPTER_WORDS = 30
    chapters = [c for c in chapters
                if len(c.text.split()) >= MIN_CHAPTER_WORDS]

    # Drop leading `chapter` entries that appear before any `front` section
    # (or before the first chapter with the lowest number). In a truncated
    # source, TOC entries for chapters whose real content is missing can
    # survive dedup; they sit in the TOC region, BEFORE the real front
    # matter or early chapters. Use position-based filtering to remove them.
    first_anchor_start = None
    for c in chapters:
        if c.kind == "front":
            first_anchor_start = c.start
            break
    if first_anchor_start is None:
        # No front matter — use the chapter with smallest number as anchor
        chapter_with_num = [c for c in chapters
                            if c.kind == "chapter" and c.number]
        if chapter_with_num:
            def _numeric(c):
                try:
                    return int(c.number) if c.number.isdigit() else 0
                except Exception:
                    return 0
            anchor = min(chapter_with_num, key=_numeric)
            first_anchor_start = anchor.start
    if first_anchor_start is not None:
        chapters = [c for c in chapters
                    if c.kind != "chapter" or c.start >= first_anchor_start]

    # Renumber IDs after filtering so they stay 001, 002, ... sequential.
    for i, c in enumerate(chapters):
        c.id = f"{i + 1:03d}"
    return chapters


def _strip_gutenberg(source: str, config: SplitConfig) -> tuple[str, int]:
    """Remove Gutenberg header/footer. Returns (stripped_source, offset_into_original)."""
    start_offset = 0
    end = len(source)
    m = re.search(config.gutenberg_start, source, re.IGNORECASE)
    if m:
        # Skip past the whole marker line
        line_end = source.find("\n", m.end())
        start_offset = line_end + 1 if line_end != -1 else m.end()
    m = re.search(config.gutenberg_end, source, re.IGNORECASE)
    if m:
        # Cut at the marker's start line
        line_start = source.rfind("\n", 0, m.start())
        end = line_start if line_start != -1 else m.start()
    return source[start_offset:end], start_offset


def _find_heading_matches(text: str, config: SplitConfig) -> list[dict[str, Any]]:
    """Scan text for heading matches; return sorted non-overlapping list."""
    hits: list[dict[str, Any]] = []
    seen: set[int] = set()
    for kind, pattern in config.heading_patterns:
        for m in re.finditer(pattern, text, flags=re.MULTILINE):
            if m.start() in seen:
                continue
            seen.add(m.start())
            groups = [g for g in m.groups() if g is not None]
            number = groups[0] if kind == "chapter" else None
            title = groups[-1].strip() if groups else ""
            if kind == "front":
                # front uses group 0 as name; keep it as the title
                title = groups[0].strip() if groups else m.group(0).strip()
                number = None
            if kind == "part":
                # part: groups = [PART|BOOK, number, title]
                number = groups[1] if len(groups) >= 2 else None
                title = groups[-1].strip() if len(groups) >= 3 else ""
            hits.append({
                "start": m.start(),
                "end": m.end(),
                "kind": kind,
                "number": number,
                "title": title,
                "raw": text[m.start():m.end()].strip(),
            })
    hits.sort(key=lambda h: h["start"])
    return hits


def _drop_toc(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TOC entries are duplicates of real content headings — the same text
    appears once in the TOC and again at the real chapter. Keep only the
    LAST occurrence of each heading (normalized by whitespace + case).

    After dedup, apply a gap-based safety filter: if any surviving match is
    separated from both its neighbors by less than the real-content
    threshold, drop it as a likely mention-in-text (e.g., a cross-reference
    inside a chapter body, not a real heading).
    """
    if not matches:
        return matches

    def _norm(s: str) -> str:
        # Strip punctuation too, so "EXTRACTS." == "EXTRACTS" and
        # "EXTRACTS (Supplied by a Sub-Sub-Librarian)." ==
        # "EXTRACTS. (Supplied by a Sub-Sub-Librarian)."
        s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
        return re.sub(r"\s+", " ", s).strip().upper()

    # Keep last occurrence per normalized heading.
    seen_last: dict[str, int] = {}
    for i, m in enumerate(matches):
        key = _norm(m["raw"])
        seen_last[key] = i
    kept = [matches[i] for i in sorted(seen_last.values())]

    # Safety filter: drop any match tightly surrounded on both sides
    # (possibly a chapter-cross-reference inside prose, not a real heading).
    # Parts are exempt — they're expected to be followed closely by their
    # first child chapter, which would otherwise make gap_next tiny.
    safe: list[dict[str, Any]] = []
    for i, m in enumerate(kept):
        if m.get("kind") == "part":
            safe.append(m)
            continue
        gap_next = (kept[i + 1]["start"] - m["end"]) if i + 1 < len(kept) else float("inf")
        gap_prev = (m["start"] - kept[i - 1]["end"]) if i > 0 else float("inf")
        if gap_next < MIN_REAL_CHAPTER_GAP_CHARS and gap_prev < MIN_REAL_CHAPTER_GAP_CHARS:
            continue
        safe.append(m)
    return safe


def _extract_title_from_next_lines(text: str, after_offset: int,
                                   max_lookahead: int = 400) -> str:
    """For books whose chapter title sits on the line after the heading
    (e.g. `CHAPTER I\\n\\nQUINCY (1838-1848)`), look forward a few lines for
    an all-caps or title-case line and use it as the title.
    """
    window = text[after_offset:after_offset + max_lookahead]
    for line in window.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Likely a title line: short, no trailing period, starts with a letter.
        if (len(stripped) < 120
                and not stripped.endswith(".")
                and stripped[0].isalpha()
                and stripped.upper() == stripped):
            return stripped
        # Otherwise we've hit actual prose — stop.
        break
    return ""
