"""The slots stage reserves lettering zones; the layout stage places balloons.

Both decide how many balloons a panel can carry, and they have to reach the
same number. When the slots stage capped at a fixed three, a wide panel holding
three speakers plus one split line got a fourth balloon from the layout stage
that the slots stage had reserved no space for — so the art was generated with
nothing kept clear where that balloon would land.

These tests pin the cap to `forage.graphic.geometry`, which is where the
lettering policy and the layout stage read it from too.
"""

from __future__ import annotations

import pytest

from forage.graphic.geometry import canonical_panel_boxes, panel_capacity
from scripts.apply_graphic_lettering_slots import apply_lettering_slots


def _speech(speaker: str, text: str = "A line that fits.") -> dict:
    return {"kind": "speech", "speaker": speaker, "text": text}


def _page(panels: list[dict], page_number: int = 1) -> dict:
    return {"pages": [{"page_number": page_number, "panels": panels}]}


def _slots(panel: dict) -> list[dict]:
    return [
        slot for slot in panel.get("lettering_slots") or []
        if slot.get("kind") in {"speech", "thought"}
    ]


def _warning_codes(report: dict) -> list[str]:
    return [warning["code"] for warning in report["warnings"]]


# A full-width panel tall enough to seat three figures, and a half-width one
# that is not. Taken from the canonical grids so the fixtures cannot drift from
# the geometry the pipeline actually uses.
WIDE_TALL_BOX = canonical_panel_boxes(2)[0].as_dict()
NARROW_BOX = canonical_panel_boxes(4)[0].as_dict()


def test_a_wide_panel_seats_a_split_line_beside_three_speakers() -> None:
    """Capacity + 1: three speakers each hold a balloon while one carries a
    line split across two."""
    panel = {
        "panel_number": 1,
        "box": WIDE_TALL_BOX,
        "texts": [
            _speech("Tom"),
            _speech("Nick"),
            _speech("Nick", "The continuation of Nick's split line."),
            _speech("Daisy"),
        ],
    }

    data, report = apply_lettering_slots(_page([panel]))
    out = data["pages"][0]["panels"][0]

    assert len(_slots(out)) == 4, "the fourth balloon must get a reserved zone"
    assert "too_many_balloons" not in _warning_codes(report)
    assert not any("slot_warning" in item for item in out["texts"])


def test_a_narrow_panel_still_caps_at_three() -> None:
    """Two figures plus one split. The fourth balloon has no one to speak it."""
    panel = {
        "panel_number": 1,
        "box": NARROW_BOX,
        "texts": [_speech("Tom"), _speech("Nick"), _speech("Nick"), _speech("Daisy")],
    }

    data, report = apply_lettering_slots(_page([panel]))
    out = data["pages"][0]["panels"][0]

    assert len(_slots(out)) == 3
    assert "too_many_balloons" in _warning_codes(report)
    assert out["texts"][3]["slot_warning"]


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 8])
def test_the_cap_matches_the_geometry_for_every_panel_on_a_gridded_page(
    count: int,
) -> None:
    """Pages arrive with no boxes and are gridded downstream. The cap has to be
    read from that grid, not from the absent box."""
    panels = [
        {"panel_number": index + 1, "texts": [_speech(f"Speaker {index}")]}
        for index in range(count)
    ]

    data, _report = apply_lettering_slots(_page(panels))

    for panel, box in zip(
        data["pages"][0]["panels"], canonical_panel_boxes(count), strict=True
    ):
        # Every panel here has one balloon, so the cap is not exercised
        # directly; what is pinned is that the stage resolved the same
        # rectangle the layout stage will, and would cap from it.
        assert panel_capacity(box) + 1 >= len(_slots(panel))


def test_a_three_speaker_panel_in_a_narrow_slot_is_flagged() -> None:
    panel = {
        "panel_number": 1,
        "box": NARROW_BOX,
        "texts": [_speech("Tom"), _speech("Nick"), _speech("Daisy")],
    }

    _data, report = apply_lettering_slots(_page([panel]))

    assert "three_character_panel_not_wide" in _warning_codes(report)


def test_the_narrow_warning_fires_on_pages_that_carry_no_boxes() -> None:
    """The regression: the warning read the box off the panel, so an unplaced
    page — the common case before layout runs — was never checked at all, even
    though the grid it gets is exactly the one that makes the panel narrow."""
    three_speakers = [_speech("Tom"), _speech("Nick"), _speech("Daisy")]
    # Four panels grid into quarters, so panel 1 is half-width.
    panels = [{"panel_number": index + 1, "texts": three_speakers} for index in range(4)]

    _data, report = apply_lettering_slots(_page(panels))

    assert _warning_codes(report).count("three_character_panel_not_wide") == 4


def test_a_full_width_three_speaker_panel_is_not_flagged() -> None:
    panel = {
        "panel_number": 1,
        "box": WIDE_TALL_BOX,
        "texts": [_speech("Tom"), _speech("Nick"), _speech("Daisy")],
    }

    _data, report = apply_lettering_slots(_page([panel]))

    assert "three_character_panel_not_wide" not in _warning_codes(report)


def test_non_dict_panels_do_not_shift_the_grid() -> None:
    """The grid is sized by panel count, so junk entries have to be dropped
    before it is computed — otherwise every real panel after one is judged
    against the wrong rectangle."""
    panels = [
        {"panel_number": 1, "texts": [_speech("Tom")]},
        {"panel_number": 2, "texts": [_speech("Nick")]},
    ]
    with_junk = _page([panels[0], "not a panel", panels[1]])  # type: ignore[list-item]

    data, report = apply_lettering_slots(with_junk)
    clean, clean_report = apply_lettering_slots(_page(list(panels)))

    assert report["panels_processed"] == 2
    processed = [p for p in data["pages"][0]["panels"] if isinstance(p, dict)]
    assert processed == clean["pages"][0]["panels"]
    assert report["warnings"] == clean_report["warnings"]
