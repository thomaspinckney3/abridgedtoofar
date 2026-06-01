"""Generate chapter action-spine graphic-novel storyboards.

This is the automated version of the manual workflow:

1. Read one or more canonical chapter files from work/<book>/chapters.
2. Ask an LLM for a short action-oriented synopsis.
3. Ask for one first-person caption sentence per frame.
4. Write frame-level, source-grounded image prompts for later generation.

Example:
  python -m scripts.graphic_action_spine mobydick --chapter-numbers 1-4
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, write_json
from forage.prompts import load_prompt

from scripts.graphic_novel_experiment import (
    _complete_json_with_retry,
    _parse_chapter_numbers,
)
from scripts.graphic_sequence_coherence import run_sequence_coherence_on_data


CAPTION_ZONES = {
    "top_left",
    "top_center",
    "top_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
}

FIRST_PERSON_RE = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.I)
COMPARISON_RISK_RE = re.compile(
    r"\b(?:like|as if|as though|for all the world|looked like)\b",
    re.I,
)
BARE_TOMAHAWK_OBJECT_RE = re.compile(r"\btomahawk\b(?![- ](?:pipe|shaped))", re.I)
TOMAHAWK_PIPE_RE = re.compile(r"\btomahawk[-_ ]pipe\b", re.I)
GENERIC_PEOPLE_RE = re.compile(
    r"\b(?:crowd|crew|passersby|townspeople|sailors|men|women|children|"
    r"people|onlookers|workers|patrons|guests)\b",
    re.I,
)


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _continuity_entry_text(name: str, entry: Any) -> str:
    if isinstance(entry, dict):
        role = str(entry.get("role", "")).strip()
        description = str(entry.get("visual_description", "")).strip()
        if role and description:
            return f"{name} ({role}): {description}"
        if description:
            return f"{name}: {description}"
    text = str(entry).strip()
    return f"{name}: {text}" if text else ""


def _prop_entry_text(name: str, entry: Any) -> str:
    if isinstance(entry, dict):
        description = str(entry.get("visual_description", "")).strip()
        avoid = str(entry.get("avoid_confusion", "")).strip()
        pieces = [part for part in (description, f"Avoid confusion: {avoid}" if avoid else "") if part]
        if pieces:
            return f"{name}: {' '.join(pieces)}"
    text = str(entry).strip()
    return f"{name}: {text}" if text else ""


def _matches_continuity_key(label: str, key: str) -> bool:
    label_n = _normalize_label(label)
    key_n = _normalize_label(key)
    if not label_n or not key_n:
        return False
    return label_n == key_n or label_n in key_n or key_n in label_n


def _split_summary_sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", text.strip())
        if part.strip()
    ]


def _chapter_metadata(book: Any, chapter_number: str) -> dict[str, Any]:
    chapters_path = book.work_dir / "chapters.json"
    metadata = json.loads(chapters_path.read_text(encoding="utf-8"))
    for chapter in metadata.get("chapters", []):
        if (
            isinstance(chapter, dict)
            and chapter.get("kind") == "chapter"
            and str(chapter.get("number")) == str(chapter_number)
        ):
            return chapter
    raise ValueError(f"chapter {chapter_number} not found in {chapters_path}")


def _chapter_text(book: Any, chapter: dict[str, Any]) -> str:
    chapter_id = str(chapter["id"])
    path = book.work_dir / "chapters" / f"{chapter_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"missing chapter text: {path}")
    heading = str(chapter.get("raw_heading") or chapter.get("title") or "").strip()
    body = path.read_text(encoding="utf-8").strip()
    return f"{heading}\n\n{body}" if heading else body


def _validate_action_spine(
    data: dict[str, Any],
    *,
    min_frames: int,
    max_frames: int,
) -> None:
    synopsis = str(data.get("action_oriented_synopsis", "")).strip()
    if len(synopsis.split()) < 20:
        raise ValueError("action_oriented_synopsis is missing or too short")
    synopsis_sentences = _split_summary_sentences(synopsis)
    if not synopsis_sentences:
        raise ValueError("action_oriented_synopsis must contain sentences")

    character_continuity = data.get("character_continuity")
    if not isinstance(character_continuity, dict) or not character_continuity:
        raise ValueError("character_continuity must be a non-empty object")
    for name, entry in character_continuity.items():
        if not str(name).strip():
            raise ValueError("character_continuity contains an empty key")
        if isinstance(entry, dict):
            if len(str(entry.get("visual_description", "")).split()) < 5:
                raise ValueError(
                    f"character_continuity[{name!r}] missing visual_description"
                )
        elif len(str(entry).split()) < 5:
            raise ValueError(
                f"character_continuity[{name!r}] must describe stable visuals"
            )

    prop_continuity = data.get("prop_continuity")
    if not isinstance(prop_continuity, dict):
        raise ValueError("prop_continuity must be an object, even if empty")
    for name, entry in prop_continuity.items():
        if not str(name).strip():
            raise ValueError("prop_continuity contains an empty key")
        if isinstance(entry, dict):
            if len(str(entry.get("visual_description", "")).split()) < 3:
                raise ValueError(
                    f"prop_continuity[{name!r}] missing visual_description"
                )
        elif len(str(entry).split()) < 3:
            raise ValueError(
                f"prop_continuity[{name!r}] must describe stable visuals"
            )

    spine = data.get("caption_spine")
    if not isinstance(spine, list) or not spine:
        raise ValueError("caption_spine must be a non-empty array")
    captions = [str(item).strip() for item in spine]
    if any(not item for item in captions):
        raise ValueError("caption_spine contains an empty caption")

    steps = data.get("action_steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("action_steps must be a non-empty array")
    if len(steps) != len(captions):
        raise ValueError(
            f"action_steps has {len(steps)} items but caption_spine has "
            f"{len(captions)}"
        )
    if len(synopsis_sentences) != len(steps):
        raise ValueError(
            "action_oriented_synopsis must contain exactly one sentence per "
            f"action_step: {len(synopsis_sentences)} sentences vs "
            f"{len(steps)} steps"
        )
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError("each action_step must be an object")
        if int(step.get("step_number") or 0) != index:
            raise ValueError(f"step_number must be sequential at step {index}")
        plain = str(step.get("plain_sentence", "")).strip()
        caption = str(step.get("first_person_caption", "")).strip()
        if len(plain.split()) < 5:
            raise ValueError(f"action step {index} plain_sentence is too short")
        if caption != captions[index - 1]:
            raise ValueError(
                f"action step {index} caption does not match caption_spine"
            )

    frames = data.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("frames must be a non-empty array")
    if not (min_frames <= len(frames) <= max_frames):
        raise ValueError(
            f"expected {min_frames}-{max_frames} frames, got {len(frames)}"
        )
    if len(frames) != len(captions):
        raise ValueError(
            f"caption_spine has {len(captions)} items but frames has {len(frames)}"
        )

    for index, frame in enumerate(frames, 1):
        if not isinstance(frame, dict):
            raise ValueError("each frame must be an object")
        if int(frame.get("frame_number") or 0) != index:
            raise ValueError(f"frame_number must be sequential at frame {index}")
        caption = str(frame.get("caption", "")).strip()
        if caption != captions[index - 1]:
            raise ValueError(
                f"frame {index} caption does not match caption_spine"
            )
        if not FIRST_PERSON_RE.search(caption):
            raise ValueError(f"frame {index} caption is not first-person: {caption!r}")
        driver = str(frame.get("driver_character", "")).strip()
        if not driver:
            raise ValueError(f"frame {index} missing driver_character")
        action = str(frame.get("primary_action", "")).strip()
        if len(action.split()) < 4:
            raise ValueError(f"frame {index} primary_action is missing or too short")
        zone = str(frame.get("caption_zone", "")).strip()
        if zone not in CAPTION_ZONES:
            raise ValueError(f"frame {index} invalid caption_zone {zone!r}")
        evidence = frame.get("source_evidence")
        if not isinstance(evidence, list) or not any(
            str(item).strip() for item in evidence
        ):
            raise ValueError(f"frame {index} missing source_evidence")
        visible = frame.get("visible_content")
        if not isinstance(visible, dict):
            raise ValueError(f"frame {index} missing visible_content")
        people = _string_list(visible.get("people"))
        if people and not any(
            _matches_continuity_key(person, driver)
            or _matches_continuity_key(driver, person)
            for person in people
        ):
            raise ValueError(
                f"frame {index} driver_character {driver!r} is not listed in "
                "visible_content.people"
            )
        continuity_keys = list(character_continuity.keys())
        for person in people:
            if GENERIC_PEOPLE_RE.search(person):
                continue
            if not any(_matches_continuity_key(person, key) for key in continuity_keys):
                raise ValueError(
                    f"frame {index} visible person {person!r} has no "
                    "character_continuity entry"
                )
        supporting = frame.get("supporting_visuals")
        if not isinstance(supporting, list):
            raise ValueError(f"frame {index} supporting_visuals must be an array")
        do_not_show = frame.get("do_not_show")
        if not isinstance(do_not_show, list):
            raise ValueError(f"frame {index} do_not_show must be an array")
        if COMPARISON_RISK_RE.search(caption) and not _string_list(do_not_show):
            raise ValueError(
                f"frame {index} caption contains a comparison or simile, but "
                "do_not_show is empty"
            )
        prompt = str(frame.get("image_prompt", "")).strip()
        if len(prompt.split()) < 20:
            raise ValueError(f"frame {index} image_prompt missing or too short")
        if "no readable text" not in prompt.lower():
            raise ValueError(f"frame {index} image_prompt must ban readable text")
        if "caption" not in prompt.lower():
            raise ValueError(f"frame {index} image_prompt must reserve caption space")
        prop_text = json.dumps(prop_continuity, ensure_ascii=False)
        has_tomahawk_pipe = bool(TOMAHAWK_PIPE_RE.search(prop_text))
        if has_tomahawk_pipe:
            combined = " ".join([caption, action, prompt])
            if BARE_TOMAHAWK_OBJECT_RE.search(combined):
                raise ValueError(
                    f"frame {index} uses bare 'tomahawk' even though "
                    "prop_continuity defines a tomahawk-pipe"
                )


def _caption_zone_instruction(zone: str) -> str:
    rendered = zone.replace("_", "-") or "top-left"
    return f"Leave clean negative space in the {rendered} for the caption."


def _normalize_action_spine(data: dict[str, Any]) -> None:
    for frame in data.get("frames", []) or []:
        if not isinstance(frame, dict):
            continue
        prompt = str(frame.get("image_prompt", "")).strip()
        if not prompt:
            continue
        lower = prompt.lower()
        additions: list[str] = []
        if "no readable text" not in lower:
            additions.append("No readable text.")
        if "caption" not in lower:
            additions.append(
                _caption_zone_instruction(str(frame.get("caption_zone", "")).strip())
            )
        if additions:
            frame["image_prompt"] = f"{prompt} {' '.join(additions)}"


def _repair_prompt(original: str, invalid_data: dict[str, Any], error: Exception) -> str:
    return "\n\n".join([
        original,
        "VALIDATION FAILURE FROM PREVIOUS RESPONSE:",
        str(error),
        "Revise the full JSON response so it satisfies every schema and "
        "validation rule. Preserve the chapter order and action-spine intent, "
        "but fix all contract violations. Return strict JSON only.",
        "Previous invalid JSON:",
        json.dumps(invalid_data, indent=2, ensure_ascii=False),
    ])


def _complete_valid_action_spine(
    *,
    rendered: str,
    model: str,
    system: str | None,
    max_tokens: int,
    work_dir: Path,
    stage: str,
    raw_path: Path,
    min_frames: int,
    max_frames: int,
    max_validation_attempts: int,
) -> dict[str, Any]:
    """Complete, normalize, validate, and repair once validation feedback exists.

    `_complete_json_with_retry` handles empty/length/parser failures. This
    wrapper handles semantically valid JSON that violates the graphic action
    spine contract, such as a third-person caption or missing continuity entry.
    """
    last_error: Exception | None = None
    current_prompt = rendered
    for attempt in range(1, max_validation_attempts + 1):
        attempt_raw_path = raw_path if attempt == 1 else raw_path.with_name(
            f"{raw_path.stem}.repair{attempt}{raw_path.suffix}"
        )
        data = _complete_json_with_retry(
            rendered=current_prompt,
            model=model,
            system=system,
            max_tokens=max_tokens,
            work_dir=work_dir,
            stage=f"{stage}:contract{attempt}",
            raw_path=attempt_raw_path,
        )
        _normalize_action_spine(data)
        try:
            _validate_action_spine(data, min_frames=min_frames, max_frames=max_frames)
            return data
        except Exception as exc:
            last_error = exc
            invalid_path = raw_path.with_name(
                f"{raw_path.stem}.invalid{attempt}.json"
            )
            write_json(invalid_path, data)
            if attempt >= max_validation_attempts:
                break
            current_prompt = _repair_prompt(rendered, data, exc)

    if last_error is None:
        last_error = ValueError("no validation attempts were made")
    raise last_error


def _markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {data.get('title', 'Graphic Action Spine')}")
    lines.append("")
    source_chapter = str(data.get("source_chapter", "")).strip()
    if source_chapter:
        lines.append(f"Source chapter: {source_chapter}")
        lines.append("")
    principle = str(data.get("adaptation_principle", "")).strip()
    if principle:
        lines.append(f"Adaptation principle: {principle}")
        lines.append("")

    continuity = data.get("character_continuity") or {}
    if isinstance(continuity, dict) and continuity:
        lines.append("## Character Continuity")
        lines.append("")
        for name, entry in continuity.items():
            text = _continuity_entry_text(str(name), entry)
            if text:
                lines.append(f"- {text}")
        lines.append("")

    prop_continuity = data.get("prop_continuity") or {}
    if isinstance(prop_continuity, dict) and prop_continuity:
        lines.append("## Prop Continuity")
        lines.append("")
        for name, entry in prop_continuity.items():
            text = _prop_entry_text(str(name), entry)
            if text:
                lines.append(f"- {text}")
        lines.append("")

    synopsis = str(data.get("action_oriented_synopsis", "")).strip()
    if synopsis:
        lines.append("## Action-Oriented Synopsis")
        lines.append("")
        lines.append(synopsis)
        lines.append("")

    spine = data.get("caption_spine") or []
    if isinstance(spine, list) and spine:
        lines.append("## Caption Spine")
        lines.append("")
        for index, caption in enumerate(spine, 1):
            lines.append(f"{index}. {caption}")
        lines.append("")

    steps = data.get("action_steps") or []
    if isinstance(steps, list) and steps:
        lines.append("## Action Steps")
        lines.append("")
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_no = step.get("step_number", "?")
            plain = str(step.get("plain_sentence", "")).strip()
            caption = str(step.get("first_person_caption", "")).strip()
            if plain:
                lines.append(f"{step_no}. {plain}")
            if caption:
                lines.append(f"   Caption: {caption}")
        lines.append("")

    frames = data.get("frames") or []
    if isinstance(frames, list) and frames:
        lines.append("## Frames")
        lines.append("")
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            frame_no = frame.get("frame_number", "?")
            lines.append(f"### Frame {frame_no}")
            lines.append("")
            for key, label in (
                ("caption", "Caption"),
                ("driver_character", "Driver character"),
                ("primary_action", "Primary action"),
                ("shot", "Shot"),
                ("caption_zone", "Caption zone"),
                ("image_prompt", "Image prompt"),
                ("purpose", "Purpose"),
            ):
                value = str(frame.get(key, "")).strip()
                if value:
                    lines.append(f"{label}: {value}")
                    lines.append("")
            evidence = frame.get("source_evidence") or []
            if isinstance(evidence, list) and evidence:
                lines.append("Source evidence:")
                for item in evidence:
                    lines.append(f"- {item}")
                lines.append("")
            supporting = _string_list(frame.get("supporting_visuals"))
            if supporting:
                lines.append("Supporting visuals:")
                for item in supporting:
                    lines.append(f"- {item}")
                lines.append("")
            do_not_show = _string_list(frame.get("do_not_show"))
            if do_not_show:
                lines.append("Do not show:")
                for item in do_not_show:
                    lines.append(f"- {item}")
                lines.append("")

    omitted = data.get("omitted_material") or []
    if isinstance(omitted, list) and omitted:
        lines.append("## Omitted Material")
        lines.append("")
        for item in omitted:
            if not isinstance(item, dict):
                continue
            material = str(item.get("material", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if material or reason:
                lines.append(f"- **{material}:** {reason}")
        lines.append("")

    notes = data.get("visual_safety_notes") or []
    if isinstance(notes, list) and notes:
        lines.append("## Visual Safety Notes")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _visible_items(frame: dict[str, Any], key: str) -> list[str]:
    visible = frame.get("visible_content")
    if not isinstance(visible, dict):
        return []
    return _string_list(visible.get(key))


def _matched_character_continuity(
    frame: dict[str, Any],
    continuity: dict[str, Any],
) -> list[str]:
    people = _visible_items(frame, "people")
    lines: list[str] = []
    seen: set[str] = set()
    for person in people:
        for name, entry in continuity.items():
            if _matches_continuity_key(person, str(name)) and str(name) not in seen:
                text = _continuity_entry_text(str(name), entry)
                if text:
                    lines.append(text)
                    seen.add(str(name))
    return lines


def _matched_prop_continuity(
    frame: dict[str, Any],
    prop_continuity: dict[str, Any],
) -> list[str]:
    props = _visible_items(frame, "props")
    prompt = str(frame.get("image_prompt", "")).strip()
    searchable = " ".join(props + [prompt])
    lines: list[str] = []
    for name, entry in prop_continuity.items():
        if _matches_continuity_key(searchable, str(name)):
            text = _prop_entry_text(str(name), entry)
            if text:
                lines.append(text)
    return lines


def _frame_prompt(
    frame: dict[str, Any],
    *,
    data: dict[str, Any],
    chapter_label: str,
) -> str:
    prompt = str(frame.get("image_prompt", "")).strip()
    zone = str(frame.get("caption_zone", "")).strip()
    frame_no = int(frame.get("frame_number") or 0)
    character_lines = _matched_character_continuity(
        frame,
        data.get("character_continuity") if isinstance(data.get("character_continuity"), dict) else {},
    )
    prop_lines = _matched_prop_continuity(
        frame,
        data.get("prop_continuity") if isinstance(data.get("prop_continuity"), dict) else {},
    )
    do_not_show = _string_list(frame.get("do_not_show"))
    supporting = _string_list(frame.get("supporting_visuals"))
    driver = str(frame.get("driver_character", "")).strip().rstrip(".")
    action = str(frame.get("primary_action", "")).strip().rstrip(".")
    lines = [
        "Use case: illustration-story",
        "Asset type: single graphic novel frame, text-free source art for later lettering",
        f"Primary request: Generate Frame {frame_no} of {chapter_label}.",
        "Hard constraints: No readable text, no caption box, no speech balloons, "
        "no labels, no signs with letters, no watermark. Do not add unsupported "
        "narrative content.",
        "Continuity rule: keep recurring people and recurring props visually "
        "consistent with the continuity notes below.",
        "Literalization rule: do not draw similes, metaphors, idioms, jokes, "
        "memories, fears, or comparisons as literal scene content.",
        "Composition rule: make the primary frame action the visual focus; "
        "supporting details must stay secondary.",
        f"Driver character: {driver}.",
        f"Primary frame action: {action}.",
        f"Caption zone reserved for later lettering: {zone}.",
        "Style: muted ink-and-wash graphic novel illustration, crisp ink line "
        "with simplified anatomy, restrained source-grounded scenery.",
    ]
    if character_lines:
        lines.append("Character continuity: " + " | ".join(character_lines))
    if prop_lines:
        lines.append("Prop continuity: " + " | ".join(prop_lines))
    if supporting:
        lines.append("Secondary supporting visuals only: " + "; ".join(supporting))
    if do_not_show:
        lines.append("Do not show: " + "; ".join(do_not_show))
    lines.extend([
        f"Scene: {prompt}",
        "Lettering will be added later from the storyboard. Do not include "
        "caption text, speech balloons, labels, signs with letters, or any "
        "visible writing in the image.",
        "",
    ])
    return "\n".join(lines)


def _write_frame_prompts(data: dict[str, Any], out_dir: Path, chapter_label: str) -> None:
    prompt_dir = out_dir / "image_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for frame in data.get("frames", []):
        if not isinstance(frame, dict):
            continue
        frame_no = int(frame.get("frame_number") or 0)
        (prompt_dir / f"frame_{frame_no:03d}.txt").write_text(
            _frame_prompt(frame, data=data, chapter_label=chapter_label),
            encoding="utf-8",
        )


def _run_chapter(
    *,
    book: Any,
    book_id: str,
    chapter_number: str,
    name: str,
    min_frames: int,
    max_frames: int,
    model: str,
    max_output_tokens: int,
    max_validation_attempts: int,
    skip_sequence_coherence: bool,
    sequence_model: str | None,
    sequence_max_output_tokens: int | None,
    dry_run: bool,
) -> Path:
    chapter = _chapter_metadata(book, chapter_number)
    chapter_text = _chapter_text(book, chapter)
    chapter_title = str(chapter.get("title") or "").strip().rstrip(".")
    chapter_label = f"{book_id} chapter {chapter_number}: {chapter_title}"
    out_dir = (
        book.work_dir
        / "graphic_novel"
        / name
        / f"chapter_{int(chapter_number):03d}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "chapter.txt").write_text(chapter_text, encoding="utf-8")

    prompt = load_prompt("graphic_action_spine")
    rendered = prompt.render(
        title=book.metadata.get("title", book_id),
        author=book.metadata.get("author", ""),
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        min_frames=min_frames,
        max_frames=max_frames,
        chapter_text=chapter_text,
    )
    (out_dir / "prompt.md").write_text(rendered, encoding="utf-8")
    write_json(out_dir / "run.json", {
        "book_id": book_id,
        "chapter_number": chapter_number,
        "chapter_id": chapter.get("id"),
        "chapter_title": chapter_title,
        "name": name,
        "min_frames": min_frames,
        "max_frames": max_frames,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "max_validation_attempts": max_validation_attempts,
        "sequence_coherence": not skip_sequence_coherence,
        "sequence_model": sequence_model,
        "sequence_max_output_tokens": sequence_max_output_tokens,
        "dry_run": dry_run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })

    if dry_run:
        print(f"wrote dry-run prompt: {out_dir / 'prompt.md'}")
        return out_dir

    data = _complete_valid_action_spine(
        rendered=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_output_tokens,
        work_dir=book.work_dir,
        stage=f"graphic_action_spine:{book_id}:{name}:chapter_{chapter_number}",
        raw_path=out_dir / "raw_response.txt",
        min_frames=min_frames,
        max_frames=max_frames,
        max_validation_attempts=max_validation_attempts,
    )
    if not skip_sequence_coherence:
        write_json(out_dir / "storyboard.pre_sequence.json", data)
        data, sequence_report = run_sequence_coherence_on_data(
            data=data,
            chapter_text=chapter_text,
            title=str(book.metadata.get("title", book_id)),
            author=str(book.metadata.get("author", "")),
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            work_dir=book.work_dir,
            out_dir=out_dir,
            model=sequence_model,
            max_output_tokens=sequence_max_output_tokens,
        )
        _normalize_action_spine(data)
        _validate_action_spine(data, min_frames=min_frames, max_frames=max_frames)
        severe_count = 0
        if isinstance(sequence_report, dict):
            for finding in sequence_report.get("findings", []) or []:
                if (
                    isinstance(finding, dict)
                    and str(finding.get("severity", "")).lower()
                    in {"blocker", "major"}
                ):
                    severe_count += 1
        if severe_count:
            print(
                f"chapter {chapter_number}: sequence coherence repaired "
                f"{severe_count} major/blocker finding(s)"
            )
    write_json(out_dir / "storyboard.json", data)
    (out_dir / "storyboard.md").write_text(_markdown(data), encoding="utf-8")
    _write_frame_prompts(data, out_dir, chapter_label=chapter_label)
    print(
        f"chapter {chapter_number}: {len(data.get('frames', []) or [])} frames -> "
        f"{out_dir / 'storyboard.md'}"
    )
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book_id")
    parser.add_argument("--chapter-numbers", required=True)
    parser.add_argument("--name", default="action_spine")
    parser.add_argument("--min-frames", type=int, default=3)
    parser.add_argument("--max-frames", type=int, default=8)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--max-validation-attempts", type=int, default=3)
    parser.add_argument(
        "--skip-sequence-coherence",
        action="store_true",
        help="Skip the caption-sequence coherence repair stage.",
    )
    parser.add_argument(
        "--sequence-model",
        default=None,
        help="Model for caption-sequence coherence repair; defaults to prompt config.",
    )
    parser.add_argument(
        "--sequence-max-output-tokens",
        type=int,
        default=None,
        help="Output cap for caption-sequence coherence repair.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.min_frames <= 0:
        raise ValueError("--min-frames must be positive")
    if args.max_frames < args.min_frames:
        raise ValueError("--max-frames must be >= --min-frames")
    if args.max_validation_attempts <= 0:
        raise ValueError("--max-validation-attempts must be positive")

    prompt = load_prompt("graphic_action_spine")
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 18000))
    )
    book = load_book(args.book_id)
    chapter_numbers = _parse_chapter_numbers(args.chapter_numbers)
    for chapter_number in chapter_numbers:
        _run_chapter(
            book=book,
            book_id=args.book_id,
            chapter_number=chapter_number,
            name=args.name,
            min_frames=args.min_frames,
            max_frames=args.max_frames,
            model=model,
            max_output_tokens=max_output_tokens,
            max_validation_attempts=args.max_validation_attempts,
            skip_sequence_coherence=args.skip_sequence_coherence,
            sequence_model=args.sequence_model,
            sequence_max_output_tokens=args.sequence_max_output_tokens,
            dry_run=args.dry_run,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
