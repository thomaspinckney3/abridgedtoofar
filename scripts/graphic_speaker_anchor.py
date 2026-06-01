"""Detect speaker anchor points for deterministic graphic-novel lettering.

Usage:
  python -m scripts.graphic_speaker_anchor \
      work/mobydick/graphic_novel/action_spine_v3/chapter_003/page_sequence_prototype

This stage runs after panel art generation and before final lettering. By
default it looks at each raw panel image, then maps the detected point into the
composed page geometry. It can also inspect a composed clean page with
--image-source page.
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
from scripts.compose_graphic_panel_page import (
    _page_size,
    _panel_boxes,
    _panel_image_path,
    _text_items,
)


def _data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _grid_overlay(source_path: Path, out_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(source_path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(16, width // 70))
    except Exception:
        font = ImageFont.load_default()

    grid_color = (0, 180, 255, 150)
    label_fill = (255, 240, 0, 240)
    label_bg = (0, 0, 0, 150)
    for step in range(1, 10):
        x = round(width * step / 10)
        y = round(height * step / 10)
        draw.line((x, 0, x, height), fill=grid_color, width=max(2, width // 700))
        draw.line((0, y, width, y), fill=grid_color, width=max(2, height // 700))
        x_label = f"x={step / 10:.1f}"
        y_label = f"y={step / 10:.1f}"
        draw.rectangle((x + 3, 3, x + 78, 28), fill=label_bg)
        draw.text((x + 6, 5), x_label, fill=label_fill, font=font)
        draw.rectangle((3, y + 3, 82, y + 28), fill=label_bg)
        draw.text((6, y + 5), y_label, fill=label_fill, font=font)
    marked = Image.alpha_composite(image, overlay)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    marked.convert("RGB").save(out_path)
    return out_path


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
                f"speaker anchor detection requires an OpenAI vision model, got {model!r}"
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


def _target_items(page: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, int]]]:
    width, height = _page_size(page)
    panels = [panel for panel in page.get("panels", []) if isinstance(panel, dict)]
    boxes = _panel_boxes(page, panels, width, height)
    targets: list[dict[str, Any]] = []
    panel_boxes: list[dict[str, int]] = []

    for panel, box in zip(panels, boxes, strict=False):
        panel_no = int(panel.get("panel_number") or 0)
        panel_boxes.append({
            "panel_number": panel_no,
            "x1": box.x1,
            "y1": box.y1,
            "x2": box.x2,
            "y2": box.y2,
        })
        for item in _text_items(panel):
            kind = str(item.get("kind") or "").strip().lower()
            if kind not in {"speech", "thought"}:
                continue
            targets.append({
                "panel_number": panel_no,
                "text_index": int(item.get("text_index") or 0),
                "kind": kind,
                "speaker": str(item.get("speaker") or "").strip(),
                "text": str(item.get("text") or "").strip(),
                "speaker_region": str(item.get("speaker_region") or item.get("speaker_side") or "").strip(),
                "speaker_visual_hint": str(item.get("speaker_visual_hint") or "").strip(),
                "balloon_zone": str(item.get("balloon_zone") or item.get("placement") or "").strip(),
            })

    return targets, panel_boxes


def _page_contract(data: dict[str, Any], page: dict[str, Any]) -> str:
    width, height = _page_size(page)
    targets, panel_boxes = _target_items(page)
    contract = {
        "title": data.get("title"),
        "source_chapter": data.get("source_chapter"),
        "image_mode": "page",
        "coordinate_grid": "visible, every 0.1 in x and y, for detection only",
        "page_number": page.get("page_number"),
        "page_size": {"width": width, "height": height},
        "panel_boxes": panel_boxes,
        "targets": targets,
    }
    return json.dumps(contract, indent=2, ensure_ascii=False)


def _panel_contract(
    data: dict[str, Any],
    page: dict[str, Any],
    panel: dict[str, Any],
    *,
    image_path: Path,
) -> str:
    width, height = _image_size(image_path)
    targets = []
    for item in _text_items(panel):
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in {"speech", "thought"}:
            continue
        targets.append({
            "panel_number": int(panel.get("panel_number") or 0),
            "text_index": int(item.get("text_index") or 0),
            "kind": kind,
            "speaker": str(item.get("speaker") or "").strip(),
            "text": str(item.get("text") or "").strip(),
            "speaker_region": str(item.get("speaker_region") or item.get("speaker_side") or "").strip(),
            "speaker_visual_hint": str(item.get("speaker_visual_hint") or "").strip(),
            "balloon_zone": str(item.get("balloon_zone") or item.get("placement") or "").strip(),
        })
    contract = {
        "title": data.get("title"),
        "source_chapter": data.get("source_chapter"),
        "image_mode": "panel",
        "coordinate_grid": "visible, every 0.1 in x and y, for detection only",
        "page_number": page.get("page_number"),
        "panel_number": panel.get("panel_number"),
        "image_size": {"width": width, "height": height},
        "targets": targets,
    }
    return json.dumps(contract, indent=2, ensure_ascii=False)


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def _clip_ratio(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_page_report(
    report: dict[str, Any],
    *,
    page: dict[str, Any],
) -> dict[str, Any]:
    page_no = int(page.get("page_number") or 0)
    if int(report.get("page_number") or 0) != page_no:
        raise ValueError(
            f"speaker anchor page_number mismatch: expected {page_no}, got {report.get('page_number')!r}"
        )
    anchors = report.get("anchors")
    if not isinstance(anchors, list):
        raise ValueError(f"speaker anchor page {page_no} missing anchors array")

    width, height = _page_size(page)
    panels = [panel for panel in page.get("panels", []) if isinstance(panel, dict)]
    boxes = {
        int(panel.get("panel_number") or 0): box
        for panel, box in zip(panels, _panel_boxes(page, panels, width, height), strict=False)
    }

    cleaned: list[dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ValueError(f"speaker anchor page {page_no} contains non-object anchor")
        panel_no = int(anchor.get("panel_number") or 0)
        text_index = int(anchor.get("text_index") or 0)
        kind = str(anchor.get("kind") or "").strip().lower()
        if kind not in {"speech", "thought"}:
            raise ValueError(f"speaker anchor page {page_no} has invalid kind {kind!r}")
        visible = bool(anchor.get("visible"))
        confidence = max(0.0, min(1.0, float(anchor.get("confidence") or 0.0)))
        box = boxes.get(panel_no)
        cleaned_anchor = {
            "panel_number": panel_no,
            "text_index": text_index,
            "kind": kind,
            "speaker": str(anchor.get("speaker") or "").strip(),
            "text": str(anchor.get("text") or "").strip(),
            "visible": visible,
            "confidence": confidence,
            "mouth_point": None,
            "mouth_point_ratio": None,
            "tail_target_point": None,
            "tail_target_point_ratio": None,
            "face_box": None,
            "evidence": str(anchor.get("evidence") or "").strip(),
            "reason": str(anchor.get("reason") or "").strip(),
            "source": "speaker_anchor_detection",
        }
        if visible and box is not None:
            point = anchor.get("mouth_point")
            ratio = anchor.get("mouth_point_ratio")
            if isinstance(ratio, dict) and ratio.get("x") is not None and ratio.get("y") is not None:
                rx = _clip_ratio(ratio["x"])
                ry = _clip_ratio(ratio["y"])
                cleaned_anchor["mouth_point_ratio"] = {"x": rx, "y": ry}
                cleaned_anchor["mouth_point"] = {
                    "x": box.x1 + round(box.width * rx),
                    "y": box.y1 + round(box.height * ry),
                }
            elif isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None:
                x = max(box.x1, min(box.x2, round(float(point["x"]))))
                y = max(box.y1, min(box.y2, round(float(point["y"]))))
                cleaned_anchor["mouth_point"] = {"x": x, "y": y}
                cleaned_anchor["mouth_point_ratio"] = {
                    "x": (x - box.x1) / max(box.width, 1),
                    "y": (y - box.y1) / max(box.height, 1),
                }
            target_ratio = anchor.get("tail_target_point_ratio")
            target_point = anchor.get("tail_target_point")
            if isinstance(target_ratio, dict) and target_ratio.get("x") is not None and target_ratio.get("y") is not None:
                tx = _clip_ratio(target_ratio["x"])
                ty = _clip_ratio(target_ratio["y"])
                cleaned_anchor["tail_target_point_ratio"] = {"x": tx, "y": ty}
                cleaned_anchor["tail_target_point"] = {
                    "x": box.x1 + round(box.width * tx),
                    "y": box.y1 + round(box.height * ty),
                }
            elif isinstance(target_point, dict) and target_point.get("x") is not None and target_point.get("y") is not None:
                x = max(box.x1, min(box.x2, round(float(target_point["x"]))))
                y = max(box.y1, min(box.y2, round(float(target_point["y"]))))
                cleaned_anchor["tail_target_point"] = {"x": x, "y": y}
                cleaned_anchor["tail_target_point_ratio"] = {
                    "x": (x - box.x1) / max(box.width, 1),
                    "y": (y - box.y1) / max(box.height, 1),
                }
            face_box = anchor.get("face_box")
            if isinstance(face_box, dict) and {"x1", "y1", "x2", "y2"} <= set(face_box):
                cleaned_anchor["face_box"] = {
                    "x1": max(box.x1, min(box.x2, round(float(face_box["x1"])))),
                    "y1": max(box.y1, min(box.y2, round(float(face_box["y1"])))),
                    "x2": max(box.x1, min(box.x2, round(float(face_box["x2"])))),
                    "y2": max(box.y1, min(box.y2, round(float(face_box["y2"])))),
                }
        cleaned.append(cleaned_anchor)

    report["anchors"] = cleaned
    return report


def _fit_panel_ratio_to_page_ratio(
    *,
    source_size: tuple[int, int],
    panel_box: Any,
    ratio: dict[str, Any],
) -> dict[str, float]:
    src_w, src_h = source_size
    raw_x = _clip_ratio(ratio["x"]) * src_w
    raw_y = _clip_ratio(ratio["y"]) * src_h
    scale = max(panel_box.width / max(src_w, 1), panel_box.height / max(src_h, 1))
    resized_w = src_w * scale
    resized_h = src_h * scale
    crop_left = (resized_w - panel_box.width) / 2
    crop_top = (resized_h - panel_box.height) / 2
    page_ratio_x = (raw_x * scale - crop_left) / max(panel_box.width, 1)
    page_ratio_y = (raw_y * scale - crop_top) / max(panel_box.height, 1)
    return {"x": _clip_ratio(page_ratio_x), "y": _clip_ratio(page_ratio_y)}


def _validate_panel_report(
    report: dict[str, Any],
    *,
    page: dict[str, Any],
    panel: dict[str, Any],
    image_path: Path,
    panel_box: Any,
) -> list[dict[str, Any]]:
    page_no = int(page.get("page_number") or 0)
    panel_no = int(panel.get("panel_number") or 0)
    if int(report.get("page_number") or 0) != page_no:
        raise ValueError(
            f"speaker anchor page_number mismatch: expected {page_no}, got {report.get('page_number')!r}"
        )
    anchors = report.get("anchors")
    if not isinstance(anchors, list):
        raise ValueError(f"speaker anchor page {page_no} panel {panel_no} missing anchors array")

    source_size = _image_size(image_path)
    cleaned: list[dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ValueError(f"speaker anchor page {page_no} panel {panel_no} contains non-object anchor")
        if int(anchor.get("panel_number") or 0) != panel_no:
            raise ValueError(
                f"speaker anchor panel mismatch: expected {panel_no}, got {anchor.get('panel_number')!r}"
            )
        kind = str(anchor.get("kind") or "").strip().lower()
        if kind not in {"speech", "thought"}:
            raise ValueError(f"speaker anchor page {page_no} panel {panel_no} has invalid kind {kind!r}")
        visible = bool(anchor.get("visible"))
        confidence = max(0.0, min(1.0, float(anchor.get("confidence") or 0.0)))
        cleaned_anchor = {
            "panel_number": panel_no,
            "text_index": int(anchor.get("text_index") or 0),
            "kind": kind,
            "speaker": str(anchor.get("speaker") or "").strip(),
            "text": str(anchor.get("text") or "").strip(),
            "visible": visible,
            "confidence": confidence,
            "mouth_point": None,
            "mouth_point_ratio": None,
            "tail_target_point": None,
            "tail_target_point_ratio": None,
            "source_image_point": None,
            "source_image_point_ratio": None,
            "source_tail_target_point": None,
            "source_tail_target_point_ratio": None,
            "face_box": None,
            "evidence": str(anchor.get("evidence") or "").strip(),
            "reason": str(anchor.get("reason") or "").strip(),
            "source": "speaker_anchor_detection_panel",
        }
        ratio = anchor.get("mouth_point_ratio")
        point = anchor.get("mouth_point")
        if visible:
            source_ratio = None
            if isinstance(ratio, dict) and ratio.get("x") is not None and ratio.get("y") is not None:
                source_ratio = {"x": _clip_ratio(ratio["x"]), "y": _clip_ratio(ratio["y"])}
            elif isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None:
                src_w, src_h = source_size
                source_ratio = {
                    "x": _clip_ratio(float(point["x"]) / max(src_w, 1)),
                    "y": _clip_ratio(float(point["y"]) / max(src_h, 1)),
                }
            if source_ratio is not None:
                page_ratio = _fit_panel_ratio_to_page_ratio(
                    source_size=source_size,
                    panel_box=panel_box,
                    ratio=source_ratio,
                )
                cleaned_anchor["source_image_point_ratio"] = source_ratio
                cleaned_anchor["source_image_point"] = {
                    "x": round(source_ratio["x"] * source_size[0]),
                    "y": round(source_ratio["y"] * source_size[1]),
                }
                cleaned_anchor["mouth_point_ratio"] = page_ratio
                cleaned_anchor["mouth_point"] = {
                    "x": panel_box.x1 + round(panel_box.width * page_ratio["x"]),
                    "y": panel_box.y1 + round(panel_box.height * page_ratio["y"]),
                }
            target_ratio_raw = anchor.get("tail_target_point_ratio")
            target_point = anchor.get("tail_target_point")
            target_source_ratio = None
            if isinstance(target_ratio_raw, dict) and target_ratio_raw.get("x") is not None and target_ratio_raw.get("y") is not None:
                target_source_ratio = {
                    "x": _clip_ratio(target_ratio_raw["x"]),
                    "y": _clip_ratio(target_ratio_raw["y"]),
                }
            elif isinstance(target_point, dict) and target_point.get("x") is not None and target_point.get("y") is not None:
                src_w, src_h = source_size
                target_source_ratio = {
                    "x": _clip_ratio(float(target_point["x"]) / max(src_w, 1)),
                    "y": _clip_ratio(float(target_point["y"]) / max(src_h, 1)),
                }
            if visible and target_source_ratio is not None:
                target_page_ratio = _fit_panel_ratio_to_page_ratio(
                    source_size=source_size,
                    panel_box=panel_box,
                    ratio=target_source_ratio,
                )
                cleaned_anchor["source_tail_target_point_ratio"] = target_source_ratio
                cleaned_anchor["source_tail_target_point"] = {
                    "x": round(target_source_ratio["x"] * source_size[0]),
                    "y": round(target_source_ratio["y"] * source_size[1]),
                }
                cleaned_anchor["tail_target_point_ratio"] = target_page_ratio
                cleaned_anchor["tail_target_point"] = {
                    "x": panel_box.x1 + round(panel_box.width * target_page_ratio["x"]),
                    "y": panel_box.y1 + round(panel_box.height * target_page_ratio["y"]),
                }
            face_box = anchor.get("face_box")
            if isinstance(face_box, dict) and {"x1", "y1", "x2", "y2"} <= set(face_box):
                src_w, src_h = source_size
                x1 = _clip_ratio(float(face_box["x1"]) / max(src_w, 1))
                y1 = _clip_ratio(float(face_box["y1"]) / max(src_h, 1))
                x2 = _clip_ratio(float(face_box["x2"]) / max(src_w, 1))
                y2 = _clip_ratio(float(face_box["y2"]) / max(src_h, 1))
                if x2 < x1:
                    x1, x2 = x2, x1
                if y2 < y1:
                    y1, y2 = y2, y1
                page_top_left = _fit_panel_ratio_to_page_ratio(
                    source_size=source_size,
                    panel_box=panel_box,
                    ratio={"x": x1, "y": y1},
                )
                page_bottom_right = _fit_panel_ratio_to_page_ratio(
                    source_size=source_size,
                    panel_box=panel_box,
                    ratio={"x": x2, "y": y2},
                )
                cleaned_anchor["face_box"] = {
                    "x1": panel_box.x1 + round(panel_box.width * page_top_left["x"]),
                    "y1": panel_box.y1 + round(panel_box.height * page_top_left["y"]),
                    "x2": panel_box.x1 + round(panel_box.width * page_bottom_right["x"]),
                    "y2": panel_box.y1 + round(panel_box.height * page_bottom_right["y"]),
                }
                cleaned_anchor["face_box_ratio"] = {
                    "x1": page_top_left["x"],
                    "y1": page_top_left["y"],
                    "x2": page_bottom_right["x"],
                    "y2": page_bottom_right["y"],
                }
        cleaned.append(cleaned_anchor)
    return cleaned


def run_anchor_detection(
    run_dir: Path,
    *,
    storyboard_path: Path | None = None,
    image_dir: Path | None = None,
    out_path: Path | None = None,
    model: str | None = None,
    max_output_tokens: int | None = None,
    image_source: str = "panels",
    grid_overlay: bool = True,
    dry_run: bool = False,
) -> Path:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    if image_source not in {"page", "panels"}:
        raise ValueError("--image-source must be page or panels")
    image_dir = image_dir or run_dir / ("panel_art" if image_source == "panels" else "generated_pages")
    out_path = out_path or run_dir / "speaker_anchors.json"
    prompt = load_prompt("graphic_speaker_anchor")
    model = model or prompt.config.get("model", "openai:gpt-5")
    max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 3000))
    )
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    pages = [page for page in data.get("pages", []) if isinstance(page, dict)]
    if not pages:
        raise ValueError(f"no pages found in {storyboard_path}")

    prompt_dir = run_dir / "speaker_anchor_prompts"
    raw_dir = run_dir / "speaker_anchor_raw"
    grid_dir = run_dir / "speaker_anchor_grid"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        raw_dir.mkdir(parents=True, exist_ok=True)

    page_reports: list[dict[str, Any]] = []
    for page in pages:
        page_no = int(page.get("page_number") or 0)
        if image_source == "page":
            image_path = image_dir / f"page_{page_no:03d}.png"
            if not image_path.exists():
                raise FileNotFoundError(f"missing clean composed page image: {image_path}")
            model_image_path = (
                _grid_overlay(image_path, grid_dir / f"page_{page_no:03d}.png")
                if grid_overlay else image_path
            )

            rendered = prompt.render(page_contract=_page_contract(data, page))
            (prompt_dir / f"page_{page_no:03d}.md").write_text(rendered, encoding="utf-8")
            if dry_run:
                continue
            raw = _call_vision_model(
                rendered=rendered,
                image_path=model_image_path,
                model=model,
                system=prompt.system,
                max_output_tokens=max_output_tokens,
            )
            (raw_dir / f"page_{page_no:03d}.txt").write_text(raw, encoding="utf-8")
            if not raw.strip():
                raise ValueError(f"speaker anchor model returned empty output for page {page_no}")
            report = parse_llm_json(raw)
            page_reports.append(_validate_page_report(report, page=page))
            continue

        width, height = _page_size(page)
        panels = [panel for panel in page.get("panels", []) if isinstance(panel, dict)]
        boxes = _panel_boxes(page, panels, width, height)
        page_anchors: list[dict[str, Any]] = []
        for panel, panel_box in zip(panels, boxes, strict=False):
            targets = [
                item for item in _text_items(panel)
                if str(item.get("kind") or "").strip().lower() in {"speech", "thought"}
            ]
            if not targets:
                continue
            panel_no = int(panel.get("panel_number") or 0)
            image_path = _panel_image_path(panel, image_dir)
            if not image_path.exists():
                raise FileNotFoundError(f"missing panel image: {image_path}")
            model_image_path = (
                _grid_overlay(image_path, grid_dir / f"page_{page_no:03d}_panel_{panel_no:03d}.png")
                if grid_overlay else image_path
            )
            rendered = prompt.render(
                page_contract=_panel_contract(
                    data,
                    page,
                    panel,
                    image_path=image_path,
                )
            )
            (prompt_dir / f"page_{page_no:03d}_panel_{panel_no:03d}.md").write_text(
                rendered,
                encoding="utf-8",
            )
            if dry_run:
                continue
            raw = _call_vision_model(
                rendered=rendered,
                image_path=model_image_path,
                model=model,
                system=prompt.system,
                max_output_tokens=max_output_tokens,
            )
            (raw_dir / f"page_{page_no:03d}_panel_{panel_no:03d}.txt").write_text(
                raw,
                encoding="utf-8",
            )
            if not raw.strip():
                raise ValueError(
                    f"speaker anchor model returned empty output for page {page_no} panel {panel_no}"
                )
            report = parse_llm_json(raw)
            page_anchors.extend(
                _validate_panel_report(
                    report,
                    page=page,
                    panel=panel,
                    image_path=image_path,
                    panel_box=panel_box,
                )
            )
        page_reports.append({"page_number": page_no, "anchors": page_anchors})

    result = {
        "run_dir": str(run_dir),
        "storyboard": str(storyboard_path),
        "image_dir": str(image_dir),
        "model": model,
        "image_source": image_source,
        "grid_overlay": grid_overlay,
        "dry_run": dry_run,
        "pages": page_reports,
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
    parser.add_argument("--image-source", choices=["page", "panels"], default="panels")
    parser.add_argument("--no-grid-overlay", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_path = run_anchor_detection(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        image_dir=args.image_dir,
        out_path=args.out,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        image_source=args.image_source,
        grid_overlay=not args.no_grid_overlay,
        dry_run=args.dry_run,
    )
    print(out_path)


if __name__ == "__main__":
    main()
