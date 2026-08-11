"""Apply deterministic captions to standalone graphic-novel frame images.

Usage:
  python -m scripts.letter_graphic_novel_frames \
      work/mobydick/graphic_novel/chapter1_four_frame_spine

Reads storyboard.json with a top-level ``frames`` array and generated frame
images named frame_###.png, then writes lettered frame_###.png files and a PDF.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from scripts.letter_graphic_novel_pages import (
    Box,
    _caption_parts,
    _draw_text_box,
    _fit_lines,
    _load_font,
    _measure_text_box,
    _placement,
)

ZONE_MAP = {
    "top_left": ("top", "left"),
    "top_center": ("top", "center"),
    "top_right": ("top", "right"),
    "middle_left": ("middle", "left"),
    "middle_center": ("middle", "center"),
    "middle_right": ("middle", "right"),
    "bottom_left": ("bottom", "left"),
    "bottom_center": ("bottom", "center"),
    "bottom_right": ("bottom", "right"),
}

ANCHOR_X = {
    "left": 0.24,
    "center_left": 0.36,
    "center": 0.50,
    "center_right": 0.64,
    "right": 0.76,
}

ANCHOR_Y = {
    "head": 0.30,
    "mouth": 0.34,
    "upper_body": 0.44,
    "hand": 0.52,
}


def _zone_origin(frame_box: Box, box_w: int, box_h: int, zone: str, inset: int) -> tuple[int, int]:
    vertical, horizontal = ZONE_MAP.get(zone, ZONE_MAP["top_center"])
    if horizontal == "left":
        x = frame_box.x1 + inset
    elif horizontal == "right":
        x = frame_box.x2 - inset - box_w
    else:
        x = frame_box.x1 + (frame_box.width - box_w) // 2

    if vertical == "bottom":
        y = frame_box.y2 - inset - box_h
    elif vertical == "middle":
        y = frame_box.y1 + (frame_box.height - box_h) // 2
    else:
        y = frame_box.y1 + inset
    return x, y


def _cap_tail_length(
    attach: tuple[int, int],
    tail_point: tuple[int, int],
    max_length: int,
) -> tuple[int, int]:
    """Shorten a tail to `max_length`, keeping its direction.

    Direction is what a tail communicates — which character is speaking. Length
    communicates nothing, so a tail long enough to cross the artwork is all cost
    and no signal. Anything already within the limit is returned untouched.
    """
    ax, ay = attach
    px, py = tail_point
    dx, dy = px - ax, py - ay
    length = (dx * dx + dy * dy) ** 0.5
    if length <= max_length or length == 0:
        return tail_point
    scale = max_length / length
    return (round(ax + dx * scale), round(ay + dy * scale))


def _attach_side(
    tail_point: tuple[int, int],
    x: int,
    y: int,
    box_w: int,
    box_h: int,
) -> str:
    """Pick the balloon edge a tail should leave from.

    Testing x before y picks a side on the wrong axis whenever the speaker is
    mostly above or below the balloon but a little to one side: a mouth 141px
    up and 18px left used to attach to the left edge, producing a sliver two
    pad-widths tall and 18px long instead of a wedge off the top. Choosing the
    edge the speaker is furthest beyond keeps the tail on the dominant axis.
    """
    # Vertical edges are listed first so that a speaker equally far below and to
    # the left tails off the bottom, which is where comics put it, rather than
    # off the side. max() keeps the first of equal values.
    gaps = {
        "bottom": tail_point[1] - (y + box_h),
        "top": y - tail_point[1],
        "left": x - tail_point[0],
        "right": tail_point[0] - (x + box_w),
    }
    return max(gaps, key=lambda side: gaps[side])


def _anchor_outside_balloon(
    tail_point: tuple[int, int],
    x: int,
    y: int,
    box_w: int,
    box_h: int,
    min_length: int,
) -> tuple[int, int]:
    """Push an anchor that the balloon has grown over back outside it.

    A tall balloon can swallow its own anchor point. The attach-side chain below
    reads that as "below the balloon" and draws the tail from the bottom edge
    *up into* the balloon, striking its outline through the last two lines of
    text. Projecting through the nearest edge first keeps the tail pointing the
    way the speaker actually lies — normally down, since the layout stages
    figures beneath the balloon band.
    """
    px, py = tail_point
    if not (x <= px <= x + box_w and y <= py <= y + box_h):
        return tail_point
    distances = (
        (py - y, (px, y - min_length)),
        ((y + box_h) - py, (px, y + box_h + min_length)),
        (px - x, (x - min_length, py)),
        ((x + box_w) - px, (x + box_w + min_length, py)),
    )
    return min(distances, key=lambda pair: pair[0])[1]


def _anchor_point(frame_box: Box, item: dict[str, Any]) -> tuple[int, int]:
    x_ratio_raw = item.get("anchor_x_ratio")
    y_ratio_raw = item.get("anchor_y_ratio")
    if x_ratio_raw is not None and y_ratio_raw is not None:
        x_ratio = max(0.0, min(1.0, float(x_ratio_raw)))
        y_ratio = max(0.0, min(1.0, float(y_ratio_raw)))
        return (
            frame_box.x1 + round(frame_box.width * x_ratio),
            frame_box.y1 + round(frame_box.height * y_ratio),
        )
    speaker_position = (
        str(item.get("speaker_position") or item.get("speaker_side") or "center")
        .strip()
        .lower()
        .replace("-", "_")
    )
    anchor = str(item.get("anchor") or "mouth").strip().lower().replace("-", "_")
    x_ratio = ANCHOR_X.get(speaker_position, ANCHOR_X["center"])
    y_ratio = ANCHOR_Y.get(anchor, ANCHOR_Y["mouth"])
    return (
        frame_box.x1 + round(frame_box.width * x_ratio),
        frame_box.y1 + round(frame_box.height * y_ratio),
    )


def _slot_box(frame_box: Box, value: dict[str, Any]) -> Box:
    if {"x1", "y1", "x2", "y2"} <= set(value):
        x1 = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(value["x1"]))))
        y1 = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(value["y1"]))))
        x2 = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(value["x2"]))))
        y2 = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(value["y2"]))))
        return Box(x1, y1, x2, y2)
    if {"x", "y", "w", "h"} <= set(value):
        x1 = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(value["x"]))))
        y1 = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(value["y"]))))
        return Box(
            x1,
            y1,
            x1 + round(frame_box.width * max(0.0, min(1.0, float(value["w"])))),
            y1 + round(frame_box.height * max(0.0, min(1.0, float(value["h"])))),
        )
    raise ValueError(f"slot box must use x/y/w/h or x1/y1/x2/y2: {value}")


def _balloon_rect_from_slot(
    image: Image.Image,
    frame_box: Box,
    text: str,
    slot_box_ratio: dict[str, Any],
) -> tuple[int, int, int, int, list[str], ImageDraw.ImageDraw, Any, int]:
    draw = ImageDraw.Draw(image)
    scale = min(image.size) / 1024
    slot = _slot_box(frame_box, slot_box_ratio)
    pad_x = max(10, round(14 * scale))
    pad_y = max(7, round(9 * scale))
    box_w = max(80, slot.width)
    box_h = max(42, slot.height)
    max_text_w = max(60, box_w - 2 * pad_x)
    max_text_h = max(24, box_h - 2 * pad_y)
    font, lines, line_h = _fit_lines(
        text,
        "dialogue",
        max_text_w,
        max_text_h,
        draw,
        max_size=max(18, round(22 * scale)),
        min_size=max(10, round(12 * scale)),
    )
    leading = math.ceil(line_h * 1.15)
    text_w = max(math.ceil(draw.textlength(line, font=font)) for line in lines)
    text_h = leading * len(lines)
    box_w = min(slot.width, max(text_w + 2 * pad_x, round(110 * scale)))
    box_h = min(slot.height, text_h + 2 * pad_y)

    slot_center_x = (slot.x1 + slot.x2) / 2
    frame_center_x = (frame_box.x1 + frame_box.x2) / 2
    if slot_center_x < frame_center_x - frame_box.width * 0.12:
        x = slot.x1
    elif slot_center_x > frame_center_x + frame_box.width * 0.12:
        x = slot.x2 - box_w
    else:
        x = slot.x1 + (slot.width - box_w) // 2

    slot_center_y = (slot.y1 + slot.y2) / 2
    frame_center_y = (frame_box.y1 + frame_box.y2) / 2
    if slot_center_y > frame_center_y:
        y = slot.y2 - box_h
    else:
        y = slot.y1

    x = max(frame_box.x1 + 4, min(x, frame_box.x2 - box_w - 4))
    y = max(frame_box.y1 + 4, min(y, frame_box.y2 - box_h - 4))
    return x, y, box_w, box_h, lines, draw, font, leading


def _balloon_rect(
    image: Image.Image,
    frame_box: Box,
    text: str,
    zone: str,
    stack_index: int,
    stack_count: int,
) -> tuple[int, int, int, int, list[str], ImageDraw.ImageDraw, Any, int]:
    draw = ImageDraw.Draw(image)
    scale = min(image.size) / 1024
    inset = max(12, round(min(frame_box.width, frame_box.height) * 0.04))
    pad_x = max(12, round(16 * scale))
    pad_y = max(8, round(10 * scale))
    gap = max(8, round(12 * scale))
    max_box_w = frame_box.width - 2 * inset
    target_w = min(max_box_w, max(round(frame_box.width * 0.30), round(210 * scale)))
    max_text_w = max(70, target_w - 2 * pad_x)
    max_text_h = max(34, round(frame_box.height * 0.30))
    font, lines, line_h = _fit_lines(
        text,
        "dialogue",
        max_text_w,
        max_text_h,
        draw,
        max_size=max(18, round(22 * scale)),
        min_size=max(12, round(13 * scale)),
    )
    leading = math.ceil(line_h * 1.15)
    text_w = max(math.ceil(draw.textlength(line, font=font)) for line in lines)
    text_h = leading * len(lines)
    box_w = min(max_box_w, max(text_w + 2 * pad_x, round(115 * scale)))
    box_h = text_h + 2 * pad_y
    x, y = _zone_origin(frame_box, box_w, box_h, zone, inset)

    vertical, horizontal = ZONE_MAP.get(zone, ZONE_MAP["top_center"])
    if stack_count > 1:
        if horizontal == "left":
            x += stack_index * (box_w + gap)
        elif horizontal == "right":
            x -= stack_index * (box_w + gap)
        else:
            total_w = stack_count * box_w + (stack_count - 1) * gap
            x = frame_box.x1 + (frame_box.width - total_w) // 2 + stack_index * (box_w + gap)
    x = max(frame_box.x1 + 4, min(x, frame_box.x2 - box_w - 4))
    y = max(frame_box.y1 + 4, min(y, frame_box.y2 - box_h - 4))
    return x, y, box_w, box_h, lines, draw, font, leading


def _rect_hits_avoidance(
    rect: tuple[int, int, int, int],
    *,
    frame_box: Box,
    item: dict[str, Any],
    placed_rects: list[tuple[int, int, int, int]] | None = None,
) -> bool:
    x1, y1, x2, y2 = rect
    pad_x = max(18, round(frame_box.width * 0.035))
    pad_y = max(18, round(frame_box.height * 0.045))
    for point in item.get("avoid_anchor_points_ratio") or []:
        if not isinstance(point, dict) or point.get("x") is None or point.get("y") is None:
            continue
        px = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(point["x"]))))
        py = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(point["y"]))))
        if x1 - pad_x <= px <= x2 + pad_x and y1 - pad_y <= py <= y2 + pad_y:
            return True
    for box in item.get("avoid_boxes_ratio") or []:
        if not isinstance(box, dict) or not {"x1", "y1", "x2", "y2"} <= set(box):
            continue
        bx1 = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(box["x1"]))))
        by1 = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(box["y1"]))))
        bx2 = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(box["x2"]))))
        by2 = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(box["y2"]))))
        if x1 - pad_x < bx2 and x2 + pad_x > bx1 and y1 - pad_y < by2 and y2 + pad_y > by1:
            return True
    # Balloons already lettered into this panel. Band placement kept them apart
    # by construction — one per zone, stacked. Placing each beside its own
    # speaker removes that guarantee, so they have to be avoided explicitly.
    for px1, py1, px2, py2 in placed_rects or ():
        if x1 - pad_x < px2 and x2 + pad_x > px1 and y1 - pad_y < py2 and y2 + pad_y > py1:
            return True
    return False


def _avoid_rects(
    frame_box: Box,
    item: dict[str, Any],
    placed_rects: list[tuple[int, int, int, int]] | None,
) -> list[tuple[int, int, int, int]]:
    """Everything in this panel a balloon should stay off, in pixels."""
    rects: list[tuple[int, int, int, int]] = list(placed_rects or ())
    for box in item.get("avoid_boxes_ratio") or []:
        if not isinstance(box, dict) or not {"x1", "y1", "x2", "y2"} <= set(box):
            continue
        rects.append((
            frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(box["x1"])))),
            frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(box["y1"])))),
            frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(box["x2"])))),
            frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(box["y2"])))),
        ))
    return rects


def _overlap_area(
    rect: tuple[int, int, int, int],
    *,
    frame_box: Box,
    item: dict[str, Any],
    placed_rects: list[tuple[int, int, int, int]] | None = None,
) -> float:
    """How much of `rect` lands on something it should not.

    A boolean hit-test cannot rank two bad positions, and when every candidate
    collides the ranking is the only thing left to choose on. Faces are weighted
    far above the rest: covering one is the defect this whole stage exists to
    prevent, while clipping a caption is merely untidy.
    """
    x1, y1, x2, y2 = rect
    total = 0.0
    face_ratios = [
        box for box in item.get("avoid_boxes_ratio") or []
        if isinstance(box, dict) and {"x1", "y1", "x2", "y2"} <= set(box)
    ]
    face_count = len(face_ratios)
    for index, (bx1, by1, bx2, by2) in enumerate(
        _avoid_rects(frame_box, item, placed_rects)
    ):
        w = min(x2, bx2) - max(x1, bx1)
        h = min(y2, by2) - max(y1, by1)
        if w <= 0 or h <= 0:
            continue
        is_face = index >= len(placed_rects or ()) and face_count
        total += w * h * (12.0 if is_face else 1.0)
    for point in item.get("avoid_anchor_points_ratio") or []:
        if not isinstance(point, dict) or point.get("x") is None or point.get("y") is None:
            continue
        px = frame_box.x1 + round(frame_box.width * max(0.0, min(1.0, float(point["x"]))))
        py = frame_box.y1 + round(frame_box.height * max(0.0, min(1.0, float(point["y"]))))
        if x1 <= px <= x2 and y1 <= py <= y2:
            total += frame_box.width * frame_box.height * 0.02
    return total


def _avoidance_zones(zone: str) -> list[str]:
    order = [
        zone,
        "top_left",
        "top_center",
        "top_right",
        "middle_left",
        "middle_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    ]
    seen: set[str] = set()
    result: list[str] = []
    for item in order:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _draw_speech_balloon(
    image: Image.Image,
    frame_box: Box,
    item: dict[str, Any],
    *,
    stack_index: int,
    stack_count: int,
    placed_rects: list[tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    text = str(item.get("text", "")).strip()
    if not text:
        return {}
    kind = str(item.get("kind") or "speech").strip().lower()
    tail_style = str(item.get("tail_style") or "auto").strip().lower().replace("-", "_")
    zone = (
        str(item.get("balloon_zone") or item.get("placement") or "top_center")
        .strip()
        .lower()
        .replace("-", "_")
    )
    placement_mode = (
        str(item.get("balloon_placement_mode") or "").strip().lower().replace("-", "_")
    )
    near_speaker = placement_mode in {"near_speaker", "near_anchor"}
    slot_box_ratio = item.get("slot_box_ratio")
    # A slot is a reserved band. Near-speaker placement uses it for size only:
    # letting it also fix the position is what parked every balloon on the floor,
    # far from the speaker, which reads as a caption strip rather than dialogue.
    using_slot = isinstance(slot_box_ratio, dict)
    if using_slot:
        x, y, box_w, box_h, lines, draw, font, leading = _balloon_rect_from_slot(
            image,
            frame_box,
            text,
            slot_box_ratio,
        )
    else:
        x, y, box_w, box_h, lines, draw, font, leading = _balloon_rect(
            image,
            frame_box,
            text,
            zone,
            stack_index,
            stack_count,
        )
    scale = min(image.size) / 1024
    tail_point = _anchor_point(frame_box, item)
    if near_speaker:
        hgap = max(14, round(min(frame_box.width, frame_box.height) * 0.055))
        vgap = max(box_h, round(frame_box.height * 0.22))
        speaker_region = (
            str(item.get("speaker_region") or item.get("speaker_side") or "")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if "right" in speaker_region:
            preferred_sides = ("right", "left")
        elif "left" in speaker_region:
            preferred_sides = ("left", "right")
        else:
            left_space = tail_point[0] - frame_box.x1
            right_space = frame_box.x2 - tail_point[0]
            preferred_sides = ("right", "left") if right_space >= left_space else ("left", "right")

        # Score every candidate and take the least-obstructed one. First-fit
        # used to fall back to its own starting guess when nothing was clear,
        # which is how a balloon ended up underneath a caption that is drawn
        # after it — the worst available position rather than the best.
        candidates: list[tuple[int, int]] = []
        for side in preferred_sides:
            side_x = (
                tail_point[0] + hgap if side == "right" else tail_point[0] - box_w - hgap
            )
            for candidate_y in (
                tail_point[1] - box_h - vgap,
                tail_point[1] - box_h - hgap,
                tail_point[1] - box_h // 2,
                tail_point[1] + round(frame_box.height * 0.10),
            ):
                candidates.append((side_x, candidate_y))
        # Directly over the speaker, as a last resort when neither side is free.
        candidates.append((tail_point[0] - box_w // 2, tail_point[1] - box_h - vgap))

        best: tuple[float, float, int, int] | None = None
        for candidate_x, candidate_y in candidates:
            cx = max(frame_box.x1 + 4, min(candidate_x, frame_box.x2 - box_w - 4))
            cy = max(frame_box.y1 + 4, min(candidate_y, frame_box.y2 - box_h - 4))
            rect = (cx, cy, cx + box_w, cy + box_h)
            penalty = _overlap_area(
                rect, frame_box=frame_box, item=item, placed_rects=placed_rects
            )
            reach = abs(cx + box_w // 2 - tail_point[0]) + abs(cy + box_h - tail_point[1])
            if best is None or (penalty, reach) < (best[0], best[1]):
                best = (penalty, reach, cx, cy)
        if best is not None:
            x, y = best[2], best[3]
    elif not using_slot and _rect_hits_avoidance(
        (x, y, x + box_w, y + box_h),
        frame_box=frame_box,
        item=item,
        placed_rects=placed_rects,
    ):
        for candidate_zone in _avoidance_zones(zone):
            cx, cy, cbox_w, cbox_h, clines, cdraw, cfont, cleading = _balloon_rect(
                image,
                frame_box,
                text,
                candidate_zone,
                stack_index,
                stack_count,
            )
            if not _rect_hits_avoidance(
                (cx, cy, cx + cbox_w, cy + cbox_h),
                frame_box=frame_box,
                item=item,
                placed_rects=placed_rects,
            ):
                zone = candidate_zone
                x, y, box_w, box_h, lines, draw, font, leading = (
                    cx,
                    cy,
                    cbox_w,
                    cbox_h,
                    clines,
                    cdraw,
                    cfont,
                    cleading,
                )
                break

    pad_x = max(12, round(16 * scale))
    pad_y = max(8, round(10 * scale))
    if kind == "thought":
        fill = (255, 253, 238, 248)
        outline = (58, 54, 48, 255)
    else:
        fill = (255, 255, 255, 250)
        outline = (18, 17, 15, 255)
    radius = max(18, min(box_h // 2, round(32 * scale)))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    rect = (x, y, x + box_w, y + box_h)
    shadow_offset = max(2, round(3 * scale))
    shadow_rect = (
        x + shadow_offset,
        y + shadow_offset,
        x + box_w + shadow_offset,
        y + box_h + shadow_offset,
    )
    odraw.rounded_rectangle(
        shadow_rect,
        radius=radius,
        fill=(0, 0, 0, 42),
    )
    odraw.rounded_rectangle(
        rect,
        radius=radius,
        fill=fill,
        outline=outline,
        width=max(3, round(3 * scale)),
    )

    tail_pad = round(10 * scale)
    # Do this before choosing an attach side: the chain below has no "inside"
    # case, and would draw the tail back through the balloon's own text.
    tail_point = _anchor_outside_balloon(
        tail_point, x, y, box_w, box_h, min_length=max(tail_pad, round(14 * scale))
    )
    attach_side = _attach_side(tail_point, x, y, box_w, box_h)
    if attach_side in {"left", "right"}:
        attach_x = x if attach_side == "left" else x + box_w
        attach_y = max(y + tail_pad, min(tail_point[1], y + box_h - tail_pad))
    else:
        attach_x = max(x + round(box_w * 0.18), min(tail_point[0], x + round(box_w * 0.82)))
        attach_y = y if attach_side == "top" else y + box_h

    # A tail reaches toward the speaker; it does not have to arrive. Once the
    # caption and balloon bands moved to opposite ends of the panel, a balloon
    # could sit a third of a panel away from the mouth it belongs to, and a
    # triangle drawn the whole distance renders as a white spike across the art.
    # Capping the length keeps the tail pointing at the right character while
    # leaving the drawing intact — which is what comics do for a distant speaker.
    tail_point = _cap_tail_length(
        (attach_x, attach_y),
        tail_point,
        max_length=max(round(frame_box.height * 0.16), tail_pad * 3),
    )

    if tail_style in {"none", "no_tail", "tailess", "tailless", "hidden", "off"}:
        pass
    elif kind == "thought":
        # Thought bubbles are anchored with small trailing circles rather than
        # a speech tail, while still using the same detected speaker point.
        dx = tail_point[0] - attach_x
        dy = tail_point[1] - attach_y
        for step, radius_scale in ((1, 0.70), (2, 0.50), (3, 0.34)):
            cx = attach_x + round(dx * step / 4)
            cy = attach_y + round(dy * step / 4)
            r = max(4, round(radius * radius_scale * 0.35))
            odraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=outline)
    else:
        # A comic tail is part of the balloon's silhouette, not a spike stuck to
        # it. Drawing the two shapes separately left the balloon's own outline
        # running across the tail's base, which reads as a cone resting on a
        # box. The base is widened to roughly an eighth of the balloon and the
        # seam between them is painted out below.
        if attach_side in {"left", "right"}:
            base = max(tail_pad, round(box_h * 0.18))
            attach_y = max(y + base + 2, min(attach_y, y + box_h - base - 2))
            corner_a = (attach_x, attach_y - base)
            corner_b = (attach_x, attach_y + base)
        else:
            base = max(tail_pad, round(box_w * 0.13))
            attach_x = max(x + base + 2, min(attach_x, x + box_w - base - 2))
            corner_a = (attach_x - base, attach_y)
            corner_b = (attach_x + base, attach_y)
        stroke = max(3, round(3 * scale))
        odraw.polygon([corner_a, corner_b, tail_point], fill=fill, outline=outline, width=stroke)
        # Erase the balloon border between the tail's base corners so the two
        # shapes read as one continuous outline.
        odraw.line([corner_a, corner_b], fill=fill, width=round(stroke * 1.8))
    image.alpha_composite(overlay)

    draw = ImageDraw.Draw(image)
    text_y = y + pad_y
    for line in lines:
        # Comic lettering is centred in the balloon; flush-left reads as a
        # caption box or a chat bubble.
        line_w = draw.textlength(line, font=font)
        draw.text(
            (x + (box_w - line_w) / 2, text_y),
            line,
            font=font,
            fill=(20, 18, 16, 255),
        )
        text_y += leading
    return {
        "kind": kind,
        "tail_style": tail_style,
        "speaker": str(item.get("speaker", "")),
        "text": text,
        "balloon_zone": zone,
        "balloon_placement_mode": str(item.get("balloon_placement_mode") or ""),
        "speaker_position": str(item.get("speaker_position") or item.get("speaker_side") or "center"),
        "anchor": str(item.get("anchor") or "mouth"),
        "anchor_x_ratio": item.get("anchor_x_ratio"),
        "anchor_y_ratio": item.get("anchor_y_ratio"),
        # Which of the three anchor sources aimed this tail — a vision
        # detection, the layout's staged mouth, or the fixed fallback ratio.
        "anchor_source": str(item.get("anchor_source") or "default_ratio"),
        "slot_id": item.get("slot_id"),
        "box": {"x1": x, "y1": y, "x2": x + box_w, "y2": y + box_h},
        "tail_point": {"x": tail_point[0], "y": tail_point[1]},
    }


def letter_frame(image_path: Path, frame: dict[str, Any], out_path: Path) -> tuple[Box, list[dict[str, Any]]]:
    source = Image.open(image_path).convert("RGBA")
    width, height = source.size
    frame_box = Box(0, 0, width, height)
    dialogue_items = [
        item for item in frame.get("dialogue", []) or [] if isinstance(item, dict)
    ]
    dialogue_layout: list[dict[str, Any]] = []
    zone_counts: dict[str, int] = {}
    for item in dialogue_items:
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
    zone_seen: dict[str, int] = {}
    for index, item in enumerate(dialogue_items):
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        zone_index = zone_seen.get(zone, 0)
        zone_seen[zone] = zone_index + 1
        layout = _draw_speech_balloon(
            source,
            frame_box,
            item,
            stack_index=zone_index,
            stack_count=zone_counts.get(zone, 1),
        )
        if layout:
            dialogue_layout.append(layout)

    caption = str(frame.get("caption", "")).strip()
    caption_parts = _caption_parts(caption, "")
    vertical, horizontal = _placement(frame, "caption")
    if caption_parts:
        heights = [
            _measure_text_box(source, frame_box, part, kind="caption")
            for part in caption_parts
        ]
        for index, part in enumerate(caption_parts):
            _draw_text_box(
                source,
                frame_box,
                part,
                kind="caption",
                vertical=vertical,
                horizontal=horizontal,
                stack_index=index,
                stack_count=len(caption_parts),
                stack_total_h=sum(heights),
                stack_box_heights=heights,
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    source.convert("RGB").save(out_path)
    return frame_box, dialogue_layout


def letter_run(
    run_dir: Path,
    *,
    storyboard_path: Path | None = None,
    generated_dir: Path | None = None,
    out_dir: Path | None = None,
) -> None:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    generated_dir = generated_dir or run_dir / "generated_frames"
    out_dir = out_dir or run_dir / "lettered_frames"
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    frames = [frame for frame in data.get("frames", []) if isinstance(frame, dict)]

    diagnostics: dict[str, Any] = {"frames": []}
    output_frames: list[Path] = []
    for frame in frames:
        frame_no = int(frame.get("frame_number") or 0)
        image_path = generated_dir / f"frame_{frame_no:03d}.png"
        out_path = out_dir / f"frame_{frame_no:03d}.png"
        box, dialogue_layout = letter_frame(image_path, frame, out_path)
        output_frames.append(out_path)
        diagnostics["frames"].append({
            "frame_number": frame_no,
            "caption": str(frame.get("caption", "")),
            "caption_zone": str(frame.get("caption_zone", "")),
            "dialogue": [
                {
                    "speaker": str(item.get("speaker", "")),
                    "text": str(item.get("text", "")),
                    "balloon_zone": str(item.get("balloon_zone") or item.get("placement") or ""),
                    "speaker_position": str(item.get("speaker_position") or item.get("speaker_side") or ""),
                    "anchor": str(item.get("anchor") or ""),
                    "anchor_x_ratio": item.get("anchor_x_ratio"),
                    "anchor_y_ratio": item.get("anchor_y_ratio"),
                }
                for item in frame.get("dialogue", []) or []
                if isinstance(item, dict)
            ],
            "dialogue_layout": dialogue_layout,
            "source_image": str(image_path),
            "lettered_image": str(out_path),
            "frame_box": {
                "x1": box.x1,
                "y1": box.y1,
                "x2": box.x2,
                "y2": box.y2,
            },
        })

    (out_dir / "lettering_layout.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n",
        encoding="utf-8",
    )
    if output_frames:
        images = [Image.open(path).convert("RGB") for path in output_frames]
        first, rest = images[0], images[1:]
        first.save(out_dir / "lettered_frames.pdf", save_all=True, append_images=rest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--storyboard-json",
        type=Path,
        help="Frame storyboard JSON; defaults to run_dir/storyboard.json.",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        help="Directory containing frame_###.png art; defaults to generated_frames.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory; defaults to run_dir/lettered_frames.",
    )
    args = parser.parse_args()
    letter_run(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        generated_dir=args.generated_dir,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
