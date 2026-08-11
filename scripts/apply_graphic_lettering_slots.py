"""Add deterministic in-panel lettering slots to a graphic storyboard.

This stage is intended to run after captions/dialogue are known and before page
image prompts are handed to an image generator. It assigns explicit caption and
balloon slots, updates image prompts with reservation constraints, and leaves a
report describing any panels that are too dense for reliable automatic
lettering.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import write_json
from forage.graphic.geometry import Box, is_wide, panel_boxes, panel_capacity


TEXT_KINDS = {"caption", "speech", "thought"}
BALLOON_KINDS = {"speech", "thought"}

SLOT_SENTENCE_RE = re.compile(
    r"\s*Leave clean negative space in the [^.]+?\."
    r"|\s*Leave [^.]*?negative space [^.]+?\.",
    re.IGNORECASE,
)
LETTERING_CONSTRAINT_RE = re.compile(
    r"\s*Lettering layout constraint:.*$",
    re.IGNORECASE | re.DOTALL,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_box(box: dict[str, float]) -> dict[str, float]:
    return {key: round(_clamp(float(value)), 4) for key, value in box.items()}


def _text_items(panel: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = panel.get("texts")
    if isinstance(raw_items, list):
        items = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            item = deepcopy(raw)
            kind = str(item.get("kind") or "").strip().lower()
            if not kind:
                kind = "speech" if str(item.get("speaker", "")).strip() else "caption"
            if kind not in TEXT_KINDS:
                continue
            item["kind"] = kind
            item.setdefault("text_index", index)
            items.append(item)
        return items

    items: list[dict[str, Any]] = []
    caption = str(panel.get("caption", "")).strip()
    if caption:
        items.append({
            "kind": "caption",
            "text": caption,
            "caption_zone": panel.get("caption_zone"),
            "lettering_notes": panel.get("lettering_notes"),
            "text_index": 0,
        })
    for raw in panel.get("dialogue") or []:
        if not isinstance(raw, dict):
            continue
        item = deepcopy(raw)
        item.setdefault("kind", "speech")
        item.setdefault("text_index", len(items))
        items.append(item)
    return items


def _zone_from_box(box: dict[str, float]) -> str:
    cx = float(box["x"]) + float(box["w"]) / 2
    cy = float(box["y"]) + float(box["h"]) / 2
    vertical = "bottom" if cy >= 0.55 else "top"
    if cx < 0.38:
        horizontal = "left"
    elif cx > 0.62:
        horizontal = "right"
    else:
        horizontal = "center"
    return f"{vertical}_{horizontal}"


def _side_from_item(item: dict[str, Any], *, index: int, count: int) -> str:
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
        return "left" if index == 0 else "right"
    return ("left", "center", "right")[min(index, 2)]


def _caption_box(zone: str, *, with_balloons: bool, text: str) -> dict[str, float]:
    zone = zone.strip().lower().replace("-", "_")
    height = 0.14
    if len(text) > 145:
        height = 0.20
    elif len(text) > 95:
        height = 0.17
    if with_balloons:
        height = min(height, 0.17)

    if zone.startswith("bottom"):
        y = 0.98 - height
    else:
        y = 0.04
    if zone.endswith("left"):
        x = 0.06
        w = 0.76
    elif zone.endswith("right"):
        x = 0.18
        w = 0.76
    else:
        x = 0.06
        w = 0.88
    return _round_box({"x": x, "y": y, "w": w, "h": height})


def _balloon_box(
    side: str,
    *,
    row_y: float,
    count: int,
    index: int,
    text: str,
) -> dict[str, float]:
    height = 0.20 if len(text) <= 70 else 0.24
    if count <= 1:
        width = 0.42
        if side == "right":
            x = 0.52
        elif side == "center":
            x = 0.29
        else:
            x = 0.06
    elif count == 2:
        width = 0.38
        x = 0.06 if index == 0 else 0.56
    else:
        width = 0.28
        x = (0.04, 0.36, 0.68)[min(index, 2)]
    return _round_box({"x": x, "y": row_y, "w": width, "h": height})


def _caption_reads_first(texts: list[dict[str, Any]], caption_indexes: list[int], balloon_indexes: list[int]) -> bool:
    if not caption_indexes or not balloon_indexes:
        return True
    return min(caption_indexes) <= min(balloon_indexes)


def _panel_archetype(balloon_count: int, distinct_speakers: int) -> str:
    if balloon_count == 0:
        return "caption_only"
    if balloon_count == 1 or distinct_speakers <= 1:
        return "single_character"
    if distinct_speakers <= 2:
        return "two_character"
    return "three_character_wide"


def _balloon_cap(box: Box | None) -> int:
    """How many balloons this panel may carry.

    One more than it has figures, so a single speaker can hold a line split
    across two linked balloons. Read from the shared geometry rather than fixed
    at three: the lettering policy and the thumbnail layout both size a panel
    this way, and a stage that caps lower reserves no space for a balloon the
    layout will place anyway.
    """
    return panel_capacity(box) + 1


def _slot_summary(slot: dict[str, Any]) -> str:
    box = slot.get("box") or {}
    pct = {
        key: round(float(box[key]) * 100)
        for key in ("x", "y", "w", "h")
        if key in box
    }
    owner = str(slot.get("speaker") or slot.get("reserved_for") or slot.get("kind") or "").strip()
    return (
        f"{slot.get('kind')} slot {slot.get('id')} for {owner}: "
        f"x {pct.get('x')}%, y {pct.get('y')}%, "
        f"width {pct.get('w')}%, height {pct.get('h')}%"
    )


def _constraints_sentence(slots: list[dict[str, Any]], balloons: list[dict[str, Any]]) -> str:
    slot_text = "; ".join(_slot_summary(slot) for slot in slots)
    speaker_bits = []
    for slot in balloons:
        speaker = str(slot.get("speaker") or "").strip()
        if not speaker:
            continue
        side = str(slot.get("speaker_side") or "").strip()
        if side:
            if side == "center":
                speaker_bits.append(f"stage {speaker} near the center, below or beside that speaker's slot")
            else:
                speaker_bits.append(f"stage {speaker} on the {side}, below or beside that speaker's slot")
    speaker_text = "; ".join(speaker_bits)
    if speaker_text:
        speaker_text = f" {speaker_text}."
    return (
        "Lettering layout constraint: reserve these empty in-panel lettering "
        f"slots for later lettering, but draw no boxes, balloons, tails, or text: {slot_text}. "
        "Keep faces, mouths, hands, active gestures, and key props completely out "
        "of those slots; use simple background or wall space there."
        f"{speaker_text}"
    )


def _clean_prompt(prompt: str) -> str:
    prompt = LETTERING_CONSTRAINT_RE.sub(" ", prompt)
    prompt = SLOT_SENTENCE_RE.sub(" ", prompt)
    return " ".join(prompt.split())


def _apply_prompt_constraint(panel: dict[str, Any], constraint: str) -> None:
    existing = str(panel.get("image_prompt") or "").strip()
    if existing:
        panel["image_prompt"] = f"{_clean_prompt(existing)} {constraint}".strip()
    panel["lettering_constraints"] = constraint


def _apply_panel_slots(
    panel: dict[str, Any],
    *,
    page_number: int,
    box: Box | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    texts = _text_items(panel)
    if not texts:
        panel["lettering_slots"] = []
        panel["panel_archetype"] = "silent"
        return panel, warnings

    caption_indexes = [
        index for index, item in enumerate(texts)
        if str(item.get("kind") or "").strip().lower() == "caption"
    ]
    balloon_indexes = [
        index for index, item in enumerate(texts)
        if str(item.get("kind") or "").strip().lower() in BALLOON_KINDS
    ]
    balloons = [texts[index] for index in balloon_indexes]
    speaker_order: list[str] = []
    for item in balloons:
        speaker = str(item.get("speaker") or "").strip().lower()
        if speaker and speaker not in speaker_order:
            speaker_order.append(speaker)
    archetype = _panel_archetype(len(balloons), len(speaker_order))
    panel["panel_archetype"] = archetype
    panel_no = int(panel.get("panel_number") or 0)

    balloon_cap = _balloon_cap(box)
    if len(balloons) > balloon_cap:
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "too_many_balloons",
            "message": (
                f"More than {balloon_cap} balloons in this panel is not reliable; "
                "split the exchange or demote weaker turns to caption."
            ),
            "balloon_cap": balloon_cap,
        })
    # The box is resolved by the caller, so this fires on unplaced pages too —
    # they are gridded downstream, and a three-speaker panel that lands in a
    # half-width slot is worth saying before the art is generated, not after.
    if archetype == "three_character_wide" and box is not None and not is_wide(box):
        warnings.append({
            "page_number": page_number,
            "panel_number": panel_no,
            "code": "three_character_panel_not_wide",
            "message": "Three-speaker panels should use a wide full-width frame.",
            "panel_width_ratio": round(box.w, 4),
        })

    caption_first = _caption_reads_first(texts, caption_indexes, balloon_indexes)
    caption_zone = "top_center" if caption_first else "bottom_center"
    balloon_y = 0.22 if caption_indexes and caption_first else 0.04

    slots: list[dict[str, Any]] = []
    caption_slot_id = None
    if caption_indexes:
        caption_text = " ".join(
            str(texts[index].get("text") or "").strip()
            for index in caption_indexes
            if str(texts[index].get("text") or "").strip()
        )
        first_caption = texts[caption_indexes[0]]
        if not balloon_indexes:
            caption_zone = str(first_caption.get("caption_zone") or "top_center").strip().lower().replace("-", "_")
            if caption_zone not in {
                "top_left",
                "top_center",
                "top_right",
                "bottom_left",
                "bottom_center",
                "bottom_right",
            }:
                caption_zone = "top_center"
        caption_slot_id = "caption"
        caption_box = _caption_box(
            caption_zone,
            with_balloons=bool(balloon_indexes),
            text=caption_text,
        )
        slots.append({
            "id": caption_slot_id,
            "kind": "caption",
            "zone": _zone_from_box(caption_box),
            "box": caption_box,
            "reserved_for": "narrator caption",
            "reading_order": min(caption_indexes) + 1,
        })

    speaker_side_by_name: dict[str, str] = {}
    for order, speaker in enumerate(speaker_order):
        if len(speaker_order) == 1:
            speaker_side_by_name[speaker] = "left"
        elif len(speaker_order) == 2:
            speaker_side_by_name[speaker] = "left" if order == 0 else "right"
        else:
            speaker_side_by_name[speaker] = ("left", "center", "right")[min(order, 2)]

    balloon_slots: list[dict[str, Any]] = []
    side_stack_seen: dict[str, int] = {}
    for order, text_index in enumerate(balloon_indexes[:balloon_cap]):
        item = texts[text_index]
        kind = str(item.get("kind") or "speech").strip().lower()
        speaker_key = str(item.get("speaker") or "").strip().lower()
        side = speaker_side_by_name.get(speaker_key) or _side_from_item(
            item, index=order, count=len(speaker_order) or len(balloon_indexes)
        )
        stack_index = side_stack_seen.get(side, 0)
        side_stack_seen[side] = stack_index + 1
        box = _balloon_box(
            side,
            row_y=balloon_y + stack_index * 0.23,
            count=min(max(1, len(speaker_order)), 3),
            index=order,
            text=str(item.get("text") or ""),
        )
        slot_id = f"balloon_{order + 1}"
        slot = {
            "id": slot_id,
            "kind": kind,
            "zone": _zone_from_box(box),
            "box": box,
            "speaker": item.get("speaker"),
            "speaker_side": side,
            "tail_target": f"{side}_speaker_mouth",
            "text_index": int(item.get("text_index") or text_index),
            "reading_order": text_index + 1,
        }
        slots.append(slot)
        balloon_slots.append(slot)
        item["slot_id"] = slot_id
        item["balloon_zone"] = slot["zone"]
        item["speaker_region"] = side
        item.setdefault("speaker_position", side)
        item["slot_box_ratio"] = box

    for index in caption_indexes:
        texts[index]["slot_id"] = caption_slot_id
        if caption_slot_id:
            texts[index]["caption_zone"] = caption_zone
            texts[index]["slot_box_ratio"] = slots[0]["box"]
    for extra_index in balloon_indexes[balloon_cap:]:
        texts[extra_index]["slot_warning"] = "no slot assigned; too many balloons for reliable automatic lettering"

    panel["texts"] = texts
    panel["lettering_slots"] = sorted(slots, key=lambda slot: int(slot.get("reading_order") or 0))
    if slots:
        _apply_prompt_constraint(panel, _constraints_sentence(panel["lettering_slots"], balloon_slots))
    return panel, warnings


def apply_lettering_slots(storyboard: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(storyboard)
    warnings: list[dict[str, Any]] = []
    panel_count = 0
    slot_count = 0
    archetypes: dict[str, int] = {}
    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        # Resolved here rather than read off each panel: a page whose panels
        # carry no boxes is still gridded downstream, and slot decisions that
        # depend on the rectangle have to see the same grid the layout stage
        # and the compositor will use. Non-dict entries are dropped first
        # because the grid is sized by panel count.
        panels = [item for item in (page.get("panels") or []) if isinstance(item, dict)]
        boxes = panel_boxes(panels)
        for index, panel in enumerate(panels):
            panel_count += 1
            _panel, panel_warnings = _apply_panel_slots(
                panel, page_number=page_no, box=boxes[index]
            )
            warnings.extend(panel_warnings)
            slot_count += len(panel.get("lettering_slots") or [])
            archetype = str(panel.get("panel_archetype") or "")
            archetypes[archetype] = archetypes.get(archetype, 0) + 1

    return data, {
        "panels_processed": panel_count,
        "slots_created": slot_count,
        "archetypes": archetypes,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard_json", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    data, report = apply_lettering_slots(storyboard)
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "output_storyboard": str(args.out_json),
    })
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
