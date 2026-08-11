"""Staging language: the geometry an image model can actually act on.

The property these tests exist to protect is that no coordinate reaches the
prompt. Percentages in an art prompt are not merely ineffective — they were
measured putting a face inside a text box on 6 of 6 dialogue panels — so a
regression that reintroduces them is expensive and silent, visible only after
paying for art.
"""

import re

import pytest

from forage.graphic.staging import (
    BAND_MARGIN,
    band_phrase,
    describe_staging,
    filter_box_rules,
    height_phrase,
)


def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _text(idx, box, kind="speech", speaker=None):
    return {"id": f"t{idx}", "kind": kind, "box": box, "speaker": speaker}


def _figure(name, side, face_y):
    return {
        "character": name,
        "side": side,
        "body_box": _box(0.06, 0.44, 0.4, 0.52),
        "face_box": _box(0.2, face_y, 0.1, 0.1),
    }


class TestNoNumbersReachThePrompt:
    """The whole point: staging text must carry no coordinates."""

    def test_dialogue_panel_emits_no_digits(self):
        lines = describe_staging(
            [
                _text(0, _box(0.06, 0.04, 0.88, 0.12), "caption"),
                _text(1, _box(0.06, 0.20, 0.38, 0.16), speaker="Tom"),
                _text(2, _box(0.56, 0.20, 0.38, 0.16), speaker="Nick"),
            ],
            [_figure("Tom Buchanan", "left", 0.48), _figure("Nick Carraway", "right", 0.48)],
        )
        blob = "\n".join(lines)
        assert "%" not in blob
        assert not re.search(r"\d", blob), f"a coordinate leaked: {blob}"

    def test_caption_only_panel_emits_no_digits(self):
        lines = describe_staging([_text(0, _box(0.06, 0.04, 0.88, 0.15), "caption")])
        blob = "\n".join(lines)
        assert "%" not in blob
        assert not re.search(r"\d", blob)


class TestBandPhrase:
    def test_names_run_top_down(self):
        assert band_phrase(0.10) == "top eighth"
        assert band_phrase(0.20) == "top fifth"
        assert band_phrase(0.36) == "top third"

    def test_saturates_rather_than_failing(self):
        # A band covering most of the panel is nonsense to reserve, but it must
        # still produce words rather than raise into the middle of a prompt.
        assert band_phrase(0.99) == "top three-quarters"

    def test_boundaries_are_inclusive(self):
        assert band_phrase(0.14) == "top eighth"
        assert band_phrase(0.1401) != "top eighth"


class TestHeightPhrase:
    @pytest.mark.parametrize(
        "y,expected",
        [
            (0.10, "high, near the top of the frame"),
            (0.30, "in the upper third of the frame"),
            (0.50, "at mid-height of the frame"),
            (0.65, "in the lower third of the frame"),
            (0.90, "low, near the bottom of the frame"),
        ],
    )
    def test_maps_height_to_words(self, y, expected):
        assert height_phrase(y) == expected


class TestReservedBandMargin:
    """The band is described deeper than the text needs, on purpose.

    Asked for exactly the space the text occupies, the model put heads just
    across the lower edge on three of six panels. The margin buys tolerance.
    """

    def test_margin_widens_the_named_band(self):
        texts = [_text(0, _box(0.06, 0.04, 0.88, 0.32))]  # extent 0.36
        with_margin = describe_staging(texts, margin=BAND_MARGIN)[1]
        without = describe_staging(texts, margin=0.0)[1]
        assert "top third" in without
        assert "top third" not in with_margin
        assert "upper two-fifths" in with_margin

    def test_zero_margin_is_honoured(self):
        texts = [_text(0, _box(0.0, 0.0, 1.0, 0.14))]
        assert "top eighth" in describe_staging(texts, margin=0.0)[1]


class TestStructure:
    def test_no_text_boxes_yields_nothing(self):
        # A caller appends this unconditionally; a bare header would be noise.
        assert describe_staging([], []) == []
        assert describe_staging([{"kind": "speech"}]) == []

    def test_speaker_ordering_line_only_when_figures_present(self):
        caption_only = describe_staging([_text(0, _box(0.06, 0.04, 0.88, 0.12), "caption")])
        assert not any("left-to-right" in line for line in caption_only)

        with_figures = describe_staging(
            [_text(0, _box(0.06, 0.04, 0.88, 0.12), "caption")],
            [_figure("Tom", "left", 0.48)],
        )
        assert any("left-to-right" in line for line in with_figures)

    def test_bottom_band_described_from_the_bottom(self):
        lines = describe_staging([_text(0, _box(0.06, 0.77, 0.88, 0.19), "caption")])
        blob = "\n".join(lines)
        assert "bottom" in blob
        # "bottom top quarter" would be a phrasing bug, not English.
        assert "bottom top" not in blob
        assert "bottom upper" not in blob

    def test_both_bands_reserved_when_text_sits_at_both_ends(self):
        lines = describe_staging([
            _text(0, _box(0.06, 0.04, 0.88, 0.12), "caption"),
            _text(1, _box(0.06, 0.80, 0.88, 0.16), "caption"),
        ])
        blob = "\n".join(lines)
        assert "top" in blob and "bottom" in blob

    def test_figure_side_is_named(self):
        lines = describe_staging(
            [_text(0, _box(0.06, 0.20, 0.38, 0.16), speaker="Tom")],
            [_figure("Tom Buchanan", "left", 0.48)],
        )
        blob = "\n".join(lines)
        assert "Tom Buchanan" in blob
        assert "on the left side" in blob

    def test_unknown_side_does_not_produce_broken_english(self):
        lines = describe_staging(
            [_text(0, _box(0.06, 0.20, 0.38, 0.16))],
            [{"character": "X", "side": "", "face_box": _box(0.2, 0.48, 0.1, 0.1)}],
        )
        blob = "\n".join(lines)
        assert "on the  side" not in blob
        assert "centred in the frame" in blob

    def test_malformed_entries_are_skipped(self):
        lines = describe_staging(
            [_text(0, _box(0.06, 0.04, 0.88, 0.12), "caption"), {"box": {"x": 1}}, None],
            [{"character": "no face"}, None],
        )
        assert lines
        assert not any("no face" in line for line in lines)


class TestFilterBoxRules:
    def test_drops_rules_that_reference_a_box(self):
        kept = filter_box_rules([
            "Draw finished art only in the panel frame.",
            "Keep all faces and mouths inside their face boxes.",
            "Keep bodies inside their body boxes unless a gesture is required.",
            "Keep active hands and key props out of text boxes.",
        ])
        assert kept == ["Draw finished art only in the panel frame."]

    def test_keeps_self_contained_rules(self):
        assert filter_box_rules(["Draw no readable text."]) == ["Draw no readable text."]

    def test_ignores_blanks(self):
        assert filter_box_rules(["", "   ", None]) == []
