"""Compose panel art into deterministic graphic-novel pages and letter them.

Usage:
  python -m scripts.compose_graphic_panel_page \
      work/mobydick/graphic_novel/action_spine_v3/chapter_003/page_sequence_prototype

Reads storyboard.json with pages[].panels[], panel art images, and structured
caption/dialogue metadata. Writes generated_pages/page_###.png,
lettered_pages/page_###.png, lettered_pages/lettered_book.pdf, and
lettered_pages/layout.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps, JpegImagePlugin  # noqa: F401

from forage.graphic.geometry import canonical_panel_boxes, page_size
from scripts.letter_graphic_novel_frames import _balloon_rect, _draw_speech_balloon
from scripts.letter_graphic_novel_pages import (
    Box,
    _caption_parts,
    _draw_text_box,
    _fit_lines,
    _load_font,
    _measure_text_box,
    _placement,
)


AnchorKey = tuple[int, int, int]


def _page_size(page: dict[str, Any]) -> tuple[int, int]:
    return page_size(page)


def _relative_box(page_box: Box, value: dict[str, Any]) -> Box:
    if {"x1", "y1", "x2", "y2"} <= set(value):
        return Box(
            page_box.x1 + round(page_box.width * float(value["x1"])),
            page_box.y1 + round(page_box.height * float(value["y1"])),
            page_box.x1 + round(page_box.width * float(value["x2"])),
            page_box.y1 + round(page_box.height * float(value["y2"])),
        )
    if {"x", "y", "w", "h"} <= set(value):
        x1 = page_box.x1 + round(page_box.width * float(value["x"]))
        y1 = page_box.y1 + round(page_box.height * float(value["y"]))
        return Box(
            x1,
            y1,
            x1 + round(page_box.width * float(value["w"])),
            y1 + round(page_box.height * float(value["h"])),
        )
    raise ValueError(f"panel box must use x/y/w/h or x1/y1/x2/y2: {value}")


def _panel_boxes(page: dict[str, Any], panels: list[dict[str, Any]], width: int, height: int) -> list[Box]:
    """Pixel rectangles to draw each panel into.

    The fallback grid is derived from the shared fractional one rather than
    hand-computed in pixels. The old six-panel grid here used fixed 420px rows,
    so it matched the grid the layout stage plans against at 1536x2048 and
    nowhere else — at 1536x3072 the bottom panel came out 0.557 of the page
    instead of 0.330, and balloons were planned against one grid and painted
    against another.

    Any panel count is gridded, not just the layouts this stage used to name:
    the layout stage grids them all, so refusing here meant a page it planned
    happily could not be rendered at all.
    """
    page_box = Box(0, 0, width, height)
    explicit: list[Box] = []
    for panel in panels:
        raw = panel.get("box")
        if isinstance(raw, dict):
            explicit.append(_relative_box(page_box, raw))
    if len(explicit) == len(panels):
        return explicit
    return [
        Box(*box.to_pixel_rect(width, height))
        for box in canonical_panel_boxes(len(panels))
    ]


def _panel_image_path(panel: dict[str, Any], panel_dir: Path) -> Path:
    raw = panel.get("image") or panel.get("image_path")
    if raw:
        path = Path(str(raw))
        if not path.is_absolute():
            path = panel_dir / path
        return path
    panel_no = int(panel.get("panel_number") or 0)
    return panel_dir / f"panel_{panel_no:03d}.png"


def _paste_panel_art(
    page_image: Image.Image,
    source_path: Path,
    box: Box,
    *,
    fit_mode: str = "crop",
    draw_border: bool = True,
) -> None:
    if not source_path.exists():
        raise FileNotFoundError(f"missing panel art: {source_path}")
    source = Image.open(source_path).convert("RGB")
    if fit_mode == "contain":
        fitted = ImageOps.contain(source, (box.width, box.height), method=Image.Resampling.LANCZOS)
        panel_bg = Image.new("RGB", (box.width, box.height), (18, 16, 14))
        panel_bg.paste(
            fitted,
            ((box.width - fitted.width) // 2, (box.height - fitted.height) // 2),
        )
        page_image.paste(panel_bg, (box.x1, box.y1))
    else:
        fitted = ImageOps.fit(source, (box.width, box.height), method=Image.Resampling.LANCZOS)
        page_image.paste(fitted, (box.x1, box.y1))
    if draw_border:
        draw = ImageDraw.Draw(page_image)
        border_w = max(3, round(min(page_image.size) * 0.0024))
        draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline=(18, 16, 14), width=border_w)


def _zone_band(raw: Any) -> str:
    zone = str(raw or "").strip().lower().replace("-", "_")
    if "_" not in zone:
        return ""
    return zone.split("_", 1)[0]


def _reserved_band_counts(panel: dict[str, Any]) -> tuple[int, int]:
    top = 0
    bottom = 0
    for item in _text_items(panel):
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "caption":
            band = _zone_band(item.get("caption_zone") or "top_center")
        elif kind in {"speech", "thought"}:
            band = _zone_band(item.get("balloon_zone") or item.get("placement") or "bottom_center")
        else:
            continue
        if band == "top":
            top += 1
        elif band in {"bottom", "middle"}:
            bottom += 1
    return top, bottom


def _reserved_band_heights(
    panel: dict[str, Any],
    box: Box,
    image: Image.Image,
    *,
    include_balloons: bool = False,
) -> tuple[int, int]:
    text_items = _text_items(panel)
    inset = max(10, round(min(box.width, box.height) * 0.04))
    gap = max(6, round(min(box.width, box.height) * 0.018))
    band_zone_heights = {"top": {}, "bottom": {}}
    zone_counts: dict[str, int] = {}
    zone_seen: dict[str, int] = {}
    for item in text_items:
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in {"speech", "thought"}:
            continue
        if not include_balloons:
            continue
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "bottom_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    for item in text_items:
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "caption":
            zone = str(item.get("caption_zone") or "top_center").strip().lower().replace("-", "_")
            band = _zone_band(zone)
            if band not in band_zone_heights:
                continue
            height = _measure_text_box(image, box, str(item.get("text") or ""), kind="caption")
        elif kind in {"speech", "thought"}:
            if not include_balloons:
                continue
            zone = (
                str(item.get("balloon_zone") or item.get("placement") or "bottom_center")
                .strip()
                .lower()
                .replace("-", "_")
            )
            band = _zone_band(zone)
            if band == "middle":
                band = "bottom"
            if band not in band_zone_heights:
                continue
            stack_index = zone_seen.get(zone, 0)
            zone_seen[zone] = stack_index + 1
            _x, _y, _w, height, _lines, _draw, _font, _leading = _balloon_rect(
                image.convert("RGBA"),
                box,
                str(item.get("text") or ""),
                zone,
                stack_index,
                zone_counts.get(zone, 1),
            )
        else:
            continue
        zone_heights = band_zone_heights[band]
        zone_heights[zone] = zone_heights.get(zone, 0) + height + (gap if zone in zone_heights else 0)

    top_h = max(band_zone_heights["top"].values(), default=0)
    bottom_h = max(band_zone_heights["bottom"].values(), default=0)
    if top_h:
        top_h += 2 * inset
    if bottom_h:
        bottom_h += 2 * inset
    max_reserved = round(box.height * 0.64)
    total = top_h + bottom_h
    if total > max_reserved and total:
        scale = max_reserved / total
        top_h = round(top_h * scale)
        bottom_h = round(bottom_h * scale)
    min_art_h = max(80, round(box.height * 0.28))
    if box.height - top_h - bottom_h < min_art_h:
        excess = min_art_h - (box.height - top_h - bottom_h)
        while excess > 0 and (top_h or bottom_h):
            if bottom_h >= top_h and bottom_h > 0:
                bottom_h -= 1
            elif top_h > 0:
                top_h -= 1
            excess -= 1
    return top_h, bottom_h


def _paste_panel_with_reserved_bands(
    page_image: Image.Image,
    source_path: Path,
    box: Box,
    *,
    fit_mode: str,
    top_h: int,
    bottom_h: int,
) -> None:
    draw = ImageDraw.Draw(page_image)
    border_w = max(3, round(min(page_image.size) * 0.0024))
    page_image.paste((247, 244, 235), (box.x1, box.y1, box.x2, box.y2))
    art_box = Box(box.x1, box.y1 + top_h, box.x2, box.y2 - bottom_h)
    if art_box.height < 40:
        art_box = box
    _paste_panel_art(
        page_image,
        source_path,
        art_box,
        fit_mode=fit_mode,
        draw_border=False,
    )
    if top_h:
        draw.line((box.x1, box.y1 + top_h, box.x2, box.y1 + top_h), fill=(202, 194, 176), width=1)
    if bottom_h:
        draw.line((box.x1, box.y2 - bottom_h, box.x2, box.y2 - bottom_h), fill=(202, 194, 176), width=1)
    draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline=(18, 16, 14), width=border_w)


def _letter_caption(image: Image.Image, panel: dict[str, Any], box: Box) -> None:
    caption = str(panel.get("text") or panel.get("caption", "")).strip()
    caption_parts = _caption_parts(caption, str(panel.get("lettering_notes", "")))
    if not caption_parts:
        return
    vertical, horizontal = _placement(panel, "caption")
    heights = [
        _measure_text_box(image, box, part, kind="caption")
        for part in caption_parts
    ]
    for index, part in enumerate(caption_parts):
        _draw_text_box(
            image,
            box,
            part,
            kind="caption",
            vertical=vertical,
            horizontal=horizontal,
            stack_index=index,
            stack_count=len(caption_parts),
            stack_total_h=sum(heights),
            stack_box_heights=heights,
        )


def _slot_box(panel_box: Box, value: dict[str, Any]) -> Box:
    if {"x1", "y1", "x2", "y2"} <= set(value):
        return Box(
            panel_box.x1 + round(panel_box.width * max(0.0, min(1.0, float(value["x1"])))),
            panel_box.y1 + round(panel_box.height * max(0.0, min(1.0, float(value["y1"])))),
            panel_box.x1 + round(panel_box.width * max(0.0, min(1.0, float(value["x2"])))),
            panel_box.y1 + round(panel_box.height * max(0.0, min(1.0, float(value["y2"])))),
        )
    if {"x", "y", "w", "h"} <= set(value):
        x1 = panel_box.x1 + round(panel_box.width * max(0.0, min(1.0, float(value["x"]))))
        y1 = panel_box.y1 + round(panel_box.height * max(0.0, min(1.0, float(value["y"]))))
        return Box(
            x1,
            y1,
            x1 + round(panel_box.width * max(0.0, min(1.0, float(value["w"])))),
            y1 + round(panel_box.height * max(0.0, min(1.0, float(value["h"])))),
        )
    raise ValueError(f"slot box must use x/y/w/h or x1/y1/x2/y2: {value}")


def _panel_slot(panel: dict[str, Any], item: dict[str, Any], kind: str) -> dict[str, Any] | None:
    slots = [slot for slot in panel.get("lettering_slots") or [] if isinstance(slot, dict)]
    slot_id = str(item.get("slot_id") or "").strip()
    if slot_id:
        for slot in slots:
            if str(slot.get("id") or "").strip() == slot_id:
                return slot
    for slot in slots:
        if str(slot.get("kind") or "").strip().lower() != kind:
            continue
        if kind == "caption":
            return slot
        speaker = str(item.get("speaker") or "").strip().lower()
        slot_speaker = str(slot.get("speaker") or "").strip().lower()
        if speaker and slot_speaker == speaker:
            return slot
    return None


def _draw_caption_slot(image: Image.Image, slot: Box, text: str) -> dict[str, Any]:
    text = " ".join(str(text or "").split())
    if not text:
        return {}
    draw = ImageDraw.Draw(image)
    scale = min(image.size) / 1024
    pad_x = max(8, round(11 * scale))
    pad_y = max(6, round(8 * scale))
    max_text_w = max(60, slot.width - 2 * pad_x)
    max_text_h = max(24, slot.height - 2 * pad_y)
    font, lines, line_h = _fit_lines(
        text,
        "caption",
        max_text_w,
        max_text_h,
        draw,
        max_size=max(16, round(20 * scale)),
        min_size=max(9, round(11 * scale)),
    )
    leading = math.ceil(line_h * 1.16)
    text_h = leading * len(lines)
    box_h = min(slot.height, text_h + 2 * pad_y)
    box_w = slot.width
    y = slot.y2 - box_h if (slot.y1 + slot.y2) / 2 > image.height / 2 else slot.y1
    fitted = Box(slot.x1, y, slot.x1 + box_w, y + box_h)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    rect = (fitted.x1, fitted.y1, fitted.x2, fitted.y2)
    odraw.rounded_rectangle(
        rect,
        radius=max(1, round(2 * scale)),
        fill=(250, 244, 224, 238),
        outline=(30, 25, 20, 235),
        width=max(1, round(scale)),
    )
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)
    text_y = fitted.y1 + pad_y
    for line in lines:
        if text_y + leading > fitted.y2 - pad_y + leading:
            break
        draw.text((fitted.x1 + pad_x, text_y), line, font=font, fill=(20, 18, 16, 255))
        text_y += leading
    return {"box": {"x1": fitted.x1, "y1": fitted.y1, "x2": fitted.x2, "y2": fitted.y2}}


def _letter_dialogue(image: Image.Image, panel: dict[str, Any], box: Box) -> list[dict[str, Any]]:
    items = [item for item in panel.get("dialogue", []) or [] if isinstance(item, dict)]
    zone_counts: dict[str, int] = {}
    for item in items:
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    zone_seen: dict[str, int] = {}
    layouts: list[dict[str, Any]] = []
    for item in items:
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        stack_index = zone_seen.get(zone, 0)
        zone_seen[zone] = stack_index + 1
        layout = _draw_speech_balloon(
            image,
            box,
            item,
            stack_index=stack_index,
            stack_count=zone_counts.get(zone, 1),
        )
        if layout:
            layouts.append(layout)
    return layouts


def _text_items(panel: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical text items for a panel.

    Newer page plans should use panel["texts"] with kind=caption|speech|thought.
    Legacy storyboards with panel["caption"] and panel["dialogue"] still work
    so earlier experiments remain reproducible.
    """
    raw_items = panel.get("texts")
    if isinstance(raw_items, list):
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            item.setdefault("text_index", index)
            kind = str(item.get("kind") or "").strip().lower()
            if not kind:
                kind = "speech" if str(item.get("speaker", "")).strip() else "caption"
            item["kind"] = kind
            items.append(item)
        return items

    items = []
    caption = str(panel.get("caption", "")).strip()
    if caption:
        items.append({
            "kind": "caption",
            "text": caption,
            "caption_zone": panel.get("caption_zone"),
            "lettering_notes": panel.get("lettering_notes"),
            "text_index": 0,
        })
    for raw in panel.get("dialogue", []) or []:
        if not isinstance(raw, dict):
            continue
        item = copy.deepcopy(raw)
        item.setdefault("kind", "speech")
        item.setdefault("text_index", len(items))
        items.append(item)
    return items


def _anchor_map(anchor_data: dict[str, Any] | None) -> dict[AnchorKey, dict[str, Any]]:
    if not anchor_data:
        return {}
    anchors: dict[AnchorKey, dict[str, Any]] = {}
    for page in anchor_data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for anchor in page.get("anchors", []) or []:
            if not isinstance(anchor, dict):
                continue
            panel_no = int(anchor.get("panel_number") or 0)
            text_index = int(anchor.get("text_index") or 0)
            if page_no and panel_no:
                anchors[(page_no, panel_no, text_index)] = anchor
    return anchors


def _apply_anchor(
    item: dict[str, Any],
    anchor: dict[str, Any] | None,
    *,
    min_confidence: float,
) -> dict[str, Any]:
    anchored = copy.deepcopy(item)
    if not anchor:
        return anchored
    confidence = float(anchor.get("confidence") or 0.0)
    same_speaker = (
        str(anchor.get("speaker") or "").strip().lower()
        == str(item.get("speaker") or "").strip().lower()
    )
    if not anchor.get("visible", True) or confidence < min_confidence or not same_speaker:
        anchored["anchor_detection"] = {
            "used": False,
            "confidence": confidence,
            "reason": (
                anchor.get("reason")
                or "low confidence, speaker not visible, or anchor speaker mismatch"
            ),
        }
        return anchored

    ratio = (
        anchor.get("tail_target_point_ratio")
        or anchor.get("mouth_point_ratio")
        or anchor.get("anchor_point_ratio")
        or {}
    )
    if not isinstance(ratio, dict) or ratio.get("x") is None or ratio.get("y") is None:
        return anchored
    anchored["anchor_x_ratio"] = max(0.0, min(1.0, float(ratio["x"])))
    anchored["anchor_y_ratio"] = max(0.0, min(1.0, float(ratio["y"])))
    anchored["anchor_source"] = "detection"
    anchored["anchor_detection"] = {
        "used": True,
        "confidence": confidence,
        "source": anchor.get("source") or "speaker_anchor_detection",
        "used_point": (
            "tail_target_point_ratio"
            if anchor.get("tail_target_point_ratio") else "mouth_point_ratio"
        ),
        "mouth_point_ratio": anchor.get("mouth_point_ratio"),
        "tail_target_point_ratio": anchor.get("tail_target_point_ratio"),
        "face_box_ratio": anchor.get("face_box_ratio"),
    }
    if isinstance(anchor.get("face_box_ratio"), dict):
        anchored["face_box_ratio"] = anchor.get("face_box_ratio")
    return anchored


def _staged_mouth_ratio(panel: dict[str, Any], speaker: Any) -> dict[str, float] | None:
    """Where the layout staged this speaker's mouth, in panel fractions.

    Without a detected anchor the letterer falls back to a fixed fraction of
    the panel — `ANCHOR_Y["mouth"]`, 0.34 — which is a guess about where a
    figure might be. The layout stage has already decided where each figure
    stands and written a `mouth_point` for it, so the tail can be aimed at the
    character the art was directed to draw rather than at a constant. It also
    keeps the tail out of the balloon, because the layout stages figures clear
    of the text boxes.

    Detected anchors still win: they see the art that actually came back, and
    this only fills in when there are none.
    """
    name = _clean_name(speaker)
    if not name:
        return None
    figures = (panel.get("thumbnail_layout") or {}).get("figures") or []
    fallback: dict[str, float] | None = None
    for figure in figures:
        if not isinstance(figure, dict):
            continue
        point = figure.get("mouth_point")
        if not isinstance(point, dict) or point.get("x") is None or point.get("y") is None:
            continue
        character = _clean_name(figure.get("character"))
        if character == name:
            return point
        # "Daisy" in the dialogue against "Daisy Buchanan" in the staging is
        # the same person; a surname-less match is accepted only if nothing
        # matches in full.
        if fallback is None and character and (
            character.split()[0] == name.split()[0]
        ):
            fallback = point
    return fallback


def _clean_name(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _letter_texts(
    image: Image.Image,
    panel: dict[str, Any],
    box: Box,
    *,
    page_number: int,
    panel_number: int,
    text_items: list[dict[str, Any]],
    balloon_tail_style: str = "auto",
    balloon_placement: str = "storyboard",
    reserve_lettering_bands: bool = False,
    reserve_balloon_bands: bool = False,
) -> list[dict[str, Any]]:
    balloon_items = [
        item for item in text_items
        if str(item.get("kind") or "").strip().lower() in {"speech", "thought"}
    ]
    prepared_balloon_items: list[dict[str, Any]] = []
    avoid_points: list[dict[str, float]] = []
    avoid_boxes: list[dict[str, float]] = []
    if not reserve_balloon_bands:
        for item in balloon_items:
            if item.get("anchor_x_ratio") is not None and item.get("anchor_y_ratio") is not None:
                avoid_points.append({
                    "x": max(0.0, min(1.0, float(item["anchor_x_ratio"]))),
                    "y": max(0.0, min(1.0, float(item["anchor_y_ratio"]))),
                })
            face_box = item.get("face_box_ratio")
            if isinstance(face_box, dict) and {"x1", "y1", "x2", "y2"} <= set(face_box):
                avoid_boxes.append({
                    "x1": max(0.0, min(1.0, float(face_box["x1"]))),
                    "y1": max(0.0, min(1.0, float(face_box["y1"]))),
                    "x2": max(0.0, min(1.0, float(face_box["x2"]))),
                    "y2": max(0.0, min(1.0, float(face_box["y2"]))),
                })
    for item in balloon_items:
        prepared = copy.deepcopy(item)
        slot = _panel_slot(panel, prepared, str(prepared.get("kind") or "speech").strip().lower())
        if prepared.get("anchor_x_ratio") is None or prepared.get("anchor_y_ratio") is None:
            staged = _staged_mouth_ratio(panel, prepared.get("speaker"))
            if staged:
                prepared["anchor_x_ratio"] = max(0.0, min(1.0, float(staged["x"])))
                prepared["anchor_y_ratio"] = max(0.0, min(1.0, float(staged["y"])))
                prepared["anchor_source"] = "thumbnail_layout"
        if slot and isinstance(slot.get("box"), dict):
            prepared["slot_id"] = slot.get("id")
            prepared["slot_box_ratio"] = slot.get("box")
            if slot.get("zone"):
                prepared["balloon_zone"] = slot.get("zone")
            if slot.get("speaker_side"):
                prepared["speaker_region"] = slot.get("speaker_side")
                prepared["speaker_position"] = slot.get("speaker_side")
        if reserve_balloon_bands:
            zone = (
                str(prepared.get("balloon_zone") or prepared.get("placement") or "bottom_center")
                .strip()
                .lower()
                .replace("-", "_")
            )
            if zone.startswith("middle_"):
                prepared["balloon_zone"] = zone.replace("middle_", "bottom_", 1)
        if balloon_tail_style != "auto":
            prepared["tail_style"] = balloon_tail_style
        if balloon_placement == "near-speaker":
            prepared["balloon_placement_mode"] = "near_speaker"
        if avoid_points:
            prepared["avoid_anchor_points_ratio"] = avoid_points
        if avoid_boxes:
            prepared["avoid_boxes_ratio"] = avoid_boxes
        prepared_balloon_items.append(prepared)
    zone_counts: dict[str, int] = {}
    for item in prepared_balloon_items:
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    zone_seen: dict[str, int] = {}
    layouts: list[dict[str, Any]] = []
    # Balloons placed beside their own speaker can collide with each other, which
    # zone stacking used to prevent. Each one is added here as it lands so the
    # next has something to avoid.
    placed_rects: list[tuple[int, int, int, int]] = []
    balloon_rects: list[tuple[int, int, int, int]] = []
    # Captions are lettered after the balloons and would paint straight over
    # them. Their boxes are known up front, so register them before any balloon
    # is placed and let the balloons route around them.
    for item in text_items:
        if str(item.get("kind") or "").strip().lower() != "caption":
            continue
        slot = _panel_slot(panel, item, "caption")
        if slot and isinstance(slot.get("box"), dict):
            caption_box = _slot_box(box, slot["box"])
            placed_rects.append(
                (caption_box.x1, caption_box.y1, caption_box.x2, caption_box.y2)
            )
    for item in prepared_balloon_items:
        zone = (
            str(item.get("balloon_zone") or item.get("placement") or "top_center")
            .strip()
            .lower()
            .replace("-", "_")
        )
        stack_index = zone_seen.get(zone, 0)
        zone_seen[zone] = stack_index + 1
        layout = _draw_speech_balloon(
            image,
            box,
            item,
            stack_index=stack_index,
            stack_count=zone_counts.get(zone, 1),
            placed_rects=placed_rects,
            # Only balloons constrain reading order. A caption reserved at the
            # bottom of the panel reads after them, so it must not be treated
            # as something they have to stay below.
            read_after_rects=balloon_rects,
        )
        if layout:
            layout.update({
                "page_number": page_number,
                "panel_number": panel_number,
                "text_index": int(item.get("text_index") or 0),
                "anchor_detection": item.get("anchor_detection"),
            })
            drawn = layout.get("box")
            if isinstance(drawn, dict):
                rect = (drawn["x1"], drawn["y1"], drawn["x2"], drawn["y2"])
                placed_rects.append(rect)
                balloon_rects.append(rect)
            layouts.append(layout)

    for item in text_items:
        if str(item.get("kind") or "").strip().lower() != "caption":
            continue
        caption_panel = copy.deepcopy(panel)
        caption_panel["text"] = item.get("text")
        if item.get("caption_zone"):
            caption_panel["caption_zone"] = item.get("caption_zone")
        if item.get("lettering_notes"):
            caption_panel["lettering_notes"] = item.get("lettering_notes")
        slot = _panel_slot(panel, item, "caption")
        if slot and isinstance(slot.get("box"), dict):
            _draw_caption_slot(image, _slot_box(box, slot["box"]), str(item.get("text") or ""))
        else:
            _letter_caption(image, caption_panel, box)
    return layouts


def _draw_debug_overlay(
    lettered_path: Path,
    out_path: Path,
    *,
    panel_boxes: list[Box],
    dialogue_layout: list[dict[str, Any]],
) -> None:
    image = Image.open(lettered_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    font = None
    for index, box in enumerate(panel_boxes, 1):
        draw.rectangle(
            (box.x1, box.y1, box.x2, box.y2),
            outline=(0, 110, 255, 220),
            width=4,
        )
        draw.text((box.x1 + 8, box.y1 + 8), f"P{index}", fill=(0, 110, 255, 255), font=font)

    for layout in dialogue_layout:
        box = layout.get("box") or {}
        point = layout.get("tail_point") or {}
        if {"x1", "y1", "x2", "y2"} <= set(box):
            draw.rectangle(
                (box["x1"], box["y1"], box["x2"], box["y2"]),
                outline=(255, 150, 0, 235),
                width=4,
            )
        if point.get("x") is not None and point.get("y") is not None:
            x = int(point["x"])
            y = int(point["y"])
            if {"x1", "y1", "x2", "y2"} <= set(box):
                cx = round((int(box["x1"]) + int(box["x2"])) / 2)
                cy = round((int(box["y1"]) + int(box["y2"])) / 2)
                draw.line((cx, cy, x, y), fill=(255, 45, 45, 235), width=3)
            r = 10
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 45, 45, 235))
            label = str(layout.get("speaker") or "")
            if label:
                draw.text((x + 12, y - 12), label, fill=(255, 45, 45, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out_path)


def compose_page(
    page: dict[str, Any],
    *,
    panel_dir: Path,
    generated_dir: Path,
    lettered_dir: Path,
    debug_dir: Path | None = None,
    anchors: dict[AnchorKey, dict[str, Any]] | None = None,
    min_anchor_confidence: float = 0.45,
    balloon_tail_style: str = "auto",
    balloon_placement: str = "storyboard",
    fit_mode: str = "crop",
    reserve_lettering_bands: bool = False,
    reserve_balloon_bands: bool = False,
) -> dict[str, Any]:
    width, height = _page_size(page)
    panels = [panel for panel in page.get("panels", []) if isinstance(panel, dict)]
    boxes = _panel_boxes(page, panels, width, height)
    page_no = int(page.get("page_number") or 0)

    clean = Image.new("RGB", (width, height), (242, 238, 226))
    for panel, box in zip(panels, boxes, strict=False):
        panel_fit_mode = str(
            panel.get("fit_mode") or page.get("fit_mode") or fit_mode
        ).strip().lower()
        if reserve_lettering_bands:
            top_h, bottom_h = _reserved_band_heights(
                panel,
                box,
                clean,
                include_balloons=reserve_balloon_bands,
            )
            _paste_panel_with_reserved_bands(
                clean,
                _panel_image_path(panel, panel_dir),
                box,
                fit_mode=panel_fit_mode,
                top_h=top_h,
                bottom_h=bottom_h,
            )
        else:
            _paste_panel_art(
                clean,
                _panel_image_path(panel, panel_dir),
                box,
                fit_mode=panel_fit_mode,
            )

    generated_dir.mkdir(parents=True, exist_ok=True)
    clean_path = generated_dir / f"page_{page_no:03d}.png"
    clean.save(clean_path)

    lettered = clean.convert("RGBA")
    dialogue_layout: list[dict[str, Any]] = []
    for panel, box in zip(panels, boxes, strict=False):
        panel_no = int(panel.get("panel_number") or 0)
        items = []
        for item in _text_items(panel):
            text_index = int(item.get("text_index") or 0)
            anchor = (anchors or {}).get((page_no, panel_no, text_index))
            items.append(
                _apply_anchor(
                    item,
                    anchor,
                    min_confidence=min_anchor_confidence,
                )
            )
        dialogue_layout.extend(
            _letter_texts(
                lettered,
                panel,
                box,
                page_number=page_no,
                panel_number=panel_no,
                text_items=items,
                balloon_tail_style=balloon_tail_style,
                balloon_placement=balloon_placement,
                reserve_lettering_bands=reserve_lettering_bands,
                reserve_balloon_bands=reserve_balloon_bands,
            )
        )

    lettered_dir.mkdir(parents=True, exist_ok=True)
    lettered_path = lettered_dir / f"page_{page_no:03d}.png"
    lettered.convert("RGB").save(lettered_path)
    debug_path = None
    if debug_dir is not None:
        debug_path = debug_dir / f"page_{page_no:03d}.png"
        _draw_debug_overlay(
            lettered_path,
            debug_path,
            panel_boxes=boxes,
            dialogue_layout=dialogue_layout,
        )
    return {
        "page_number": page_no,
        "generated_page": str(clean_path),
        "lettered_page": str(lettered_path),
        "debug_page": str(debug_path) if debug_path else None,
        "panel_boxes": [
            {"x1": box.x1, "y1": box.y1, "x2": box.x2, "y2": box.y2}
            for box in boxes
        ],
        "dialogue_layout": dialogue_layout,
    }


def compose_run(
    run_dir: Path,
    *,
    storyboard_path: Path | None = None,
    panel_dir: Path | None = None,
    generated_dir: Path | None = None,
    lettered_dir: Path | None = None,
    anchors_path: Path | None = None,
    debug_dir: Path | None = None,
    min_anchor_confidence: float = 0.45,
    balloon_tail_style: str = "auto",
    balloon_placement: str = "storyboard",
    fit_mode: str = "crop",
    reserve_lettering_bands: bool = False,
    reserve_balloon_bands: bool = False,
) -> dict[str, Any]:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    panel_dir = panel_dir or run_dir / "panel_art"
    generated_dir = generated_dir or run_dir / "generated_pages"
    lettered_dir = lettered_dir or run_dir / "lettered_pages"
    debug_dir = debug_dir or run_dir / "debug_pages"
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    anchor_data = json.loads(anchors_path.read_text(encoding="utf-8")) if anchors_path else None
    anchors = _anchor_map(anchor_data)
    pages = [page for page in data.get("pages", []) if isinstance(page, dict)]
    diagnostics = {
        "storyboard": str(storyboard_path),
        "panel_dir": str(panel_dir),
        "anchors": str(anchors_path) if anchors_path else None,
        "min_anchor_confidence": min_anchor_confidence,
        "balloon_tail_style": balloon_tail_style,
        "balloon_placement": balloon_placement,
        "fit_mode": fit_mode,
        "reserve_lettering_bands": reserve_lettering_bands,
        "reserve_balloon_bands": reserve_balloon_bands,
        "pages": [
            compose_page(
                page,
                panel_dir=panel_dir,
                generated_dir=generated_dir,
                lettered_dir=lettered_dir,
                debug_dir=debug_dir,
                anchors=anchors,
                min_anchor_confidence=min_anchor_confidence,
                balloon_tail_style=balloon_tail_style,
                balloon_placement=balloon_placement,
                fit_mode=fit_mode,
                reserve_lettering_bands=reserve_lettering_bands,
                reserve_balloon_bands=reserve_balloon_bands,
            )
            for page in pages
        ],
    }

    lettered_paths = [Path(page["lettered_page"]) for page in diagnostics["pages"]]
    if lettered_paths:
        images = [Image.open(path).convert("RGB") for path in lettered_paths]
        images[0].save(lettered_dir / "lettered_book.pdf", save_all=True, append_images=images[1:])
    (lettered_dir / "layout.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n",
        encoding="utf-8",
    )
    return diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--storyboard-json", type=Path)
    parser.add_argument("--panel-dir", type=Path)
    parser.add_argument("--generated-dir", type=Path)
    parser.add_argument("--lettered-dir", type=Path)
    parser.add_argument("--anchors-json", type=Path)
    parser.add_argument("--debug-dir", type=Path)
    parser.add_argument("--min-anchor-confidence", type=float, default=0.45)
    parser.add_argument(
        "--balloon-tail-style",
        choices=["auto", "none"],
        default="auto",
        help="Speech/thought tail rendering style. 'none' omits tails/trails.",
    )
    parser.add_argument(
        "--balloon-placement",
        choices=["storyboard", "near-speaker"],
        default="storyboard",
        help="Use storyboard balloon zones, or place balloons near detected speakers.",
    )
    parser.add_argument(
        "--fit-mode",
        choices=["crop", "contain"],
        default="crop",
        help="How panel art is fit into panel boxes.",
    )
    parser.add_argument(
        "--reserve-lettering-bands",
        action="store_true",
        help="Shrink panel art away from caption bands before lettering.",
    )
    parser.add_argument(
        "--reserve-balloon-bands",
        action="store_true",
        help="Also reserve bands for speech/thought balloons. This is unsafe for no-tail dialogue unless speaker attribution is otherwise clear.",
    )
    args = parser.parse_args(argv)
    diagnostics = compose_run(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        panel_dir=args.panel_dir,
        generated_dir=args.generated_dir,
        lettered_dir=args.lettered_dir,
        anchors_path=args.anchors_json,
        debug_dir=args.debug_dir,
        min_anchor_confidence=args.min_anchor_confidence,
        balloon_tail_style=args.balloon_tail_style,
        balloon_placement=args.balloon_placement,
        fit_mode=args.fit_mode,
        reserve_lettering_bands=args.reserve_lettering_bands,
        reserve_balloon_bands=args.reserve_balloon_bands,
    )
    for page in diagnostics["pages"]:
        print(page["lettered_page"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
