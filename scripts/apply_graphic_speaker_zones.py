"""Assign no-tail speech/thought balloon zones from detected speaker anchors.

This is a deterministic bridge between speaker-anchor detection and reserved
zone lettering. It does not place balloons at mouth points. Instead, it uses
the detected speaker x positions to assign left/center/right zones, and moves
the caption to the opposite vertical band when balloons are present.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import write_json


HORIZ = ("left", "center", "right")


def _anchor_index(anchor_data: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    index: dict[tuple[int, int, int], dict[str, Any]] = {}
    for page in anchor_data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for anchor in page.get("anchors", []) or []:
            if not isinstance(anchor, dict):
                continue
            key = (
                page_no,
                int(anchor.get("panel_number") or 0),
                int(anchor.get("text_index") or 0),
            )
            index[key] = anchor
    return index


def _anchor_x(anchor: dict[str, Any] | None, item: dict[str, Any]) -> float:
    if (
        anchor
        and anchor.get("visible")
        and float(anchor.get("confidence") or 0.0) >= 0.45
        and _same_speaker(anchor.get("speaker"), item.get("speaker"))
    ):
        ratio = anchor.get("tail_target_point_ratio") or anchor.get("mouth_point_ratio")
        if isinstance(ratio, dict) and ratio.get("x") is not None:
            return max(0.0, min(1.0, float(ratio["x"])))
    region = str(item.get("speaker_region") or item.get("speaker_side") or "").lower()
    if "left" in region:
        return 0.2
    if "right" in region:
        return 0.8
    return 0.5


def _same_speaker(a: Any, b: Any) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _caption_band(texts: list[dict[str, Any]]) -> str:
    for item in texts:
        if str(item.get("kind") or "").lower() != "caption":
            continue
        zone = str(item.get("caption_zone") or "").lower().replace("-", "_")
        if zone.startswith("bottom_"):
            return "bottom"
        if zone.startswith("top_"):
            return "top"
    return "bottom"


def _balloon_band(caption_band: str, count: int) -> str:
    if count >= 2:
        return "top"
    return "top" if caption_band != "top" else "bottom"


def _assign_horizontals(items: list[tuple[int, dict[str, Any], float]]) -> dict[int, str]:
    if len(items) == 1:
        index, _item, x = items[0]
        if x < 0.4:
            return {index: "left"}
        if x > 0.6:
            return {index: "right"}
        return {index: "center"}
    ordered = sorted(items, key=lambda t: (t[2], t[0]))
    if len(items) == 2:
        return {ordered[0][0]: "left", ordered[1][0]: "right"}
    result: dict[int, str] = {}
    for slot, (index, _item, _x) in zip(HORIZ, ordered[:3], strict=False):
        result[index] = slot
    for index, _item, x in ordered[3:]:
        if x < 0.4:
            result[index] = "left"
        elif x > 0.6:
            result[index] = "right"
        else:
            result[index] = "center"
    return result


def apply_speaker_zones(
    storyboard: dict[str, Any],
    anchors: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(storyboard)
    anchor_index = _anchor_index(anchors)
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
            balloon_items: list[tuple[int, dict[str, Any], float]] = []
            for index, item in enumerate(texts):
                kind = str(item.get("kind") or "").lower()
                if kind not in {"speech", "thought"}:
                    continue
                anchor = anchor_index.get((page_no, panel_no, index))
                balloon_items.append((index, item, _anchor_x(anchor, item)))
            if not balloon_items:
                continue

            cap_band = _caption_band(texts)
            band = _balloon_band(cap_band, len(balloon_items))
            horiz_by_index = _assign_horizontals(balloon_items)
            used_zones = []
            for index, item, _x in balloon_items:
                old_zone = str(item.get("balloon_zone") or "").lower().replace("-", "_")
                new_zone = f"{band}_{horiz_by_index[index]}"
                item["balloon_zone"] = new_zone
                used_zones.append(new_zone)
                if old_zone != new_zone:
                    adjustments.append({
                        "page_number": page_no,
                        "panel_number": panel_no,
                        "text_index": index,
                        "speaker": item.get("speaker"),
                        "old_balloon_zone": old_zone,
                        "new_balloon_zone": new_zone,
                    })

            caption_target_band = "bottom" if band == "top" else "top"
            for item in texts:
                if str(item.get("kind") or "").lower() != "caption":
                    continue
                old_zone = str(item.get("caption_zone") or "bottom_center").lower().replace("-", "_")
                horizontal = old_zone.rsplit("_", 1)[-1] if "_" in old_zone else "center"
                if horizontal not in HORIZ:
                    horizontal = "center"
                new_zone = f"{caption_target_band}_{horizontal}"
                item["caption_zone"] = new_zone
                if old_zone != new_zone:
                    adjustments.append({
                        "page_number": page_no,
                        "panel_number": panel_no,
                        "old_caption_zone": old_zone,
                        "new_caption_zone": new_zone,
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
    data, report = apply_speaker_zones(storyboard, anchors)
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
