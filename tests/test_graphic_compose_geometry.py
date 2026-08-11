"""The layout stage plans balloon positions; the compositor draws panels.

They are separate modules that must agree on where a panel is, or a balloon
planned for the top of panel 3 is painted over the middle of panel 4. These
tests pin that agreement, because it used to hold only by coincidence: the
compositor's grid was hand-computed in pixels with fixed 420px rows, so it
matched the layout's fractional grid at 1536x2048 and nowhere else.
"""

from __future__ import annotations

import pytest

from forage.graphic.geometry import canonical_panel_boxes
from scripts.compose_graphic_panel_page import _page_size, _panel_boxes

PAGE_SIZES = [(1536, 2048), (1536, 3072), (2048, 2048), (1024, 1536), (3840, 2160)]


def _as_fractions(boxes, width: int, height: int):
    return [
        ((b.x2 - b.x1) / width, (b.y2 - b.y1) / height, b.x1 / width, b.y1 / height)
        for b in boxes
    ]


@pytest.mark.parametrize("width,height", PAGE_SIZES)
def test_the_six_panel_grid_matches_the_layout_grid_at_any_page_size(
    width: int, height: int
) -> None:
    """The regression: at 1536x3072 the bottom panel was 0.557 of the page here
    and 0.330 in the layout stage."""
    panels = [{"panel_number": i + 1} for i in range(6)]

    drawn = _as_fractions(_panel_boxes({}, panels, width, height), width, height)
    planned = [(b.w, b.h, b.x, b.y) for b in canonical_panel_boxes(6)]

    for got, want in zip(drawn, planned, strict=True):
        assert got == pytest.approx(want, abs=0.002)


@pytest.mark.parametrize("width,height", PAGE_SIZES)
@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 8])
def test_unplaced_pages_grid_the_same_way_in_both_stages(
    count: int, width: int, height: int
) -> None:
    panels = [{"panel_number": i + 1} for i in range(count)]

    drawn = _as_fractions(
        _panel_boxes({"page_number": 1}, panels, width, height), width, height
    )
    planned = [(b.w, b.h, b.x, b.y) for b in canonical_panel_boxes(count)]

    assert len(drawn) == count, "every panel must get a rectangle to draw into"
    for got, want in zip(drawn, planned, strict=True):
        assert got == pytest.approx(want, abs=0.002)


def test_explicit_boxes_still_win() -> None:
    panels = [{"box": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.25}}]

    box = _panel_boxes({"page_number": 1}, panels, 1000, 1000)[0]

    assert (box.x1, box.y1, box.x2, box.y2) == (100, 200, 600, 450)


def test_a_page_with_no_panels_yields_no_boxes() -> None:
    """Degenerate but harmless — there is nothing to draw. Unchanged behavior."""
    assert _panel_boxes({"page_number": 1}, [], 1536, 2048) == []


@pytest.mark.parametrize("width,height", PAGE_SIZES)
def test_the_compositor_reads_page_size_the_same_way_the_layout_does(
    width: int, height: int
) -> None:
    """Agreeing on the grid is worth nothing if the two stages disagree on how
    big the page is — the fractions would be resolved against different pixels."""
    page = {"page_size": {"width": width, "height": height}}

    assert _page_size(page) == (width, height)
    assert _page_size({}) == _page_size({"page_size": {}})
