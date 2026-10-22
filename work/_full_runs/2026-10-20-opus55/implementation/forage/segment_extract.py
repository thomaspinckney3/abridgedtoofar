"""Locate a segment's source text from the plan's start/end hints.

Gutenberg-style sources use curly quotes, em-dashes, and `_word_` italics
while LLM-emitted hints tend to be ASCII. Both get canonicalized before
matching, and a norm-index -> original-index mapping carries us back to
the real offsets for slicing.
"""

from __future__ import annotations

from rapidfuzz import fuzz

# Character-level canonicalization. Maps each source char to a canonical form
# (possibly empty) used only for matching.
_CHAR_MAP: dict[str, str] = {
    "\u2018": "'", "\u2019": "'",            # curly singles
    "\u201C": '"', "\u201D": '"',            # curly doubles
    "\u2014": "-", "\u2013": "-",            # em/en dashes
    "_": "",                                  # Gutenberg italic markup
}


def _canon_char(ch: str) -> str:
    return _CHAR_MAP.get(ch, ch)


def _normalize(text: str) -> tuple[str, list[int]]:
    """Canonicalize punctuation, strip underscore italics, collapse whitespace.

    Returns the normalized string and a mapping norm_idx -> original_idx.
    """
    out: list[str] = []
    mapping: list[int] = []
    prev_space = True  # swallow leading whitespace
    for i, ch in enumerate(text):
        canon = _canon_char(ch)
        if canon == "":
            continue
        if canon.isspace():
            if prev_space:
                continue
            out.append(" ")
            mapping.append(i)
            prev_space = True
        else:
            out.append(canon)
            mapping.append(i)
            prev_space = False
    return "".join(out), mapping


def extract_segment(
    source: str,
    start_hint: str,
    end_hint: str,
    *,
    search_from: int = 0,
) -> tuple[str, int]:
    """Return (text, end_offset). `search_from` is an offset into *source*.

    Only the first occurrence at or after `search_from` is considered, so
    callers that process segments in order can pass the previous segment's
    end_offset to defend against hints that happen to match earlier in the book.

    Raises ValueError if either hint is not found after `search_from`.
    """
    norm, mapping = _normalize(source)
    norm_start_hint, _ = _normalize(start_hint)
    norm_end_hint, _ = _normalize(end_hint)

    # Translate `search_from` (original offset) to a normalized offset.
    norm_search_from = 0
    while norm_search_from < len(mapping) and mapping[norm_search_from] < search_from:
        norm_search_from += 1

    si = _find_hint(norm, norm_start_hint, norm_search_from)
    if si is None:
        raise ValueError(f"start hint not found after offset {search_from}: "
                         f"{norm_start_hint[:60]!r}")
    start_len = si[1]
    si = si[0]

    after_start = si + start_len
    ei = _find_hint(norm, norm_end_hint, after_start)
    if ei is None:
        raise ValueError(f"end hint not found after start: "
                         f"{norm_end_hint[:60]!r}")
    end_len = ei[1]
    ei = ei[0]

    orig_start = mapping[si]
    orig_end = mapping[ei + end_len - 1] + 1
    return source[orig_start:orig_end], orig_end


def _find_hint(haystack: str, needle: str, from_offset: int) -> tuple[int, int] | None:
    """Locate `needle` in `haystack` starting at or after `from_offset`.

    Returns (position, matched_length) on success, None on failure. Tries:
      1. Exact substring match (fast path — most hints are clean).
      2. Prefix match — first 8 words of needle as a substring.
      3. Fuzzy match on the prefix — rapidfuzz partial_ratio ≥ 88 across a
         sliding window. Rescues hints the LLM slightly paraphrased.
    """
    # Tier 1: exact
    pos = haystack.find(needle, from_offset)
    if pos >= 0:
        return (pos, len(needle))

    # Tier 2: prefix substring (first 8 words)
    prefix_tokens = needle.split()[:8]
    if not prefix_tokens:
        return None
    prefix = " ".join(prefix_tokens)
    pos = haystack.find(prefix, from_offset)
    if pos >= 0:
        return (pos, len(prefix))

    # Tier 3: fuzzy match on the prefix across windows of haystack
    window_len = len(prefix)
    if window_len < 8:
        return None  # too short to fuzzy match safely
    best_score = 0
    best_pos = -1
    # Sample windows at word boundaries to keep this fast; ~ every 4 words.
    step = max(1, len(prefix_tokens))  # ~ step by needle length in tokens
    i = from_offset
    while i < len(haystack) - window_len:
        window = haystack[i:i + window_len + 30]  # small tail tolerance
        score = fuzz.partial_ratio(prefix, window)
        if score > best_score:
            best_score = score
            best_pos = i
            if score == 100:
                break
        # advance by a word
        nxt = haystack.find(" ", i + step)
        if nxt < 0:
            break
        i = nxt + 1
    if best_score >= 88 and best_pos >= 0:
        return (best_pos, window_len)
    return None


def extract_all(source: str, segments: list[dict]) -> dict[str, dict]:
    """Extract source text for every segment in order with a monotone cursor.

    Returns a dict keyed by segment id with fields:
      - text: extracted source (or None if extraction failed)
      - error: error message if extraction failed, else None
      - word_count: len(text.split()) if extracted
      - start_offset, end_offset: absolute offsets in `source`
    """
    results: dict[str, dict] = {}
    cursor = 0
    for s in segments:
        sid = s["id"]
        try:
            text, end = extract_segment(
                source,
                s["source_start_hint"],
                s["source_end_hint"],
                search_from=cursor,
            )
            # Find original start offset (recompute; cheap for small segments).
            norm_source, mapping = _normalize(source[cursor:])
            ns, _ = _normalize(s["source_start_hint"])
            offs_in_substr = norm_source.find(ns)
            start_offset = cursor + mapping[offs_in_substr] if offs_in_substr >= 0 else cursor
            results[sid] = {
                "text": text,
                "error": None,
                "word_count": len(text.split()),
                "start_offset": start_offset,
                "end_offset": end,
            }
            cursor = end
        except ValueError as e:
            results[sid] = {
                "text": None,
                "error": str(e),
                "word_count": 0,
                "start_offset": None,
                "end_offset": None,
            }
            # Cursor unchanged — next segment searches from same position.
    return results
