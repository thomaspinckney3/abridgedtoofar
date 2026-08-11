"""Tests for splitting over-long dialogue across linked balloons.

The point of splitting is that it is *lossless*: unlike demoting a line to
reported narration or paraphrasing it, every word the character said survives.
The round-trip tests below are the ones that matter — they assert that claim
directly against real dialogue rather than trusting the split logic by eye.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.apply_graphic_lettering_policy import MAX_BALLOON_CHARS
from scripts.graphic_balloon_split import (
    ELLIPSIS,
    MAX_BALLOONS_PER_SPEAKER,
    split_balloon_text,
    split_panel_balloons,
)

LIMIT = MAX_BALLOON_CHARS


def _rejoin(parts: list[str]) -> str:
    """Undo the visual break marks, recovering the spoken line."""
    return " ".join(part.strip(ELLIPSIS) for part in parts).strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


# --- the core property: nothing is lost -------------------------------------


@pytest.mark.parametrize("line", [
    "Terrible place. It does her good to get away. Wilson thinks she's visiting "
    "her sister—he's so dumb he doesn't know he's alive.",
    "You did it, Tom. I know you didn't mean to, but you did. That's what I get "
    "for marrying a brute of a hulking man.",
    "Whenever you feel like criticizing anyone, just remember that not all the "
    "people in this world have had your advantages.",
    "Don't talk. Tom's got some woman in New York. She might have the decency "
    "not to telephone him at dinner time.",
])
def test_splitting_preserves_every_word(line: str) -> None:
    parts = split_balloon_text(line, limit=LIMIT)

    assert parts is not None, "expected this line to split"
    assert _words(_rejoin(parts)) == _words(line)


@pytest.mark.parametrize("line", [
    "Terrible place. It does her good to get away. Wilson thinks she's visiting "
    "her sister—he's so dumb he doesn't know he's alive.",
    "Whenever you feel like criticizing anyone, just remember that not all the "
    "people in this world have had your advantages.",
])
def test_every_part_fits_the_balloon(line: str) -> None:
    parts = split_balloon_text(line, limit=LIMIT)

    assert parts is not None
    assert all(len(part) <= LIMIT for part in parts)
    assert len(parts) <= MAX_BALLOONS_PER_SPEAKER


def test_the_whole_corpus_splits_losslessly_or_not_at_all() -> None:
    """No line may come back from the splitter having quietly lost words."""
    checked = 0
    for path in sorted(Path("work").rglob("storyboard.json")):
        try:
            storyboard = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for page in storyboard.get("pages") or []:
            for panel in page.get("panels") or []:
                items = list(panel.get("dialogue") or [])
                items += [
                    item for item in (panel.get("texts") or [])
                    if str(item.get("kind") or "").lower() in {"speech", "thought"}
                ]
                for item in items:
                    line = " ".join(str(item.get("text") or "").split())
                    if not line:
                        continue
                    parts = split_balloon_text(line, limit=LIMIT)
                    if parts is None:
                        continue
                    checked += 1
                    assert _words(_rejoin(parts)) == _words(line), line
                    assert all(len(part) <= LIMIT for part in parts)
    assert checked, "expected some storyboard dialogue to exercise this"


# --- where the breaks land --------------------------------------------------


def test_a_line_that_already_fits_is_left_alone() -> None:
    assert split_balloon_text("Come on then.", limit=LIMIT) == ["Come on then."]


def test_sentence_breaks_need_no_ellipsis() -> None:
    line = ("I've gotten to be a terrible pessimist. Have you read The Rise of "
            "the Coloured Empires, by this man Goddard?")

    parts = split_balloon_text(line, limit=LIMIT)

    assert parts == [
        "I've gotten to be a terrible pessimist.",
        "Have you read The Rise of the Coloured Empires, by this man Goddard?",
    ]
    assert not any(ELLIPSIS in part for part in parts)


def test_a_mid_sentence_break_carries_an_ellipsis_both_ways() -> None:
    line = ("Whenever you feel like criticizing anyone, just remember that not "
            "all the people in this world have had your advantages.")

    parts = split_balloon_text(line, limit=LIMIT)

    assert parts is not None and len(parts) == 2
    assert parts[0].endswith(ELLIPSIS)
    assert parts[1].startswith(ELLIPSIS)
    # The comma is replaced by the ellipsis rather than left dangling before it.
    assert not parts[0].rstrip(ELLIPSIS).endswith(",")


def test_breaks_are_balanced_rather_than_leaving_a_stub() -> None:
    """Greedy packing would leave "I always do." alone in a second balloon."""
    line = ("In two weeks it'll be the longest day in the year. Do you always "
            "watch for it and then miss it? I always do.")

    parts = split_balloon_text(line, limit=LIMIT)

    assert parts is not None and len(parts) == 2
    shortest, longest = sorted(len(part) for part in parts)
    assert shortest > 20, f"one balloon left as a stub: {parts}"
    assert longest <= LIMIT


# --- when splitting cannot help --------------------------------------------


def test_a_long_sentence_with_no_joint_cannot_be_split() -> None:
    line = "I have been telling you for the better part of an hour that " + "x" * 60

    assert split_balloon_text(line, limit=LIMIT) is None


def test_a_monologue_needing_more_balloons_than_allowed_is_refused() -> None:
    """Daisy's 302-character speech needs five balloons; the budget allows two,
    so it is handed back for paraphrase rather than silently overflowing."""
    line = (
        "She was less than an hour old and Tom was God knows where. I woke out "
        "of the ether, asked if it was a boy or a girl — and turned my head away "
        "and wept. 'All right,' I said. 'I'm glad it's a girl. And I hope she'll "
        "be a fool — that's the best thing a girl can be in this world. A "
        "beautiful little fool.'"
    )

    assert split_balloon_text(line, limit=LIMIT) is None
    assert split_balloon_text(line, limit=LIMIT, max_parts=5) is not None


def test_empty_text_is_refused() -> None:
    assert split_balloon_text("   ", limit=LIMIT) is None


# --- panel-level budgeting --------------------------------------------------


def _panel_texts(*speech: tuple[str, str]) -> list[dict[str, str]]:
    return [
        {"kind": "speech", "speaker": who, "text": what, "balloon_zone": "top_left"}
        for who, what in speech
    ]


def test_a_split_line_is_marked_and_loses_its_stale_zone() -> None:
    texts = _panel_texts(
        ("Tom", "Terrible place. It does her good to get away. Wilson thinks "
                "she's visiting her sister—he's so dumb he doesn't know he's alive."),
    )

    result, unfittable = split_panel_balloons(texts, limit=LIMIT, capacity=2)

    assert unfittable == []
    assert [item["balloon_part"] for item in result] == [1, 2]
    assert all(item["balloon_parts"] == 2 for item in result)
    assert all(item["speaker"] == "Tom" for item in result)
    # The layout recomputes zones; a stale one would pin both halves together.
    assert not any("balloon_zone" in item for item in result)


def test_a_panel_allows_only_one_split() -> None:
    """Each split costs a balloon, so a two-speaker panel may spend one."""
    long_a = ("You did it, Tom. I know you didn't mean to, but you did. That's "
              "what I get for marrying a brute of a hulking man.")
    long_b = ("Don't talk. Tom's got some woman in New York. She might have the "
              "decency not to telephone him at dinner time.")

    result, unfittable = split_panel_balloons(
        _panel_texts(("Daisy", long_a), ("Jordan", long_b)), limit=LIMIT, capacity=2
    )

    assert len(result) == 3, "expected exactly one line to split"
    assert len(unfittable) == 1


def test_an_unsplittable_line_is_reported_not_mangled() -> None:
    line = "I have been telling you for the better part of an hour that " + "x" * 60
    texts = _panel_texts(("Tom", line))

    result, unfittable = split_panel_balloons(texts, limit=LIMIT, capacity=2)

    assert result == texts, "the line must be left intact for paraphrase"
    assert [item["text"] for item in unfittable] == [line]


def test_captions_are_not_split() -> None:
    texts = [{"kind": "caption", "text": "A caption long enough to exceed the "
                                         "balloon budget several times over, " + "x" * 60}]

    result, unfittable = split_panel_balloons(texts, limit=LIMIT, capacity=2)

    assert result == texts
    assert unfittable == []


def test_the_policy_stage_is_idempotent_over_a_split_line() -> None:
    """The experiment scripts rerun this stage over their own output, so the
    part markers have to survive a second pass — otherwise the halves lose
    their linkage and get re-pinned to a single balloon zone."""
    from scripts.apply_graphic_lettering_policy import apply_lettering_policy

    storyboard = {"pages": [{"page_number": 1, "panels": [{
        "panel_number": 1,
        "texts": [{
            "kind": "speech", "speaker": "Tom",
            "text": "Terrible place. It does her good to get away. Wilson thinks "
                    "she's visiting her sister—he's so dumb he doesn't know he's alive.",
        }],
    }]}]}

    once, _ = apply_lettering_policy(storyboard)
    twice, report = apply_lettering_policy(once)

    assert twice == once
    assert report["changed_panels"] == []
    texts = once["pages"][0]["panels"][0]["texts"]
    assert [item["balloon_part"] for item in texts] == [1, 2]


def _scan_order(panel: dict[str, Any]) -> list[str]:
    """Balloon ids in the order a reader's eye crosses them."""
    boxes = [
        box for box in panel["thumbnail_layout"]["text_boxes"]
        if box.get("kind") in {"speech", "thought"}
    ]
    return [
        box["id"] for box in
        sorted(boxes, key=lambda b: (round(b["box"]["y"], 3), b["box"]["x"]))
    ]


def test_another_speaker_never_interrupts_a_split_line() -> None:
    """Balloons are normally placed side by side, one per speaker. A split puts
    two balloons on one side, and stacking per side then leaves the other
    speaker level with the first half — so the reader crosses into their line
    between the two halves of a sentence."""
    from scripts.apply_graphic_lettering_policy import apply_lettering_policy
    from scripts.apply_graphic_thumbnail_layout import apply_thumbnail_layout

    storyboard = {"pages": [{"page_number": 1, "panels": [{
        "panel_number": 1,
        "texts": [
            {"kind": "speech", "speaker": "Daisy",
             "text": "You did it, Tom. I know you didn't mean to, but you did. "
                     "That's what I get for marrying a brute of a hulking man."},
            {"kind": "speech", "speaker": "Tom",
             "text": "I've gotten to be a terrible pessimist."},
        ],
    }]}]}

    lettered, _ = apply_lettering_policy(storyboard)
    laid_out, _ = apply_thumbnail_layout(lettered)
    panel = laid_out["pages"][0]["panels"][0]

    assert [item.get("balloon_part") for item in panel["texts"]] == [1, 2, None]
    assert _scan_order(panel) == ["balloon_1", "balloon_2", "balloon_3"]


def test_every_balloon_gets_a_box_when_a_split_fills_the_panel() -> None:
    """A panel may hold one balloon more than it has figures. If placement caps
    below that, the extra balloon is lettered nowhere."""
    from scripts.apply_graphic_lettering_policy import apply_lettering_policy
    from scripts.apply_graphic_thumbnail_layout import apply_thumbnail_layout

    # A lone full-width panel seats three figures, so four balloons are possible.
    storyboard = {"pages": [{"page_number": 1, "panels": [{
        "panel_number": 1,
        "texts": [
            {"kind": "speech", "speaker": "Daisy",
             "text": "You did it, Tom. I know you didn't mean to, but you did. "
                     "That's what I get for marrying a brute of a hulking man."},
            {"kind": "speech", "speaker": "Tom", "text": "I never meant to."},
            {"kind": "speech", "speaker": "Jordan", "text": "Don't talk."},
        ],
    }]}]}

    lettered, _ = apply_lettering_policy(storyboard)
    laid_out, _ = apply_thumbnail_layout(lettered)
    panel = laid_out["pages"][0]["panels"][0]

    balloons = [item for item in panel["texts"] if item["kind"] == "speech"]
    placed = [
        box for box in panel["thumbnail_layout"]["text_boxes"]
        if box.get("kind") == "speech"
    ]
    assert len(balloons) == 4, "expected the split to add a fourth balloon"
    assert len(placed) == len(balloons), "a balloon was left without a box"
    assert _scan_order(panel) == [box["id"] for box in placed]


def test_splitting_is_idempotent() -> None:
    texts = _panel_texts(
        ("Tom", "Terrible place. It does her good to get away. Wilson thinks "
                "she's visiting her sister—he's so dumb he doesn't know he's alive."),
    )

    once, _ = split_panel_balloons(texts, limit=LIMIT, capacity=2)
    twice, unfittable = split_panel_balloons(once, limit=LIMIT, capacity=2)

    assert twice == once
    assert unfittable == []
