"""Book-level critic: per-synopsis-sentence verification of the abridgment.

For each of the ~15 sentences in `work/<book>/book_synopsis.md`, checks
whether the assembled abridgment contains evidence of that plot claim.
Each sentence is classified `present | missing | distorted`. Any `missing`
or `distorted` → verdict `hold`; all-present → `ship`.

Runs against `abridgment.md` when present; falls back to a concatenation
of `segments/NNN.md` with a [PARTIAL] marker so it can run mid-pipeline.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from .artifacts import Book
from .llm import complete
from .prompts import load_prompt

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_array(text: str) -> list:
    s = text.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        result = json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("["), s.rfind("]")
        if start < 0 or end < 0:
            raise
        result = json.loads(s[start:end + 1])
    if not isinstance(result, list):
        raise ValueError(f"expected JSON array, got {type(result).__name__}")
    return result


def _read_abridgment(book: Book) -> tuple[str, bool]:
    """Return (text, is_partial). Prefers assemble's `abridgment.md`; falls
    back to concat of per-segment drafts with is_partial=True.
    """
    abr = book.work_dir / "abridgment.md"
    if abr.exists():
        return abr.read_text(), False
    seg_dir = book.work_dir / "segments"
    parts = []
    for p in sorted(seg_dir.glob("[0-9]*.md")):
        t = p.read_text().strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts), True


def _split_synopsis_sentences(text: str) -> list[str]:
    """Parse the synopsis into individual sentences.

    Handles both formats the summarizer produces:
      - one sentence per line (from the merge step of chunked synopses)
      - one paragraph of prose (from single-call whole-book summaries)

    Leading numeric prefixes like "1. " are stripped.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        # Sentence-per-line format.
        return [re.sub(r"^\d+\.\s*", "", ln) for ln in lines]
    if not lines:
        return []
    # Paragraph format — split on sentence boundaries. The lookbehind for
    # terminal punctuation + lookahead for a capital / opening quote
    # tolerates ". She" and '." The' without over-splitting on abbreviations
    # like "Dr. Smith" (which would need a capital after the space — true —
    # but abbreviations in prose synopses are rare enough that this is
    # acceptably accurate).
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\u201C])', lines[0])
    return [re.sub(r"^\d+\.\s*", "", s).strip() for s in sentences if s.strip()]


def run_book_critic(book: Book) -> dict:
    synopsis_path = book.work_dir / "book_synopsis.md"
    if not synopsis_path.exists():
        raise FileNotFoundError(
            f"no book_synopsis.md — run `forage summarize {book.book_id}` first")
    sentences = _split_synopsis_sentences(synopsis_path.read_text())
    if not sentences:
        raise RuntimeError(f"no sentences parsed from {synopsis_path}")

    abridgment, is_partial = _read_abridgment(book)
    if not abridgment.strip():
        raise RuntimeError(
            f"no abridgment content — run `forage draft {book.book_id}` first")

    partial_note = (
        "**Note:** the abridgment is PARTIAL — some chapters may not "
        "yet be drafted. Missing material in the partial may reflect "
        "incompleteness rather than preservation failures; note this in "
        "the `note` field for any missing sentence whose content would "
        "plausibly appear in an undrafted chapter."
        if is_partial else "")

    prompt = load_prompt("critic_book")
    rendered = prompt.render(
        sentences=sentences,
        partial_note=partial_note,
        abridgment=abridgment,
    )
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-sonnet-4-6"),
        max_tokens=prompt.config.get("max_tokens", 8000),
        cache=False,
        work_dir=book.work_dir,
        stage=f"critic:book:{book.book_id}",
    )

    verdicts = _parse_json_array(resp.text)
    counts = Counter(v.get("status", "?") for v in verdicts)
    verdict = ("ship"
               if counts.get("missing", 0) == 0 and counts.get("distorted", 0) == 0
               else "hold")

    result = {
        "book_id": book.book_id,
        "verdict": verdict,
        "is_partial": is_partial,
        "synopsis_sentence_count": len(sentences),
        "counts": dict(counts),
        "findings": verdicts,
    }
    (book.work_dir / "book_critic.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result
