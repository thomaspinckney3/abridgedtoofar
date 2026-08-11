"""Balloons belong beside the speaker, not parked in a reserved band.

The band approach kept balloons off faces by keeping them away from everything:
one strip along the bottom of the panel, every balloon in it, tails reaching up
across the artwork. Nothing covered a face because nothing was near one, and the
page stopped reading as comics — the dialogue looked like a row of subtitles.

Near-speaker placement already existed but was gated on the panel having no slot,
and the layout stage gives every balloon a slot, so it never ran. These tests pin
the behaviour that gate was hiding.
"""

from __future__ import annotations

from PIL import Image

from scripts.letter_graphic_novel_frames import _draw_speech_balloon, _overlap_area
from scripts.letter_graphic_novel_pages import Box

FRAME = Box(0, 0, 700, 900)
TEXT = "Her family is one aunt about a thousand years old."
# The band the layout stage reserves along the bottom of the panel.
BOTTOM_SLOT = {"x": 0.06, "y": 0.80, "w": 0.40, "h": 0.16}


def _canvas() -> Image.Image:
    return Image.new("RGBA", (FRAME.x2, FRAME.y2), (90, 60, 50, 255))


def _speak(**overrides):
    item = {
        "kind": "speech",
        "text": TEXT,
        "speaker": "Daisy Buchanan",
        "anchor_x_ratio": 0.30,
        "anchor_y_ratio": 0.30,
        "balloon_placement_mode": "near_speaker",
    }
    item.update(overrides)
    return item


def _draw(item, placed_rects=None):
    return _draw_speech_balloon(
        _canvas(), FRAME, item, stack_index=0, stack_count=1, placed_rects=placed_rects
    )


class TestSlotsDoNotPinPosition:
    def test_a_bottom_slot_does_not_park_a_balloon_at_the_bottom(self):
        layout = _draw(_speak(slot_box_ratio=BOTTOM_SLOT))
        # The speaker is at y 0.30; the slot says 0.80. The speaker wins.
        assert layout["box"]["y1"] < FRAME.height * 0.6

    def test_the_balloon_lands_near_its_speaker(self):
        layout = _draw(_speak(slot_box_ratio=BOTTOM_SLOT))
        box = layout["box"]
        anchor_y = FRAME.height * 0.30
        # Within roughly a third of the panel of the mouth it belongs to.
        assert abs((box["y1"] + box["y2"]) / 2 - anchor_y) < FRAME.height * 0.35

    def test_the_tail_reaches_the_speaker_rather_than_stopping_short(self):
        # An anchor the balloon itself covers is projected out to the balloon's
        # edge, so the tail stops a little short by design. What matters is that
        # it ends at the speaker rather than being capped partway across the
        # panel, which is what a band-placed balloon a third of a panel away did.
        layout = _draw(_speak(slot_box_ratio=BOTTOM_SLOT))
        tail = layout["tail_point"]
        assert abs(tail["x"] - FRAME.width * 0.30) < FRAME.width * 0.08
        assert abs(tail["y"] - FRAME.height * 0.30) < FRAME.height * 0.08


class TestObstaclesAreAvoided:
    def test_a_balloon_routes_around_a_caption(self):
        # Captions are lettered after balloons and would paint over them.
        caption = (0, 0, FRAME.x2, round(FRAME.height * 0.22))
        layout = _draw(_speak(anchor_y_ratio=0.30), placed_rects=[caption])
        assert layout["box"]["y1"] >= caption[3] - 24

    def test_two_balloons_do_not_land_on_each_other(self):
        first = _draw(_speak(anchor_x_ratio=0.30))
        box = first["box"]
        second = _draw(
            _speak(anchor_x_ratio=0.34, speaker="Tom"),
            placed_rects=[(box["x1"], box["y1"], box["x2"], box["y2"])],
        )
        other = second["box"]
        overlap_w = min(box["x2"], other["x2"]) - max(box["x1"], other["x1"])
        overlap_h = min(box["y2"], other["y2"]) - max(box["y1"], other["y1"])
        assert overlap_w <= 0 or overlap_h <= 0, "balloons overlap"


class TestOverlapScoring:
    """Ranking matters most when every candidate collides with something."""

    def test_a_face_costs_more_than_a_caption_of_the_same_size(self):
        rect = (100, 100, 300, 200)
        face = _overlap_area(
            rect,
            frame_box=FRAME,
            item={"avoid_boxes_ratio": [{"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}]},
        )
        caption = _overlap_area(
            rect,
            frame_box=FRAME,
            item={},
            placed_rects=[(0, 0, FRAME.x2, FRAME.y2)],
        )
        assert face > caption

    def test_a_clear_rectangle_scores_zero(self):
        assert _overlap_area((10, 10, 60, 60), frame_box=FRAME, item={}) == 0
