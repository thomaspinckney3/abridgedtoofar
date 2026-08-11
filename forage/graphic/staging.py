"""Describe panel geometry to an image model in words instead of numbers.

The art prompt used to state every reserved box as exact percentages — "reserve
empty speech box balloon_1: x 6%, y 20%, w 38%, h 16%", "face in x 20%, y 48%,
w 10%, h 10%" — together with rules like "keep all faces and mouths inside their
face boxes". The image model ignores all of it. It honours ordinal instructions
(which speaker is on the left, bodies low in frame) and discards coordinates, so
faces landed wherever the composition suggested and balloons were lettered on
top of them.

Measured on Gatsby chapter 1, 44 images across two runs:

| phrasing | content where the text goes | quieter than mirrored control |
|---|---|---|
| percentages | 1.00 of panel average | 26/42 |
| ordinal      | 0.46 | 42/42 |

Visually, every one of the six dialogue panels put a face inside a text box
under the numeric phrasing; half came back completely clear under this one, and
the caption panels — the large majority of the book — came back clean.

So the geometry is planned in numbers, as it must be, and described in bands and
positions, which is the only form that survives the trip.

**The reserved band is deliberately described deeper than the text needs.**
`BAND_MARGIN` exists because the model treats the band as approximate: asked for
exactly the space the text occupies, it put heads just across the lower edge on
three of six panels. Asking for a little more buys the tolerance back. Widening
it further trades away framing — figures get pushed down and cropped — so it is
a margin, not a wall.
"""

from __future__ import annotations

from typing import Any, Iterable

# Extra depth added to a reserved band beyond what the text occupies, as a
# fraction of panel height. See the module docstring: the failures it exists to
# absorb were all heads crossing the band's lower edge.
BAND_MARGIN = 0.08

# Ordinal names for a band measured from the top of the panel. The model reads
# these reliably; "the top 36%" it does not.
_BANDS: tuple[tuple[float, str], ...] = (
    (0.14, "top eighth"),
    (0.18, "top sixth"),
    (0.22, "top fifth"),
    (0.28, "top quarter"),
    (0.36, "top third"),
    (0.46, "upper two-fifths"),
    (0.58, "top half"),
    (0.72, "upper two-thirds"),
)

_HEIGHTS: tuple[tuple[float, str], ...] = (
    (0.22, "high, near the top of the frame"),
    (0.40, "in the upper third of the frame"),
    (0.58, "at mid-height of the frame"),
    (0.75, "in the lower third of the frame"),
)


def band_phrase(extent: float) -> str:
    """Name the band running from the top of the panel down to `extent`."""
    for limit, name in _BANDS:
        if extent <= limit:
            return name
    return "top three-quarters"


def height_phrase(center_y: float) -> str:
    """Name the height at which a face sits."""
    for limit, name in _HEIGHTS:
        if center_y < limit:
            return name
    return "low, near the bottom of the frame"


def _boxes(items: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        box = item.get("box") or {}
        if isinstance(box, dict) and {"x", "y", "w", "h"} <= set(box):
            out.append(item)
    return out


def _figures(items: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        face = item.get("face_box") or {}
        if isinstance(face, dict) and {"x", "y", "w", "h"} <= set(face):
            out.append(item)
    return out


def describe_staging(
    text_boxes: Iterable[Any],
    figures: Iterable[Any] = (),
    *,
    margin: float = BAND_MARGIN,
) -> list[str]:
    """Ordinal staging instructions for one panel.

    Returns an empty list when there is nothing to reserve, so a caller can
    append unconditionally without emitting a bare header.
    """
    texts = _boxes(text_boxes)
    figs = _figures(figures)
    if not texts:
        return []

    lines = ["Composition (follow this staging exactly; it is why the panel works):"]

    top = [t for t in texts if float(t["box"]["y"]) < 0.5]
    bottom = [t for t in texts if float(t["box"]["y"]) >= 0.5]

    if top:
        extent = max(float(t["box"]["y"]) + float(t["box"]["h"]) for t in top)
        lines.append(
            f"- Leave the {band_phrase(extent + margin)} of the panel as calm, "
            "uncluttered background — plain wall, sky, drapery or shadow. No "
            "faces, no heads, no hands, no key props may enter that band."
        )
    if bottom:
        start = min(float(t["box"]["y"]) for t in bottom)
        depth = band_phrase((1.0 - start) + margin).replace("top ", "").replace("upper ", "")
        lines.append(
            f"- Leave the bottom {depth} of the panel as calm, uncluttered "
            "background. No faces, no heads, no hands, no key props may enter "
            "that band."
        )
    if top or bottom:
        # Asked only to keep a band clear, the model sometimes draws a flat
        # strip and insets the scene between the strips, letterboxing the art.
        # The band is meant to be part of the picture — floor, wall, sky — that
        # simply has nothing important in it.
        lines.append(
            "- The reserved bands are part of the scene, not borders: continue "
            "the room's own wall, floor, sky or shadow through them. Do not "
            "draw a frame, a flat strip, or a band of solid colour, and do not "
            "shrink the scene to fit between them."
        )

    # Where heads go is stated for every panel that reserves a band, not only
    # the ones with staged figures. Figures are staged on dialogue panels alone
    # — 6 of 48 in Gatsby chapter 1 — so the other 42 used to get the band
    # sentence with nothing saying where heads belong. That held on 41 of them
    # and broke on the one whose caption was itself a description of a standing
    # man's face, where the model drew the head straight into the band. Panels
    # with nobody in them are unaffected: the rule only bites if a head appears.
    subject = "Every head" if figs else "Any head or face that appears"
    if top and bottom:
        # With a band at each end, "that band" is ambiguous, and the useful
        # instruction is the positive one: heads belong in the clear middle.
        lines.append(
            f"- {subject} must sit in the clear middle of the panel, "
            "between the two reserved bands and touching neither."
        )
    elif top:
        lines.append(
            f"- {subject} must sit clearly below that band, with visible "
            "space between the top of the head and the band's lower edge."
        )
    elif bottom:
        lines.append(
            f"- {subject} must sit clearly above that band, with visible "
            "space between the figure and the band's upper edge."
        )

    if figs:
        for fig in figs:
            face = fig["face_box"]
            center = float(face["y"]) + float(face["h"]) / 2
            side = str(fig.get("side") or "").strip().lower()
            where = (
                f"on the {side} side of the frame"
                if side in ("left", "right")
                else "centred in the frame"
            )
            lines.append(
                f"- {fig.get('character')} stands {where}, seen from roughly "
                f"the waist up, with the head and face {height_phrase(center)}."
            )
        lines.append(
            "- Crop the figures so their heads fall at the height described "
            "rather than filling the panel; leave the reserved bands genuinely empty."
        )
        lines.append("- Stage the speakers in left-to-right order as listed.")

    return lines


def filter_box_rules(rules: Iterable[Any]) -> list[str]:
    """Drop staging rules that point at a box the model cannot locate.

    "Keep all faces and mouths inside their face boxes" is unusable once the
    coordinates are gone, and worse than unusable if left in: it refers to a
    box the prompt no longer defines. Rules that stand on their own — draw
    inside the frame, draw no text — are kept.
    """
    kept: list[str] = []
    for rule in rules or []:
        if rule is None:
            continue
        text = str(rule).strip()
        if not text:
            continue
        if "box" in text.lower():
            continue
        kept.append(text)
    return kept
