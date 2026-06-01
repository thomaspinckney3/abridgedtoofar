"""Run vision QA on generated graphic-novel frame art.

Usage:
  python -m scripts.graphic_image_qa \
      work/mobydick/graphic_novel/action_spine_auto/chapter_003

This stage is intended to run after image generation and before deterministic
lettering. It compares each generated frame image against storyboard.json and
flags visible failures such as character-continuity drift, prop confusion,
literalized metaphors, unsupported content, readable text, and bad lettering
slots.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from forage.artifacts import write_json
from forage.json_parse import parse_llm_json
from forage.prompts import load_prompt


def _data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _frame_contract(data: dict[str, Any], frame: dict[str, Any]) -> str:
    visible = frame.get("visible_content")
    if not isinstance(visible, dict):
        visible = {}

    contract = {
        "title": data.get("title"),
        "source_chapter": data.get("source_chapter"),
        "character_continuity": data.get("character_continuity", {}),
        "prop_continuity": data.get("prop_continuity", {}),
        "frame": {
            "frame_number": frame.get("frame_number"),
            "caption": frame.get("caption"),
            "driver_character": frame.get("driver_character"),
            "primary_action": frame.get("primary_action"),
            "shot": frame.get("shot"),
            "panel_archetype": frame.get("panel_archetype"),
            "caption_zone": frame.get("caption_zone"),
            "lettering_slots": frame.get("lettering_slots"),
            "lettering_constraints": frame.get("lettering_constraints"),
            "thumbnail_layout": frame.get("thumbnail_layout"),
            "thumbnail_constraints": frame.get("thumbnail_constraints"),
            "visible_people": _string_list(visible.get("people")),
            "visible_places": _string_list(visible.get("places")),
            "visible_props": _string_list(visible.get("props")),
            "visible_actions": _string_list(visible.get("actions")),
            "supporting_visuals": _string_list(frame.get("supporting_visuals")),
            "do_not_show": _string_list(frame.get("do_not_show")),
            "image_prompt": frame.get("image_prompt"),
            "purpose": frame.get("purpose"),
        },
    }
    return json.dumps(contract, indent=2, ensure_ascii=False)


def _validate_report(report: dict[str, Any], frame_no: int) -> None:
    if int(report.get("frame_number") or 0) != frame_no:
        raise ValueError(
            f"QA report frame_number mismatch: expected {frame_no}, "
            f"got {report.get('frame_number')!r}"
        )
    if not isinstance(report.get("valid"), bool):
        raise ValueError(f"QA report for frame {frame_no} missing boolean valid")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError(f"QA report for frame {frame_no} missing findings array")
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError(f"QA report for frame {frame_no} has non-object finding")
        for key in ("severity", "category", "finding", "visible_evidence"):
            if not str(finding.get(key, "")).strip():
                raise ValueError(
                    f"QA report for frame {frame_no} finding missing {key}"
                )


def _call_vision_model(
    *,
    rendered: str,
    image_path: Path,
    model: str,
    system: str | None,
    max_output_tokens: int,
) -> str:
    import openai

    provider, sep, model_id = model.partition(":")
    if sep:
        if provider != "openai":
            raise ValueError(
                f"graphic image QA currently requires an OpenAI model, got {model!r}"
            )
    else:
        model_id = model

    client = openai.OpenAI()
    response = client.responses.create(
        model=model_id,
        instructions=system,
        max_output_tokens=max_output_tokens,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": rendered},
                    {
                        "type": "input_image",
                        "image_url": _data_url(image_path),
                        "detail": "high",
                    },
                ],
            }
        ],
    )
    return response.output_text


def run_qa(
    run_dir: Path,
    *,
    storyboard_path: Path | None = None,
    image_dir: Path | None = None,
    out_path: Path | None = None,
    model: str | None = None,
    max_output_tokens: int | None = None,
    dry_run: bool = False,
) -> Path:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    image_dir = image_dir or run_dir / "generated_frames"
    out_path = out_path or run_dir / "image_qa_report.json"
    prompt = load_prompt("graphic_image_qa")
    model = model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 4000))
    )
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    frames = [frame for frame in data.get("frames", []) if isinstance(frame, dict)]
    if not frames:
        raise ValueError(f"no frames found in {storyboard_path}")

    prompt_dir = run_dir / "image_qa_prompts"
    raw_dir = run_dir / "image_qa_raw"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        raw_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for frame in frames:
        frame_no = int(frame.get("frame_number") or 0)
        if frame_no <= 0:
            raise ValueError("frames must have positive frame_number")
        image_path = image_dir / f"frame_{frame_no:03d}.png"
        if not image_path.exists():
            raise FileNotFoundError(f"missing generated frame image: {image_path}")
        rendered = prompt.render(frame_contract=_frame_contract(data, frame))
        (prompt_dir / f"frame_{frame_no:03d}.md").write_text(
            rendered,
            encoding="utf-8",
        )
        if dry_run:
            continue
        raw = _call_vision_model(
            rendered=rendered,
            image_path=image_path,
            model=model,
            system=prompt.system,
            max_output_tokens=max_output_tokens,
        )
        (raw_dir / f"frame_{frame_no:03d}.txt").write_text(raw, encoding="utf-8")
        report = parse_llm_json(raw)
        _validate_report(report, frame_no)
        reports.append(report)

    result = {
        "run_dir": str(run_dir),
        "storyboard": str(storyboard_path),
        "image_dir": str(image_dir),
        "model": model,
        "dry_run": dry_run,
        "frames": reports,
        "valid": all(report.get("valid") for report in reports) if reports else None,
    }
    write_json(out_path, result)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--storyboard-json", type=Path)
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_path = run_qa(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        image_dir=args.image_dir,
        out_path=args.out,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        dry_run=args.dry_run,
    )
    print(out_path)


if __name__ == "__main__":
    main()
