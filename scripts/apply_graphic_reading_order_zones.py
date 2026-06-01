"""Assign balloon zones so reading order wins over speaker-side proximity.

For no-tail or short-tail lettering, putting each balloon nearest its speaker can
reverse dialogue order when the first speaker is on the right and the response
speaker is on the left. This stage uses speaker anchors only to pick a rough
horizontal side, then stacks conflicting turns vertically so top-to-bottom /
left-to-right reading matches the text order.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import write_json


def _anchor_index(anchor_data: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    anchors = {}
    for page in anchor_data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for anchor in page.get("anchors", []) or []:
            if not isinstance(anchor, dict):
                continue
            anchors[(page_no, int(anchor.get("panel_number") or 0), int(anchor.get("text_index") or 0))] = anchor
    return anchors


def _side_from_anchor(anchor: dict[str, Any] | None, item: dict[str, Any]) -> str:
    if (
        anchor
        and anchor.get("visible")
        and str(anchor.get("speaker") or "").strip().lower() == str(item.get("speaker") or "").strip().lower()
    ):
        ratio = anchor.get("tail_target_point_ratio") or anchor.get("mouth_point_ratio") or {}
        if isinstance(ratio, dict) and ratio.get("x") is not None:
            x = float(ratio["x"])
            if x < 0.38:
                return "left"
            if x > 0.62:
                return "right"
            return "center"
    region = str(item.get("speaker_region") or item.get("speaker_side") or "").lower()
    if "left" in region:
        return "left"
    if "right" in region:
        return "right"
    return "center"


def _side_rank(side: str) -> int:
    return {"left": 0, "center": 1, "right": 2}.get(side, 1)


def _caption_items(texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in texts if str(item.get("kind") or "").lower() == "caption"]


def _assign_zones(balloon_sides: list[str], *, caption_count: int) -> list[str]:
    count = len(balloon_sides)
    if count == 0:
        return []
    if caption_count:
        if count == 1:
            return [f"bottom_{balloon_sides[0]}"]
        if count == 2:
            return ["bottom_left", "bottom_right"]
        horizontals = ["left", "center", "right"]
        return [f"bottom_{horizontals[min(i, len(horizontals) - 1)]}" for i in range(count)]
    if count == 1:
        return [f"top_{balloon_sides[0]}"]
    if count == 2:
        if _side_rank(balloon_sides[0]) <= _side_rank(balloon_sides[1]):
            return [f"top_{balloon_sides[0]}", f"top_{balloon_sides[1]}"]
        return [f"top_{balloon_sides[0]}", f"bottom_{balloon_sides[1]}"]
    rows = ["top", "middle", "bottom"]
    return [f"{rows[min(i, len(rows) - 1)]}_{side}" for i, side in enumerate(balloon_sides)]


def apply_reading_order_zones(
    storyboard: dict[str, Any],
    anchor_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(storyboard)
    anchors = _anchor_index(anchor_data)
    adjustments: list[dict[str, Any]] = []
    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            panel_no = int(panel.get("panel_number") or 0)
            texts = [item for item in panel.get("texts", []) if isinstance(item, dict)]
            balloon_indexes = [
                index for index, item in enumerate(texts)
                if str(item.get("kind") or "").lower() in {"speech", "thought"}
            ]
            if not balloon_indexes:
                continue
            sides = [
                _side_from_anchor(anchors.get((page_no, panel_no, index)), texts[index])
                for index in balloon_indexes
            ]
            zones = _assign_zones(sides, caption_count=len(_caption_items(texts)))
            used_bands = {zone.split("_", 1)[0] for zone in zones}
            for index, zone in zip(balloon_indexes, zones, strict=False):
                old = str(texts[index].get("balloon_zone") or "")
                texts[index]["balloon_zone"] = zone
                if old != zone:
                    adjustments.append({
                        "page_number": page_no,
                        "panel_number": panel_no,
                        "text_index": index,
                        "speaker": texts[index].get("speaker"),
                        "old_balloon_zone": old,
                        "new_balloon_zone": zone,
                    })
            for item in _caption_items(texts):
                old = str(item.get("caption_zone") or "bottom_center").replace("-", "_")
                item["caption_zone"] = "top_center" if "top" not in used_bands else "bottom_center"
                if old != item["caption_zone"]:
                    adjustments.append({
                        "page_number": page_no,
                        "panel_number": panel_no,
                        "old_caption_zone": old,
                        "new_caption_zone": item["caption_zone"],
                    })
            panel["texts"] = texts
    return data, {"adjustments": adjustments}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard_json", type=Path)
    parser.add_argument("--anchors-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    anchors = json.loads(args.anchors_json.read_text(encoding="utf-8"))
    data, report = apply_reading_order_zones(storyboard, anchors)
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "anchors": str(args.anchors_json),
        "output_storyboard": str(args.out_json),
    })
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
