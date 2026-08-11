"""Split over-long dialogue across linked balloons instead of losing it.

A prose line that will not fit one balloon has three possible fates: it can be
demoted to narration (which discards the character's actual words), paraphrased
(which costs an LLM call and risks the author's voice), or split across two
balloons from the same speaker — which is what a letterer actually does, and
which preserves the line exactly.

Splitting is tried first because it is free and lossless. Only lines that
cannot be made to fit this way need escalating to a paraphrase pass.

Break points, in order of preference:

1. Sentence boundaries. A speech of several sentences divides cleanly and needs
   no visual marker — the reader follows balloon to balloon.
2. Clause joints (commas, semicolons, dashes) within a single over-long
   sentence. These carry an ellipsis out of one balloon and into the next, the
   long-standing comics convention for a sentence continuing across a break.

A line with no usable joint is reported back unsplit, for the caller to
paraphrase or keep oversized.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# One speaker may hold at most this many balloons in a panel. Two keeps the art
# readable and matches the drafter's "prefer 0-2 balloons per panel" rule; a
# monologue needing more should be compressed, not stacked over the figure.
MAX_BALLOONS_PER_SPEAKER = 2

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Clause joints a letterer would break on. The lookbehinds keep the punctuation
# attached to the piece it belongs to, so rejoining with a space restores the
# original text exactly.
_CLAUSE_RE = re.compile(
    r"(?<=[,;:])\s+(?=\w)"          # comma, semicolon, colon
    r"|(?<=\S)\s+—\s+(?=\w)"        # em dash, spaced
    r"|(?<=\S)\s*--\s*(?=\w)"       # ASCII double hyphen
)

ELLIPSIS = "…"


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split())


def _units(text: str, limit: int) -> list[tuple[str, bool]] | None:
    """Break `text` into the smallest pieces worth keeping together.

    Each piece is paired with whether it ends a sentence, which decides later
    whether a break after it needs an ellipsis. Sentences that already fit are
    left whole — breaking them would be gratuitous.
    """
    units: list[tuple[str, bool]] = []
    for sentence in (s for s in _SENTENCE_RE.split(text) if s.strip()):
        if len(sentence) <= limit:
            units.append((sentence, True))
            continue
        clauses = [c for c in _CLAUSE_RE.split(sentence) if c and c.strip()]
        if len(clauses) < 2:
            # An over-long sentence with no joint cannot be split losslessly.
            return None
        for index, clause in enumerate(clauses):
            units.append((clause, index == len(clauses) - 1))
    return units or None


def _mark(parts: list[list[tuple[str, bool]]]) -> list[str]:
    """Join each part, carrying an ellipsis across mid-sentence breaks."""
    marked: list[str] = []
    for index, part in enumerate(parts):
        text = " ".join(piece for piece, _ends in part)
        if index and not parts[index - 1][-1][1]:
            text = ELLIPSIS + text
        if index < len(parts) - 1 and not part[-1][1]:
            text = text.rstrip(",;:") + ELLIPSIS
        marked.append(text)
    return marked


def _pack(units: list[tuple[str, bool]], width: int, max_parts: int) -> list[str] | None:
    """Greedily fill parts up to `width`, then check the marked result fits."""
    parts: list[list[tuple[str, bool]]] = [[]]
    for unit in units:
        current = parts[-1]
        candidate = len(" ".join(piece for piece, _ in [*current, unit]))
        if current and candidate > width:
            parts.append([unit])
            if len(parts) > max_parts:
                return None
        else:
            current.append(unit)
    if not parts[0]:
        return None
    marked = _mark(parts)
    return marked if all(len(part) <= width for part in marked) else None


def split_balloon_text(
    text: str,
    *,
    limit: int,
    max_parts: int = MAX_BALLOONS_PER_SPEAKER,
) -> list[str] | None:
    """Fit `text` into at most `max_parts` balloons of `limit` characters.

    Returns the balloon texts, or None when the line cannot be split to fit and
    must be paraphrased instead. The parts are as even as possible: the search
    runs from the narrowest width upward and stops at the first that works, so
    a two-sentence line breaks in the middle rather than leaving a stub.
    """
    normalized = _normalize(text)
    if not normalized:
        return None
    if len(normalized) <= limit:
        return [normalized]
    if max_parts < 2:
        return None

    units = _units(normalized, limit)
    if units is None:
        return None

    longest = max(len(piece) for piece, _ends in units)
    for width in range(longest, limit + 1):
        packed = _pack(units, width, max_parts)
        if packed:
            return packed
    return None


def _is_balloon(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and str(item.get("kind") or "").strip().lower() in {"speech", "thought"}
        and str(item.get("text") or "").strip()
    )


def split_panel_balloons(
    texts: list[dict[str, Any]],
    *,
    limit: int,
    capacity: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split over-long balloons in one panel, within its balloon budget.

    Returns the rewritten texts and the balloons that are still over-long — the
    ones a paraphrase pass would have to handle.

    A split costs the panel an extra balloon, so only one line per panel may
    take one. Panels are allowed `capacity + 1` balloons for that reason:
    `capacity` speakers can each still hold a balloon while one of them carries
    a line across two. The longest offender is split first, since it is the one
    most likely to overrun its balloon.
    """
    result = deepcopy(texts)
    over_long = [
        (index, item) for index, item in enumerate(result)
        if _is_balloon(item) and len(_normalize(item.get("text"))) > limit
    ]
    if not over_long:
        return result, []

    budget = capacity + 1 - sum(1 for item in result if _is_balloon(item))
    unfittable: list[dict[str, Any]] = []
    # Longest first; ties broken by position so the result is deterministic.
    replacements: dict[int, list[dict[str, Any]]] = {}
    for index, item in sorted(
        over_long, key=lambda pair: (-len(_normalize(pair[1].get("text"))), pair[0])
    ):
        parts = split_balloon_text(_normalize(item.get("text")), limit=limit) if budget > 0 else None
        if not parts or len(parts) < 2:
            unfittable.append(item)
            continue
        budget -= len(parts) - 1
        pieces: list[dict[str, Any]] = []
        for order, part in enumerate(parts):
            piece = deepcopy(item)
            piece["text"] = part
            # The layout recomputes zones, and a stale one would pin both halves
            # to the same spot.
            piece.pop("balloon_zone", None)
            piece["balloon_part"] = order + 1
            piece["balloon_parts"] = len(parts)
            pieces.append(piece)
        replacements[index] = pieces

    if not replacements:
        return result, unfittable

    rebuilt: list[dict[str, Any]] = []
    for index, item in enumerate(result):
        rebuilt.extend(replacements.get(index, [item]))
    return rebuilt, unfittable
