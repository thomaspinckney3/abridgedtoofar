"""Repair ordered graphic-novel captions for sequence coherence.

Usage:
  python -m scripts.graphic_sequence_coherence \
      work/mobydick/graphic_novel/action_spine_v3/chapter_003

This stage is intended to run after action-spine storyboard generation and
before image generation or deterministic lettering. It keeps frame count,
frame order, image prompts, and visual planning fixed, but lets a sequence
editor rewrite captions when the ordered caption spine drops setup/payoff,
uses dangling references, or compresses a joke/idiom past readability.
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
from forage.prompts import load_prompt

from scripts.graphic_novel_experiment import _complete_json_with_retry


FIRST_PERSON_RE = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.I)


def _storyboard_payload(data: dict[str, Any]) -> str:
    """Return only the parts the sequence critic needs."""

    payload = {
        "title": data.get("title"),
        "source_chapter": data.get("source_chapter"),
        "adaptation_principle": data.get("adaptation_principle"),
        "action_oriented_synopsis": data.get("action_oriented_synopsis"),
        "caption_spine": data.get("caption_spine"),
        "action_steps": data.get("action_steps"),
        "frames": [
            {
                "frame_number": frame.get("frame_number"),
                "caption": frame.get("caption"),
                "driver_character": frame.get("driver_character"),
                "primary_action": frame.get("primary_action"),
                "visible_content": frame.get("visible_content"),
                "purpose": frame.get("purpose"),
                "source_evidence": frame.get("source_evidence"),
            }
            for frame in data.get("frames", []) or []
            if isinstance(frame, dict)
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _validate_sequence_response(
    report: dict[str, Any],
    *,
    frame_count: int,
    require_first_person: bool,
) -> None:
    if not isinstance(report.get("valid"), bool):
        raise ValueError("sequence report missing boolean valid")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("sequence report missing findings array")
    spine = report.get("revised_caption_spine")
    if not isinstance(spine, list) or len(spine) != frame_count:
        raise ValueError(
            "sequence report revised_caption_spine must contain exactly "
            f"{frame_count} captions"
        )
    captions = [str(item).strip() for item in spine]
    if any(not caption for caption in captions):
        raise ValueError("sequence report contains an empty revised caption")
    if require_first_person:
        for index, caption in enumerate(captions, 1):
            if not FIRST_PERSON_RE.search(caption):
                raise ValueError(
                    f"revised caption {index} is not first-person: {caption!r}"
                )
    updates = report.get("frame_caption_updates")
    if not isinstance(updates, list):
        updates = []
    seen: set[int] = set()
    for update in updates:
        if not isinstance(update, dict):
            raise ValueError("sequence report contains non-object frame update")
        frame_no = int(update.get("frame_number") or 0)
        if frame_no < 1 or frame_no > frame_count:
            raise ValueError(f"sequence frame update out of range: {frame_no}")
        if frame_no in seen:
            raise ValueError(f"duplicate sequence frame update: {frame_no}")
        seen.add(frame_no)
        caption = str(update.get("caption", "")).strip()
        if caption != captions[frame_no - 1]:
            raise ValueError(
                f"frame {frame_no} update caption does not match revised spine"
            )
    report["frame_caption_updates"] = [
        {
            "frame_number": index,
            "caption": caption,
        }
        for index, caption in enumerate(captions, 1)
    ]


def apply_caption_sequence_report(
    data: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Return a storyboard copy with only caption fields updated."""

    updated = deepcopy(data)
    frames = [
        frame for frame in updated.get("frames", []) or [] if isinstance(frame, dict)
    ]
    captions = [str(item).strip() for item in report["revised_caption_spine"]]
    updated["caption_spine"] = captions

    for index, caption in enumerate(captions, 1):
        frame = frames[index - 1]
        frame["caption"] = caption
        steps = updated.get("action_steps")
        if isinstance(steps, list) and index <= len(steps) and isinstance(steps[index - 1], dict):
            steps[index - 1]["first_person_caption"] = caption

    updated["sequence_coherence"] = {
        "valid": bool(report.get("valid")),
        "findings": report.get("findings", []),
    }
    return updated


def run_sequence_coherence_on_data(
    *,
    data: dict[str, Any],
    chapter_text: str,
    title: str,
    author: str,
    chapter_number: str,
    chapter_title: str,
    work_dir: Path,
    out_dir: Path,
    model: str | None = None,
    max_output_tokens: int | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    frames = [
        frame for frame in data.get("frames", []) or [] if isinstance(frame, dict)
    ]
    if not frames:
        raise ValueError("storyboard has no frames")
    frame_count = len(frames)
    original_captions = [
        str(frame.get("caption", "")).strip()
        for frame in frames
    ]
    require_first_person = all(FIRST_PERSON_RE.search(caption) for caption in original_captions)

    prompt = load_prompt("graphic_sequence_coherence")
    model = model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 10000))
    )
    rendered = prompt.render(
        title=title,
        author=author,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        chapter_text=chapter_text,
        storyboard_json=_storyboard_payload(data),
    )
    (out_dir / "sequence_coherence_prompt.md").write_text(
        rendered,
        encoding="utf-8",
    )
    if dry_run:
        return data, None

    report = _complete_json_with_retry(
        rendered=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_output_tokens,
        work_dir=work_dir,
        stage=f"graphic_sequence_coherence:{out_dir.parent.name}:{out_dir.name}",
        raw_path=out_dir / "sequence_coherence_raw_response.txt",
    )
    _validate_sequence_response(
        report,
        frame_count=frame_count,
        require_first_person=require_first_person,
    )
    updated = apply_caption_sequence_report(data, report)
    write_json(out_dir / "sequence_coherence_report.json", report)
    return updated, report


def run_sequence_coherence(
    run_dir: Path,
    *,
    book_id: str | None = None,
    chapter_number: str | None = None,
    storyboard_path: Path | None = None,
    chapter_text_path: Path | None = None,
    out_storyboard_path: Path | None = None,
    model: str | None = None,
    max_output_tokens: int | None = None,
    dry_run: bool = False,
) -> Path:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    chapter_text_path = chapter_text_path or run_dir / "chapter.txt"
    out_storyboard_path = out_storyboard_path or run_dir / "storyboard.sequence.json"
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    chapter_text = chapter_text_path.read_text(encoding="utf-8")

    if book_id:
        book = load_book(book_id)
        title = str(book.metadata.get("title", book_id))
        author = str(book.metadata.get("author", ""))
    else:
        title = str(data.get("title") or "")
        author = ""
    chapter_number = chapter_number or str(data.get("source_chapter") or "")
    chapter_title = str(data.get("source_chapter") or "")

    updated, report = run_sequence_coherence_on_data(
        data=data,
        chapter_text=chapter_text,
        title=title,
        author=author,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        work_dir=run_dir,
        out_dir=run_dir,
        model=model,
        max_output_tokens=max_output_tokens,
        dry_run=dry_run,
    )
    if not dry_run:
        write_json(out_storyboard_path, updated)
    return out_storyboard_path if not dry_run else run_dir / "sequence_coherence_prompt.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--book-id")
    parser.add_argument("--chapter-number")
    parser.add_argument("--storyboard-json", type=Path)
    parser.add_argument("--chapter-text", type=Path)
    parser.add_argument("--out-storyboard", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    out_path = run_sequence_coherence(
        args.run_dir,
        book_id=args.book_id,
        chapter_number=args.chapter_number,
        storyboard_path=args.storyboard_json,
        chapter_text_path=args.chapter_text,
        out_storyboard_path=args.out_storyboard,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        dry_run=args.dry_run,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
