"""Backwards-compatible alias for `forage.graphic.geometry`.

Panel capacity moved into the shared geometry module, because how many figures
a panel holds is a question about its rectangle and the two were drifting apart
in separate files. Existing imports keep working; new code should import from
`forage.graphic.geometry` directly.
"""

from __future__ import annotations

from forage.graphic.geometry import (  # noqa: F401
    CROWDED_PANEL_FIGURES,
    DEFAULT_PANEL_FIGURES,
    WIDE_MIN_W,
    WIDE_TALL_MIN_AREA,
    WIDE_TALL_MIN_H,
    Box,
    box_from_dict,
    canonical_panel_boxes,
    is_wide,
    is_wide_tall,
    page_size,
    panel_boxes,
    panel_capacities,
    panel_capacity,
)

__all__ = [
    "CROWDED_PANEL_FIGURES",
    "DEFAULT_PANEL_FIGURES",
    "WIDE_MIN_W",
    "WIDE_TALL_MIN_AREA",
    "WIDE_TALL_MIN_H",
    "Box",
    "box_from_dict",
    "canonical_panel_boxes",
    "is_wide",
    "is_wide_tall",
    "page_size",
    "panel_boxes",
    "panel_capacities",
    "panel_capacity",
]
