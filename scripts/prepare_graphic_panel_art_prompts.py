"""Prepare slot-aware panel art prompts for graphic-novel page composition.

This stage bridges a page storyboard to the image-generation CLI. It hydrates
panels that only reference source chapter/frame numbers with the original frame
art prompt, appends explicit lettering-slot constraints, and writes one JSONL
generation job per panel image.
"""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import write_json

from scripts.compose_graphic_panel_page import _page_size, _panel_boxes


DEFAULT_STYLE = (
    "historical graphic novel panel, fine ink linework with muted watercolor "
    "wash, expressive faces, grounded physical action, consistent character "
    "designs"
)

GLOBAL_CONSTRAINTS = (
    "No readable text, no labels, no signs, no caption boxes, no speech "
    "balloons, no lettering, no watermarks. The art may be stylized but must "
    "not invent unsupported props, animals, symbols, or future-story imagery."
)


def _load_chapter_storyboards(
    source_root: Path,
    *,
    allowed_chapters: set[int] | None = None,
) -> dict[int, dict[str, Any]]:
    chapters: dict[int, dict[str, Any]] = {}
    for path in sorted(source_root.glob("chapter_*/storyboard*.json")):
        try:
            chapter_no = int(path.parent.name.rsplit("_", 1)[-1])
        except ValueError:
            continue
        if allowed_chapters is not None and chapter_no not in allowed_chapters:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        current = chapters.get(chapter_no, {})
        if "frames" in data:
            current.setdefault("frames", [])
            known = {
                int(frame.get("frame_number") or 0)
                for frame in current["frames"]
                if isinstance(frame, dict)
            }
            for frame in data.get("frames") or []:
                if not isinstance(frame, dict):
                    continue
                frame_no = int(frame.get("frame_number") or 0)
                if frame_no not in known:
                    current["frames"].append(frame)
        for key in ("character_continuity", "prop_continuity", "visual_safety_notes"):
            if key in data and key not in current:
                current[key] = data[key]
        chapters[chapter_no] = current
    return chapters


def _frame_index(chapters: dict[int, dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    index: dict[tuple[int, int], dict[str, Any]] = {}
    for chapter_no, data in chapters.items():
        for frame in data.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            frame_no = int(frame.get("frame_number") or 0)
            if frame_no:
                index[(chapter_no, frame_no)] = frame
    return index


def _character_lines(chapters: dict[int, dict[str, Any]], chapter_no: int | None = None) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    source_items = (
        [chapters[chapter_no]]
        if chapter_no is not None and chapter_no in chapters
        else list(chapters.values())
    )
    for data in source_items:
        continuity = data.get("character_continuity")
        if not isinstance(continuity, dict):
            continue
        for name, info in continuity.items():
            if name in seen:
                continue
            seen.add(str(name))
            if isinstance(info, dict):
                desc = str(info.get("visual_description") or "").strip()
            else:
                desc = str(info).strip()
            if desc:
                lines.append(f"- {name}: {desc}")
    return lines


def _storyboard_style(storyboard: dict[str, Any]) -> str:
    style = storyboard.get("style_bible")
    if not isinstance(style, dict):
        return DEFAULT_STYLE
    pieces: list[str] = []
    for key, value in style.items():
        if key == "lettering":
            continue
        if isinstance(value, list):
            text = "; ".join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        if text:
            pieces.append(f"{key.replace('_', ' ')}: {text}")
    return "; ".join(pieces) if pieces else DEFAULT_STYLE


def _storyboard_character_lines(storyboard: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for char in storyboard.get("characters") or []:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        bits = []
        for key in ("visual_anchor", "costume", "continuity_note"):
            value = str(char.get(key) or "").strip()
            if value:
                bits.append(value)
        if bits:
            lines.append(f"- {name}: {' '.join(bits)}")
    return lines


def _fallback_landlord_prompt(panel: dict[str, Any]) -> str:
    panel_no = int(panel.get("panel_number") or 0)
    base = (
        "Inside the Spouter-Inn bar-room, Ishmael, a young dark-haired sailor "
        "in a worn dark jacket, and Peter Coffin, a lean late-middle-aged "
        "landlord in shirtsleeves and waistcoat, carry on a comic exchange "
        "about the absent harpooneer selling preserved heads. Keep the preserved "
        "head material understated and non-gory; use a sea-bag or wrapped trade "
        "bundle as context only when needed."
    )
    beats = {
        1: "Wide two-shot: Ishmael is on the left leaning forward with a questioning look; Peter Coffin is on the right, amused and wry, hands near a small whittling knife on the table.",
        2: "Medium close on Ishmael near the center, puzzled and incredulous, one hand lifted as he repeats the idea back.",
        3: "Medium close on Peter Coffin on the right, amused, explaining with a dry grin while he whittles or gestures at the table.",
        4: "Medium close on Ishmael near the center, confused, palm open in a plain question.",
        5: "Medium close on Peter Coffin on the right, spreading his hands as if the answer is obvious.",
        6: "Wide two-shot: Ishmael listens on the left while Peter Coffin on the right leans in and explains; a weathered sea-bag or wrapped trade bundle sits low in the foreground as context, not as a grisly display.",
    }
    return f"{base} {beats.get(panel_no, '')}".strip()


def _fallback_prompt(panel: dict[str, Any]) -> str:
    if str(panel.get("source_expanded_sequence") or "") == "landlord_selling_heads_exchange":
        return _fallback_landlord_prompt(panel)
    speakers = [
        str(item.get("speaker") or "").strip()
        for item in panel.get("texts") or []
        if isinstance(item, dict) and str(item.get("speaker") or "").strip()
    ]
    speaker_text = ", ".join(dict.fromkeys(speakers))
    if speaker_text:
        return (
            "Source-grounded graphic novel panel in the Spouter-Inn. Show "
            f"{speaker_text} in the physical action implied by the panel text; "
            "keep the staging clear and avoid invented symbolic imagery."
        )
    return (
        "Source-grounded graphic novel panel in the Spouter-Inn, focused on the "
        "panel's concrete physical action, with no invented symbolic imagery."
    )


def _base_prompt(
    panel: dict[str, Any],
    frame_prompts: dict[tuple[int, int], dict[str, Any]],
) -> str:
    prompt = str(panel.get("image_prompt") or "").strip()
    if prompt:
        return prompt
    chapter = int(panel.get("source_chapter") or 0)
    frame_no = int(panel.get("source_frame_number") or 0)
    frame = frame_prompts.get((chapter, frame_no))
    if frame:
        prompt = str(frame.get("image_prompt") or "").strip()
        if prompt:
            return prompt
    return _fallback_prompt(panel)


def _slot_lines(panel: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    thumbnail = panel.get("thumbnail_layout")
    thumbnail_constraints = str(panel.get("thumbnail_constraints") or "").strip()
    if isinstance(thumbnail, dict):
        if thumbnail_constraints:
            lines.append(thumbnail_constraints)
        text_boxes = [
            item for item in thumbnail.get("text_boxes") or []
            if isinstance(item, dict)
        ]
        if text_boxes:
            lines.append("Thumbnail text boxes that must remain empty:")
            for item in text_boxes:
                box = item.get("box") or {}
                if isinstance(box, dict) and {"x", "y", "w", "h"} <= set(box):
                    owner = item.get("speaker") or item.get("reserved_for") or item.get("kind")
                    lines.append(
                        f"- {item.get('id')}: {item.get('kind')} for {owner}, "
                        f"x={float(box['x']) * 100:.0f}%, y={float(box['y']) * 100:.0f}%, "
                        f"w={float(box['w']) * 100:.0f}%, h={float(box['h']) * 100:.0f}%."
                    )
        figures = [
            item for item in thumbnail.get("figures") or []
            if isinstance(item, dict)
        ]
        if figures:
            lines.append("Thumbnail figure boxes to follow:")
            for item in figures:
                body = item.get("body_box") or {}
                face = item.get("face_box") or {}
                if not (
                    isinstance(body, dict)
                    and isinstance(face, dict)
                    and {"x", "y", "w", "h"} <= set(body)
                    and {"x", "y", "w", "h"} <= set(face)
                ):
                    continue
                lines.append(
                    f"- {item.get('character')}: body x={float(body['x']) * 100:.0f}%, "
                    f"y={float(body['y']) * 100:.0f}%, w={float(body['w']) * 100:.0f}%, "
                    f"h={float(body['h']) * 100:.0f}%; face x={float(face['x']) * 100:.0f}%, "
                    f"y={float(face['y']) * 100:.0f}%, w={float(face['w']) * 100:.0f}%, "
                    f"h={float(face['h']) * 100:.0f}%."
                )
        rules = [str(rule).strip() for rule in thumbnail.get("rules") or [] if str(rule).strip()]
        if rules:
            lines.append("Thumbnail rules:")
            lines.extend(f"- {rule}" for rule in rules)
        return lines

    constraints = str(panel.get("lettering_constraints") or "").strip()
    if constraints:
        lines.append(constraints)
    slots = [slot for slot in panel.get("lettering_slots") or [] if isinstance(slot, dict)]
    if slots:
        lines.append("Reserved lettering slots, measured as percentages of the panel:")
        for slot in slots:
            box = slot.get("box") or {}
            if isinstance(box, dict) and {"x", "y", "w", "h"} <= set(box):
                lines.append(
                    f"- {slot.get('id')}: {slot.get('kind')} for "
                    f"{slot.get('speaker') or slot.get('reserved_for') or 'caption'}, "
                    f"x={float(box['x']) * 100:.0f}%, y={float(box['y']) * 100:.0f}%, "
                    f"w={float(box['w']) * 100:.0f}%, h={float(box['h']) * 100:.0f}%."
                )
    return lines


def _clean_legacy_reservation(prompt: str) -> str:
    for phrase in (
        "No readable text.",
        "Leave clean negative space in the top-left for the caption.",
        "Leave clean negative space in the top-center for the caption.",
        "Leave clean negative space in the top-right for the caption.",
        "Leave clean negative space in the bottom-left for the caption.",
        "Leave clean negative space in the bottom-center for the caption.",
        "Leave clean negative space in the bottom-right for the caption.",
    ):
        prompt = prompt.replace(phrase, "")
    return " ".join(prompt.split())


def _prompt_for_panel(
    panel: dict[str, Any],
    *,
    page_number: int,
    frame_prompts: dict[tuple[int, int], dict[str, Any]],
    chapters_by_number: dict[int, dict[str, Any]],
    style_text: str,
    storyboard_character_lines: list[str],
) -> str:
    chapter_no = int(panel.get("source_chapter") or 0) or None
    character_lines = [
        *storyboard_character_lines,
        *_character_lines(chapters_by_number, chapter_no),
    ]
    text_context = []
    for item in panel.get("texts") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        text = str(item.get("text") or "").strip()
        speaker = str(item.get("speaker") or "").strip()
        if kind and text:
            prefix = f"{kind}"
            if speaker:
                prefix += f" by {speaker}"
            text_context.append(f"- {prefix}: {text}")

    parts = [
        f"Create clean text-free panel art for page {page_number}, panel {panel.get('panel_number')}.",
        f"Style: {style_text}.",
        "Character continuity:",
        *character_lines,
        "",
        "Panel content:",
        _clean_legacy_reservation(_base_prompt(panel, frame_prompts)),
        "",
        "Lettering-aware staging:",
        *_slot_lines(panel),
        "",
        "Later lettering text for staging only; do not draw it:",
        *text_context,
        "",
        f"Hard constraints: {GLOBAL_CONSTRAINTS}",
    ]
    return "\n".join(part for part in parts if part is not None).strip()


def _rounded_size_for_box(box: Any) -> str:
    aspect = max(1 / 3, min(3.0, box.width / max(box.height, 1)))
    if aspect >= 1:
        width = 1536
        height = int(round((width / aspect) / 16) * 16)
        height = max(512, min(1536, height))
    else:
        height = 1536
        width = int(round((height * aspect) / 16) * 16)
        width = max(512, min(1536, width))
    if width * height < 655_360:
        scale = math.sqrt(655_360 / (width * height))
        width = int(math.ceil(width * scale / 16) * 16)
        height = int(math.ceil(height * scale / 16) * 16)
    return f"{width}x{height}"


def prepare_panel_art_prompts(
    run_dir: Path,
    *,
    storyboard_path: Path,
    source_root: Path,
    out_storyboard: Path,
    jobs_jsonl: Path,
    prompt_dir: Path,
    quality: str,
) -> dict[str, Any]:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    style_text = _storyboard_style(storyboard)
    storyboard_characters = _storyboard_character_lines(storyboard)
    allowed_chapters = {
        int(panel.get("source_chapter") or 0)
        for page in storyboard.get("pages") or []
        if isinstance(page, dict)
        for panel in page.get("panels") or []
        if isinstance(panel, dict) and int(panel.get("source_chapter") or 0)
    }
    chapters = _load_chapter_storyboards(
        source_root,
        allowed_chapters=allowed_chapters or None,
    )
    frame_prompts = _frame_index(chapters)
    data = deepcopy(storyboard)
    jobs: list[dict[str, Any]] = []
    prompt_dir.mkdir(parents=True, exist_ok=True)

    for page in data.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        panels = [panel for panel in page.get("panels") or [] if isinstance(panel, dict)]
        page_w, page_h = _page_size(page)
        boxes = _panel_boxes(page, panels, page_w, page_h)
        for panel, box in zip(panels, boxes, strict=False):
            panel_no = int(panel.get("panel_number") or 0)
            image_name = str(panel.get("image") or f"page{page_no:03d}_panel{panel_no:03d}.png")
            panel["image"] = image_name
            prompt = _prompt_for_panel(
                panel,
                page_number=page_no,
                frame_prompts=frame_prompts,
                chapters_by_number=chapters,
                style_text=style_text,
                storyboard_character_lines=storyboard_characters,
            )
            panel["image_prompt"] = prompt
            prompt_path = prompt_dir / f"page_{page_no:03d}_panel_{panel_no:03d}.txt"
            prompt_path.write_text(prompt + "\n", encoding="utf-8")
            jobs.append({
                "prompt": prompt,
                "out": image_name,
                "size": _rounded_size_for_box(box),
                "quality": quality,
                "output_format": "png",
            })

    write_json(out_storyboard, data)
    jobs_jsonl.parent.mkdir(parents=True, exist_ok=True)
    jobs_jsonl.write_text(
        "\n".join(json.dumps(job, ensure_ascii=False) for job in jobs) + "\n",
        encoding="utf-8",
    )
    return {
        "source_storyboard": str(storyboard_path),
        "source_root": str(source_root),
        "output_storyboard": str(out_storyboard),
        "jobs_jsonl": str(jobs_jsonl),
        "prompt_dir": str(prompt_dir),
        "job_count": len(jobs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--storyboard-json", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--out-storyboard", type=Path, required=True)
    parser.add_argument("--jobs-jsonl", type=Path, required=True)
    parser.add_argument("--prompt-dir", type=Path, required=True)
    parser.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="low")
    args = parser.parse_args()

    source_root = args.source_root or args.run_dir.parent
    report = prepare_panel_art_prompts(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        source_root=source_root,
        out_storyboard=args.out_storyboard,
        jobs_jsonl=args.jobs_jsonl,
        prompt_dir=args.prompt_dir,
        quality=args.quality,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
