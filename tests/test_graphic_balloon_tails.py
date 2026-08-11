"""A balloon tail has to point at the speaker, and out of the balloon.

Both failed on real pages. Rendering Gatsby chapter 1 pages 6/7/11, six of
twelve balloons drew their tail *inside* themselves — the attach-side chain
had no case for an anchor the balloon had grown over, so it drew the triangle
from the bottom edge upward, striking the outline through the last two lines of
text. Every one of the six was four lines or taller.

The anchor was wrong to begin with. With no vision detection the letterer fell
back to `ANCHOR_Y["mouth"]`, a fixed 0.34 of the panel, while the layout stage
had staged those faces at 0.54 and written a `mouth_point` for each. Aiming at
the staged mouth both points the tail at the character the art was directed to
draw and keeps it clear of the balloon, because the layout stages figures out
of the text boxes.
"""

from __future__ import annotations

from PIL import Image

from scripts.compose_graphic_panel_page import _staged_mouth_ratio
from scripts.letter_graphic_novel_frames import (
    _anchor_outside_balloon,
    _draw_speech_balloon,
)
from scripts.letter_graphic_novel_pages import Box

# A balloon at 100,100 measuring 200x160.
BOX = {"x": 100, "y": 100, "w": 200, "h": 160}


def _project(px: int, py: int, min_length: int = 20) -> tuple[int, int]:
    return _anchor_outside_balloon(
        (px, py), BOX["x"], BOX["y"], BOX["w"], BOX["h"], min_length
    )


def test_an_anchor_the_balloon_swallowed_is_pushed_out_the_nearest_edge() -> None:
    """The regression. Low in the balloon means the speaker is below it."""
    assert _project(200, 240) == (200, 280)  # nearest edge is the bottom, 100+160


def test_an_anchor_high_in_the_balloon_leaves_through_the_top() -> None:
    assert _project(200, 110) == (200, 80)


def test_an_anchor_near_a_side_leaves_through_that_side() -> None:
    assert _project(110, 180) == (80, 180)
    assert _project(295, 180) == (320, 180)


def test_an_anchor_already_outside_is_left_alone() -> None:
    """The common case must not move — this only rescues the swallowed one."""
    for point in ((200, 400), (50, 180), (400, 180), (200, 20)):
        assert _project(*point) == point


def test_the_projected_anchor_clears_the_balloon_by_the_minimum_length() -> None:
    x, y = _project(200, 240, min_length=35)
    assert y == BOX["y"] + BOX["h"] + 35
    assert not (BOX["y"] <= y <= BOX["y"] + BOX["h"])


def test_a_tall_balloon_draws_its_tail_outside_itself() -> None:
    """End to end through the real renderer: a balloon with enough text to grow
    over its own anchor still puts the tail point outside the box."""
    image = Image.new("RGBA", (1536, 2048), (255, 255, 255, 255))
    frame = Box(23, 31, 756, 1008)
    item = {
        "kind": "speech",
        "speaker": "Daisy Buchanan",
        "text": "Her family is one aunt about a thousand years old. "
                "Besides, Nick's going to look after her.",
        "slot_box_ratio": {"x": 0.42, "y": 0.2, "w": 0.36, "h": 0.22},
        # 0.34 was the old fixed fallback, and it lands inside this balloon.
        "anchor_x_ratio": 0.74,
        "anchor_y_ratio": 0.34,
    }

    layout = _draw_speech_balloon(image, frame, item, stack_index=0, stack_count=1)

    box, tail = layout["box"], layout["tail_point"]
    inside = (
        box["x1"] <= tail["x"] <= box["x2"] and box["y1"] <= tail["y"] <= box["y2"]
    )
    assert not inside, "the tail must not point back into the balloon's own text"


PANEL = {
    "thumbnail_layout": {
        "figures": [
            {"character": "Tom Buchanan", "mouth_point": {"x": 0.252, "y": 0.5409}},
            {"character": "Daisy Buchanan", "mouth_point": {"x": 0.74, "y": 0.5409}},
        ]
    }
}


def test_the_staged_mouth_is_found_by_full_name() -> None:
    assert _staged_mouth_ratio(PANEL, "Daisy Buchanan") == {"x": 0.74, "y": 0.5409}


def test_a_surname_less_speaker_still_matches_its_figure() -> None:
    """Pages carry both 'Daisy' and 'Daisy Buchanan' for the same character."""
    assert _staged_mouth_ratio(PANEL, "Daisy") == {"x": 0.74, "y": 0.5409}


def test_a_full_match_beats_a_first_name_match() -> None:
    panel = {
        "thumbnail_layout": {
            "figures": [
                {"character": "Daisy Fay", "mouth_point": {"x": 0.2, "y": 0.5}},
                {"character": "Daisy Buchanan", "mouth_point": {"x": 0.8, "y": 0.5}},
            ]
        }
    }

    assert _staged_mouth_ratio(panel, "Daisy Buchanan") == {"x": 0.8, "y": 0.5}


def test_an_unstaged_speaker_has_no_mouth() -> None:
    assert _staged_mouth_ratio(PANEL, "Jordan Baker") is None
    assert _staged_mouth_ratio(PANEL, "") is None
    assert _staged_mouth_ratio({}, "Tom Buchanan") is None


def test_a_figure_without_a_mouth_point_is_skipped() -> None:
    panel = {"thumbnail_layout": {"figures": [{"character": "Tom Buchanan"}]}}

    assert _staged_mouth_ratio(panel, "Tom Buchanan") is None
