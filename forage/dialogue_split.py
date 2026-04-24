"""Post-hoc dialogue paragraph splitter.

Under compression pressure the drafter (GPT-5) sometimes concatenates multiple
dialogue turns into a single paragraph, losing the standard fiction convention
that each new speaker's turn gets its own paragraph. This module detects such
cases and splits them conservatively — only where a new speaker is clearly
unambiguous.

Split rules (within a single paragraph only):

  A. Directly adjacent quoted turns — closing-terminal-quote + whitespace +
     opening-quote, with nothing between. Always a speaker change.

  B. Closing-terminal-quote + short attribution (<=120 chars, contains a
     speaker verb like said/replied/asked, ends with terminal punctuation) +
     opening-quote. Safe signal of speaker change.

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

SPEAKER_VERBS = (
    r"said|replied|answered|asked|whispered|murmured|added|continued|"
    r"went\s+on|remarked|shouted|yelled|hissed|breathed|exclaimed|"
    r"interrupted|muttered|laughed|cried|responded|protested|demanded|"
    r"retorted|insisted|declared|agreed|admitted|confessed|sighed|"
    r"grumbled|snapped|stammered|repeated|pressed|nodded|began|spoke|"
    r"told\s+me|told\s+him|told\s+her|called|returned|put\s+in|"
    r"observed|went\s+on|ventured|volunteered|mused|teased|conceded|"
    r"reminded|suggested|pointed\s+out|objected"
)

# Rule A: closing-terminal-quote + whitespace + opening-quote.
RULE_A = re.compile(
    rf"({TERM_PUNCT}{CLOSE_Q})(\s+)({OPEN_Q})"
)

# Rule B: closing-quote (comma or terminal punct) + short attribution
# (contains a speaker verb, ends with terminal punct) + opening-quote.
RULE_B = re.compile(
    rf"([,{TERM_PUNCT[1:-1]}]{CLOSE_Q})"
    rf"(\s+[^\u201c\u201d\"\n]{{1,120}}?\b(?:{SPEAKER_VERBS})\b[^\u201c\u201d\"\n]{{0,100}}?{TERM_PUNCT})"
    rf"(\s+)({OPEN_Q})"
)


def split_dialogue_paragraphs(text: str) -> tuple[str, int]:
    """Return (modified_text, split_count). Only splits within paragraphs
    (inputs already separated by blank lines). Conservative — see module
    docstring."""
    paragraphs = re.split(r"\n\s*\n", text)
    total_splits = 0
    new_paragraphs: list[str] = []

    for para in paragraphs:
        if not para.strip():
            continue
        original = para
        # Apply Rule B first (longer patterns) then Rule A.
        # Rule B: insert break before the opening quote; keep attribution
        # with the preceding quote.
        para = RULE_B.sub(lambda m: f"{m.group(1)}{m.group(2)}\n\n{m.group(4)}", para)
        # Rule A: insert break between adjacent quotes.
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
