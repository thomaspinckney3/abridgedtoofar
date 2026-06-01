"""Remove dialogue balloons that cannot be placed unambiguously.

For no-tail lettering, speaker proximity and reading order must agree. If an
exchange reads right-to-left by speaker position, a deterministic renderer
cannot make the dialogue clear without tails or manual layout. This stage
demotes those balloon lines into caption text instead of allowing misplaced
balloons.
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
        and str(anchor.get("speaker") or "").strip().lower()
        == str(item.get("speaker") or "").strip().lower()
    ):
        ratio = anchor.get("tail_target_point_ratio") or anchor.get("mouth_point_ratio") or {}
        if isinstance(ratio, dict) and ratio.get("x") is not None:
            x = float(ratio["x"])
            if x < 0.42:
                return "left"
            if x > 0.58:
                return "right"
            return "center"
    region = str(item.get("speaker_region") or item.get("speaker_side") or "").lower()
    if "left" in region:
        return "left"
    if "right" in region:
        return "right"
    if "center" in region:
        return "center"
    return ""


def _side_rank(side: str) -> int:
    return {"left": 0, "center": 1, "right": 2}.get(side, 1)


def _speaker_caption(item: dict[str, Any], *, narrator_name: str | None) -> str:
    text = str(item.get("text") or "").strip()
    speaker = str(item.get("speaker") or "").strip()
    kind = str(item.get("kind") or "speech").strip().lower()
    if not text:
        return ""
    if narrator_name and speaker.lower() == narrator_name.lower():
        if kind == "thought":
            return f"I thought: {text}"
        return f'I said, "{text}"'
    if kind == "thought":
        return f"{speaker} thought: {text}" if speaker else text
    return f'{speaker} said, "{text}"' if speaker else text


def _merge_into_caption(
    texts: list[dict[str, Any]],
    demoted: list[dict[str, Any]],
    *,
    narrator_name: str | None,
) -> list[dict[str, Any]]:
    pieces = [
        _speaker_caption(item, narrator_name=narrator_name)
        for item in demoted
    ]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return texts
    result: list[dict[str, Any]] = []
    caption_written = False
    for item in texts:
        if str(item.get("kind") or "").strip().lower() == "caption":
            merged = deepcopy(item)
            current = str(merged.get("text") or "").strip()
            merged["text"] = " ".join([part for part in [current, *pieces] if part])
            merged["caption_zone"] = merged.get("caption_zone") or "top_center"
            note = str(merged.get("lettering_notes") or "").strip()
            extra = "demoted ambiguous no-tail dialogue"
            merged["lettering_notes"] = f"{note}; {extra}" if note else extra
            result.append(merged)
            caption_written = True
        else:
            result.append(item)
    if not caption_written:
        result.insert(0, {
            "kind": "caption",
            "text": " ".join(pieces),
            "caption_zone": "top_center",
            "lettering_notes": "demoted ambiguous no-tail dialogue",
        })
    return result


def _assign_speaker_zone(item: dict[str, Any], side: str, *, caption_present: bool) -> dict[str, Any]:
    updated = deepcopy(item)
    horizontal = side if side in {"left", "right"} else "center"
    band = "bottom" if caption_present else "top"
    updated["balloon_zone"] = f"{band}_{horizontal}"
    return updated


def apply_dialogue_feasibility(
    storyboard: dict[str, Any],
    anchor_data: dict[str, Any],
    *,
    narrator_name: str | None = None,
    demote_all_balloons: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(storyboard)
    anchors = _anchor_index(anchor_data)
    changes: list[dict[str, Any]] = []

    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            panel_no = int(panel.get("panel_number") or 0)
            texts = [item for item in panel.get("texts", []) if isinstance(item, dict)]
            balloon_entries: list[tuple[int, dict[str, Any], str]] = []
            for index, item in enumerate(texts):
                kind = str(item.get("kind") or "").strip().lower()
                if kind not in {"speech", "thought"}:
                    continue
                side = _side_from_anchor(anchors.get((page_no, panel_no, index)), item)
                balloon_entries.append((index, item, side))
            if not balloon_entries:
                continue

            demote_indexes: set[int] = set()
            reason = ""
            if demote_all_balloons:
                demote_indexes = {index for index, _item, _side in balloon_entries}
                reason = "all balloons disabled for safe automated lettering"
            elif any(not side for _index, _item, side in balloon_entries):
                demote_indexes = {index for index, _item, _side in balloon_entries}
                reason = "speaker anchor unavailable"
            else:
                ranks = [_side_rank(side) for _index, _item, side in balloon_entries]
                if any(left > right for left, right in zip(ranks, ranks[1:], strict=False)):
                    demote_indexes = {index for index, _item, _side in balloon_entries}
                    reason = "speaker positions would read out of dialogue order"

            caption_present = any(
                str(item.get("kind") or "").strip().lower() == "caption"
                for item in texts
            )
            demoted = [item for index, item, _side in balloon_entries if index in demote_indexes]
            kept: list[dict[str, Any]] = []
            for index, item in enumerate(texts):
                if index in demote_indexes:
                    continue
                matching = next((side for entry_index, _entry_item, side in balloon_entries if entry_index == index), "")
                if matching:
                    kept.append(_assign_speaker_zone(item, matching, caption_present=caption_present))
                else:
                    kept.append(item)
            if demoted:
                kept = _merge_into_caption(kept, demoted, narrator_name=narrator_name)
            if kept != texts:
                panel["texts"] = kept
                changes.append({
                    "page_number": page_no,
                    "panel_number": panel_no,
                    "reason": reason or "assigned speaker-near zones",
                    "demoted_count": len(demoted),
                    "old_texts": texts,
                    "new_texts": kept,
                })

    return data, {"changed_panels": changes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard_json", type=Path)
    parser.add_argument("--anchors-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--narrator-name")
    parser.add_argument(
        "--demote-all-balloons",
        action="store_true",
        help="Convert every speech/thought balloon to caption text.",
    )
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    anchors = json.loads(args.anchors_json.read_text(encoding="utf-8"))
    data, report = apply_dialogue_feasibility(
        storyboard,
        anchors,
        narrator_name=args.narrator_name,
        demote_all_balloons=args.demote_all_balloons,
    )
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
