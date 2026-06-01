"""Ad-hoc graphic novel storyboard generator.

Usage:
  python -m scripts.graphic_novel_experiment gatsby --max-words 1600 --pages 4

Reads books/<book_id>/abridgment.txt, asks an LLM for a page/panel storyboard,
and writes JSON + Markdown under work/<book_id>/graphic_novel/<name>/.
This is intentionally outside the shipping abridgment pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import BOOKS_DIR, load_book, write_json
from forage.json_parse import parse_llm_json
from forage.llm import complete
from forage.prompts import load_prompt
from scripts.apply_graphic_lettering_policy import apply_lettering_policy
from scripts.apply_graphic_lettering_slots import apply_lettering_slots
from scripts.apply_graphic_thumbnail_layout import apply_thumbnail_layout


def _excerpt_units(
    text: str,
    start_word: int,
    max_words: int,
    unit_mode: str = "sentence",
) -> tuple[str, int, int, list[dict[str, Any]]]:
    words = text.split()
    if start_word < 1:
        raise ValueError("--start-word is 1-based and must be >= 1")
    start_idx = start_word - 1
    if start_idx >= len(words):
        raise ValueError(
            f"--start-word {start_word} is beyond abridgment length {len(words)}"
        )
    target_start = start_idx + 1
    target_end = min(len(words), start_idx + max_words)

    units: list[dict[str, Any]] = []
    excerpt_parts: list[str] = []
    cursor = 1
    for raw_para in re.split(r"\n\s*\n", text):
        para = raw_para.strip()
        if not para:
            continue
        pieces = [para] if unit_mode == "paragraph" else _sentence_like_units(para)
        for sentence in pieces:
            sent_words = sentence.split()
            sent_start = cursor
            sent_end = cursor + len(sent_words) - 1
            cursor = sent_end + 1
            if sent_end < target_start:
                continue
            if sent_start > target_end:
                break
            units.append({
                "id": len(units) + 1,
                "start_word": sent_start,
                "end_word": sent_end,
                "text": sentence,
            })
            excerpt_parts.append(sentence)
        if cursor > target_end:
            break

    if units:
        target_start = int(units[0]["start_word"])
        target_end = int(units[-1]["end_word"])

    return "\n\n".join(excerpt_parts), target_start, target_end, units


def _parse_chapter_numbers(spec: str) -> list[str]:
    numbers: list[int] = []
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = [p.strip() for p in part.split("-", 1)]
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"invalid chapter range {part!r}")
            numbers.extend(range(start, end + 1))
        else:
            numbers.append(int(part))
    if not numbers:
        raise ValueError("--chapter-numbers did not contain any chapters")
    seen: set[int] = set()
    deduped = []
    for number in numbers:
        if number <= 0:
            raise ValueError("chapter numbers must be positive")
        if number not in seen:
            deduped.append(str(number))
            seen.add(number)
    return deduped


def _chapter_excerpt_text(book: Any, chapter_numbers: str) -> tuple[str, list[str]]:
    chapters_path = book.work_dir / "chapters.json"
    if not chapters_path.exists():
        raise FileNotFoundError(f"missing chapter metadata: {chapters_path}")
    metadata = json.loads(chapters_path.read_text(encoding="utf-8"))
    wanted = set(_parse_chapter_numbers(chapter_numbers))
    selected: list[dict[str, Any]] = []
    for chapter in metadata.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        if chapter.get("kind") == "chapter" and str(chapter.get("number")) in wanted:
            selected.append(chapter)

    found = {str(chapter.get("number")) for chapter in selected}
    missing = sorted(wanted - found, key=int)
    if missing:
        raise ValueError(f"chapter numbers not found in {chapters_path}: {missing}")

    parts: list[str] = []
    chapter_ids: list[str] = []
    for chapter in selected:
        chapter_id = str(chapter.get("id"))
        chapter_path = book.work_dir / "chapters" / f"{chapter_id}.md"
        if not chapter_path.exists():
            raise FileNotFoundError(f"missing chapter text: {chapter_path}")
        heading = str(chapter.get("raw_heading") or chapter.get("title") or "").strip()
        body = chapter_path.read_text(encoding="utf-8").strip()
        parts.append(f"{heading}\n\n{body}" if heading else body)
        chapter_ids.append(chapter_id)
    return "\n\n".join(parts), chapter_ids


def _sentence_like_units(paragraph: str) -> list[str]:
    """Split prose into small storyboard source units.

    Paragraphs are often too coarse for comics: one paragraph can contain a
    whole causal chain. This splitter is intentionally simple and conservative;
    it keeps punctuation with the sentence and only splits after terminal
    punctuation followed by a likely sentence start.
    """
    pieces = [
        p.strip()
        for p in re.split(r"(?<=[.!?])\s+(?=[\"'“‘A-Z])", paragraph.strip())
        if p.strip()
    ]
    abbreviations = (
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Rev.", "St.", "Jr.", "Sr.",
    )
    merged: list[str] = []
    for piece in pieces:
        if merged and merged[-1].endswith(abbreviations):
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def _published_abridgment_path(book_id: str) -> Path:
    path = BOOKS_DIR / book_id / "abridgment.txt"
    if not path.exists():
        raise FileNotFoundError(f"no published abridgment at {path}")
    return path


def _validate_storyboard(data: dict[str, Any]) -> None:
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("storyboard JSON must contain a non-empty pages array")
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("each page must be an object")
        panels = page.get("panels")
        if not isinstance(panels, list) or not panels:
            raise ValueError(f"page {page.get('page_number')} has no panels")
        for panel in panels:
            if not isinstance(panel, dict):
                raise ValueError("each panel must be an object")
            if not str(panel.get("image_prompt", "")).strip():
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} missing image_prompt"
                )


def _validate_storyboard_plot_coverage(
    data: dict[str, Any],
    expected_beat_ids: list[str],
) -> None:
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("storyboard JSON must contain pages")

    known = set(expected_beat_ids)
    seen: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("each page must be an object")
        panels = page.get("panels")
        if not isinstance(panels, list) or not panels:
            raise ValueError(f"page {page.get('page_number')} has no panels")
        for panel in panels:
            if not isinstance(panel, dict):
                raise ValueError("each panel must be an object")
            ids = panel.get("graphic_beat_ids")
            if not isinstance(ids, list) or not ids:
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} missing graphic_beat_ids"
                )
            normalized = [str(beat_id).strip() for beat_id in ids if str(beat_id).strip()]
            if not normalized:
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} has empty graphic_beat_ids"
                )
            unknown = [beat_id for beat_id in normalized if beat_id not in known]
            if unknown:
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} references unknown beats {unknown}"
                )
            panel["graphic_beat_ids"] = normalized
            seen.extend(normalized)
            if not str(panel.get("driver_character", "")).strip():
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} missing driver_character"
                )
            action = str(panel.get("character_action", "")).strip()
            if not action:
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} missing character_action"
                )
            if _INANIMATE_SPINE_START_RE.search(action):
                raise ValueError(
                    f"page {page.get('page_number')} panel "
                    f"{panel.get('panel_number')} has inanimate-driven action: "
                    f"{action!r}"
                )

    deduped: list[str] = []
    for beat_id in seen:
        if not deduped or deduped[-1] != beat_id:
            deduped.append(beat_id)
    if deduped != expected_beat_ids:
        raise ValueError(
            "storyboard panels must cover plot beats exactly in order after "
            f"dedupe: expected {expected_beat_ids}, got {deduped}"
        )


def _normalize_panel_numbers(data: dict[str, Any]) -> None:
    pages = data.get("pages")
    if not isinstance(pages, list):
        return
    for page in pages:
        if not isinstance(page, dict):
            continue
        panels = page.get("panels")
        if not isinstance(panels, list):
            continue
        for index, panel in enumerate(panels, 1):
            if isinstance(panel, dict):
                panel["panel_number"] = index


def _source_unit_lookup(source_units: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(unit["id"]): unit for unit in source_units}


def _coerce_source_ids(value: Any, unit_by_id: dict[int, dict[str, Any]]) -> list[int]:
    if not isinstance(value, list):
        return []
    seen: set[int] = set()
    ids: list[int] = []
    for raw_id in value:
        try:
            unit_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if unit_id in unit_by_id and unit_id not in seen:
            ids.append(unit_id)
            seen.add(unit_id)
    return sorted(ids)


def _source_anchor(ids: list[int]) -> str:
    if not ids:
        return ""
    ranges: list[str] = []
    start = prev = ids[0]
    for unit_id in ids[1:]:
        if unit_id == prev + 1:
            prev = unit_id
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = unit_id
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(ranges)


def _normalize_source_references(
    data: dict[str, Any],
    source_units: list[dict[str, Any]],
) -> None:
    """Trust the source-unit IDs, not LLM-authored ranges/anchors."""
    unit_by_id = _source_unit_lookup(source_units)
    pages = data.get("pages")
    if not isinstance(pages, list):
        return

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_ids: list[int] = []
        panels = page.get("panels")
        if isinstance(panels, list):
            for panel in panels:
                if not isinstance(panel, dict):
                    continue
                ids = _coerce_source_ids(panel.get("source_unit_ids"), unit_by_id)
                if not ids:
                    continue
                panel["source_unit_ids"] = ids
                panel["source_word_range"] = [
                    int(unit_by_id[ids[0]]["start_word"]),
                    int(unit_by_id[ids[-1]]["end_word"]),
                ]
                panel["source_anchor"] = _source_anchor(ids)
                page_ids.extend(ids)

        ids = _coerce_source_ids(page.get("source_unit_ids"), unit_by_id)
        if not ids:
            ids = sorted(set(page_ids))
        if ids:
            page["source_unit_ids"] = ids
            page["source_word_range"] = [
                int(unit_by_id[ids[0]]["start_word"]),
                int(unit_by_id[ids[-1]]["end_word"]),
            ]


def _page_panel_source_ids(page: dict[str, Any]) -> list[int]:
    panel_ids: list[int] = []
    panels = page.get("panels")
    if not isinstance(panels, list):
        return panel_ids
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        raw_ids = panel.get("source_unit_ids")
        if not isinstance(raw_ids, list):
            continue
        for raw_id in raw_ids:
            try:
                panel_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
    return panel_ids


def _validate_page_source_coverage(
    page: dict[str, Any],
    assigned_units: list[dict[str, Any]],
) -> None:
    expected = [int(unit["id"]) for unit in assigned_units]
    actual = _page_panel_source_ids(page)
    normalized_actual = _collapse_adjacent_duplicates(actual)
    if actual != expected and normalized_actual != expected:
        raise ValueError(
            f"page {page.get('page_number')} panel source coverage mismatch: "
            f"expected {expected}, got {actual}"
        )


def _collapse_adjacent_duplicates(values: list[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        if result and result[-1] == value:
            continue
        result.append(value)
    return result


_GRAPHIC_PLOT_DISPOSITIONS = {
    "keep_as_panel",
    "keep_as_caption",
    "merge_into_adjacent_beat",
    "imply_visually",
    "omit",
}

_GRAPHIC_BEAT_TYPES = {
    "orientation",
    "entrance",
    "relationship",
    "action",
    "dialogue_exchange",
    "revelation",
    "decision",
    "reaction",
    "transition",
    "setup",
    "payoff",
}

_GRAPHIC_BEAT_IMPORTANCE = {
    "high",
    "medium",
    "low",
}


_INANIMATE_PLOT_DRIVERS = {
    "aerial",
    "bay",
    "book",
    "books",
    "building",
    "bungalow",
    "camera",
    "car",
    "cottage",
    "diagram",
    "dust",
    "house",
    "label",
    "landscape",
    "leaves",
    "map",
    "mansion",
    "object",
    "place",
    "setting",
    "shoreline",
    "signpost",
    "sound",
    "sun",
    "train",
    "water",
    "weather",
    "window",
}

_INANIMATE_SPINE_START_RE = re.compile(
    r"^\s*(?:"
    r"aerial|bay|book|books|building|bungalow|camera|car|cottage|diagram|"
    r"dust|house|label|landscape|leaves|map|mansion|object|place|pull back|"
    r"inset|insets|montage|quick montage|quick vignettes|sequence|"
    r"sepia montage|setting|shoreline|shot|signpost|sound|sun|timeline|"
    r"transition|transitions|vignette|vignettes|water|weather|window"
    r")\b",
    re.IGNORECASE,
)


def _nonempty_string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _validate_graphic_plot_version(
    data: dict[str, Any],
    source_units: list[dict[str, Any]],
    *,
    require_beat_contract: bool = False,
) -> None:
    raw_contract_version = data.get("beat_contract_version")
    strict_beat_contract = str(raw_contract_version).strip() == "2"
    if require_beat_contract and not strict_beat_contract:
        raise ValueError("plot version must declare beat_contract_version: 2")

    expected_ids = [int(unit["id"]) for unit in source_units]
    treatments = data.get("unit_treatments")
    if not isinstance(treatments, list):
        raise ValueError("plot version must contain unit_treatments array")
    treatment_ids: list[int] = []
    non_omit_ids: list[int] = []
    for item in treatments:
        if not isinstance(item, dict):
            raise ValueError("each unit_treatment must be an object")
        try:
            unit_id = int(item.get("source_unit_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("unit_treatment missing numeric source_unit_id") from exc
        disposition = str(item.get("disposition", "")).strip()
        if disposition not in _GRAPHIC_PLOT_DISPOSITIONS:
            raise ValueError(
                f"source unit {unit_id} has invalid disposition {disposition!r}"
            )
        treatment_ids.append(unit_id)
        if disposition != "omit":
            non_omit_ids.append(unit_id)

    if treatment_ids != expected_ids:
        raise ValueError(
            f"unit_treatments must cover source units exactly in order: "
            f"expected {expected_ids}, got {treatment_ids}"
        )

    beats = data.get("graphic_beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError("plot version must contain non-empty graphic_beats array")
    beat_ids: list[int] = []
    beat_id_order: list[str] = []
    known_ids = set(expected_ids)
    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError("each graphic beat must be an object")
        beat_id = str(beat.get("beat_id", "")).strip()
        if not beat_id:
            raise ValueError("each graphic beat must have a non-empty beat_id")
        if beat_id in beat_id_order:
            raise ValueError(f"duplicate graphic beat_id {beat_id!r}")
        beat_id_order.append(beat_id)
    known_beat_ids = set(beat_id_order)
    prior_beat_ids: set[str] = set()

    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError("each graphic beat must be an object")
        beat_id = str(beat.get("beat_id", "")).strip()
        raw_ids = beat.get("source_unit_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError(f"graphic beat {beat_id} has no source ids")
        ids: list[int] = []
        for raw_id in raw_ids:
            try:
                unit_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"graphic beat {beat_id} has non-numeric source id"
                ) from exc
            if unit_id not in known_ids:
                raise ValueError(
                    f"graphic beat {beat_id} references unknown "
                    f"source unit {unit_id}"
                )
            ids.append(unit_id)
        if ids != sorted(ids):
            raise ValueError(
                f"graphic beat {beat_id} source ids are out of order"
            )
        beat["source_unit_ids"] = ids
        beat_ids.extend(ids)
        driver = str(beat.get("driver_character", "")).strip()
        if not driver:
            raise ValueError(
                f"graphic beat {beat_id} missing driver_character"
            )
        if driver.lower() in _INANIMATE_PLOT_DRIVERS:
            raise ValueError(
                f"graphic beat {beat_id} has inanimate "
                f"driver_character {driver!r}"
            )
        state_change = str(beat.get("character_goal_or_state_change", "")).strip()
        if not state_change:
            raise ValueError(
                f"graphic beat {beat_id} missing "
                "character_goal_or_state_change"
            )
        spine = str(beat.get("physical_action_spine", "")).strip()
        if not spine:
            raise ValueError(
                f"graphic beat {beat_id} missing physical_action_spine"
            )
        if _INANIMATE_SPINE_START_RE.search(spine):
            raise ValueError(
                f"graphic beat {beat_id} action spine appears "
                f"inanimate-driven: {spine!r}"
            )
        evidence = beat.get("visual_evidence")
        if not isinstance(evidence, list) or not any(
            str(item).strip() for item in evidence
        ):
            raise ValueError(
                f"graphic beat {beat_id} missing visual_evidence"
            )
        if strict_beat_contract:
            beat_type = str(beat.get("beat_type", "")).strip()
            if beat_type not in _GRAPHIC_BEAT_TYPES:
                raise ValueError(
                    f"graphic beat {beat_id} has invalid beat_type {beat_type!r}"
                )
            importance = str(beat.get("importance", "")).strip()
            if importance not in _GRAPHIC_BEAT_IMPORTANCE:
                raise ValueError(
                    f"graphic beat {beat_id} has invalid importance {importance!r}"
                )
            for key in (
                "scene",
                "time",
                "actor",
                "action",
                "result",
                "reader_new_info",
            ):
                if not str(beat.get(key, "")).strip():
                    raise ValueError(f"graphic beat {beat_id} missing {key}")
            if not isinstance(beat.get("object"), str):
                raise ValueError(f"graphic beat {beat_id} missing object string")
            participants = _nonempty_string_items(beat.get("participants"))
            if not participants:
                raise ValueError(f"graphic beat {beat_id} missing participants")
            required = _nonempty_string_items(beat.get("required_visuals"))
            if not required:
                raise ValueError(f"graphic beat {beat_id} missing required_visuals")
            forbidden = beat.get("forbidden_visuals")
            if not isinstance(forbidden, list):
                raise ValueError(
                    f"graphic beat {beat_id} forbidden_visuals must be an array"
                )
            if not isinstance(beat.get("visualizable"), bool):
                raise ValueError(f"graphic beat {beat_id} missing visualizable boolean")
            depends_on = _nonempty_string_items(beat.get("depends_on"))
            enables = _nonempty_string_items(beat.get("enables"))
            unknown_depends = [item for item in depends_on if item not in known_beat_ids]
            if unknown_depends:
                raise ValueError(
                    f"graphic beat {beat_id} depends on unknown beats "
                    f"{unknown_depends}"
                )
            future_depends = [item for item in depends_on if item not in prior_beat_ids]
            if future_depends:
                raise ValueError(
                    f"graphic beat {beat_id} depends on non-prior beats "
                    f"{future_depends}"
                )
            unknown_enables = [item for item in enables if item not in known_beat_ids]
            if unknown_enables:
                raise ValueError(
                    f"graphic beat {beat_id} enables unknown beats "
                    f"{unknown_enables}"
                )
            beat["participants"] = participants
            beat["depends_on"] = depends_on
            beat["enables"] = enables
            beat["required_visuals"] = required
            beat["forbidden_visuals"] = _nonempty_string_items(forbidden)
        prior_beat_ids.add(beat_id)

    if beat_ids != non_omit_ids:
        raise ValueError(
            "graphic_beats must cover every non-omitted source unit exactly "
            f"in order: expected {non_omit_ids}, got {beat_ids}"
        )


def _panel_dialogue(panel: dict[str, Any]) -> list[str]:
    dialogue = panel.get("dialogue") or []
    if not isinstance(dialogue, list):
        return []
    rendered = []
    for item in dialogue:
        if isinstance(item, dict):
            speaker = str(item.get("speaker", "")).strip()
            text = str(item.get("text", "")).strip()
            if speaker or text:
                rendered.append(f"{speaker}: {text}".strip(": "))
    return rendered


def _format_lettering_slot(slot: dict[str, Any]) -> str:
    box = slot.get("box") or {}
    if isinstance(box, dict) and {"x", "y", "w", "h"} <= set(box):
        box_text = (
            f"x={float(box['x']) * 100:.0f}%, y={float(box['y']) * 100:.0f}%, "
            f"w={float(box['w']) * 100:.0f}%, h={float(box['h']) * 100:.0f}%"
        )
    elif isinstance(box, dict) and {"x1", "y1", "x2", "y2"} <= set(box):
        box_text = (
            f"x1={float(box['x1']) * 100:.0f}%, y1={float(box['y1']) * 100:.0f}%, "
            f"x2={float(box['x2']) * 100:.0f}%, y2={float(box['y2']) * 100:.0f}%"
        )
    else:
        box_text = "box unspecified"
    owner = str(slot.get("speaker") or slot.get("reserved_for") or "").strip()
    owner_text = f" for {owner}" if owner else ""
    return (
        f"- {slot.get('id', '?')}: {slot.get('kind', '?')}{owner_text}, "
        f"{slot.get('zone', '')}, {box_text}"
    )


def _write_page_image_prompts(
    data: dict[str, Any],
    out_dir: Path,
    prompt_dir_name: str = "image_prompts",
) -> None:
    prompt_dir = out_dir / prompt_dir_name
    prompt_dir.mkdir(parents=True, exist_ok=True)

    style = data.get("style_bible") or {}
    style_lines = []
    if isinstance(style, dict):
        for key, value in style.items():
            if key in {"lettering", "recurring_motifs"}:
                continue
            if isinstance(value, list):
                rendered = "; ".join(str(v) for v in value)
            else:
                rendered = str(value)
            style_lines.append(f"- {key.replace('_', ' ')}: {rendered}")

    character_lines = []
    characters = data.get("characters") or []
    if isinstance(characters, list):
        for char in characters:
            if not isinstance(char, dict):
                continue
            name = str(char.get("name", "Unnamed")).strip()
            anchor = str(char.get("visual_anchor", "")).strip()
            costume = str(char.get("costume", "")).strip()
            note = str(char.get("continuity_note", "")).strip()
            character_lines.append(
                f"- {name}: {anchor} Costume: {costume} Continuity: {note}"
            )

    for page in data.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        panels = [p for p in page.get("panels", []) if isinstance(p, dict)]
        lines = [
            "Create one finished graphic novel page as clean, text-free art.",
            "",
            "Hard constraints:",
            "- No readable text anywhere.",
            "- No speech balloons, caption boxes, labels, signs, maps, or lettering.",
            "- Do not combine panels or remix the order.",
            "- Keep every panel visually tied to its listed beat only.",
            "- Do not add motifs, props, animals, objects, or symbols just "
            "because they appear elsewhere in the book.",
            "- Reserve the explicit in-panel lettering slots listed for each panel.",
            "- Keep those slots as simple empty background; keep faces, mouths, "
            "hands, active gestures, and key props out of them.",
            "- Do not reserve lettering space in gutters or outside panel frames.",
            f"- Page has {len(panels)} panels, read left-to-right, top-to-bottom.",
            "",
            "Style:",
            "- Treat these as rendering/style directions only, not as a content "
            "inventory. Panel art prompts control what appears.",
            *style_lines,
            "",
            "Character continuity:",
            *character_lines,
            "",
            f"Page {page_no} summary: {page.get('page_summary', '')}",
            "",
            "Panels:",
        ]
        for panel in panels:
            panel_no = panel.get("panel_number", "?")
            lines.append("")
            lines.append(f"Panel {panel_no}:")
            lines.append(f"Beat: {panel.get('beat', '')}")
            lines.append(f"Shot: {panel.get('shot', '')}")
            archetype = str(panel.get("panel_archetype") or "").strip()
            if archetype:
                lines.append(f"Panel archetype: {archetype}")
            slots = [
                slot for slot in panel.get("lettering_slots") or []
                if isinstance(slot, dict)
            ]
            if slots:
                lines.append("In-panel lettering slots to reserve in the art:")
                lines.extend(_format_lettering_slot(slot) for slot in slots)
            else:
                zone = str(panel.get("caption_zone", "")).strip()
                if zone:
                    lines.append(f"Caption zone reserved for later lettering: {zone}")
            thumbnail = panel.get("thumbnail_layout")
            if isinstance(thumbnail, dict):
                constraints_text = str(panel.get("thumbnail_constraints") or "").strip()
                if constraints_text:
                    lines.append(f"Thumbnail layout: {constraints_text}")
                figures = [
                    item for item in thumbnail.get("figures") or []
                    if isinstance(item, dict)
                ]
                if figures:
                    lines.append("Thumbnail figure boxes:")
                    for item in figures:
                        body = item.get("body_box") or {}
                        face = item.get("face_box") or {}
                        if (
                            isinstance(body, dict)
                            and isinstance(face, dict)
                            and {"x", "y", "w", "h"} <= set(body)
                            and {"x", "y", "w", "h"} <= set(face)
                        ):
                            lines.append(
                                f"- {item.get('character')}: body "
                                f"x={float(body['x']) * 100:.0f}%, "
                                f"y={float(body['y']) * 100:.0f}%, "
                                f"w={float(body['w']) * 100:.0f}%, "
                                f"h={float(body['h']) * 100:.0f}%; face "
                                f"x={float(face['x']) * 100:.0f}%, "
                                f"y={float(face['y']) * 100:.0f}%, "
                                f"w={float(face['w']) * 100:.0f}%, "
                                f"h={float(face['h']) * 100:.0f}%"
                            )
            constraints = str(panel.get("lettering_constraints") or "").strip()
            if constraints:
                lines.append(f"Lettering constraints: {constraints}")
            lines.append(f"Art prompt: {panel.get('image_prompt', '')}")
        (prompt_dir / f"page_{page_no:03d}.txt").write_text(
            "\n".join(lines).rstrip() + "\n",
            encoding="utf-8",
        )


def _chunk_units_by_pages(
    source_units: list[dict[str, Any]],
    page_count: int,
) -> list[list[dict[str, Any]]]:
    if page_count <= 0:
        raise ValueError("page_count must be > 0")
    if not source_units:
        raise ValueError("no source units to storyboard")

    total_words = sum(
        int(u["end_word"]) - int(u["start_word"]) + 1
        for u in source_units
    )
    target = max(1, round(total_words / page_count))
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_words = 0

    for index, unit in enumerate(source_units):
        remaining_units = len(source_units) - index
        remaining_pages = page_count - len(chunks)
        unit_words = int(unit["end_word"]) - int(unit["start_word"]) + 1
        should_flush = (
            current
            and current_words >= target
            and remaining_units >= remaining_pages
        )
        if should_flush:
            chunks.append(current)
            current = []
            current_words = 0
        current.append(unit)
        current_words += unit_words

    if current:
        chunks.append(current)

    while len(chunks) < page_count:
        chunks.append([])
    if len(chunks) > page_count:
        chunks[page_count - 1].extend(
            unit for chunk in chunks[page_count:] for unit in chunk
        )
        chunks = chunks[:page_count]
    return chunks


def _merge_characters(existing: list[dict[str, Any]],
                      updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for char in existing + updates:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name", "")).strip()
        if not name:
            continue
        current = by_name.get(name, {})
        merged = {**current, **{k: v for k, v in char.items() if v not in (None, "")}}
        by_name[name] = merged
    return list(by_name.values())


def _compact_characters(characters: list[dict[str, Any]]) -> str:
    lines = []
    for char in characters:
        name = str(char.get("name", "")).strip()
        if not name:
            continue
        anchor = str(char.get("visual_anchor", "")).strip()
        costume = str(char.get("costume", "")).strip()
        note = str(char.get("continuity_note", "")).strip()
        lines.append(f"- {name}: {anchor} Costume: {costume} Continuity: {note}")
    return "\n".join(lines) if lines else "(none yet)"


def _complete_json_with_retry(
    *,
    rendered: str,
    model: str,
    system: str | None,
    max_tokens: int,
    work_dir: Path,
    stage: str,
    raw_path: Path,
) -> dict[str, Any]:
    caps = [max_tokens]
    doubled = min(max_tokens * 2, 64000)
    if doubled > max_tokens:
        caps.append(doubled)

    last_error: Exception | None = None
    for attempt, cap in enumerate(caps, 1):
        resp = complete(
            prompt=rendered,
            model=model,
            system=system,
            max_tokens=cap,
            work_dir=work_dir,
            stage=f"{stage}:attempt{attempt}",
        )
        suffix = "" if attempt == 1 else f".attempt{attempt}"
        attempt_path = raw_path.with_name(
            f"{raw_path.stem}{suffix}{raw_path.suffix}"
        )
        attempt_path.write_text(resp.text, encoding="utf-8")
        if not resp.text.strip():
            last_error = ValueError(
                f"empty response with stop_reason={resp.stop_reason} cap={cap}"
            )
            continue
        try:
            return parse_llm_json(resp.text)
        except Exception as exc:
            last_error = exc
            if resp.stop_reason != "length":
                break
    if last_error is None:
        last_error = ValueError("no LLM response attempts were made")
    raise last_error


def _run_page_by_page(
    *,
    book_id: str,
    title: str,
    author: str,
    book_work_dir: Path,
    out_dir: Path,
    source_path: Path,
    source_units: list[dict[str, Any]],
    excerpt_words: tuple[int, int],
    pages: int,
    panels_per_page: int,
    model: str,
    max_tokens: int,
    dry_run: bool,
) -> int:
    prompt = load_prompt("graphic_storyboard_page")
    chunks = _chunk_units_by_pages(source_units, pages)
    write_json(out_dir / "page_unit_chunks.json", [
        {
            "page_number": i + 1,
            "source_unit_ids": [u["id"] for u in chunk],
            "source_word_range": (
                [chunk[0]["start_word"], chunk[-1]["end_word"]]
                if chunk else []
            ),
        }
        for i, chunk in enumerate(chunks)
    ])

    style_bible: dict[str, Any] = {}
    characters: list[dict[str, Any]] = []
    page_results: list[dict[str, Any]] = []
    continuity: dict[str, Any] = {
        "covered_source_unit_ids": [],
        "last_scene": "",
        "active_characters": [],
        "character_updates": [],
        "visual_motifs": [],
        "next_page_needs": [],
    }

    prompt_dir = out_dir / "page_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "page_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for page_index, chunk in enumerate(chunks, 1):
        rendered = prompt.render(
            title=title,
            author=author,
            page_number=page_index,
            total_pages=pages,
            panels_per_page=panels_per_page,
            source_units=chunk,
            prior_context=json.dumps(continuity, indent=2, ensure_ascii=False),
            existing_style_bible=json.dumps(
                style_bible, indent=2, ensure_ascii=False
            ) if style_bible else "",
            existing_characters=_compact_characters(characters),
        )
        (prompt_dir / f"page_{page_index:03d}.md").write_text(
            rendered, encoding="utf-8"
        )
        if dry_run:
            continue

        data = _complete_json_with_retry(
            rendered=rendered,
            model=model,
            system=prompt.system,
            max_tokens=max_tokens,
            work_dir=book_work_dir,
            stage=f"graphic_storyboard_page:{book_id}:page{page_index:03d}",
            raw_path=raw_dir / f"page_{page_index:03d}.txt",
        )
        page = data.get("page")
        if not isinstance(page, dict):
            raise ValueError(f"page {page_index} response missing page object")
        _normalize_source_references({"pages": [page]}, source_units)
        _validate_page_source_coverage(page, chunk)
        page_results.append(page)
        if isinstance(data.get("style_bible"), dict):
            style_bible = {**style_bible, **data["style_bible"]}
        characters = _merge_characters(
            characters,
            data.get("characters") if isinstance(data.get("characters"), list) else [],
        )
        if isinstance(data.get("continuity_state"), dict):
            continuity = data["continuity_state"]

    if dry_run:
        print(f"wrote page-by-page dry-run prompts to {prompt_dir}")
        return 0

    storyboard = {
        "title": f"{title} — Pagewise Graphic Novel Trial",
        "adaptation_scope": (
            f"Page-by-page storyboard for words {excerpt_words[0]}-"
            f"{excerpt_words[1]} of {source_path}."
        ),
        "format": {
            "page_count": pages,
            "target_panels_per_page": panels_per_page,
            "reading_order": "left-to-right, top-to-bottom",
            "drafting_mode": "page_by_page",
        },
        "style_bible": style_bible,
        "characters": characters,
        "pages": page_results,
        "open_questions": continuity.get("next_page_needs", []),
    }
    _normalize_source_references(storyboard, source_units)
    _validate_storyboard(storyboard)
    storyboard, policy_report = apply_lettering_policy(storyboard)
    storyboard, slot_report = apply_lettering_slots(storyboard)
    storyboard, thumbnail_report = apply_thumbnail_layout(storyboard)
    write_json(out_dir / "storyboard.json", storyboard)
    write_json(out_dir / "lettering_policy_report.json", policy_report)
    write_json(out_dir / "lettering_slots_report.json", slot_report)
    write_json(out_dir / "thumbnail_layout_report.json", thumbnail_report)
    _write_page_image_prompts(storyboard, out_dir)
    markdown = _markdown_storyboard(
        storyboard, book_id=book_id, source_path=source_path,
        excerpt_words=excerpt_words,
    )
    (out_dir / "storyboard.md").write_text(markdown, encoding="utf-8")

    panel_count = sum(len(p.get("panels", []) or []) for p in page_results)
    print(f"wrote {len(page_results)} pages / {panel_count} panels")
    print(f"json: {out_dir / 'storyboard.json'}")
    print(f"markdown: {out_dir / 'storyboard.md'}")
    print(f"image prompts: {out_dir / 'image_prompts'}")
    return 0


def _markdown_storyboard(data: dict[str, Any], *, book_id: str,
                         source_path: Path, excerpt_words: tuple[int, int]) -> str:
    lines: list[str] = []
    title = data.get("title") or book_id
    lines.append(f"# {title} Graphic Novel Experiment")
    lines.append("")
    lines.append(f"- Book id: `{book_id}`")
    lines.append(f"- Source: `{source_path}`")
    lines.append(f"- Excerpt words: {excerpt_words[0]}-{excerpt_words[1]}")
    lines.append("")

    scope = data.get("adaptation_scope")
    if scope:
        lines.append("## Scope")
        lines.append("")
        lines.append(str(scope).strip())
        lines.append("")

    style = data.get("style_bible") or {}
    if isinstance(style, dict) and style:
        lines.append("## Style Bible")
        lines.append("")
        for key, value in style.items():
            label = str(key).replace("_", " ").title()
            if isinstance(value, list):
                rendered = "; ".join(str(v) for v in value)
            else:
                rendered = str(value)
            lines.append(f"- **{label}:** {rendered}")
        lines.append("")

    characters = data.get("characters") or []
    if isinstance(characters, list) and characters:
        lines.append("## Characters")
        lines.append("")
        for char in characters:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "Unnamed")
            parts = []
            for key in ("visual_anchor", "costume", "expression_range",
                        "continuity_note"):
                value = str(char.get(key, "")).strip()
                if value:
                    parts.append(f"{key.replace('_', ' ')}: {value}")
            lines.append(f"- **{name}:** {'; '.join(parts)}")
        lines.append("")

    for page in data.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_no = page.get("page_number", "?")
        lines.append(f"## Page {page_no}")
        lines.append("")
        summary = str(page.get("page_summary", "")).strip()
        if summary:
            lines.append(summary)
            lines.append("")
        for panel in page.get("panels", []):
            if not isinstance(panel, dict):
                continue
            panel_no = panel.get("panel_number", "?")
            shot = panel.get("shot", "")
            lines.append(f"### Panel {page_no}.{panel_no} {f'({shot})' if shot else ''}")
            lines.append("")
            for key, label in (
                ("beat", "Beat"),
                ("image_prompt", "Image Prompt"),
                ("caption_zone", "Caption Zone"),
                ("caption", "Caption"),
            ):
                value = str(panel.get(key, "")).strip()
                if value:
                    lines.append(f"- **{label}:** {value}")
            rendered = _panel_dialogue(panel)
            if rendered:
                lines.append(f"- **Dialogue:** {' / '.join(rendered)}")
            sfx = panel.get("sfx") or []
            if isinstance(sfx, list) and sfx:
                lines.append(f"- **SFX:** {', '.join(str(x) for x in sfx)}")
            for key, label in (
                ("continuity_notes", "Continuity"),
                ("source_unit_ids", "Source Units"),
                ("source_word_range", "Source Word Range"),
                ("source_anchor", "Source Anchor"),
                ("adaptation_note", "Adaptation Note"),
            ):
                raw_value = panel.get(key, "")
                if isinstance(raw_value, list):
                    value = ", ".join(str(x) for x in raw_value).strip()
                else:
                    value = str(raw_value).strip()
                if value:
                    lines.append(f"- **{label}:** {value}")
            lines.append("")

    questions = data.get("open_questions") or []
    if isinstance(questions, list) and questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in questions:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _markdown_graphic_plot_version(
    data: dict[str, Any],
    *,
    book_id: str,
    source_path: Path,
    excerpt_words: tuple[int, int],
) -> str:
    lines: list[str] = []
    title = data.get("title") or book_id
    lines.append(f"# {title} Graphic Plot Version")
    lines.append("")
    lines.append(f"- Book id: `{book_id}`")
    lines.append(f"- Source: `{source_path}`")
    lines.append(f"- Excerpt words: {excerpt_words[0]}-{excerpt_words[1]}")
    lines.append("")

    scope = str(data.get("adaptation_scope", "")).strip()
    if scope:
        lines.append("## Scope")
        lines.append("")
        lines.append(scope)
        lines.append("")

    strategy = data.get("pacing_strategy") or {}
    if isinstance(strategy, dict) and strategy:
        lines.append("## Pacing Strategy")
        lines.append("")
        for key in (
            "summary",
            "target_reader_experience",
            "compression_ratio",
        ):
            value = str(strategy.get(key, "")).strip()
            if value:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        risks = strategy.get("main_risks") or []
        if isinstance(risks, list) and risks:
            lines.append(f"- **Main Risks:** {'; '.join(str(r) for r in risks)}")
        lines.append("")

    frames = data.get("time_frames") or []
    if isinstance(frames, list) and frames:
        lines.append("## Time Frames")
        lines.append("")
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            label = str(frame.get("label") or frame.get("id") or "").strip()
            parts = []
            for key in ("chronological_position", "reader_cue", "visual_cue"):
                value = str(frame.get(key, "")).strip()
                if value:
                    parts.append(f"{key.replace('_', ' ')}: {value}")
            if label:
                lines.append(f"- **{label}:** {'; '.join(parts)}")
        lines.append("")

    beats = data.get("graphic_beats") or []
    if isinstance(beats, list) and beats:
        lines.append("## Graphic Beats")
        lines.append("")
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", "")).strip()
            subject = str(beat.get("subject", "")).strip()
            heading = beat_id if beat_id else "Beat"
            if subject:
                heading = f"{heading}: {subject}"
            lines.append(f"### {heading}")
            lines.append("")
            for key, label in (
                ("source_unit_ids", "Source Units"),
                ("beat_type", "Beat Type"),
                ("time_frame", "Time Frame"),
                ("scene", "Scene"),
                ("time", "Time"),
                ("participants", "Participants"),
                ("driver_character", "Driver Character"),
                ("actor", "Actor"),
                ("action", "Action"),
                ("object", "Object"),
                ("result", "Result"),
                ("reader_new_info", "Reader New Info"),
                ("depends_on", "Depends On"),
                ("enables", "Enables"),
                ("character_goal_or_state_change", "Goal / State Change"),
                ("physical_action_spine", "Action Spine"),
                ("narrative_function", "Narrative Function"),
                ("setting_or_orientation", "Setting / Orientation"),
                ("visual_anchor", "Visual Anchor"),
                ("required_visuals", "Required Visuals"),
                ("forbidden_visuals", "Forbidden Visuals"),
                ("visualizable", "Visualizable"),
                ("visual_evidence", "Visual Evidence"),
                ("compression_guidance", "Compression Guidance"),
                ("storyboard_guidance", "Storyboard Guidance"),
                ("importance", "Importance"),
                ("pacing_priority", "Pacing Priority"),
            ):
                raw_value = beat.get(key, "")
                if isinstance(raw_value, list):
                    value = ", ".join(str(x) for x in raw_value).strip()
                else:
                    value = str(raw_value).strip()
                if value:
                    lines.append(f"- **{label}:** {value}")
            for key, label in (
                ("essential_facts", "Essential Facts"),
                ("character_relationships", "Character Relationships"),
                ("caption_candidates", "Caption Candidates"),
            ):
                raw_value = beat.get(key, "")
                if isinstance(raw_value, list) and raw_value:
                    lines.append(f"- **{label}:**")
                    for item in raw_value:
                        lines.append(f"  - {item}")
            lines.append("")

    treatments = data.get("unit_treatments") or []
    if isinstance(treatments, list) and treatments:
        lines.append("## Source Unit Treatment")
        lines.append("")
        for item in treatments:
            if not isinstance(item, dict):
                continue
            unit_id = item.get("source_unit_id", "?")
            disposition = str(item.get("disposition", "")).strip()
            subject = str(item.get("subject", "")).strip()
            function = str(item.get("narrative_function", "")).strip()
            reason = str(
                item.get("omit_or_compress_reason")
                or item.get("preservation_reason")
                or ""
            ).strip()
            parts = [p for p in (subject, function, reason) if p]
            lines.append(
                f"- **{unit_id}:** `{disposition}`"
                f"{' - ' + ' | '.join(parts) if parts else ''}"
            )
        lines.append("")

    omitted = data.get("omitted_units") or []
    if isinstance(omitted, list) and omitted:
        lines.append("## Omitted Units")
        lines.append("")
        for item in omitted:
            if not isinstance(item, dict):
                continue
            unit_id = item.get("source_unit_id", "?")
            reason = str(item.get("reason", "")).strip()
            safe = str(item.get("safe_because", "")).strip()
            lines.append(f"- **{unit_id}:** {reason}{f' - {safe}' if safe else ''}")
        lines.append("")

    requirements = data.get("continuity_requirements") or []
    if isinstance(requirements, list) and requirements:
        lines.append("## Continuity Requirements")
        lines.append("")
        for req in requirements:
            if not isinstance(req, dict):
                continue
            name = str(req.get("name", "")).strip()
            kind = str(req.get("type", "")).strip()
            requirement = str(req.get("requirement", "")).strip()
            label = f"{kind}: {name}" if kind and name else name or kind
            if label or requirement:
                lines.append(f"- **{label}:** {requirement}")
        lines.append("")

    instructions = data.get("storyboard_instructions") or []
    if isinstance(instructions, list) and instructions:
        lines.append("## Storyboard Instructions")
        lines.append("")
        for item in instructions:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _markdown_lettering_script(data: dict[str, Any]) -> str:
    lines: list[str] = []
    title = data.get("title") or "Graphic Novel"
    lines.append(f"# {title} Lettering Script")
    lines.append("")
    lines.append("Captions, dialogue, and SFX are intended for post-lettering.")
    lines.append("")

    for page in data.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_no = page.get("page_number", "?")
        lines.append(f"## Page {page_no}")
        lines.append("")
        summary = str(page.get("page_summary", "")).strip()
        if summary:
            lines.append(summary)
            lines.append("")
        for panel in page.get("panels", []):
            if not isinstance(panel, dict):
                continue
            panel_no = panel.get("panel_number", "?")
            beat_ids = panel.get("graphic_beat_ids") or []
            if isinstance(beat_ids, list):
                beat_text = ", ".join(str(x) for x in beat_ids)
            else:
                beat_text = str(beat_ids)
            lines.append(f"### Panel {page_no}.{panel_no}")
            if beat_text:
                lines.append(f"- **Graphic Beats:** {beat_text}")
            caption = str(panel.get("caption", "")).strip()
            if caption:
                lines.append(f"- **Caption:** {caption}")
            rendered = _panel_dialogue(panel)
            if rendered:
                lines.append(f"- **Dialogue:** {' / '.join(rendered)}")
            sfx = panel.get("sfx") or []
            if isinstance(sfx, list) and sfx:
                lines.append(f"- **SFX:** {', '.join(str(x) for x in sfx)}")
            notes = str(panel.get("lettering_notes", "")).strip()
            if notes:
                lines.append(f"- **Lettering Notes:** {notes}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book_id")
    parser.add_argument("--name", default="trial",
                        help="output subdirectory under work/<book>/graphic_novel")
    parser.add_argument("--start-word", type=int, default=1)
    parser.add_argument("--max-words", type=int, default=1600)
    parser.add_argument(
        "--chapter-numbers",
        help=(
            "Use complete drafted/published chapter numbers, e.g. 1-3. "
            "This reads work/<book>/chapters metadata and ignores start/max words."
        ),
    )
    parser.add_argument(
        "--unit-mode",
        choices=["sentence", "paragraph"],
        default="sentence",
        help="Source-unit granularity for plot/storyboard accounting.",
    )
    parser.add_argument("--pages", type=int, default=4)
    parser.add_argument("--panels-per-page", type=int, default=5)
    parser.add_argument("--model", default=None,
                        help="override prompt model, e.g. openai:gpt-5")
    parser.add_argument("--max-output-tokens", type=int, default=None,
                        help="override per-call LLM output token cap")
    parser.add_argument("--plot-version", action="store_true",
                        help="write an intermediate graphic-novel plot treatment and exit")
    parser.add_argument("--storyboard-from-plot", type=Path, default=None,
                        help="read a plot_version.json and write storyboard/caption/dialogue files")
    parser.add_argument("--page-by-page", action="store_true",
                        help="draft each page in a separate LLM call with continuity context")
    parser.add_argument("--dry-run", action="store_true",
                        help="write the prompt and excerpt without calling an LLM")
    args = parser.parse_args(argv)

    if args.max_words <= 0:
        raise ValueError("--max-words must be > 0")
    if args.pages <= 0:
        raise ValueError("--pages must be > 0")
    if args.panels_per_page <= 0:
        raise ValueError("--panels-per-page must be > 0")
    stage_flags = sum(bool(x) for x in (
        args.plot_version,
        args.page_by_page,
        args.storyboard_from_plot,
    ))
    if stage_flags > 1:
        raise ValueError(
            "--plot-version, --page-by-page, and --storyboard-from-plot "
            "are separate stages"
        )

    book = load_book(args.book_id)
    out_dir = book.work_dir / "graphic_novel" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    chapter_ids: list[str] = []
    if args.chapter_numbers:
        abridgment, chapter_ids = _chapter_excerpt_text(book, args.chapter_numbers)
        excerpt, start_word, end_word, source_units = _excerpt_units(
            abridgment, 1, max(1, len(abridgment.split())), args.unit_mode
        )
        source_path = out_dir / "excerpt.txt"
    else:
        source_path = _published_abridgment_path(args.book_id)
        abridgment = source_path.read_text(encoding="utf-8")
        excerpt, start_word, end_word, source_units = _excerpt_units(
            abridgment, args.start_word, args.max_words, args.unit_mode
        )

    (out_dir / "excerpt.txt").write_text(excerpt, encoding="utf-8")
    write_json(out_dir / "source_units.json", source_units)

    if args.plot_version:
        prompt_name = "graphic_plot_version"
    elif args.storyboard_from_plot:
        prompt_name = "graphic_storyboard_from_plot"
    elif args.page_by_page:
        prompt_name = "graphic_storyboard_page"
    else:
        prompt_name = "graphic_storyboard"
    prompt = load_prompt(prompt_name)
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 12000))
    )

    run_meta = {
        "book_id": args.book_id,
        "name": args.name,
        "source_path": str(source_path),
        "start_word": start_word,
        "end_word": end_word,
        "max_words": args.max_words,
        "chapter_numbers": args.chapter_numbers,
        "chapter_ids": chapter_ids,
        "unit_mode": args.unit_mode,
        "pages": args.pages,
        "panels_per_page": args.panels_per_page,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "plot_version": args.plot_version,
        "storyboard_from_plot": str(args.storyboard_from_plot)
        if args.storyboard_from_plot else None,
        "page_by_page": args.page_by_page,
        "dry_run": args.dry_run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_json(out_dir / "run.json", run_meta)

    if args.plot_version:
        rendered = prompt.render(
            title=book.metadata.get("title", args.book_id),
            author=book.metadata.get("author", ""),
            source_units=source_units,
            start_word=start_word,
            end_word=end_word,
            pages=args.pages,
            panels_per_page=args.panels_per_page,
        )
        (out_dir / "plot_prompt.md").write_text(rendered, encoding="utf-8")

        if args.dry_run:
            print(f"wrote plot-version dry-run prompt to {out_dir / 'plot_prompt.md'}")
            return 0

        data = _complete_json_with_retry(
            rendered=rendered,
            model=model,
            system=prompt.system,
            max_tokens=max_output_tokens,
            work_dir=book.work_dir,
            stage=f"graphic_plot_version:{args.book_id}:{args.name}",
            raw_path=out_dir / "plot_raw_response.txt",
        )
        _validate_graphic_plot_version(
            data,
            source_units,
            require_beat_contract=True,
        )
        write_json(out_dir / "plot_version.json", data)
        markdown = _markdown_graphic_plot_version(
            data, book_id=args.book_id, source_path=source_path,
            excerpt_words=(start_word, end_word)
        )
        (out_dir / "plot_version.md").write_text(markdown, encoding="utf-8")

        beat_count = len(data.get("graphic_beats", []) or [])
        omitted_count = sum(
            1 for item in data.get("unit_treatments", []) or []
            if isinstance(item, dict) and item.get("disposition") == "omit"
        )
        print(f"wrote graphic plot version: {beat_count} beats")
        print(f"omitted source units: {omitted_count}")
        print(f"json: {out_dir / 'plot_version.json'}")
        print(f"markdown: {out_dir / 'plot_version.md'}")
        return 0

    if args.storyboard_from_plot:
        plot_path = args.storyboard_from_plot
        if not plot_path.is_absolute():
            plot_path = Path.cwd() / plot_path
        plot_version = json.loads(plot_path.read_text(encoding="utf-8"))
        _validate_graphic_plot_version(plot_version, source_units)
        expected_beat_ids = [
            str(beat.get("beat_id", "")).strip()
            for beat in plot_version.get("graphic_beats", []) or []
            if isinstance(beat, dict) and str(beat.get("beat_id", "")).strip()
        ]
        if not expected_beat_ids:
            raise ValueError(f"no graphic beats found in {plot_path}")
        rendered = prompt.render(
            title=book.metadata.get("title", args.book_id),
            author=book.metadata.get("author", ""),
            pages=args.pages,
            panels_per_page=args.panels_per_page,
            plot_version_json=json.dumps(
                plot_version, indent=2, ensure_ascii=False
            ),
        )
        (out_dir / "storyboard_from_plot_prompt.md").write_text(
            rendered, encoding="utf-8"
        )

        if args.dry_run:
            print(
                "wrote storyboard-from-plot dry-run prompt to "
                f"{out_dir / 'storyboard_from_plot_prompt.md'}"
            )
            return 0

        data = _complete_json_with_retry(
            rendered=rendered,
            model=model,
            system=prompt.system,
            max_tokens=max_output_tokens,
            work_dir=book.work_dir,
            stage=f"graphic_storyboard_from_plot:{args.book_id}:{args.name}",
            raw_path=out_dir / "storyboard_from_plot_raw_response.txt",
        )
        _normalize_panel_numbers(data)
        _validate_storyboard(data)
        _validate_storyboard_plot_coverage(data, expected_beat_ids)
        data, policy_report = apply_lettering_policy(data)
        data, slot_report = apply_lettering_slots(data)
        data, thumbnail_report = apply_thumbnail_layout(data)
        write_json(out_dir / "storyboard.json", data)
        write_json(out_dir / "lettering_policy_report.json", policy_report)
        write_json(out_dir / "lettering_slots_report.json", slot_report)
        write_json(out_dir / "thumbnail_layout_report.json", thumbnail_report)
        _write_page_image_prompts(data, out_dir)
        markdown = _markdown_storyboard(
            data, book_id=args.book_id, source_path=source_path,
            excerpt_words=(start_word, end_word)
        )
        (out_dir / "storyboard.md").write_text(markdown, encoding="utf-8")
        (out_dir / "lettering_script.md").write_text(
            _markdown_lettering_script(data), encoding="utf-8"
        )

        page_count = len(data.get("pages", []))
        panel_count = sum(
            len(p.get("panels", []) or [])
            for p in data.get("pages", []) if isinstance(p, dict)
        )
        print(f"wrote storyboard from plot: {page_count} pages / {panel_count} panels")
        print(f"json: {out_dir / 'storyboard.json'}")
        print(f"markdown: {out_dir / 'storyboard.md'}")
        print(f"lettering: {out_dir / 'lettering_script.md'}")
        print(f"image prompts: {out_dir / 'image_prompts'}")
        return 0

    if args.page_by_page:
        return _run_page_by_page(
            book_id=args.book_id,
            title=book.metadata.get("title", args.book_id),
            author=book.metadata.get("author", ""),
            book_work_dir=book.work_dir,
            out_dir=out_dir,
            source_path=source_path,
            source_units=source_units,
            excerpt_words=(start_word, end_word),
            pages=args.pages,
            panels_per_page=args.panels_per_page,
            model=model,
            max_tokens=max_output_tokens,
            dry_run=args.dry_run,
        )

    rendered = prompt.render(
        title=book.metadata.get("title", args.book_id),
        author=book.metadata.get("author", ""),
        excerpt=excerpt,
        source_units=source_units,
        start_word=start_word,
        end_word=end_word,
        pages=args.pages,
        panels_per_page=args.panels_per_page,
    )
    (out_dir / "prompt.md").write_text(rendered, encoding="utf-8")

    if args.dry_run:
        print(f"wrote dry-run prompt to {out_dir / 'prompt.md'}")
        return 0

    resp = complete(
        prompt=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_output_tokens,
        temperature=prompt.config.get("temperature"),
        work_dir=book.work_dir,
        stage=f"graphic_storyboard:{args.book_id}:{args.name}",
    )
    (out_dir / "raw_response.txt").write_text(resp.text, encoding="utf-8")

    data = parse_llm_json(resp.text)
    _normalize_source_references(data, source_units)
    _validate_storyboard(data)
    data, policy_report = apply_lettering_policy(data)
    data, slot_report = apply_lettering_slots(data)
    data, thumbnail_report = apply_thumbnail_layout(data)
    write_json(out_dir / "storyboard.json", data)
    write_json(out_dir / "lettering_policy_report.json", policy_report)
    write_json(out_dir / "lettering_slots_report.json", slot_report)
    write_json(out_dir / "thumbnail_layout_report.json", thumbnail_report)
    _write_page_image_prompts(data, out_dir)
    markdown = _markdown_storyboard(
        data, book_id=args.book_id, source_path=source_path,
        excerpt_words=(start_word, end_word)
    )
    (out_dir / "storyboard.md").write_text(markdown, encoding="utf-8")

    page_count = len(data.get("pages", []))
    panel_count = sum(len(p.get("panels", []) or []) for p in data.get("pages", [])
                      if isinstance(p, dict))
    print(f"wrote {page_count} pages / {panel_count} panels")
    print(f"json: {out_dir / 'storyboard.json'}")
    print(f"markdown: {out_dir / 'storyboard.md'}")
    print(f"image prompts: {out_dir / 'image_prompts'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
