"""Rewrite graphic-novel storyboard lettering into a reproducible caption pass.

Usage:
  python -m scripts.graphic_caption_policy \
      work/gatsby/graphic_novel/opening_trial_v7_from_plot \
      --mode first-person

The stage preserves pages, panels, beats, character actions, and art prompts
except for adding caption-zone reservation text. It rewrites only caption,
dialogue, SFX, lettering notes, and caption zones, then writes a new storyboard
JSON and lettering script for deterministic rendering.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, write_json
from forage.prompts import load_prompt

from scripts.graphic_novel_experiment import (
    _complete_json_with_retry,
    _markdown_lettering_script,
    _markdown_storyboard,
    _normalize_panel_numbers,
    _write_page_image_prompts,
)


VALID_ZONES = {
    "top_left",
    "top_center",
    "top_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
}

FIRST_PERSON_RE = re.compile(
    r"\b(?:I|me|my|mine|myself|we|us|our|ours|ourselves)\b",
    re.IGNORECASE,
)


def _load_run_meta(run_dir: Path) -> dict[str, Any]:
    run_path = run_dir / "run.json"
    if not run_path.exists():
        raise FileNotFoundError(f"missing run metadata: {run_path}")
    return json.loads(run_path.read_text(encoding="utf-8"))


def _panel_key(panel: dict[str, Any]) -> tuple[Any, ...]:
    return (
        panel.get("panel_number"),
        tuple(str(x) for x in panel.get("graphic_beat_ids") or []),
        panel.get("driver_character"),
        panel.get("character_action"),
        panel.get("beat"),
        panel.get("shot"),
    )


def _validate_captioned_storyboard(
    original: dict[str, Any],
    captioned: dict[str, Any],
    *,
    require_first_person: bool,
    allow_dialogue: bool,
) -> None:
    _normalize_panel_numbers(captioned)
    original_pages = original.get("pages")
    captioned_pages = captioned.get("pages")
    if not isinstance(original_pages, list) or not isinstance(captioned_pages, list):
        raise ValueError("both original and captioned storyboards must contain pages")
    if len(original_pages) != len(captioned_pages):
        raise ValueError(
            f"page count changed: {len(original_pages)} -> {len(captioned_pages)}"
        )

    for original_page, captioned_page in zip(original_pages, captioned_pages, strict=True):
        if not isinstance(original_page, dict) or not isinstance(captioned_page, dict):
            raise ValueError("pages must be objects")
        if original_page.get("page_number") != captioned_page.get("page_number"):
            raise ValueError(
                "page number changed: "
                f"{original_page.get('page_number')} -> {captioned_page.get('page_number')}"
            )
        original_panels = original_page.get("panels")
        captioned_panels = captioned_page.get("panels")
        if not isinstance(original_panels, list) or not isinstance(captioned_panels, list):
            raise ValueError("pages must contain panel arrays")
        if len(original_panels) != len(captioned_panels):
            raise ValueError(
                f"page {original_page.get('page_number')} panel count changed"
            )
        for original_panel, captioned_panel in zip(
            original_panels, captioned_panels, strict=True
        ):
            if not isinstance(original_panel, dict) or not isinstance(captioned_panel, dict):
                raise ValueError("panels must be objects")
            if _panel_key(original_panel) != _panel_key(captioned_panel):
                raise ValueError(
                    "non-lettering panel fields changed at "
                    f"page {captioned_page.get('page_number')} "
                    f"panel {captioned_panel.get('panel_number')}"
                )
            caption = str(captioned_panel.get("caption", "")).strip()
            if not caption:
                raise ValueError(
                    f"page {captioned_page.get('page_number')} "
                    f"panel {captioned_panel.get('panel_number')} missing caption"
                )
            if require_first_person and not FIRST_PERSON_RE.search(caption):
                raise ValueError(
                    f"page {captioned_page.get('page_number')} "
                    f"panel {captioned_panel.get('panel_number')} is not first-person: "
                    f"{caption!r}"
                )
            zone = str(captioned_panel.get("caption_zone", "")).strip()
            if zone not in VALID_ZONES:
                raise ValueError(
                    f"page {captioned_page.get('page_number')} "
                    f"panel {captioned_panel.get('panel_number')} invalid caption_zone "
                    f"{zone!r}"
                )
            dialogue = captioned_panel.get("dialogue") or []
            if not allow_dialogue and dialogue:
                raise ValueError(
                    f"page {captioned_page.get('page_number')} "
                    f"panel {captioned_panel.get('panel_number')} has dialogue despite "
                    "--no-dialogue"
                )


def _caption_pass_markdown(
    data: dict[str, Any],
    *,
    book_id: str,
    source_path: Path,
    excerpt_words: tuple[int, int],
) -> str:
    return _markdown_storyboard(
        data,
        book_id=book_id,
        source_path=source_path,
        excerpt_words=excerpt_words,
    )


def _derive_default_paths(run_dir: Path, suffix: str) -> tuple[Path, Path, Path]:
    out_json = run_dir / f"storyboard_{suffix}.json"
    out_md = run_dir / f"storyboard_{suffix}.md"
    out_lettering = run_dir / f"lettering_script_{suffix}.md"
    return out_json, out_md, out_lettering


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--storyboard-json",
        type=Path,
        help="Storyboard JSON to rewrite; defaults to run_dir/storyboard.json.",
    )
    parser.add_argument(
        "--source-units-json",
        type=Path,
        help="Source units JSON; defaults to run_dir/source_units.json.",
    )
    parser.add_argument("--mode", choices=["first-person"], default="first-person")
    parser.add_argument("--allow-dialogue", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--suffix", default="first_person")
    args = parser.parse_args(argv)

    run_dir = args.run_dir
    run_meta = _load_run_meta(run_dir)
    book_id = str(run_meta.get("book_id") or "")
    if not book_id:
        raise ValueError(f"run metadata has no book_id: {run_dir / 'run.json'}")
    book = load_book(book_id)

    storyboard_path = args.storyboard_json or run_dir / "storyboard.json"
    source_units_path = args.source_units_json or run_dir / "source_units.json"
    original = json.loads(storyboard_path.read_text(encoding="utf-8"))
    source_units = json.loads(source_units_path.read_text(encoding="utf-8"))

    prompt = load_prompt("graphic_caption_first_person")
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 24000))
    )
    require_first_person = args.mode == "first-person"
    rendered = prompt.render(
        title=book.metadata.get("title", book_id),
        author=book.metadata.get("author", ""),
        narration_policy=(
            "first-person narrator captions; every caption should read as "
            "the narrator saying I/me/my/we/us where natural"
        ),
        dialogue_policy=(
            "dialogue allowed only when explicitly source-quoted and visible "
            "speaker anchoring is unambiguous"
            if args.allow_dialogue
            else "no speech balloons; convert spoken information into captions"
        ),
        source_units_json=json.dumps(source_units, indent=2, ensure_ascii=False),
        storyboard_json=json.dumps(original, indent=2, ensure_ascii=False),
    )
    prompt_path = run_dir / f"caption_policy_{args.suffix}_prompt.md"
    prompt_path.write_text(rendered, encoding="utf-8")

    if args.dry_run:
        print(f"wrote caption-policy dry-run prompt to {prompt_path}")
        return 0

    data = _complete_json_with_retry(
        rendered=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_output_tokens,
        work_dir=book.work_dir,
        stage=f"graphic_caption_policy:{book_id}:{run_dir.name}:{args.suffix}",
        raw_path=run_dir / f"caption_policy_{args.suffix}_raw_response.txt",
    )
    captioned = deepcopy(data)
    _validate_captioned_storyboard(
        original,
        captioned,
        require_first_person=require_first_person,
        allow_dialogue=args.allow_dialogue,
    )
    captioned["lettering_policy"] = {
        "variant": args.suffix,
        "mode": args.mode,
        "allow_dialogue": args.allow_dialogue,
        "rules": [
            "Every panel has exactly one caption.",
            "Captions preserve panel/book order.",
            "First-person sources use first-person narrator captions.",
            "Speech balloons are disabled unless explicitly allowed.",
            "Each panel carries a caption_zone for deterministic lettering.",
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out_json, out_md, out_lettering = _derive_default_paths(run_dir, args.suffix)
    write_json(out_json, captioned)
    image_prompt_dir_name = f"image_prompts_{args.suffix}"
    _write_page_image_prompts(captioned, run_dir, prompt_dir_name=image_prompt_dir_name)
    source_path = Path(str(run_meta.get("source_path") or ""))
    start_word = int(run_meta.get("start_word") or 1)
    end_word = int(run_meta.get("end_word") or start_word)
    out_md.write_text(
        _caption_pass_markdown(
            captioned,
            book_id=book_id,
            source_path=source_path,
            excerpt_words=(start_word, end_word),
        ),
        encoding="utf-8",
    )
    out_lettering.write_text(_markdown_lettering_script(captioned), encoding="utf-8")

    panel_count = sum(
        len(page.get("panels", []) or [])
        for page in captioned.get("pages", [])
        if isinstance(page, dict)
    )
    print(f"wrote caption policy storyboard: {panel_count} panels")
    print(f"json: {out_json}")
    print(f"markdown: {out_md}")
    print(f"lettering: {out_lettering}")
    print(f"image prompts: {run_dir / image_prompt_dir_name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
