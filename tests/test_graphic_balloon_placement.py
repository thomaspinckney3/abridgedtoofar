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

from scripts.letter_graphic_novel_frames import (
    _draw_speech_balloon,
    _overlap_area,
    _reads_before,
)
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


class TestBalloonsSitBesideTheSpeaker:
    """Sideways, not overhead — that is how comics read.

    The first near-speaker pass offset the balloon by a fraction of the panel
    height but only a hair horizontally, so it landed directly above the head
    and every tail dropped straight down. Vertical offsets are now fractions of
    the balloon's own height, so the balloon straddles head height and the
    horizontal gap dominates.
    """

    def _placement(self, **overrides):
        layout = _draw(_speak(**overrides))
        box = layout["box"]
        return {
            "dx": abs((box["x1"] + box["x2"]) / 2 - FRAME.width * overrides.get("anchor_x_ratio", 0.30)),
            "dy": abs((box["y1"] + box["y2"]) / 2 - FRAME.height * overrides.get("anchor_y_ratio", 0.30)),
            "box": box,
        }

    def test_offset_is_mostly_horizontal(self):
        p = self._placement(anchor_x_ratio=0.30, anchor_y_ratio=0.45, speaker_region="left")
        assert p["dx"] > p["dy"], "balloon sits overhead rather than beside the speaker"

    def test_offset_is_mostly_horizontal_for_a_right_speaker(self):
        p = self._placement(anchor_x_ratio=0.70, anchor_y_ratio=0.55, speaker_region="right")
        assert p["dx"] > p["dy"]

    def test_the_mouth_is_not_inside_the_balloons_horizontal_span(self):
        # If it is, the tail leaves the top or bottom edge and drops vertically.
        p = self._placement(anchor_x_ratio=0.30, anchor_y_ratio=0.45, speaker_region="left")
        mouth_x = FRAME.width * 0.30
        assert not (p["box"]["x1"] <= mouth_x <= p["box"]["x2"])

    def test_the_balloon_straddles_head_height(self):
        p = self._placement(anchor_x_ratio=0.30, anchor_y_ratio=0.45, speaker_region="left")
        # Not floating a fifth of the panel above the speaker.
        assert p["dy"] < FRAME.height * 0.15


class TestReadingOrderSurvivesFreePlacement:
    """A later line must not land above the line it answers.

    The old bottom band gave reading order for free: balloons were stacked in
    it top to bottom. Placing each beside its own speaker removed that, and on
    page 11 panel 2 Tom's reply landed above Daisy's line — the caption for that
    panel literally reads "Daisy began on Louisville before Tom cut in".
    """

    def test_a_reply_does_not_land_above_the_line_it_answers(self):
        first = _draw(_speak(anchor_x_ratio=0.30, anchor_y_ratio=0.55, speaker_region="left"))
        a = first["box"]
        second = _draw_speech_balloon(
            _canvas(),
            FRAME,
            _speak(anchor_x_ratio=0.75, anchor_y_ratio=0.30, speaker_region="right", speaker="Tom"),
            stack_index=0,
            stack_count=1,
            placed_rects=[(a["x1"], a["y1"], a["x2"], a["y2"])],
            read_after_rects=[(a["x1"], a["y1"], a["x2"], a["y2"])],
        )
        b = second["box"]
        assert not _reads_before(
            (b["x1"], b["y1"], b["x2"], b["y2"]),
            (a["x1"], a["y1"], a["x2"], a["y2"]),
        ), "the second balloon reads before the first"

    def test_reads_before_orders_by_row_then_column(self):
        above = (0, 0, 100, 50)
        below = (0, 200, 100, 250)
        assert _reads_before(above, below)
        assert not _reads_before(below, above)
        left = (0, 100, 100, 180)
        right = (300, 110, 400, 190)
        assert _reads_before(left, right), "same row should order left to right"
        assert not _reads_before(right, left)


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
