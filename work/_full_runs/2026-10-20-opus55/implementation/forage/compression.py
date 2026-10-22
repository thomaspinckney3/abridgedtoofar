"""Target word count computation: strict 2× ratio against full source."""

from __future__ import annotations

from dataclasses import dataclass

MIN_SOURCE_WORDS = 24_000
MAX_SOURCE_WORDS = 600_000
WPM = 200  # operational proxy
RATIO = 2.0  # source/target — applies against full source incl. cut chapters


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

    target_words = int(source_words / RATIO)
    target_hours = target_words / (WPM * 60)
    return CompressionPlan(source_words, target_words, target_hours, RATIO)
