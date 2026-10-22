"""Text normalization + fuzzy matching for mechanical preservation checks.

Source text and drafts differ on many incidental features: Gutenberg uses
curly quotes, em-dashes, and `_word_` italics; drafts may use straight ASCII
punctuation and markdown `**emphasis**`. A normalization pass canonicalizes
those differences before any equality or substring check runs.

Matching tiers:
  - `normalize()` produces a canonical form for storage or naive substring.
  - `fuzzy_contains()` uses rapidfuzz partial_ratio; tolerates small drift.
  - `count_phrases()` returns the number of occurrences of a phrase, with
    fuzzy tolerance — suitable for motif concordance.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

# Character-level canonicalization. Maps source chars to a canonical form.
_CHAR_MAP: dict[str, str] = {
    "\u2018": "'", "\u2019": "'", "\u201A": "'", "\u201B": "'",
    "\u201C": '"', "\u201D": '"', "\u201E": '"', "\u201F": '"',
    "\u2014": "-", "\u2013": "-", "\u2012": "-", "\u2212": "-",
    "\u2026": "...",                 # single-char ellipsis -> three dots
    "\u00A0": " ",                    # non-breaking space
    "_": "",                          # Gutenberg italic markup
}

# Markdown emphasis tokens to strip (leave the word content intact).
_MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*", flags=re.DOTALL), r"\1"),  # **bold**
    (re.compile(r"\*(.+?)\*", flags=re.DOTALL), r"\1"),      # *italic*
    (re.compile(r"`([^`]+)`"), r"\1"),                         # `code`
    (re.compile(r"^#{1,6}\s+", flags=re.MULTILINE), ""),       # ## headings
]


def normalize(text: str, *, case_fold: bool = True) -> str:
    """Canonicalize text for mechanical comparison.

    Steps: Unicode NFKC, strip Markdown emphasis tokens, apply character
    map (quotes/dashes/underscores), collapse whitespace, optionally
    case-fold.
    """
    if not text:
        return ""
    # Unicode normalization
    out = unicodedata.normalize("NFKC", text)
    # Strip markdown markers (keeps the word content)
    for pattern, repl in _MARKDOWN_PATTERNS:
        out = pattern.sub(repl, out)
    # Character map: curly quotes, dashes, underscore italics
    out = "".join(_CHAR_MAP.get(ch, ch) for ch in out)
    # Collapse whitespace
    out = re.sub(r"\s+", " ", out).strip()
    if case_fold:
        out = out.casefold()
    return out


@dataclass
class MatchResult:
    present: bool
    score: int              # 0-100
    ambiguous: bool         # True when score is in the borderline band


def fuzzy_contains(
    needle: str,
    haystack: str,
    *,
    threshold: int = 85,
    ambiguous_band: int = 15,
    prefix_words: int | None = None,
) -> MatchResult:
    """Is `needle` present in `haystack` within fuzzy tolerance?

    Both sides are normalized (case-folded). Returns a score 0-100 from
    rapidfuzz.fuzz.partial_ratio. `present` is True when score >= threshold;
    `ambiguous` is True when threshold-ambiguous_band <= score < threshold,
    i.e. borderline cases worth flagging for LLM adjudication.

    `prefix_words` clips the needle to its first N words before matching —
    useful when the needle is a long `passage_hint` and we want to match on
    its opening rather than require the whole passage verbatim.
    """
    if not needle or not haystack:
        return MatchResult(present=False, score=0, ambiguous=False)
    norm_needle = normalize(needle)
    norm_haystack = normalize(haystack)
    if prefix_words is not None:
        norm_needle = " ".join(norm_needle.split()[:prefix_words])
    score = int(fuzz.partial_ratio(norm_needle, norm_haystack))
    present = score >= threshold
    ambiguous = (not present) and score >= (threshold - ambiguous_band)
    return MatchResult(present=present, score=score, ambiguous=ambiguous)


def count_phrases(
    phrase: str,
    text: str,
    *,
    threshold: int = 88,
) -> int:
    """Count non-overlapping fuzzy occurrences of `phrase` in `text`.

    Scans word-by-word over the normalized text with a window the size of
    the normalized phrase's token count. Counts windows whose score >=
    threshold, then skips ahead by the window size to avoid double-counting
    adjacent matches.

    Suitable for motif concordance — phrases are typically 1-4 words and we
    want a frequency, not a single hit.
    """
    if not phrase or not text:
        return 0
    needle_tokens = normalize(phrase).split()
    if not needle_tokens:
        return 0
    haystack_tokens = normalize(text).split()
    n = len(needle_tokens)
    needle_joined = " ".join(needle_tokens)
    count = 0
    i = 0
    while i <= len(haystack_tokens) - n:
        window = " ".join(haystack_tokens[i:i + n])
        score = int(fuzz.ratio(needle_joined, window))
        if score >= threshold:
            count += 1
            i += n
        else:
            i += 1
    return count
