"""One source of truth for graphic-novel page geometry.

Panel rectangles are decided in one stage and drawn in another. Before this
module each stage carried its own copy — two `Box` classes with incompatible
fields (`x/y/w/h` versus `x1/y1/x2/y2`), two page-size readers, two panel-box
resolvers, and two hand-written six-panel grids. They happened to agree, but
nothing made them agree, and a balloon planned against one grid and drawn
against another lands somewhere the layout never intended.

Two coordinate systems exist on purpose:

- **Fractions of the page** (this module's `Box`) are what stages exchange and
  what is written to the storyboard JSON. They survive a change of output
  resolution.
- **Pixels** are what the compositor and letterer draw in. Convert at the edge
  with `to_pixel_rect`, never earlier.

Capacity lives here too, because how many figures a panel can hold is a
question about its rectangle. The lettering policy caps balloons and the
thumbnail layout caps staged figures; both read the cap from here so they
cannot disagree and leave a balloon with no one to speak it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_PAGE_WIDTH = 1536
DEFAULT_PAGE_HEIGHT = 2048

WIDE_MIN_W = 0.86
WIDE_TALL_MIN_H = 0.55

# A page split into two equal tiers leaves each panel about 0.48 high once
# margins and the gutter are taken out, so a height-only test can never promote
# the most common full-width panel. Area preserves the intent — a panel with
# room for three figures — without excluding two-tier pages.
WIDE_TALL_MIN_AREA = 0.42

CROWDED_PANEL_FIGURES = 3
DEFAULT_PANEL_FIGURES = 2

PAGE_MARGIN = 0.015
PANEL_GUTTER = 0.016


@dataclass(frozen=True)
class Box:
    """A rectangle in page fractions, origin top-left."""

    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h

    def as_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "w": round(self.w, 4),
            "h": round(self.h, 4),
        }

    def to_pixel_rect(self, width: int, height: int) -> tuple[int, int, int, int]:
        """(x1, y1, x2, y2) in pixels, for the compositor and letterer."""
        return (
            round(self.x * width),
            round(self.y * height),
            round(self.x2 * width),
            round(self.y2 * height),
        )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def box_from_dict(raw: Any) -> Box | None:
    """Read either storage form, or None when the value is not a rectangle.

    Stages write `x/y/w/h`; some older artifacts carry `x1/y1/x2/y2`. Both are
    accepted so a stage never has to care which produced its input.
    """
    if not isinstance(raw, dict):
        return None
    try:
        if {"x", "y", "w", "h"} <= set(raw):
            return Box(_clamp(float(raw["x"])), _clamp(float(raw["y"])),
                       _clamp(float(raw["w"])), _clamp(float(raw["h"])))
        if {"x1", "y1", "x2", "y2"} <= set(raw):
            x1, y1 = _clamp(float(raw["x1"])), _clamp(float(raw["y1"]))
            x2, y2 = _clamp(float(raw["x2"])), _clamp(float(raw["y2"]))
            return Box(x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1))
    except (TypeError, ValueError):
        return None
    return None


def page_size(page: Any) -> tuple[int, int]:
    """Output pixel size for a page, defaulting to the standard trim."""
    if not isinstance(page, dict):
        return DEFAULT_PAGE_WIDTH, DEFAULT_PAGE_HEIGHT
    size = page.get("page_size") or {}
    try:
        width = int(size.get("width") or page.get("width") or DEFAULT_PAGE_WIDTH)
        height = int(size.get("height") or page.get("height") or DEFAULT_PAGE_HEIGHT)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_WIDTH, DEFAULT_PAGE_HEIGHT
    return width, height


# Hand-tuned grids, keyed by panel count, as (x, y, w, h) fractions.
_CANONICAL_GRIDS: dict[int, tuple[tuple[float, float, float, float], ...]] = {
    1: ((0.015, 0.015, 0.97, 0.97),),
    2: (
        (0.015, 0.012, 0.97, 0.482),
        (0.015, 0.506, 0.97, 0.482),
    ),
    3: (
        (0.015, 0.015, 0.97, 0.39),
        (0.015, 0.42, 0.477, 0.565),
        (0.508, 0.42, 0.477, 0.565),
    ),
    4: (
        (0.015, 0.015, 0.477, 0.477),
        (0.508, 0.015, 0.477, 0.477),
        (0.015, 0.508, 0.477, 0.477),
        (0.508, 0.508, 0.477, 0.477),
    ),
    5: (
        (0.015, 0.015, 0.97, 0.29),
        (0.015, 0.32, 0.477, 0.32),
        (0.508, 0.32, 0.477, 0.32),
        (0.015, 0.655, 0.477, 0.33),
        (0.508, 0.655, 0.477, 0.33),
    ),
    # Six-panel exchange: wide top, two two-up rows, wide bottom.
    6: (
        (0.015, 0.012, 0.97, 0.205),
        (0.015, 0.227, 0.477, 0.205),
        (0.508, 0.227, 0.477, 0.205),
        (0.015, 0.443, 0.477, 0.205),
        (0.508, 0.443, 0.477, 0.205),
        (0.015, 0.658, 0.97, 0.33),
    ),
}


def _stacked_grid(count: int) -> tuple[tuple[float, float, float, float], ...]:
    """A two-up grid for panel counts the hand-tuned table does not cover.

    `--panels-per-page` is unbounded and the storyboard model can overshoot its
    target, so a page can arrive with more panels than any canonical grid holds.
    Without this every panel past the table would be left unplaced, and an
    unplaced panel is dropped from layout entirely — losing its art direction and
    every balloon on it. The proportions match the four-panel grid so a large
    page reads as more of the same page, not a different design.
    """
    usable = 1.0 - 2 * PAGE_MARGIN
    rows = (count + 1) // 2
    row_h = (usable - PANEL_GUTTER * (rows - 1)) / rows
    col_w = (usable - PANEL_GUTTER) / 2
    right_x = PAGE_MARGIN + col_w + PANEL_GUTTER

    boxes: list[tuple[float, float, float, float]] = []
    for index in range(count):
        row, col = divmod(index, 2)
        y = PAGE_MARGIN + row * (row_h + PANEL_GUTTER)
        # An odd final panel has no partner, so it spans the tier.
        if index == count - 1 and col == 0:
            boxes.append((PAGE_MARGIN, y, usable, row_h))
        else:
            boxes.append((PAGE_MARGIN if col == 0 else right_x, y, col_w, row_h))
    return tuple(boxes)


def canonical_panel_boxes(count: int) -> list[Box]:
    """The grid assigned to a page of `count` panels that carries no boxes."""
    if count <= 0:
        return []
    grid = _CANONICAL_GRIDS.get(count) or _stacked_grid(count)
    return [Box(x, y, w, h) for x, y, w, h in grid]


def panel_boxes(panels: list[Any]) -> list[Box]:
    """Rectangles for a page's panels, falling back to the canonical grid.

    Explicit boxes are honored only when *every* panel carries one: a
    half-placed page is regridded wholesale rather than mixing authored and
    canonical geometry, which would overlap. The result lines up one-to-one with
    `panels`, so callers can index it by panel position.
    """
    if not panels:
        return []
    explicit = [
        box_from_dict(panel.get("box")) if isinstance(panel, dict) else None
        for panel in panels
    ]
    if all(box is not None for box in explicit):
        return [box for box in explicit if box is not None]
    return canonical_panel_boxes(len(panels))


def is_wide(box: Any) -> bool:
    resolved = box if isinstance(box, Box) else box_from_dict(box)
    return resolved is not None and resolved.w >= WIDE_MIN_W


def is_wide_tall(box: Any) -> bool:
    """True when a panel is big enough to stage a three-way exchange."""
    resolved = box if isinstance(box, Box) else box_from_dict(box)
    if resolved is None or resolved.w < WIDE_MIN_W:
        return False
    return resolved.h >= WIDE_TALL_MIN_H or resolved.area >= WIDE_TALL_MIN_AREA


def panel_capacity(box: Any) -> int:
    """Maximum figures — and therefore speakers — this panel can carry.

    Panels with no usable rectangle fall back to the conservative cap, which is
    what every stage assumed before boxes existed.
    """
    return CROWDED_PANEL_FIGURES if is_wide_tall(box) else DEFAULT_PANEL_FIGURES


def panel_capacities(panels: list[Any]) -> list[int]:
    """Per-panel capacity for a page, resolving boxes first."""
    return [panel_capacity(box) for box in panel_boxes(panels)]
