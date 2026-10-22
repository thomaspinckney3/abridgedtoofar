"""Post-hoc dialogue paragraph splitter.

Under compression pressure the drafter sometimes concatenates multiple
dialogue turns into a single paragraph, losing the standard fiction convention
that each new speaker's turn gets its own paragraph. This module detects such
cases and splits them — but only where a new speaker is unambiguous.

Split rule (within a single paragraph only):

  Directly adjacent quoted turns — closing-terminal-quote + whitespace +
  opening-quote, with nothing between. This pattern can only mean a speaker
  change, so it's always safe to split.

An earlier version of this module also had a Rule B that split on
`"A." attribution. "B."` patterns where the attribution ended in a period.
That rule over-split same-speaker continuations (e.g. Gatsby's *"We don't
know each other very well, Nick," she said suddenly. "Even if we are
cousins…"* — Daisy continuing in one paragraph, not two speakers), so it
was removed. Same-speaker continuations with mid-attribution are
linguistically ambiguous without reading context; leaving them alone is
safer than breaking them.

The splitter never breaks across paragraph boundaries (inputs are already
split on blank lines).
"""

from __future__ import annotations

import re
from pathlib import Path

# Curly and straight quote characters.
CLOSE_Q = r"[\u201d\"]"
OPEN_Q = r"[\u201c\"]"
TERM_PUNCT = r"[.!?]"

# Rule A: closing-terminal-quote + whitespace + opening-quote.
RULE_A = re.compile(
    rf"({TERM_PUNCT}{CLOSE_Q})(\s+)({OPEN_Q})"
)


def split_dialogue_paragraphs(text: str) -> tuple[str, int]:
    """Return (modified_text, split_count). Only splits within paragraphs
    (inputs already separated by blank lines). See module docstring."""
    paragraphs = re.split(r"\n\s*\n", text)
    total_splits = 0
    new_paragraphs: list[str] = []

    for para in paragraphs:
        if not para.strip():
            continue
        original = para
        # Rule A: insert break between directly adjacent quotes.
        para = RULE_A.sub(lambda m: f"{m.group(1)}\n\n{m.group(3)}", para)
        if para != original:
            total_splits += para.count("\n\n") - original.count("\n\n")
        new_paragraphs.append(para)

    return "\n\n".join(new_paragraphs) + ("\n" if text.endswith("\n") else ""), total_splits


def split_file(path: Path) -> int:
    """Rewrite the file with dialogue paragraphs split. Returns count of
    splits introduced."""
    text = path.read_text()
    new_text, n = split_dialogue_paragraphs(text)
    if n > 0:
        path.write_text(new_text)
    return n


def split_book_drafts(book_work_dir: Path) -> dict:
    """Split dialogue in every NNN.md draft under work/<book>/segments/ and
    the assembled abridgment.md if present. Returns a summary dict."""
    seg_dir = book_work_dir / "segments"
    drafts = sorted(seg_dir.glob("[0-9][0-9][0-9].md"))
    per_file: dict[str, int] = {}
    total = 0
    for p in drafts:
        n = split_file(p)
        per_file[p.name] = n
        total += n
    abr = book_work_dir / "abridgment.md"
    abr_splits = split_file(abr) if abr.exists() else 0
    return {
        "drafts_total_splits": total,
        "abridgment_splits": abr_splits,
        "per_file": {k: v for k, v in per_file.items() if v > 0},
    }
