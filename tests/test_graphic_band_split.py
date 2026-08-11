"""Caption and balloons are reserved at opposite ends, not stacked.

A caption that reads first used to push the balloons down beneath it, reserving
one block from the top of the panel to about 36% of it. Measured against
generated art, the image model does not clear a band that deep — a head crossed
the balloon box on 3 of 6 dialogue panels — and deepening the band made it worse,
because two standing figures framed from the waist up have nowhere to put their
heads. Shallow bands at either end it does clear.

These tests pin the resulting invariant: when a panel carries both a caption and
balloons, the reserved space is split between the two ends of the panel and the
middle is left for faces.
"""

import pytest

from scripts.apply_graphic_thumbnail_layout import (
    BAND_EDGE_CLEARANCE,
    apply_thumbnail_layout,
)


def _panel(texts, *, panel_number=1, shot="medium"):
    return {
        "panel_number": panel_number,
        "shot": shot,
        "panel_archetype": "two_speaker_exchange",
        "texts": texts,
    }


def _caption(text="Tom crossed the room and asked what I did.", index=0):
    return {"kind": "caption", "text": text, "text_index": index}


def _speech(speaker, text, index):
    return {"kind": "speech", "speaker": speaker, "text": text, "text_index": index}


def _layout(panel, page_number=1):
    """Run the real stage entry point over a one-panel storyboard."""
    storyboard = {"pages": [{"page_number": page_number, "panels": [panel]}]}
    result, report = apply_thumbnail_layout(storyboard)
    laid_out = result["pages"][0]["panels"][0]
    return laid_out["thumbnail_layout"], report


def _boxes(layout):
    return {t["id"]: t["box"] for t in layout["text_boxes"] if t.get("box")}


class TestCaptionFirstSplitsBands:
    def test_balloons_move_to_the_bottom(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom Buchanan", "Never heard of them.", 1),
            _speech("Nick Carraway", "You will if you stay in the East.", 2),
        ])
        layout, _ = _layout(panel)
        boxes = _boxes(layout)

        assert boxes["caption"]["y"] < 0.2, "caption that reads first stays on top"
        for name in ("balloon_1", "balloon_2"):
            assert boxes[name]["y"] > 0.5, f"{name} should be reserved at the bottom"

    def test_bottom_band_is_inset_from_the_frame(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom", "Never heard of them.", 1),
        ])
        layout, _ = _layout(panel)
        lowest = max(b["y"] + b["h"] for b in _boxes(layout).values())
        assert lowest == pytest.approx(1.0 - BAND_EDGE_CLEARANCE, abs=0.02)

    def test_middle_of_the_panel_is_left_clear(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom", "Never heard of them.", 1),
            _speech("Nick", "You will if you stay in the East.", 2),
        ])
        layout, _ = _layout(panel)
        boxes = _boxes(layout)
        top_band = max(b["y"] + b["h"] for b in boxes.values() if b["y"] < 0.5)
        bottom_band = min(b["y"] for b in boxes.values() if b["y"] >= 0.5)
        assert bottom_band - top_band > 0.4, "faces need the middle of the panel"

    def test_faces_are_staged_in_the_clear_middle(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom Buchanan", "Never heard of them.", 1),
            _speech("Nick Carraway", "You will if you stay in the East.", 2),
        ])
        layout, _ = _layout(panel)
        boxes = _boxes(layout)
        top_band = max(b["y"] + b["h"] for b in boxes.values() if b["y"] < 0.5)
        bottom_band = min(b["y"] for b in boxes.values() if b["y"] >= 0.5)
        faces = [f["face_box"] for f in layout.get("figures") or []]
        assert faces, "a two-speaker exchange should stage figures"
        for face in faces:
            assert face["y"] >= top_band, "face must clear the top band"
            assert face["y"] + face["h"] <= bottom_band, "face must clear the bottom band"


class TestUnaffectedCases:
    def test_caption_last_is_left_alone(self):
        # This path already reserved shallow bands: balloons on top, caption
        # below. Splitting it again would be a second move for no reason.
        panel = _panel([
            _speech("Tom", "Never heard of them.", 0),
            _caption(index=1),
        ])
        layout, _ = _layout(panel)
        boxes = _boxes(layout)
        assert boxes["balloon_1"]["y"] < 0.5
        assert boxes["caption"]["y"] > 0.5

    def test_caption_only_panel_keeps_its_zone(self):
        panel = _panel([_caption(index=0)])
        layout, _ = _layout(panel)
        boxes = _boxes(layout)
        assert set(boxes) == {"caption"}
        assert boxes["caption"]["y"] < 0.5

    def test_balloons_only_panel_stays_at_the_top(self):
        panel = _panel([
            _speech("Tom", "Never heard of them.", 0),
            _speech("Nick", "You will.", 1),
        ])
        layout, _ = _layout(panel)
        for name, box in _boxes(layout).items():
            assert box["y"] < 0.5, f"{name} should stay at the top with no caption"


class TestReadingOrderSurvives:
    def test_caption_reads_before_the_balloons_it_precedes(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom", "Never heard of them.", 1),
            _speech("Nick", "You will if you stay in the East.", 2),
        ])
        layout, _ = _layout(panel)
        ordered = sorted(
            (t for t in layout["text_boxes"] if t.get("box")),
            key=lambda t: t["reading_order"],
        )
        assert ordered[0]["id"] == "caption"
        # Reading top to bottom must agree with reading order.
        tops = [t["box"]["y"] for t in ordered]
        assert tops == sorted(tops), "reading order must not jump back up the page"

    def test_split_line_halves_stay_in_text_order(self):
        panel = _panel([
            _caption(index=0),
            _speech("Tom", "Never heard of them, and I have looked.", 1),
            _speech("Tom", "Not once, in all the years I have been here.", 2),
        ])
        layout, _ = _layout(panel)
        ordered = sorted(
            (t for t in layout["text_boxes"] if t["id"].startswith("balloon")),
            key=lambda t: t["reading_order"],
        )
        ys = [t["box"]["y"] for t in ordered]
        assert ys == sorted(ys), "a split line must not read bottom-up"
