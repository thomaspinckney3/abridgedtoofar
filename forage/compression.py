"""Target word count computation per the spec's compression schedule."""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_SOURCE_WORDS = 24_000
MAX_SOURCE_WORDS = 600_000
MIN_OUTPUT_WORDS = 12_000
MAX_OUTPUT_WORDS = 60_000
WPM = 200  # operational proxy


@dataclass
class CompressionPlan:
    source_words: int
    target_words: int
    target_hours: float
    ratio: float
    refusal: str | None = None  # None, "too-short", or "too-long"


def count_words(text: str) -> int:
    return len(text.split())


def plan_compression(source_words: int) -> CompressionPlan:
    if source_words < MIN_SOURCE_WORDS:
        return CompressionPlan(source_words, 0, 0.0, 0.0,
                               refusal="too-short")
    if source_words > MAX_SOURCE_WORDS:
        return CompressionPlan(source_words, 0, 0.0, 0.0,
                               refusal="too-long")

    # Log-scaled reading time: 1h at 24k words → 5h at 600k words.
    span = math.log(MAX_SOURCE_WORDS / MIN_SOURCE_WORDS)
    frac = math.log(source_words / MIN_SOURCE_WORDS) / span
    target_hours = max(1.0, min(5.0, 1.0 + 4.0 * frac))
    target_words = int(round(target_hours * WPM * 60))

    # Clamp to valid output window: [max(12k, S/10), min(60k, S/2)].
    lo = max(MIN_OUTPUT_WORDS, source_words // 10)
    hi = min(MAX_OUTPUT_WORDS, source_words // 2)
    target_words = max(lo, min(hi, target_words))

    ratio = source_words / target_words
    return CompressionPlan(source_words, target_words, target_hours, ratio)
