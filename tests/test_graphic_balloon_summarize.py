"""Tests for the last-resort compression of unletterable dialogue.

No test here calls a model. The stage is exercised through `apply_compressions`
with canned responses, which is where every decision that can put words in a
character's mouth actually lives.

The validation tests carry the weight: compression is the only lossy step in
the fitting chain, so a bad response has to degrade to "leave the line alone"
rather than reach the page.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.apply_graphic_lettering_policy import MAX_BALLOON_CHARS
from scripts.graphic_balloon_summarize import (
    apply_compressions,
    collect_oversized,
    validate_compression,
)

LIMIT = MAX_BALLOON_CHARS

# Too long for one balloon, and no clause joint that lets it break into two.
UNSPLITTABLE = (
    "I have been telling you for the better part of an hour that the arrangement "
    "was never mine to make in the first place whatever he may claim about it now"
)
# Long, but breaks cleanly at a sentence boundary.
SPLITTABLE = (
    "Terrible place. It does her good to get away. Wilson thinks she's visiting "
    "her sister—he's so dumb he doesn't know he's alive."
)


def _storyboard(*texts: dict[str, Any]) -> dict[str, Any]:
    return {"pages": [{"page_number": 1, "panels": [
        {"panel_number": 1, "texts": list(texts)},
    ]}]}


def _speech(text: str, speaker: str = "Tom") -> dict[str, Any]:
    return {"kind": "speech", "speaker": speaker, "text": text}


# --- only genuinely unletterable lines are sent -----------------------------


def test_a_splittable_line_is_never_sent_for_compression() -> None:
    """Splitting is lossless and free, so it must win before anything is paid
    for — a line that can be broken across balloons is not a candidate."""
    targets = collect_oversized(_storyboard(_speech(SPLITTABLE)))

    assert targets == []


def test_a_line_that_already_fits_is_never_sent() -> None:
    assert collect_oversized(_storyboard(_speech("Come on then."))) == []


def test_an_unsplittable_line_is_collected_with_its_location() -> None:
    targets = collect_oversized(_storyboard(
        {"kind": "caption", "text": "The hall was quiet."},
        _speech(UNSPLITTABLE, speaker="Daisy"),
    ))

    assert len(targets) == 1
    assert targets[0]["speaker"] == "Daisy"
    assert targets[0]["text_index"] == 1
    assert targets[0]["id"] == "p1.panel1.text1"


def test_captions_are_never_collected() -> None:
    """Captions are narration and are not balloon-constrained."""
    assert collect_oversized(_storyboard({"kind": "caption", "text": UNSPLITTABLE})) == []


# --- validation: a bad answer must never reach the page ---------------------


def test_a_compression_that_still_overflows_is_rejected() -> None:
    reason = validate_compression(UNSPLITTABLE, UNSPLITTABLE, limit=LIMIT)

    assert reason and "over the" in reason


def test_an_invented_name_is_rejected() -> None:
    """The failure that matters most: putting a person into the book who was
    never in the line."""
    reason = validate_compression(
        "I told him the arrangement was never mine to make in the first place.",
        "Gatsby says the arrangement was never mine to make.",
        limit=LIMIT,
    )

    assert reason and "introduces names" in reason
    assert "gatsby" in reason


def test_a_name_already_in_the_line_is_allowed() -> None:
    assert validate_compression(
        "I told Gatsby the arrangement was never mine to make in the first place.",
        "Gatsby, the arrangement was never mine to make.",
        limit=LIMIT,
    ) is None


def test_a_sentence_opening_word_is_not_mistaken_for_a_name() -> None:
    """"Terrible" opens the sentence; capitalization there names nobody."""
    assert validate_compression(
        "It does her good to get away from that terrible place by the ashheaps.",
        "Terrible place. It does her good to get away.",
        limit=LIMIT,
    ) is None


@pytest.mark.parametrize("compressed", [
    # The live run rejected this real compression of Daisy's monologue because
    # "I'm" reduced to an "i'm" token the original's words could never match.
    "Tom was God knows where. I'm glad it's a girl—I hope she'll be a beautiful little fool.",
    "I'm glad it's a girl.",
    "It's her grave, and I won't forget.",
])
def test_a_contraction_is_not_mistaken_for_an_invented_name(compressed: str) -> None:
    original = (
        "She was less than an hour old and Tom was God knows where. I woke out of "
        "the ether and wept. I'm glad it's a girl. I hope she'll be a fool — the "
        "best thing a girl can be in this world. A beautiful little fool. It's her "
        "mother's grave and I won't forget."
    )

    assert validate_compression(original, compressed, limit=LIMIT) is None


def test_invention_is_still_caught_after_the_contraction_fix() -> None:
    """The loosened matching must not open a hole for a real invented name."""
    reason = validate_compression(
        "She was less than an hour old and Tom was God knows where.",
        "Gatsby was God knows where.",
        limit=LIMIT,
    )

    assert reason and "gatsby" in reason


@pytest.mark.parametrize("returned", ["", "   "])
def test_an_empty_compression_is_rejected(returned: str) -> None:
    assert validate_compression(UNSPLITTABLE, returned, limit=LIMIT) == "empty"


def test_an_unchanged_line_is_rejected() -> None:
    assert validate_compression("Come on then.", "come on then.", limit=LIMIT) == "unchanged"


# --- applying results -------------------------------------------------------


def _apply(returned: dict[str, Any], line: str = UNSPLITTABLE):
    storyboard = _storyboard(_speech(line))
    targets = collect_oversized(storyboard)
    return apply_compressions(storyboard, targets, {targets[0]["id"]: returned})


def test_an_accepted_compression_is_applied_and_stays_auditable() -> None:
    data, report = _apply({
        "id": "p1.panel1.text0", "kind": "speech",
        "text": "The arrangement was never mine to make.",
        "dropped": "cut the hour-long preamble",
    })
    item = data["pages"][0]["panels"][0]["texts"][0]

    assert item["text"] == "The arrangement was never mine to make."
    # The original survives on the item so the loss can be reviewed later.
    assert item["summarized_from"] == UNSPLITTABLE
    assert item["lettering_notes"] == "cut the hour-long preamble"
    assert len(report["applied"]) == 1 and not report["rejected"]


def test_a_rejected_compression_leaves_the_line_untouched() -> None:
    data, report = _apply({
        "id": "p1.panel1.text0", "kind": "speech",
        "text": "Gatsby said the arrangement was never mine to make.",
    })
    item = data["pages"][0]["panels"][0]["texts"][0]

    assert item["text"] == UNSPLITTABLE, "an invented name must not reach the page"
    assert "summarized_from" not in item
    assert len(report["rejected"]) == 1
    assert "introduces names" in report["rejected"][0]["reason"]


def test_a_missing_response_leaves_the_line_untouched() -> None:
    storyboard = _storyboard(_speech(UNSPLITTABLE))
    targets = collect_oversized(storyboard)

    data, report = apply_compressions(storyboard, targets, {})

    assert data == storyboard
    assert report["rejected"][0]["reason"] == "no response for this line"


def test_an_actionless_line_becomes_narration() -> None:
    """The prompt may judge a line to be pure atmosphere; it then stops being
    speech rather than becoming a balloon that says nothing."""
    data, report = _apply({
        "id": "p1.panel1.text0", "kind": "caption",
        "text": "He went on about the arrangement for the better part of an hour.",
    })
    item = data["pages"][0]["panels"][0]["texts"][0]

    assert item["kind"] == "caption"
    assert "speaker" not in item
    assert item["caption_zone"] == "top_left"
    assert report["applied"][0]["kind"] == "caption"


def test_an_unknown_kind_falls_back_to_speech() -> None:
    data, _ = _apply({
        "id": "p1.panel1.text0", "kind": "shout",
        "text": "The arrangement was never mine to make.",
    })

    assert data["pages"][0]["panels"][0]["texts"][0]["kind"] == "speech"


def test_the_compressed_result_is_letterable() -> None:
    """The whole point: what comes out must actually fit a balloon."""
    data, _ = _apply({
        "id": "p1.panel1.text0", "kind": "speech",
        "text": "The arrangement was never mine to make.",
    })

    assert len(data["pages"][0]["panels"][0]["texts"][0]["text"]) <= LIMIT
