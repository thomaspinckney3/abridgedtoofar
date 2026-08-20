"""Add source-backed speech/thought balloons to a page storyboard.

Usage:
  python -m scripts.graphic_dialogue_draft \
      work/mobydick/graphic_novel/action_spine_v3/reserved_zone_redraft_chapters_003_004 \
      --book-id mobydick \
      --chapter-source 3=work/mobydick/chapters/006.md \
      --chapter-source 4=work/mobydick/chapters/007.md \
      --frame-storyboard 3=work/mobydick/graphic_novel/action_spine_v3/chapter_003/storyboard.sequence.json \
      --frame-storyboard 4=work/mobydick/graphic_novel/action_spine_v3/chapter_004/storyboard.json

The stage preserves page/panel structure and writes a new storyboard JSON with
panel["texts"] augmented by source-supported speech and thought items.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, write_json
from forage.json_parse import parse_llm_json
from forage.llm import complete
from forage.prompts import load_prompt
from forage.graphic.geometry import DEFAULT_PANEL_FIGURES


VALID_KINDS = {"caption", "speech", "thought"}
VALID_ZONES = {
    "top_left",
    "top_center",
    "top_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
}

INDIRECT_SPEECH_RE = re.compile(
    r"\b(?:i|he|she|they|we)\s+"
    r"(?:told|asked|begged|entreated|requested|informed|answered|replied|said)\s+"
    r"(?:him|her|them|me|us|[a-z][a-z'’-]*)\s+"
    r"(?:that|whether|if|to)\b",
    re.IGNORECASE,
)
INTERNAL_NARRATION_RE = re.compile(
    r"\b(?:i|we)\s+"
    r"(?:thought|felt|wondered|supposed|concluded|resolved|decided|remembered|"
    r"knew|found|saw|looked|never\s+liked)\b",
    re.IGNORECASE,
)
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


def _parse_mapping(raw_items: list[str], *, label: str) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for raw in raw_items:
        key, sep, value = raw.partition("=")
        if not sep:
            raise ValueError(f"{label} must be CHAPTER=PATH, got {raw!r}")
        chapter = int(key)
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(f"{label} path does not exist: {path}")
        result[chapter] = path
    return result


def _load_frame_context(paths: dict[int, Path]) -> dict[int, dict[int, dict[str, Any]]]:
    by_chapter: dict[int, dict[int, dict[str, Any]]] = {}
    for chapter, path in paths.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        frames = data.get("frames") or []
        by_chapter[chapter] = {
            int(frame.get("frame_number") or 0): frame
            for frame in frames
            if isinstance(frame, dict) and int(frame.get("frame_number") or 0)
        }
    return by_chapter


def _chapter_sources(paths: dict[int, Path]) -> list[dict[str, Any]]:
    sources = []
    for chapter in sorted(paths):
        path = paths[chapter]
        sources.append({
            "chapter_number": chapter,
            "path": str(path),
            "text": path.read_text(encoding="utf-8"),
        })
    return sources


def _panel_context(
    storyboard: dict[str, Any],
    frame_context: dict[int, dict[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    for page in storyboard.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_number = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            chapter = int(panel.get("source_chapter") or 0)
            frame_number = int(panel.get("source_frame_number") or 0)
            frame = frame_context.get(chapter, {}).get(frame_number, {})
            panels.append({
                "page_number": page_number,
                "panel_number": int(panel.get("panel_number") or 0),
                "source_chapter": chapter or None,
                "source_frame_number": frame_number or None,
                "source_expanded_sequence": panel.get("source_expanded_sequence"),
                "current_texts": panel.get("texts") or [],
                "caption": _caption_from_texts(panel.get("texts") or []),
                "frame_caption": frame.get("caption"),
                "driver_character": frame.get("driver_character"),
                "primary_action": frame.get("primary_action"),
                "source_evidence": frame.get("source_evidence"),
                "visible_content": frame.get("visible_content"),
            })
    return panels


def _caption_from_texts(texts: list[Any]) -> str:
    for item in texts:
        if isinstance(item, dict) and str(item.get("kind") or "").lower() == "caption":
            return str(item.get("text") or "")
    return ""


def _panel_identity(panel: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_chapter": panel.get("source_chapter"),
        "source_frame_number": panel.get("source_frame_number"),
        "source_expanded_sequence": panel.get("source_expanded_sequence"),
        "image": panel.get("image"),
        "box": panel.get("box"),
        "fit_mode": panel.get("fit_mode"),
    }


def _validate_and_merge(
    original: dict[str, Any],
    drafted: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    original_pages = original.get("pages")
    drafted_pages = drafted.get("pages")
    if not isinstance(original_pages, list) or not isinstance(drafted_pages, list):
        raise ValueError("both original and drafted JSON must contain pages arrays")

    merged = deepcopy(original)
    summary = {
        "page_count": len(original_pages),
        "panel_count": 0,
        "speech_count": 0,
        "thought_count": 0,
        "caption_count": 0,
        "zone_adjustments": [],
        "updated_panels": [],
    }

    original_index: dict[int, tuple[int, dict[str, Any], dict[int, tuple[int, dict[str, Any]]]]] = {}
    for page_index, original_page in enumerate(original_pages):
        if not isinstance(original_page, dict):
            raise ValueError("pages must be objects")
        page_number = int(original_page.get("page_number") or 0)
        panel_index: dict[int, tuple[int, dict[str, Any]]] = {}
        panels = original_page.get("panels") or []
        if not isinstance(panels, list):
            raise ValueError(f"page {page_number} panels must be an array")
        for panel_i, original_panel in enumerate(panels):
            if not isinstance(original_panel, dict):
                raise ValueError(f"page {page_number} panels must be objects")
            panel_number = int(original_panel.get("panel_number") or 0)
            panel_index[panel_number] = (panel_i, original_panel)
            summary["panel_count"] += 1
            counts = _count_texts(
                _clean_texts(
                    original_panel.get("texts") or [],
                    page_number=page_number,
                    panel_number=panel_number,
                )
            )
            summary["caption_count"] += counts["caption"]
            summary["speech_count"] += counts["speech"]
            summary["thought_count"] += counts["thought"]
        original_index[page_number] = (page_index, original_page, panel_index)

    for drafted_page in drafted_pages:
        if not isinstance(drafted_page, dict):
            raise ValueError("drafted pages must be objects")
        page_number = int(drafted_page.get("page_number") or 0)
        if page_number not in original_index:
            raise ValueError(f"unknown drafted page number: {page_number}")
        page_index, _original_page, panel_index = original_index[page_number]
        drafted_panels = drafted_page.get("panels")
        if not isinstance(drafted_panels, list):
            raise ValueError(f"drafted page {page_number} panels must be an array")

        for drafted_panel in drafted_panels:
            if not isinstance(drafted_panel, dict):
                raise ValueError(f"drafted page {page_number} panels must be objects")
            panel_number = int(drafted_panel.get("panel_number") or 0)
            if panel_number not in panel_index:
                raise ValueError(
                    f"unknown drafted panel: page {page_number} panel {panel_number}"
                )
            panel_i, original_panel = panel_index[panel_number]
            _validate_identity_if_present(
                original_panel,
                drafted_panel,
                page_number=page_number,
                panel_number=panel_number,
                enforce_role_purity=False,
            )
            texts = _clean_texts(
                drafted_panel.get("texts"),
                page_number=page_number,
                panel_number=panel_number,
                enforce_role_purity=True,
            )
            old_texts = _clean_texts(
                original_panel.get("texts") or [],
                page_number=page_number,
                panel_number=panel_number,
                enforce_role_purity=False,
            )
            if texts == old_texts:
                continue
            merged["pages"][page_index]["panels"][panel_i]["texts"] = texts
            old_counts = _count_texts(old_texts)
            new_counts = _count_texts(texts)
            for kind in ("caption", "speech", "thought"):
                summary[f"{kind}_count"] += new_counts[kind] - old_counts[kind]
            summary["updated_panels"].append({
                "page_number": page_number,
                "panel_number": panel_number,
                "counts": new_counts,
            })

    summary["zone_adjustments"] = _avoid_caption_balloon_band_collisions(merged)
    return merged, summary


def _validate_identity_if_present(
    original_panel: dict[str, Any],
    drafted_panel: dict[str, Any],
    *,
    page_number: int,
    panel_number: int,
    enforce_role_purity: bool = False,
) -> None:
    for key, original_value in _panel_identity(original_panel).items():
        if key not in drafted_panel:
            continue
        if drafted_panel.get(key) != original_value:
            raise ValueError(
                f"non-lettering field {key!r} changed on page {page_number} "
                f"panel {panel_number}"
            )


def _avoid_caption_balloon_band_collisions(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    adjustments: list[dict[str, Any]] = []
    for page in storyboard.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_number = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            panel_number = int(panel.get("panel_number") or 0)
            texts = panel.get("texts") or []
            if not isinstance(texts, list):
                continue
            balloon_bands = {
                _zone_band(item.get("balloon_zone"))
                for item in texts
                if isinstance(item, dict)
                and str(item.get("kind") or "").strip().lower() in {"speech", "thought"}
            }
            balloon_bands.discard("")
            if not balloon_bands:
                continue
            for item in texts:
                if not isinstance(item, dict):
                    continue
                if str(item.get("kind") or "").strip().lower() != "caption":
                    continue
                old_zone = _normal_zone(item.get("caption_zone") or "top_left")
                old_band = _zone_band(old_zone)
                if old_band not in balloon_bands:
                    continue
                opposite = "bottom" if old_band == "top" else "top"
                if opposite in balloon_bands:
                    continue
                horizontal = old_zone.rsplit("_", 1)[-1]
                new_zone = f"{opposite}_{horizontal}"
                if new_zone not in VALID_ZONES:
                    new_zone = f"{opposite}_center"
                item["caption_zone"] = new_zone
                adjustments.append({
                    "page_number": page_number,
                    "panel_number": panel_number,
                    "old_caption_zone": old_zone,
                    "new_caption_zone": new_zone,
                    "reason": "moved caption away from speech/thought band",
                })
    return adjustments


def _zone_band(raw: Any) -> str:
    zone = str(raw or "").strip().lower().replace("-", "_")
    if "_" not in zone:
        return ""
    return zone.split("_", 1)[0]


def _clean_texts(
    raw_texts: Any,
    *,
    page_number: int,
    panel_number: int,
    enforce_role_purity: bool = False,
    max_balloons: int = DEFAULT_PANEL_FIGURES,
) -> list[dict[str, Any]]:
    if not isinstance(raw_texts, list):
        raise ValueError(f"page {page_number} panel {panel_number} texts must be an array")
    cleaned: list[dict[str, Any]] = []
    for raw in raw_texts:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in VALID_KINDS:
            raise ValueError(
                f"page {page_number} panel {panel_number} invalid text kind {kind!r}"
            )
        item: dict[str, Any] = {"kind": kind, "text": text}
        if kind == "caption":
            if enforce_role_purity and DIRECT_SPEECH_IN_CAPTION_RE.search(text):
                raise ValueError(
                    f"page {page_number} panel {panel_number} caption contains "
                    f"quoted spoken dialogue instead of a speech item: {text!r}"
                )
            if enforce_role_purity and EXPLICIT_THOUGHT_IN_CAPTION_RE.search(text):
                raise ValueError(
                    f"page {page_number} panel {panel_number} caption contains "
                    f"explicit internal monologue instead of a thought item: {text!r}"
                )
            zone = _normal_zone(raw.get("caption_zone") or "top_left")
            item["caption_zone"] = zone
            if raw.get("lettering_notes"):
                item["lettering_notes"] = str(raw["lettering_notes"])
        else:
            if kind == "speech" and _should_demote_speech(raw):
                zone = _normal_zone(raw.get("caption_zone") or _caption_zone_from_balloon(raw.get("balloon_zone")))
                item = {
                    "kind": "caption",
                    "text": text,
                    "caption_zone": zone,
                    "lettering_notes": "demoted from speech: indirect or internal narration",
                }
                cleaned.append(item)
                continue
            speaker = str(raw.get("speaker") or "").strip()
            if not speaker:
                raise ValueError(
                    f"page {page_number} panel {panel_number} {kind} missing speaker"
                )
            item["speaker"] = speaker
            item["balloon_zone"] = _normal_zone(raw.get("balloon_zone") or "top_center")
            if raw.get("speaker_region"):
                item["speaker_region"] = str(raw.get("speaker_region"))
            if raw.get("speaker_visual_hint"):
                item["speaker_visual_hint"] = str(raw.get("speaker_visual_hint"))
            evidence = str(raw.get("source_evidence") or "").strip()
            if evidence:
                item["source_evidence"] = evidence
            # A line already split across linked balloons keeps its part markers,
            # so rerunning the lettering stage neither loses the linkage nor
            # re-pins both halves to one zone.
            part = raw.get("balloon_part")
            parts = raw.get("balloon_parts")
            if isinstance(part, int) and isinstance(parts, int) and 1 <= part <= parts:
                item["balloon_part"] = part
                item["balloon_parts"] = parts
                item.pop("balloon_zone", None)
        cleaned.append(item)
    return _limit_balloon_items(
        _merge_caption_items(cleaned), max_balloons=max_balloons
    )


def _should_demote_speech(raw: dict[str, Any]) -> bool:
    evidence = str(raw.get("source_evidence") or "").strip()
    text = str(raw.get("text") or "").strip()
    haystack = f"{evidence} {text}"
    if INDIRECT_SPEECH_RE.search(haystack):
        return True
    if INTERNAL_NARRATION_RE.search(evidence):
        return True
    return False


def _caption_zone_from_balloon(raw: Any) -> str:
    zone = str(raw or "").strip().lower().replace("-", "_")
    if zone not in VALID_ZONES:
        return "bottom_center"
    return zone


def _merge_caption_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captions = [item for item in items if item.get("kind") == "caption"]
    if len(captions) <= 1:
        return items

    first_caption = captions[0]
    pieces: list[str] = []
    notes: list[str] = []
    for item in captions:
        text = str(item.get("text") or "").strip()
        if text:
            pieces.append(text)
        note = str(item.get("lettering_notes") or "").strip()
        if note:
            notes.append(note)
    first_caption["text"] = " ".join(pieces)
    if notes:
        first_caption["lettering_notes"] = "; ".join(dict.fromkeys(notes))

    merged: list[dict[str, Any]] = []
    caption_written = False
    for item in items:
        if item.get("kind") == "caption":
            if not caption_written:
                merged.append(first_caption)
                caption_written = True
            continue
        merged.append(item)
    return merged


def _limit_balloon_items(
    items: list[dict[str, Any]], *, max_balloons: int = DEFAULT_PANEL_FIGURES
) -> list[dict[str, Any]]:
    balloon_count = 0
    overflow_captions: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for item in items:
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in {"speech", "thought"}:
            kept.append(item)
            continue
        if balloon_count < max_balloons:
            kept.append(item)
            balloon_count += 1
            continue
        overflow_captions.append({
            "kind": "caption",
            "text": _caption_text_from_balloon(item),
            "caption_zone": "top_center",
            "lettering_notes": f"demoted from {kind}: panel exceeded {max_balloons} balloons",
        })
    if not overflow_captions:
        return kept
    return _merge_caption_items([*kept, *overflow_captions])


def _caption_text_from_balloon(item: dict[str, Any]) -> str:
    text = str(item.get("text") or "").strip()
    speaker = str(item.get("speaker") or "").strip()
    kind = str(item.get("kind") or "").strip().lower()
    if not speaker:
        return text
    if kind == "thought":
        return f"{speaker} thought: {text}"
    return f'{speaker} said, "{text}"'


def _normal_zone(raw: Any) -> str:
    zone = str(raw or "").strip().lower().replace("-", "_")
    if zone not in VALID_ZONES:
        raise ValueError(f"invalid lettering zone {zone!r}")
    return zone


def _count_texts(texts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"caption": 0, "speech": 0, "thought": 0}
    for item in texts:
        kind = str(item.get("kind") or "")
        if kind in counts:
            counts[kind] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--book-id", required=True)
    parser.add_argument(
        "--storyboard-json",
        type=Path,
        help="Storyboard to augment; defaults to run_dir/storyboard.json.",
    )
    parser.add_argument("--chapter-source", action="append", default=[], metavar="N=PATH")
    parser.add_argument("--frame-storyboard", action="append", default=[], metavar="N=PATH")
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument(
        "--raw-response",
        type=Path,
        help="Parse and merge an existing raw LLM response instead of calling the model.",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    run_dir = args.run_dir
    storyboard_path = args.storyboard_json or run_dir / "storyboard.json"
    original = json.loads(storyboard_path.read_text(encoding="utf-8"))
    chapter_paths = _parse_mapping(args.chapter_source, label="--chapter-source")
    frame_paths = _parse_mapping(args.frame_storyboard, label="--frame-storyboard")
    frame_context = _load_frame_context(frame_paths)
    panel_context = _panel_context(original, frame_context)
    chapter_sources = _chapter_sources(chapter_paths)

    book = load_book(args.book_id)
    prompt = load_prompt("graphic_dialogue_draft")
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_tokens = args.max_output_tokens or int(prompt.config.get("max_tokens", 16000))
    rendered = prompt.render(
        title=book.metadata.get("title", args.book_id),
        author=book.metadata.get("author", ""),
        chapter_sources_json=json.dumps(chapter_sources, indent=2, ensure_ascii=False),
        panel_context_json=json.dumps(panel_context, indent=2, ensure_ascii=False),
        storyboard_json=json.dumps(original, indent=2, ensure_ascii=False),
    )

    prompt_path = run_dir / "dialogue_draft_prompt.md"
    prompt_path.write_text(rendered, encoding="utf-8")
    if args.dry_run:
        print(f"wrote dry-run prompt to {prompt_path}")
        return 0

    if args.raw_response:
        raw_path = args.raw_response
        raw_text = raw_path.read_text(encoding="utf-8")
        response_model = model
        stop_reason = "raw_response"
    else:
        resp = complete(
            prompt=rendered,
            model=model,
            system=prompt.system,
            max_tokens=max_tokens,
            temperature=prompt.config.get("temperature"),
            work_dir=book.work_dir,
            stage=f"graphic_dialogue_draft:{args.book_id}:{run_dir.name}",
        )
        raw_path = run_dir / "dialogue_draft_raw_response.txt"
        raw_path.write_text(resp.text, encoding="utf-8")
        raw_text = resp.text
        response_model = resp.model
        stop_reason = resp.stop_reason
    data = parse_llm_json(raw_text)
    merged, summary = _validate_and_merge(original, data)

    out_json = args.out_json or run_dir / "storyboard_dialogue.json"
    out_report = args.out_report or run_dir / "dialogue_draft_report.json"
    write_json(out_json, merged)
    report = {
        "source_storyboard": str(storyboard_path),
        "output_storyboard": str(out_json),
        "raw_response": str(raw_path),
        "prompt": str(prompt_path),
        "model": response_model,
        "stop_reason": stop_reason,
        "notes": data.get("notes") or [],
        **summary,
    }
    write_json(out_report, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
