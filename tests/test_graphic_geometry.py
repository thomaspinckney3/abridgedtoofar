"""Tests for the shared graphic-novel panel-capacity rule.

The lettering policy caps balloons and the thumbnail layout caps staged
figures. These stages run one after the other over the same storyboard, so a
disagreement between their caps produces a panel that contradicts itself: a
balloon whose speaker was never drawn. Everything here defends that agreement,
plus the demotion rules that decide whether a line survives at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.apply_graphic_lettering_policy import (
    MAX_BALLOON_CHARS,
    _UNINFORMATIVE_REPORT_RE,
    _caption_restates,
    _sanitize_caption_artifacts,
    apply_lettering_policy,
)
from scripts.apply_graphic_thumbnail_layout import (
    _canonical_panel_boxes,
    _panel_boxes,
    apply_thumbnail_layout,
)
from forage.graphic.geometry import (
    CROWDED_PANEL_FIGURES,
    DEFAULT_PANEL_FIGURES,
    canonical_panel_boxes,
    panel_boxes,
    panel_capacities,
    panel_capacity,
)

PANEL_COUNTS = list(range(1, 9))


def _balloons(panel: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in panel.get("texts") or []
        if str(item.get("kind") or "").strip().lower() in {"speech", "thought"}
        and str(item.get("text") or "").strip()
    ]


def _page(panels: list[dict[str, Any]], page_number: int = 1) -> dict[str, Any]:
    return {"pages": [{"page_number": page_number, "panels": panels}]}


def _speech(speaker: str, text: str) -> dict[str, Any]:
    return {"kind": "speech", "speaker": speaker, "text": text}


# --- the two stages must resolve identical geometry ------------------------


@pytest.mark.parametrize("count", [0, *PANEL_COUNTS])
def test_canonical_grid_matches_layout_stage(count: int) -> None:
    """The shared table is the layout stage's grid, not a copy of it."""
    shared = canonical_panel_boxes(count)
    layout = _canonical_panel_boxes(count)

    assert len(shared) == len(layout)
    for mine, theirs in zip(shared, layout, strict=True):
        assert mine.x == pytest.approx(theirs.x)
        assert mine.y == pytest.approx(theirs.y)
        assert mine.w == pytest.approx(theirs.w)
        assert mine.h == pytest.approx(theirs.h)


@pytest.mark.parametrize("count", PANEL_COUNTS)
def test_resolve_panel_boxes_matches_layout_for_unplaced_pages(count: int) -> None:
    """Before layout runs no panel has a box, and both stages must still agree."""
    panels = [{"panel_number": index + 1} for index in range(count)]
    page = {"page_number": 1, "panels": panels}

    for mine, theirs in zip(panel_boxes(panels), _panel_boxes(page, panels),
                            strict=True):
        assert mine.w == pytest.approx(theirs.w)
        assert mine.h == pytest.approx(theirs.h)


@pytest.mark.parametrize("count", PANEL_COUNTS)
def test_every_panel_gets_a_box(count: int) -> None:
    """An unplaced panel is dropped from layout outright, taking its balloons
    with it, so the grid must cover counts past the hand-tuned table."""
    boxes = canonical_panel_boxes(count)

    assert len(boxes) == count
    for box in boxes:
        assert 0.0 <= box.x < box.x2 <= 1.0
        assert 0.0 <= box.y < box.y2 <= 1.0


@pytest.mark.parametrize("count", PANEL_COUNTS)
def test_canonical_panels_do_not_overlap(count: int) -> None:
    boxes = canonical_panel_boxes(count)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            apart = (
                a.x2 <= b.x + 1e-9 or b.x2 <= a.x + 1e-9
                or a.y2 <= b.y + 1e-9 or b.y2 <= a.y + 1e-9
            )
            assert apart, f"{count}-panel grid overlaps: {a} and {b}"


def test_explicit_boxes_are_honored() -> None:
    panels = [{"box": {"x": 0.0, "y": 0.0, "w": 0.97, "h": 0.6}},
              {"box": {"x": 0.0, "y": 0.6, "w": 0.4, "h": 0.3}}]

    assert [box.as_dict() for box in panel_boxes(panels)] == [
        panel["box"] for panel in panels
    ]
    assert panel_capacities(panels) == [CROWDED_PANEL_FIGURES, DEFAULT_PANEL_FIGURES]


def test_a_partial_rectangle_is_not_a_box() -> None:
    """The layout stage used to hand capacity a width/height-only dict. Silently
    treating that as a rectangle, or silently rejecting it, both hide the error —
    the caller should pass a real Box."""
    from forage.graphic.geometry import box_from_dict

    assert box_from_dict({"w": 0.97, "h": 0.6}) is None
    assert box_from_dict({"x": 0.0, "y": 0.0, "w": 0.97, "h": 0.6}) is not None
    # Corner form is a real rectangle and must still be read.
    assert box_from_dict({"x1": 0.0, "y1": 0.0, "x2": 0.97, "y2": 0.6}) is not None


def test_partially_placed_page_falls_back_to_the_canonical_grid() -> None:
    """Mirrors the layout stage, which regrids rather than mixing geometry."""
    panels = [{"box": {"x": 0.0, "y": 0.0, "w": 0.97, "h": 0.6}}, {"panel_number": 2}]

    assert panel_boxes(panels) == canonical_panel_boxes(2)


def test_corner_form_boxes_are_measured() -> None:
    """The layout stage accepts x1/y1/x2/y2, so capacity must read it too."""
    corner = {"x1": 0.0, "y1": 0.0, "x2": 0.97, "y2": 0.6}

    assert panel_capacity(corner) == CROWDED_PANEL_FIGURES
    assert panel_capacity({"x1": 0.0, "y1": 0.0, "x2": 0.4, "y2": 0.6}) == DEFAULT_PANEL_FIGURES


def test_unmeasurable_box_falls_back_to_the_conservative_cap() -> None:
    for box in (None, {}, {"w": "wide", "h": 0.6}, {"w": 0.97}):
        assert panel_capacity(box) == DEFAULT_PANEL_FIGURES


def test_two_tier_pages_can_stage_a_three_way_exchange() -> None:
    """A full-width half-page panel is too short for the height test but not
    too small for three figures — the area rule is what admits it."""
    assert panel_capacities([{}, {}]) == [CROWDED_PANEL_FIGURES] * 2


def test_small_panels_stay_conservative() -> None:
    assert panel_capacities([{} for _ in range(4)]) == [DEFAULT_PANEL_FIGURES] * 4


# --- the caps must agree end to end ----------------------------------------


@pytest.mark.parametrize("count", PANEL_COUNTS)
def test_every_balloon_speaker_survives_into_a_drawn_figure(count: int) -> None:
    """The bug this module exists to prevent: a balloon with no one to speak it."""
    panels = [
        {
            "panel_number": index + 1,
            "texts": [
                {"kind": "caption", "text": f"Panel {index + 1} of the argument."},
                _speech("Tom", "You never asked me."),
                _speech("Daisy", "I did ask."),
                _speech("Nick", "Both of you stop."),
                _speech("Jordan", "Let them finish."),
            ],
        }
        for index in range(count)
    ]

    lettered, _ = apply_lettering_policy(_page(panels))
    laid_out, _ = apply_thumbnail_layout(lettered)

    for panel in laid_out["pages"][0]["panels"]:
        drawn = {
            str(figure.get("character") or "").strip().lower()
            for figure in panel["thumbnail_layout"]["figures"]
        }
        for balloon in _balloons(panel):
            speaker = str(balloon.get("speaker") or "").strip().lower()
            assert speaker in drawn, (
                f"balloon for {speaker!r} has no figure drawn to speak it"
            )


@pytest.mark.parametrize("count", PANEL_COUNTS)
def test_balloons_never_exceed_panel_capacity(count: int) -> None:
    panels = [
        {
            "panel_number": index + 1,
            "texts": [
                {"kind": "caption", "text": "They talked over each other."},
                _speech("Tom", "You never asked me."),
                _speech("Daisy", "I did ask."),
                _speech("Nick", "Both of you stop."),
                _speech("Jordan", "Let them finish."),
            ],
        }
        for index in range(count)
    ]
    capacities = panel_capacities(panels)

    lettered, _ = apply_lettering_policy(_page(panels))

    for panel, capacity in zip(lettered["pages"][0]["panels"], capacities, strict=True):
        assert len(_balloons(panel)) <= capacity


def test_a_stray_non_dict_panel_does_not_shift_the_grid() -> None:
    """Both stages drop malformed entries before gridding; so must capacity."""
    panels: list[Any] = [
        "not a panel",
        {"panel_number": 1, "texts": [_speech("Tom", "Come on then."),
                                      _speech("Daisy", "Not yet.")]},
        {"panel_number": 2, "texts": [_speech("Nick", "Later.")]},
    ]

    lettered, _ = apply_lettering_policy(_page(panels))
    laid_out, _ = apply_thumbnail_layout(lettered)

    # Two well-formed panels means the two-tier grid, which seats three.
    for panel in laid_out["pages"][0]["panels"]:
        assert len(_balloons(panel)) <= CROWDED_PANEL_FIGURES


# --- demotion must never silently delete a line ----------------------------


def test_a_short_lone_balloon_is_kept_rather_than_erased() -> None:
    """Demoting this line yields "Tom spoke.", which the caption sanitizer
    strips right back out — so the line would vanish from the page."""
    storyboard = _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption", "text": "The room was hot and the afternoon dragged."},
            _speech("Tom", "Come on then."),
        ],
    }])

    lettered, _ = apply_lettering_policy(storyboard)
    panel = lettered["pages"][0]["panels"][0]

    assert [item["text"] for item in _balloons(panel)] == ["Come on then."]
    caption = next(item for item in panel["texts"] if item["kind"] == "caption")
    assert "The room was hot" in caption["text"]
    # Nothing was folded in, so the panel must not claim a demotion happened.
    assert "demoted" not in str(caption.get("lettering_notes") or "")


def _redundant_panel() -> dict[str, Any]:
    """A caption that genuinely restates the line beside it."""
    return _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption",
             "text": "He had told me to remember my advantages, and said no more."},
            _speech("Daisy", "Just remember that you've had advantages I never had."),
        ],
    }])


def test_an_informative_demotion_still_happens() -> None:
    lettered, _ = apply_lettering_policy(_redundant_panel())
    panel = lettered["pages"][0]["panels"][0]
    caption = next(item for item in panel["texts"] if item["kind"] == "caption")

    assert _balloons(panel) == []
    assert "Daisy told me to remember" in caption["text"]
    assert "demoted" in caption["lettering_notes"]


def test_reported_speech_keeps_the_pronoun_capitalized() -> None:
    """The clause is lowercased when folded mid-sentence, but "I" is a pronoun."""
    lettered, _ = apply_lettering_policy(_redundant_panel())
    caption = next(
        item for item in lettered["pages"][0]["panels"][0]["texts"]
        if item["kind"] == "caption"
    )

    assert " i " not in f" {caption['text']} "
    assert "that I had" in caption["text"]


def test_a_lone_speaker_keeps_the_balloon_when_the_caption_is_unrelated() -> None:
    """Being the only speaker is not evidence of redundancy. In a graphic novel
    a spoken line belongs in a balloon unless the caption already says it."""
    storyboard = _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption",
             "text": "Often I feigned sleep when an intimate revelation quivered."},
            _speech("Jordan", "We ought to plan something."),
        ],
    }])

    lettered, _ = apply_lettering_policy(storyboard)
    panel = lettered["pages"][0]["panels"][0]

    assert [item["text"] for item in _balloons(panel)] == ["We ought to plan something."]


@pytest.mark.parametrize("caption,line,restates", [
    ("He had told me to remember my advantages.",
     "Just remember that you've had advantages I never had.", True),
    ("Often I feigned sleep when an intimate revelation quivered.",
     "We ought to plan something.", False),
    # A single incidental shared word is not a restatement.
    ("The candles guttered on the table.", "Why candles?", False),
    # Too few meaningful words to judge either way.
    ("The room was still.", "I just—", False),
])
def test_caption_restatement_detection(caption: str, line: str, restates: bool) -> None:
    assert _caption_restates(caption, line) is restates


def test_an_overlong_line_is_not_traded_for_an_empty_caption() -> None:
    """"X spoke at length." is stripped by the sanitizer, so demoting an
    over-long balloon with no special-cased phrasing would lose it outright.
    An over-long balloon is a fitting problem; a dropped line is unrecoverable."""
    long_line = (
        "I have been telling you for the better part of an hour that the "
        "arrangement was never mine to make in the first place, whatever he claims."
    )
    assert len(long_line) > MAX_BALLOON_CHARS

    storyboard = _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption", "text": "The argument had been going a while."},
            _speech("Tom", long_line),
            _speech("Daisy", "That is not what happened."),
        ],
    }])

    lettered, _ = apply_lettering_policy(storyboard)
    panel = lettered["pages"][0]["panels"][0]

    assert long_line in [item["text"] for item in _balloons(panel)]


@pytest.mark.parametrize("report", [
    "Tom spoke.",
    "Tom spoke briefly.",
    "Tom spoke at length.",
    "My father spoke.",
    "Someone asked a question.",
])
def test_contentless_reports_are_detected(report: str) -> None:
    """These carry none of the line they replace, so the balloon must be kept."""
    assert _UNINFORMATIVE_REPORT_RE.match(report)


@pytest.mark.parametrize("report", [
    "Tom spoke.",
    "Tom spoke briefly.",
    "Tom spoke at length.",
    "Someone asked a question.",
])
def test_anything_the_sanitizer_erases_is_detected_first(report: str) -> None:
    """The direction that matters: if demoting would produce a phrase the
    caption sanitizer deletes, the guard must already have kept the balloon.
    The guard is deliberately the broader of the two — it also catches reports
    like "My father spoke." that survive sanitizing but still say nothing."""
    assert _sanitize_caption_artifacts(f"The hall was quiet. {report}") == (
        "The hall was quiet."
    )
    assert _UNINFORMATIVE_REPORT_RE.match(report)


@pytest.mark.parametrize("report", [
    "Daisy told me to remember that I had had advantages.",
    "Myrtle began listing the things she meant to buy and do.",
    "A stranger asked how to get to West Egg.",
])
def test_informative_reports_survive_both_patterns(report: str) -> None:
    assert not _UNINFORMATIVE_REPORT_RE.match(report)
    assert report in _sanitize_caption_artifacts(f"The hall was quiet. {report}")


def test_a_caption_sanitized_to_nothing_is_removed() -> None:
    """A caption that is only a stripped artifact would otherwise letter an
    empty box onto the panel, and survive one pass but not the next."""
    storyboard = _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption", "text": "Ishmael spoke."},
            _speech("Queequeg", "Me sabbee plenty."),
        ],
    }])

    lettered, _ = apply_lettering_policy(storyboard)
    texts = lettered["pages"][0]["panels"][0]["texts"]

    assert all(str(item.get("text") or "").strip() for item in texts)
    assert not any(item["kind"] == "caption" for item in texts)


def test_lettering_policy_is_idempotent() -> None:
    """The stage reruns over its own output in the experiment scripts."""
    storyboard = _page([{
        "panel_number": 1,
        "texts": [
            {"kind": "caption", "text": "The room was hot and the afternoon dragged."},
            _speech("Tom", "Come on then."),
            _speech("Daisy", "Not yet."),
        ],
    }])

    once, _ = apply_lettering_policy(storyboard)
    twice, report = apply_lettering_policy(once)

    assert twice == once
    assert report["changed_panels"] == []
