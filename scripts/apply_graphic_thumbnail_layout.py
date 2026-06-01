"""Create comic thumbnail layouts with text, figure, and face boxes.

This stage runs after the panel/caption/dialogue plan and before image
generation. It turns the soft instruction "leave room for lettering" into a
machine-readable layout contract:

- page panel boxes
- caption and balloon boxes
- speaker body boxes
- speaker face boxes
- rules that art generation and vision QA can enforce

It also writes simple rough-in PNGs so the layout contract can be reviewed
before generating finished art.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from forage.artifacts import write_json
from scripts.letter_graphic_novel_frames import _slot_box as _pixel_slot_box
from scripts.letter_graphic_novel_pages import Box as PixelBox
from scripts.letter_graphic_novel_pages import _fit_lines


@dataclass(frozen=True)
class Box:
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

    def as_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "w": round(self.w, 4),
            "h": round(self.h, 4),
        }


VALID_ZONES = {
    "top_left",
    "top_center",
    "top_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
}

DIRECT_SPEECH_IN_CAPTION_RE = re.compile(
    r"\b(?:said|cried|called|asked|answered|replied|shouted|whispered|exclaimed)\b"
    r"[^\"“”]{0,24}[\"“][^\"“”]+[\"”]",
    re.IGNORECASE,
)
EXPLICIT_THOUGHT_IN_CAPTION_RE = re.compile(
    r"\b(?:thought\s+I|I\s+wondered|I\s+said\s+to\s+myself|"
    r"I\s+asked\s+myself)\b|\bI\s+thought\s*[:\"“]",
    re.IGNORECASE,
)
LEGACY_LAYOUT_CONSTRAINT_RE = re.compile(
    r"\s*Lettering layout constraint:.*$",
    re.IGNORECASE | re.DOTALL,
)
LEGACY_RESERVATION_SENTENCE_RE = re.compile(
    r"\s*(?:Reserve|Leave|Keep)\s+[^.;]*?"
    r"(?:caption|speech|balloon|lettering|empty area|empty band|clear zone)"
    r"[^.;]*[.;]",
    re.IGNORECASE,
)


def _text_role_warnings(
    texts: list[dict[str, Any]],
    *,
    page_number: int,
    panel_number: int,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for item in texts:
        kind = str(item.get("kind") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if kind == "caption" and DIRECT_SPEECH_IN_CAPTION_RE.search(text):
            warnings.append({
                "page_number": page_number,
                "panel_number": panel_number,
                "code": "caption_contains_direct_speech",
                "message": (
                    "Narrator captions must not contain quoted spoken dialogue; "
                    "move the line to a speech balloon or paraphrase it as action."
                ),
                "text": text,
            })
        if kind == "caption" and EXPLICIT_THOUGHT_IN_CAPTION_RE.search(text):
            warnings.append({
                "page_number": page_number,
                "panel_number": panel_number,
                "code": "caption_contains_explicit_thought",
                "message": (
                    "Explicit internal monologue should be a thought balloon, "
                    "not a narrator caption."
                ),
                "text": text,
            })
        if kind in {"speech", "thought"} and not str(item.get("speaker") or "").strip():
            warnings.append({
                "page_number": page_number,
                "panel_number": panel_number,
                "code": "balloon_missing_speaker",
                "message": "Speech and thought balloons must name the speaking or thinking character.",
                "text": text,
            })
    return warnings


def _missing_caption_warning(
    texts: list[dict[str, Any]],
    *,
    page_number: int,
    panel_number: int,
) -> dict[str, Any] | None:
    if any(
        str(item.get("kind") or "").strip().lower() == "caption"
        and str(item.get("text") or "").strip()
        for item in texts
    ):
        return None
    return {
        "page_number": page_number,
        "panel_number": panel_number,
        "code": "panel_missing_caption",
        "message": "Every panel must carry one in-panel caption for automated story flow.",
    }


def _speaker_absence_warnings(
    panel: dict[str, Any],
    balloons: list[dict[str, Any]],
    *,
    page_number: int,
    panel_number: int,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    haystack = " ".join(
        str(panel.get(field) or "")
        for field in ("beat", "image_prompt", "continuity_notes", "adaptation_note")
    ).lower()
    if not haystack:
        return warnings
    for item in balloons:
        speaker = str(item.get("speaker") or "").strip()
        if not speaker:
            continue
        for alias in _speaker_absence_aliases(speaker):
            pattern = re.compile(
                rf"\bno\s+{re.escape(alias)}\s+(?:is\s+)?visible\b"
                rf"|\b{re.escape(alias)}\s+(?:is\s+)?not\s+visible\b"
                rf"|\bwithout\s+{re.escape(alias)}\b",
                re.IGNORECASE,
            )
            if pattern.search(haystack):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_number,
                    "code": "balloon_speaker_explicitly_absent",
                    "message": (
                        "A speech or thought balloon names a speaker the panel "
                        "itself says is not visible; move the line to a panel "
                        "where the speaker is staged or convert it to narration."
                    ),
                    "speaker": speaker,
                    "text": item.get("text"),
                })
                break
    return warnings


def _speaker_absence_aliases(speaker: str) -> list[str]:
    normalized = " ".join(speaker.lower().replace("’", "'").split())
    aliases = [normalized]
    without_title = re.sub(r"^(?:mr|mrs|ms|miss|dr)\.?\s+", "", normalized).strip()
    if without_title and without_title not in aliases:
        aliases.append(without_title)
    if "father" in normalized or without_title in {"carraway", "mr carraway", "mr. carraway"}:
        aliases.append("father")
    if "roadside man" in normalized:
        aliases.append("man")
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _load_source_frame_index(source_root: Path | None) -> dict[tuple[int, int], dict[str, Any]]:
    if source_root is None:
        return {}
    frames: dict[tuple[int, int], dict[str, Any]] = {}
    for path in sorted(source_root.glob("chapter_*/storyboard*.json")):
        try:
            chapter_no = int(path.parent.name.rsplit("_", 1)[-1])
        except ValueError:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for frame in data.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            frame_no = int(frame.get("frame_number") or 0)
            if frame_no and (chapter_no, frame_no) not in frames:
                frames[(chapter_no, frame_no)] = frame
    return frames


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _box_from_dict(raw: dict[str, Any]) -> Box:
    if {"x", "y", "w", "h"} <= set(raw):
        return Box(
            _clamp(float(raw["x"])),
            _clamp(float(raw["y"])),
            _clamp(float(raw["w"])),
            _clamp(float(raw["h"])),
        )
    if {"x1", "y1", "x2", "y2"} <= set(raw):
        x1 = _clamp(float(raw["x1"]))
        y1 = _clamp(float(raw["y1"]))
        x2 = _clamp(float(raw["x2"]))
        y2 = _clamp(float(raw["y2"]))
        return Box(x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1))
    raise ValueError(f"box must use x/y/w/h or x1/y1/x2/y2: {raw!r}")


def _intersects(a: Box, b: Box, pad: float = 0.0) -> bool:
    return (
        a.x < b.x2 + pad
        and a.x2 + pad > b.x
        and a.y < b.y2 + pad
        and a.y2 + pad > b.y
    )


def _contains(outer: Box, inner: Box, pad: float = 0.0) -> bool:
    return (
        inner.x >= outer.x - pad
        and inner.y >= outer.y - pad
        and inner.x2 <= outer.x2 + pad
        and inner.y2 <= outer.y2 + pad
    )


def _page_size(page: dict[str, Any]) -> tuple[int, int]:
    size = page.get("page_size") or {}
    return int(size.get("width") or page.get("width") or 1536), int(
        size.get("height") or page.get("height") or 2048
    )


def _canonical_panel_boxes(count: int) -> list[Box]:
    if count <= 0:
        return []
    if count == 1:
        return [Box(0.015, 0.015, 0.97, 0.97)]
    if count == 2:
        return [
            Box(0.015, 0.012, 0.97, 0.482),
            Box(0.015, 0.506, 0.97, 0.482),
        ]
    if count == 3:
        return [
            Box(0.015, 0.015, 0.97, 0.39),
            Box(0.015, 0.42, 0.477, 0.565),
            Box(0.508, 0.42, 0.477, 0.565),
        ]
    if count == 4:
        return [
            Box(0.015, 0.015, 0.477, 0.477),
            Box(0.508, 0.015, 0.477, 0.477),
            Box(0.015, 0.508, 0.477, 0.477),
            Box(0.508, 0.508, 0.477, 0.477),
        ]
    if count == 5:
        return [
            Box(0.015, 0.015, 0.97, 0.29),
            Box(0.015, 0.32, 0.477, 0.32),
            Box(0.508, 0.32, 0.477, 0.32),
            Box(0.015, 0.655, 0.477, 0.33),
            Box(0.508, 0.655, 0.477, 0.33),
        ]
    # Six-panel exchange: wide top, two two-up rows, wide bottom.
    return [
        Box(0.015, 0.012, 0.97, 0.205),
        Box(0.015, 0.227, 0.477, 0.205),
        Box(0.508, 0.227, 0.477, 0.205),
        Box(0.015, 0.443, 0.477, 0.205),
        Box(0.508, 0.443, 0.477, 0.205),
        Box(0.015, 0.658, 0.97, 0.33),
    ][:count]


def _panel_boxes(page: dict[str, Any], panels: list[dict[str, Any]]) -> list[Box]:
    explicit = [
        _box_from_dict(panel["box"])
        for panel in panels
        if isinstance(panel.get("box"), dict)
    ]
    if len(explicit) == len(panels):
        return explicit
    return _canonical_panel_boxes(len(panels))


def _size_class(box: Box) -> str:
    if box.w >= 0.86 and box.h >= 0.75:
        return "full_page"
    if box.w >= 0.86 and box.h >= 0.30:
        return "wide_large"
    if box.w >= 0.86:
        return "wide_strip"
    if box.h >= box.w * 1.25:
        return "tall"
    return "standard"


def _text_items(panel: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = panel.get("texts")
    if isinstance(raw_items, list):
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            kind = str(item.get("kind") or "").strip().lower()
            if not kind:
                kind = "speech" if str(item.get("speaker") or "").strip() else "caption"
            if kind not in {"caption", "speech", "thought"}:
                continue
            item["kind"] = kind
            item.setdefault("text_index", index)
            items.append(item)
        return items

    items = []
    caption = str(panel.get("caption") or "").strip()
    if caption:
        items.append({
            "kind": "caption",
            "text": caption,
            "caption_zone": panel.get("caption_zone"),
            "text_index": 0,
        })
    for raw in panel.get("dialogue") or []:
        if not isinstance(raw, dict):
            continue
        item = copy.deepcopy(raw)
        item.setdefault("kind", "speech")
        item.setdefault("text_index", len(items))
        items.append(item)
    return items


def _zone_from_box(box: Box) -> str:
    cx = box.x + box.w / 2
    cy = box.y + box.h / 2
    vertical = "bottom" if cy >= 0.55 else "top"
    if cx < 0.38:
        horizontal = "left"
    elif cx > 0.62:
        horizontal = "right"
    else:
        horizontal = "center"
    return f"{vertical}_{horizontal}"


def _speaker_side(item: dict[str, Any], order: int, count: int) -> str:
    raw = (
        str(item.get("speaker_region") or item.get("speaker_side") or item.get("speaker_position") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    if "left" in raw:
        return "left"
    if "right" in raw:
        return "right"
    if "center" in raw:
        return "center"
    if count == 1:
        return "center"
    if count == 2:
        return "left" if order == 0 else "right"
    return ("left", "center", "right")[min(order, 2)]


def _clean_character_name(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    base = text.split("(", 1)[0].strip()
    normalized = base.lower()
    if "ishmael" in normalized or normalized == "narrator":
        return "Ishmael"
    if "queequeg" in normalized or "harpooneer" in normalized:
        return "Queequeg"
    if "peter coffin" in normalized or normalized == "landlord" or "landlord" in normalized:
        return "Peter Coffin"
    if len(base.split()) > 4:
        return None
    return " ".join(base.split()) or None


def _add_unique_name(names: list[str], raw: Any) -> None:
    name = _clean_character_name(raw)
    if name and name not in names:
        names.append(name)


def _source_people(
    panel: dict[str, Any],
    source_frames: dict[tuple[int, int], dict[str, Any]] | None,
) -> list[str]:
    names: list[str] = []
    for field in ("driver_character", "focus_character", "subject_character"):
        _add_unique_name(names, panel.get(field))

    source_frame: dict[str, Any] = {}
    if source_frames:
        chapter_no = int(panel.get("source_chapter") or 0)
        frame_no = int(panel.get("source_frame_number") or panel.get("source_panel_number") or 0)
        source_frame = source_frames.get((chapter_no, frame_no), {})

    visible = source_frame.get("visible_content")
    if isinstance(visible, dict):
        for raw in visible.get("people") or []:
            _add_unique_name(names, raw)
    for field in ("driver_character", "focus_character", "subject_character"):
        _add_unique_name(names, source_frame.get(field))

    panel_visible = panel.get("visible_content")
    if isinstance(panel_visible, dict):
        for raw in panel_visible.get("people") or []:
            _add_unique_name(names, raw)

    return names[:3]


def _side_for_order(order: int, count: int) -> str:
    if count <= 1:
        return "center"
    if count == 2:
        return "left" if order == 0 else "right"
    return ("left", "center", "right")[min(order, 2)]


def _caption_height(text: str, *, has_balloons: bool) -> float:
    if has_balloons:
        return 0.12 if len(text) <= 110 else 0.15
    if len(text) > 165:
        return 0.19
    if len(text) > 105:
        return 0.15
    return 0.11


def _caption_box(zone: str, text: str, *, has_balloons: bool, top_clearance: float) -> Box:
    zone = zone if zone in VALID_ZONES else "top_center"
    h = _caption_height(text, has_balloons=has_balloons)
    if zone.startswith("bottom"):
        y = 0.96 - h
    else:
        y = top_clearance
    if zone.endswith("left"):
        return Box(0.06, y, 0.72, h)
    if zone.endswith("right"):
        return Box(0.22, y, 0.72, h)
    return Box(0.06, y, 0.88, h)


def _balloon_height(text: str, panel_box: Box) -> float:
    narrow = panel_box.w < 0.60
    short = panel_box.h < 0.28
    text_len = len(text)
    if narrow and short:
        if text_len > 44:
            return 0.27
        if text_len > 24:
            return 0.23
        return 0.18
    if text_len > 85:
        return 0.22
    if text_len > 55:
        return 0.19
    return 0.16


def _balloon_box(
    side: str,
    order: int,
    count: int,
    *,
    y: float,
    text: str,
    panel_box: Box,
    stack_index: int = 0,
) -> Box:
    h = _balloon_height(text, panel_box)
    if stack_index:
        y += stack_index * (h + 0.025)
    y = min(y, 0.96 - h)
    if count >= 3:
        w_by_side = {"left": 0.28, "center": 0.28, "right": 0.28}
        x_by_side = {"left": 0.04, "center": 0.36, "right": 0.68}
        return Box(x_by_side.get(side, (0.04, 0.36, 0.68)[min(order, 2)]), y, w_by_side.get(side, 0.28), h)
    if side == "left":
        return Box(0.06, y, 0.38, h)
    if side == "right":
        return Box(0.56, y, 0.38, h)
    return Box(0.30, y, 0.40, h)


def _figure_box(side: str, *, top: float, bottom: float, wide: bool, lane_count: int) -> Box:
    bottom = max(0.42, min(bottom, 0.96))
    top = max(0.26, min(top, bottom - 0.18))
    h = max(0.18, bottom - top)
    if lane_count >= 3:
        if side == "left":
            return Box(0.04, top, 0.28, h)
        if side == "right":
            return Box(0.68, top, 0.28, h)
        return Box(0.36, top, 0.28, h)
    if side == "left":
        return Box(0.06, top, 0.36 if wide else 0.40, h)
    if side == "right":
        return Box(0.58 if wide else 0.54, top, 0.36 if wide else 0.40, h)
    return Box(0.31, top, 0.38, h)


def _face_box(body: Box, side: str) -> Box:
    if side == "left":
        x = body.x + body.w * 0.36
    elif side == "right":
        x = body.x + body.w * 0.38
    else:
        x = body.x + body.w * 0.36
    return Box(x, body.y + body.h * 0.07, body.w * 0.24, body.h * 0.20)


def _layout_archetype(balloon_count: int, speaker_count: int, size_class: str) -> str:
    if balloon_count == 0:
        return "caption_action"
    if balloon_count == 1 or speaker_count <= 1:
        return "single_speaker"
    if speaker_count <= 2:
        return "two_speaker_exchange"
    if size_class.startswith("wide") or size_class == "full_page":
        return "three_speaker_wide"
    return "three_speaker_needs_wide_panel"


def _text_slot_fit_warning(
    item: dict[str, Any],
    panel_box: Box,
    *,
    page_size: tuple[int, int],
    page_number: int,
    panel_number: int,
) -> dict[str, Any] | None:
    slot_ratio = item.get("slot_box_ratio")
    if not isinstance(slot_ratio, dict):
        return None
    text = " ".join(str(item.get("text") or "").split())
    if not text:
        return None
    page_w, page_h = page_size
    frame = PixelBox(
        round(page_w * panel_box.x),
        round(page_h * panel_box.y),
        round(page_w * panel_box.x2),
        round(page_h * panel_box.y2),
    )
    slot = _pixel_slot_box(frame, slot_ratio)
    image = Image.new("RGBA", page_size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    scale = min(page_size) / 1024
    pad_x = max(10, round(14 * scale))
    pad_y = max(7, round(9 * scale))
    max_text_w = max(60, slot.width - 2 * pad_x)
    max_text_h = max(24, slot.height - 2 * pad_y)
    kind = str(item.get("kind") or "").strip().lower()
    fit_kind = "caption" if kind == "caption" else "dialogue"
    min_size = max(10, round((11 if kind == "caption" else 12) * scale))
    max_size = max(17, round((20 if kind == "caption" else 22) * scale))
    font, lines, line_h = _fit_lines(
        text,
        fit_kind,
        max_text_w,
        max_text_h,
        draw,
        max_size=max_size,
        min_size=min_size,
    )
    leading = math.ceil(line_h * 1.15)
    text_h = leading * len(lines)
    font_size = getattr(font, "size", None)
    if text_h <= max_text_h and font_size != min_size:
        return None
    code = "caption_slot_too_tight" if kind == "caption" else "dialogue_slot_too_tight"
    return {
        "page_number": page_number,
        "panel_number": panel_number,
        "code": code,
        "message": "Lettering text barely fits or overflows the planned text box.",
        "speaker": item.get("speaker"),
        "text": text,
        "slot_px": {"w": slot.width, "h": slot.height},
        "text_area_px": {"w": max_text_w, "h": max_text_h},
        "line_count": len(lines),
        "font_size": font_size,
        "min_font_size": min_size,
        "text_height_px": text_h,
        "fits": text_h <= max_text_h,
    }


def _layout_panel(
    panel: dict[str, Any],
    panel_box: Box,
    *,
    page_number: int,
    page_size: tuple[int, int],
    source_frames: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    panel_no = int(panel.get("panel_number") or 0)
    texts = _text_items(panel)
    missing_caption = _missing_caption_warning(
        texts,
        page_number=page_number,
        panel_number=panel_no,
    )
    if missing_caption:
        warnings.append(missing_caption)
    warnings.extend(_text_role_warnings(texts, page_number=page_number, panel_number=panel_no))
    caption_indexes = [
        idx for idx, item in enumerate(texts)
        if item.get("kind") == "caption" and str(item.get("text") or "").strip()
    ]
    balloon_indexes = [
        idx for idx, item in enumerate(texts)
        if item.get("kind") in {"speech", "thought"} and str(item.get("text") or "").strip()
    ]
    balloons = [texts[idx] for idx in balloon_indexes]
    warnings.extend(
        _speaker_absence_warnings(
            panel,
            balloons,
            page_number=page_number,
            panel_number=panel_no,
        )
    )
    speakers = []
    for item in balloons:
        speaker = str(item.get("speaker") or "").strip()
        if speaker and speaker not in speakers:
            speakers.append(speaker)
    speaker_items: list[tuple[str, str, dict[str, Any]]] = []
    speaker_keys: list[str] = []
    for item in balloons:
        speaker = str(item.get("speaker") or "").strip()
        key = _clean_character_name(speaker) or speaker
        if not key or key in speaker_keys:
            continue
        speaker_keys.append(key)
        speaker_items.append((key, speaker, item))
    speaker_side_by_key: dict[str, str] = {}
    for order, (key, _speaker, item) in enumerate(speaker_items):
        side = _speaker_side(item, order, len(speaker_items))
        if len(speaker_items) == 2:
            side = "left" if order == 0 else "right"
        elif len(speaker_items) >= 3:
            side = ("left", "center", "right")[order]
        speaker_side_by_key[key] = side

    size_class = _size_class(panel_box)
    archetype = _layout_archetype(len(balloons), len(speakers), size_class)
    wide = panel_box.w >= 0.86
    wide_tall = wide and panel_box.h >= 0.55
    caption_first = not balloon_indexes or (
        caption_indexes and min(caption_indexes) <= min(balloon_indexes)
    )

    text_boxes: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []
    caption_bottom = 0.04
    if caption_indexes:
        caption_text = " ".join(str(texts[idx].get("text") or "").strip() for idx in caption_indexes)
        requested_zone = str(texts[caption_indexes[0]].get("caption_zone") or "").strip().lower().replace("-", "_")
        if balloon_indexes:
            zone = "top_center" if caption_first else "bottom_center"
        else:
            zone = requested_zone if requested_zone in VALID_ZONES else "top_center"
        cbox = _caption_box(zone, caption_text, has_balloons=bool(balloon_indexes), top_clearance=0.04)
        caption_bottom = cbox.y2 + 0.04 if zone.startswith("top") else 0.04
        text_box = {
            "id": "caption",
            "kind": "caption",
            "box": cbox.as_dict(),
            "zone": _zone_from_box(cbox),
            "reserved_for": "narrator caption",
            "text_indexes": caption_indexes,
            "reading_order": min(caption_indexes) + 1,
        }
        text_boxes.append(text_box)
        slots.append(text_box)
        for idx in caption_indexes:
            texts[idx]["slot_id"] = "caption"
            texts[idx]["caption_zone"] = text_box["zone"]
            texts[idx]["slot_box_ratio"] = cbox.as_dict()

    balloon_y = caption_bottom if caption_indexes and caption_first else 0.04
    if caption_indexes and caption_first:
        balloon_y = max(balloon_y, 0.18)
    balloon_boxes: list[Box] = []
    side_stack_seen: dict[str, int] = {}
    for order, idx in enumerate(balloon_indexes[:3]):
        item = texts[idx]
        speaker_key = _clean_character_name(item.get("speaker")) or str(item.get("speaker") or "").strip()
        side = speaker_side_by_key.get(speaker_key) or _speaker_side(item, order, len(balloon_indexes))
        stack_index = side_stack_seen.get(side, 0)
        side_stack_seen[side] = stack_index + 1
        bbox = _balloon_box(
            side,
            order,
            min(max(1, len(speaker_items)), 3),
            y=balloon_y,
            text=str(item.get("text") or ""),
            panel_box=panel_box,
            stack_index=stack_index,
        )
        balloon_boxes.append(bbox)
        slot_id = f"balloon_{order + 1}"
        text_box = {
            "id": slot_id,
            "kind": item.get("kind") or "speech",
            "box": bbox.as_dict(),
            "zone": _zone_from_box(bbox),
            "speaker": item.get("speaker"),
            "speaker_side": side,
            "text_index": int(item.get("text_index") or idx),
            "reading_order": idx + 1,
        }
        text_boxes.append(text_box)
        slots.append(text_box)
        item["slot_id"] = slot_id
        item["slot_box_ratio"] = bbox.as_dict()
        item["balloon_zone"] = text_box["zone"]
        item["speaker_region"] = side
        item["speaker_position"] = side

    for idx in balloon_indexes[3:]:
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "too_many_balloons_for_thumbnail",
            "message": "More than three balloons in one panel should be split before art generation.",
        })

    figure_top = 0.28
    figure_bottom = 0.96
    if text_boxes:
        text_box_values = [_box_from_dict(item["box"]) for item in text_boxes]
        top_text_boxes = [box for box in text_box_values if box.y < 0.55]
        if top_text_boxes:
            top_text_bottom = max(box.y2 for box in top_text_boxes)
            figure_top = max(0.28, top_text_bottom + 0.08)
        bottom_text_boxes = [box for box in text_box_values if box.y >= 0.55]
        if bottom_text_boxes:
            bottom_text_top = min(box.y for box in bottom_text_boxes)
            figure_bottom = min(0.96, bottom_text_top - 0.04)

    max_figures = 3 if wide_tall else 2
    source_names = _source_people(panel, source_frames)
    expected_names: list[str] = []
    for key, _speaker, _item in speaker_items:
        if key and key not in expected_names:
            expected_names.append(key)
    for name in source_names:
        if name not in expected_names:
            expected_names.append(name)
    expected_figure_count = max(1, min(max_figures, len(expected_names) or len(speaker_items) or 1))
    if (
        max_figures == 2
        and expected_figure_count > 1
        and len(speaker_items) == 1
        and speaker_side_by_key.get(speaker_items[0][0]) == "center"
    ):
        speaker_side_by_key[speaker_items[0][0]] = "left"

    figures: list[dict[str, Any]] = []
    for order, (speaker_key, speaker, item) in enumerate(speaker_items[:max_figures]):
        speaker = speaker or speaker_key or f"speaker_{order + 1}"
        side = speaker_side_by_key.get(speaker_key) or _speaker_side(item, order, len(speaker_items))
        body = _figure_box(
            side,
            top=figure_top,
            bottom=figure_bottom,
            wide=wide,
            lane_count=expected_figure_count,
        )
        face = _face_box(body, side)
        figures.append({
            "id": f"figure_{order + 1}",
            "character": speaker,
            "role": "speaker",
            "side": side,
            "body_box": body.as_dict(),
            "face_box": face.as_dict(),
            "mouth_point": {
                "x": round(face.x + face.w * 0.50, 4),
                "y": round(face.y + face.h * 0.62, 4),
            },
        })

    if not figures:
        placed_count = min(len(source_names), max_figures)
        for order, name in enumerate(source_names[:max_figures]):
            side = _side_for_order(order, placed_count)
            body = _figure_box(
                side,
                top=figure_top,
                bottom=figure_bottom,
                wide=wide,
                lane_count=placed_count,
            )
            face = _face_box(body, side)
            figures.append({
                "id": f"figure_{order + 1}",
                "character": name,
                "role": "visible_character",
                "side": side,
                "body_box": body.as_dict(),
                "face_box": face.as_dict(),
                "mouth_point": {
                    "x": round(face.x + face.w * 0.50, 4),
                    "y": round(face.y + face.h * 0.62, 4),
                },
            })
    elif len(figures) < max_figures:
        placed_names = {
            _clean_character_name(figure.get("character"))
            for figure in figures
        }
        used_sides = {str(figure.get("side") or "") for figure in figures}
        side_order = ("right", "left") if max_figures == 2 else ("left", "center", "right")
        open_sides = [side for side in side_order if side not in used_sides]
        for name in source_names:
            if name in placed_names or len(figures) >= max_figures:
                continue
            side = open_sides.pop(0) if open_sides else _side_for_order(len(figures), max_figures)
            body = _figure_box(
                side,
                top=figure_top,
                bottom=figure_bottom,
                wide=wide,
                lane_count=expected_figure_count,
            )
            face = _face_box(body, side)
            figures.append({
                "id": f"figure_{len(figures) + 1}",
                "character": name,
                "role": "visible_character",
                "side": side,
                "body_box": body.as_dict(),
                "face_box": face.as_dict(),
                "mouth_point": {
                    "x": round(face.x + face.w * 0.50, 4),
                    "y": round(face.y + face.h * 0.62, 4),
                },
            })

    text_rects = [_box_from_dict(item["box"]) for item in text_boxes]
    for left_index, left_box in enumerate(text_rects):
        for right_index, right_box in enumerate(text_rects[left_index + 1 :], left_index + 1):
            if _intersects(left_box, right_box, pad=0.005):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_no,
                    "code": "thumbnail_text_text_overlap",
                    "message": "Two text boxes overlap in the thumbnail contract.",
                    "left": text_boxes[left_index].get("id"),
                    "right": text_boxes[right_index].get("id"),
                })

    body_rects: list[tuple[dict[str, Any], Box]] = []
    face_rects: list[tuple[dict[str, Any], Box]] = []
    for figure in figures:
        body = _box_from_dict(figure["body_box"])
        face = _box_from_dict(figure["face_box"])
        body_rects.append((figure, body))
        face_rects.append((figure, face))
        if not _contains(body, face, pad=0.001):
            warnings.append({
                "page_number": page_number,
                "panel_number": panel_no,
                "code": "thumbnail_face_outside_body",
                "message": f"Face box for {figure['character']} is not contained in its body box.",
                "figure": figure["id"],
            })
        for text_rect in text_rects:
            if _intersects(body, text_rect, pad=0.005):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_no,
                    "code": "thumbnail_body_text_overlap",
                    "message": f"Body box for {figure['character']} overlaps a text box.",
                    "figure": figure["id"],
                })
            if _intersects(face, text_rect, pad=0.015):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_no,
                    "code": "thumbnail_face_text_overlap",
                    "message": f"Face box for {figure['character']} overlaps a text box.",
                    "figure": figure["id"],
                })
    for left_index, (left_figure, left_body) in enumerate(body_rects):
        for right_figure, right_body in body_rects[left_index + 1 :]:
            if _intersects(left_body, right_body, pad=0.005):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_no,
                    "code": "thumbnail_body_body_overlap",
                    "message": "Two character body boxes overlap in the thumbnail contract.",
                    "left": left_figure.get("id"),
                    "right": right_figure.get("id"),
                })
    for figure, face in face_rects:
        for other_figure, other_body in body_rects:
            if figure is other_figure:
                continue
            if _intersects(face, other_body, pad=0.005):
                warnings.append({
                    "page_number": page_number,
                    "panel_number": panel_no,
                    "code": "thumbnail_face_other_body_overlap",
                    "message": "A face box overlaps a different character body box.",
                    "figure": figure.get("id"),
                    "other": other_figure.get("id"),
                })

    if len(speaker_items) >= 3 and not wide_tall:
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "three_speaker_panel_needs_wide_tall",
            "message": "A three-speaker exchange requires a wide-tall panel or a split exchange.",
            "panel_box": panel_box.as_dict(),
        })
    if len(speaker_items) > max_figures:
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "panel_too_small_for_all_speakers",
            "message": "The panel is too small to stage every speaking character; split the exchange or use a wide-tall panel.",
            "speakers": [item.get("speaker") for item in balloons],
        })
    if len(source_names) > max_figures:
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "extra_figures_suppressed_for_panel_size",
            "message": "Only wide-tall panels may stage three visible figures; extra non-speaking figures were omitted from the thumbnail contract.",
            "panel_box": panel_box.as_dict(),
            "source_people": source_names,
            "figures_kept": [figure.get("character") for figure in figures],
        })
    for item in balloons:
        if len(str(item.get("text") or "")) > 95:
            warnings.append({
                "page_number": page_number,
                "panel_number": panel_no,
                "code": "long_balloon_text",
                "message": "Balloon text is long enough to threaten panel composition.",
                "speaker": item.get("speaker"),
                "text": item.get("text"),
            })

    for item in texts:
        if str(item.get("kind") or "").strip().lower() not in {"caption", "speech", "thought"}:
            continue
        fit_warning = _text_slot_fit_warning(
            item,
            panel_box,
            page_size=page_size,
            page_number=page_number,
            panel_number=panel_no,
        )
        if fit_warning:
            warnings.append(fit_warning)

    panel["box"] = panel_box.as_dict()
    panel["texts"] = texts
    panel["panel_archetype"] = archetype
    panel["lettering_slots"] = [
        {
            "id": slot["id"],
            "kind": slot["kind"],
            "zone": slot["zone"],
            "box": slot["box"],
            "speaker": slot.get("speaker"),
            "speaker_side": slot.get("speaker_side"),
            "reserved_for": slot.get("reserved_for"),
            "text_index": slot.get("text_index"),
            "reading_order": slot.get("reading_order"),
        }
        for slot in slots
    ]
    panel["thumbnail_layout"] = {
        "version": "thumbnail_layout_v1",
        "panel_size_class": size_class,
        "panel_archetype": archetype,
        "panel_box": panel_box.as_dict(),
        "text_boxes": text_boxes,
        "figures": figures,
        "key_prop_boxes": [],
        "rules": [
            "Draw finished art only in the panel frame.",
            "Keep every text box empty for later lettering; draw no boxes or text there.",
            "Keep all faces and mouths inside their face boxes.",
            "Keep bodies inside their body boxes unless a gesture is explicitly required.",
            "Keep active hands and key props out of text boxes.",
            "Stage speakers in the same left-to-right order as their text boxes.",
        ],
    }
    panel["thumbnail_constraints"] = _thumbnail_constraints_text(panel["thumbnail_layout"])
    panel["lettering_constraints"] = panel["thumbnail_constraints"]
    if str(panel.get("image_prompt") or "").strip():
        panel["image_prompt"] = _clean_legacy_layout_text(str(panel["image_prompt"]))
    return panel, warnings


def _clean_legacy_layout_text(prompt: str) -> str:
    prompt = LEGACY_LAYOUT_CONSTRAINT_RE.sub(" ", prompt)
    prompt = LEGACY_RESERVATION_SENTENCE_RE.sub(" ", prompt)
    return " ".join(prompt.split())


def _thumbnail_constraints_text(layout: dict[str, Any]) -> str:
    parts = ["Thumbnail layout contract:"]
    for text_box in layout.get("text_boxes") or []:
        box = text_box.get("box") or {}
        owner = text_box.get("speaker") or text_box.get("reserved_for") or text_box.get("kind")
        parts.append(
            f"- Reserve empty {text_box.get('kind')} box {text_box.get('id')} for {owner}: "
            f"x {float(box.get('x', 0)) * 100:.0f}%, y {float(box.get('y', 0)) * 100:.0f}%, "
            f"w {float(box.get('w', 0)) * 100:.0f}%, h {float(box.get('h', 0)) * 100:.0f}%."
        )
    for figure in layout.get("figures") or []:
        body = figure.get("body_box") or {}
        face = figure.get("face_box") or {}
        parts.append(
            f"- Place {figure.get('character')} body in x {float(body.get('x', 0)) * 100:.0f}%, "
            f"y {float(body.get('y', 0)) * 100:.0f}%, w {float(body.get('w', 0)) * 100:.0f}%, "
            f"h {float(body.get('h', 0)) * 100:.0f}%; face in x {float(face.get('x', 0)) * 100:.0f}%, "
            f"y {float(face.get('y', 0)) * 100:.0f}%, w {float(face.get('w', 0)) * 100:.0f}%, "
            f"h {float(face.get('h', 0)) * 100:.0f}%."
        )
    parts.append("Keep faces, mouths, active hands, and key props out of all text boxes.")
    return " ".join(parts)


def apply_thumbnail_layout(
    storyboard: dict[str, Any],
    *,
    source_frames: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = copy.deepcopy(storyboard)
    warnings: list[dict[str, Any]] = []
    archetypes: dict[str, int] = {}
    panel_count = 0
    for page in data.get("pages") or []:
        if not isinstance(page, dict):
            continue
        panels = [panel for panel in page.get("panels") or [] if isinstance(panel, dict)]
        boxes = _panel_boxes(page, panels)
        page_no = int(page.get("page_number") or 0)
        page_size = _page_size(page)
        for panel, panel_box in zip(panels, boxes, strict=False):
            panel_count += 1
            _panel, panel_warnings = _layout_panel(
                panel,
                panel_box,
                page_number=page_no,
                page_size=page_size,
                source_frames=source_frames,
            )
            warnings.extend(panel_warnings)
            archetype = str(panel.get("panel_archetype") or "")
            archetypes[archetype] = archetypes.get(archetype, 0) + 1
        page["panels"] = panels
        page["thumbnail_layout_version"] = "thumbnail_layout_v1"
    return data, {
        "panels_processed": panel_count,
        "archetypes": archetypes,
        "warnings": warnings,
    }


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _absolute(panel_abs: tuple[int, int, int, int], box: dict[str, Any]) -> tuple[int, int, int, int]:
    px1, py1, px2, py2 = panel_abs
    panel_w = px2 - px1
    panel_h = py2 - py1
    rel = _box_from_dict(box)
    return (
        px1 + round(panel_w * rel.x),
        py1 + round(panel_h * rel.y),
        px1 + round(panel_w * rel.x2),
        py1 + round(panel_h * rel.y2),
    )


def render_thumbnail_pages(storyboard: dict[str, Any], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    small = _font(16)
    medium = _font(22)
    for page in storyboard.get("pages") or []:
        if not isinstance(page, dict):
            continue
        width, height = _page_size(page)
        image = Image.new("RGB", (width, height), (246, 244, 236))
        draw = ImageDraw.Draw(image)
        panels = [panel for panel in page.get("panels") or [] if isinstance(panel, dict)]
        for panel in panels:
            pbox = _box_from_dict(panel.get("box") or {"x": 0, "y": 0, "w": 1, "h": 1})
            panel_abs = (
                round(width * pbox.x),
                round(height * pbox.y),
                round(width * pbox.x2),
                round(height * pbox.y2),
            )
            draw.rectangle(panel_abs, outline=(20, 20, 20), width=5)
            draw.text((panel_abs[0] + 8, panel_abs[1] + 8), f"P{panel.get('panel_number')}", fill=(20, 20, 20), font=medium)
            layout = panel.get("thumbnail_layout") or {}
            for text_box in layout.get("text_boxes") or []:
                rect = _absolute(panel_abs, text_box.get("box") or {})
                kind = str(text_box.get("kind") or "")
                color = (255, 230, 90) if kind == "caption" else (110, 180, 255)
                draw.rectangle(rect, fill=color, outline=(20, 20, 20), width=3)
                label = text_box.get("id") or kind
                if text_box.get("speaker"):
                    label = f"{label}: {text_box.get('speaker')}"
                draw.text((rect[0] + 6, rect[1] + 6), str(label), fill=(0, 0, 0), font=small)
            for figure in layout.get("figures") or []:
                body_rect = _absolute(panel_abs, figure.get("body_box") or {})
                face_rect = _absolute(panel_abs, figure.get("face_box") or {})
                draw.rectangle(body_rect, outline=(30, 150, 80), width=4)
                draw.rectangle(face_rect, fill=(255, 145, 145), outline=(150, 20, 20), width=3)
                draw.text((body_rect[0] + 6, max(body_rect[1] + 6, face_rect[3] + 4)), str(figure.get("character") or ""), fill=(20, 90, 45), font=small)
        page_no = int(page.get("page_number") or 0)
        out_path = out_dir / f"page_{page_no:03d}.png"
        image.save(out_path)
        output_paths.append(out_path)
    return output_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard_json", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--rough-dir", type=Path)
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit non-zero when the thumbnail contract emits any warning.",
    )
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    source_frames = _load_source_frame_index(args.source_root)
    data, report = apply_thumbnail_layout(storyboard, source_frames=source_frames)
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "output_storyboard": str(args.out_json),
        "source_root": str(args.source_root) if args.source_root else None,
        "source_frames_loaded": len(source_frames),
    })
    if args.rough_dir:
        paths = render_thumbnail_pages(data, args.rough_dir)
        report["rough_pages"] = [str(path) for path in paths]
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.fail_on_warning and report.get("warnings"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
