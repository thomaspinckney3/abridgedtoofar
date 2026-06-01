"""Apply deterministic lettering to graphic-novel page images.

Usage:
  python -m scripts.letter_graphic_novel_pages \
      work/gatsby/graphic_novel/opening_trial_v7_from_plot

Reads storyboard.json and generated_pages/page_###.png, detects the panel
layout from page gutters, and writes lettered_pages/page_###.png plus a
multi-page PDF.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin  # noqa: F401


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


FONT_CANDIDATES = {
    "caption": [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "dialogue": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "sfx": [
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
}


def _font_path(kind: str) -> str | None:
    for candidate in FONT_CANDIDATES[kind]:
        if Path(candidate).exists():
            return candidate
    return None


def _load_font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path(kind)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def _near_white(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    # Generated comic gutters are often warm off-white, not pure white.
    return min(r, g, b) >= 200


def _bands(values: list[float], threshold: float, min_len: int) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_len:
                bands.append((start, index))
            start = None
    if start is not None and len(values) - start >= min_len:
        bands.append((start, len(values)))
    return bands


def _content_intervals(
    gaps: list[tuple[int, int]],
    total: int,
    min_size: int,
) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    cursor = 0
    for start, end in gaps:
        if start - cursor >= min_size:
            intervals.append((cursor, start))
        cursor = max(cursor, end)
    if total - cursor >= min_size:
        intervals.append((cursor, total))
    return intervals


def _trim_interval(
    image: Image.Image,
    box: Box,
    *,
    horizontal: bool,
) -> tuple[int, int]:
    """Trim white page margins off one interval without chasing panel art."""
    rgb = image.convert("RGB")
    if horizontal:
        values = []
        for y in range(box.y1, box.y2):
            white = 0
            samples = 0
            for x in range(box.x1, box.x2, 8):
                samples += 1
                if _near_white(rgb.getpixel((x, y))):
                    white += 1
            values.append(white / max(samples, 1))
        offset = box.y1
    else:
        values = []
        for x in range(box.x1, box.x2):
            white = 0
            samples = 0
            for y in range(box.y1, box.y2, 8):
                samples += 1
                if _near_white(rgb.getpixel((x, y))):
                    white += 1
            values.append(white / max(samples, 1))
        offset = box.x1

    start = 0
    end = len(values)
    max_trim = min(len(values) // 8, 18)
    while start < end and start < max_trim and values[start] >= 0.75:
        start += 1
    while end > start and len(values) - end < max_trim and values[end - 1] >= 0.75:
        end -= 1
    return offset + start, offset + end


def detect_panel_boxes(image: Image.Image, expected_count: int) -> list[Box]:
    """Detect comic panels by treating mostly-white gutters as separators."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    row_values: list[float] = []
    dark_row_values: list[float] = []
    for y in range(height):
        white = 0
        dark = 0
        samples = 0
        for x in range(0, width, 4):
            samples += 1
            pixel = rgb.getpixel((x, y))
            if _near_white(pixel):
                white += 1
            if sum(pixel) <= 130:
                dark += 1
        row_values.append(white / max(samples, 1))
        dark_row_values.append(dark / max(samples, 1))

    row_gaps = _bands(row_values, threshold=0.66, min_len=max(2, height // 700))
    row_gaps = [
        (start, end)
        for start, end in row_gaps
        if start == 0
        or end == height
        or max(dark_row_values[max(0, start - 4):min(height, end + 4)] or [0]) >= 0.25
    ]
    rows = _content_intervals(row_gaps, height, min_size=max(80, height // 10))
    if not rows:
        rows = [(0, height)]

    panels: list[Box] = []
    for y1, y2 in rows:
        row_box = Box(0, y1, width, y2)
        trim_y1, trim_y2 = _trim_interval(rgb, row_box, horizontal=True)
        if trim_y2 - trim_y1 < 60:
            continue
        col_values: list[float] = []
        for x in range(width):
            white = 0
            samples = 0
            for y in range(trim_y1, trim_y2, 4):
                samples += 1
                if _near_white(rgb.getpixel((x, y))):
                    white += 1
            col_values.append(white / max(samples, 1))

        col_gaps = _bands(col_values, threshold=0.68, min_len=max(2, width // 700))
        columns = _content_intervals(col_gaps, width, min_size=max(120, width // 7))
        if not columns:
            columns = [(0, width)]

        for x1, x2 in columns:
            col_box = Box(x1, trim_y1, x2, trim_y2)
            trim_x1, trim_x2 = _trim_interval(rgb, col_box, horizontal=False)
            if trim_x2 - trim_x1 >= 80:
                panels.append(Box(trim_x1, trim_y1, trim_x2, trim_y2))

    panels.sort(key=lambda b: (b.y1, b.x1))
    if len(panels) == expected_count:
        return panels

    # Fallback keeps the stage productive even if generated art lacks gutters.
    strip_h = height / expected_count
    return [
        Box(0, round(index * strip_h), width, round((index + 1) * strip_h))
        for index in range(expected_count)
    ]


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return max(1, bbox[3] - bbox[1])


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_lines(
    text: str,
    kind: str,
    max_width: int,
    max_height: int,
    draw: ImageDraw.ImageDraw,
    *,
    max_size: int,
    min_size: int,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    for size in range(max_size, min_size - 1, -1):
        font = _load_font(kind, size)
        lines = _wrap_text(text, font, max_width, draw)
        line_h = _line_height(draw, font)
        total_h = math.ceil(line_h * 1.18) * len(lines)
        if total_h <= max_height:
            return font, lines, line_h
    font = _load_font(kind, min_size)
    lines = _wrap_text(text, font, max_width, draw)
    return font, lines, _line_height(draw, font)


def _caption_parts(text: str, notes: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    wants_two = "two" in notes.lower() or len(text) > 185
    if not wants_two:
        return [text]

    splits = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    if len(splits) == 2 and all(splits):
        return splits
    # A caption split into two separate boxes reads like two narration beats.
    # If there is no sentence boundary, keep the caption in one box and let the
    # layout or upstream caption pass shorten it instead of creating a
    # mid-sentence break.
    return [text]


def _dialogue_lines(panel: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for item in panel.get("dialogue") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            rendered.append(text)
    return rendered


def _placement(panel: dict[str, Any], kind: str) -> tuple[str, str]:
    zone = str(panel.get("caption_zone", "")).strip().lower().replace("-", "_")
    zone_map = {
        "top_left": ("top", "left"),
        "top_center": ("top", "center"),
        "top_right": ("top", "right"),
        "bottom_left": ("bottom", "left"),
        "bottom_center": ("bottom", "center"),
        "bottom_right": ("bottom", "right"),
    }
    if kind == "caption" and zone in zone_map:
        return zone_map[zone]

    notes = str(panel.get("lettering_notes", "")).lower()
    if kind == "dialogue":
        return "top", "right"
    vertical = "top"
    horizontal = "left"
    if "low" in notes or "lower" in notes:
        vertical = "bottom"
    if "right" in notes:
        horizontal = "right"
    if "center" in notes:
        horizontal = "center"
    if "window frame" in notes:
        horizontal = "right"
    return vertical, horizontal


def _box_origin(
    panel_box: Box,
    box_w: int,
    box_h: int,
    total_h: int,
    *,
    index: int,
    count: int,
    vertical: str,
    horizontal: str,
    inset: int,
    gap: int,
) -> tuple[int, int]:
    if horizontal == "right":
        x = panel_box.x2 - inset - box_w
    elif horizontal == "center":
        x = panel_box.x1 + (panel_box.width - box_w) // 2
    else:
        x = panel_box.x1 + inset

    if vertical == "bottom":
        start_y = panel_box.y2 - inset - total_h
    else:
        start_y = panel_box.y1 + inset
    y = start_y + index * (box_h + gap)
    return x, y


def _draw_text_box(
    image: Image.Image,
    panel_box: Box,
    text: str,
    *,
    kind: str,
    vertical: str,
    horizontal: str,
    stack_index: int = 0,
    stack_count: int = 1,
    stack_total_h: int | None = None,
    stack_box_heights: list[int] | None = None,
) -> None:
    draw = ImageDraw.Draw(image)
    page_w, page_h = image.size
    scale = min(page_w, page_h) / 1024
    inset = max(10, round(min(panel_box.width, panel_box.height) * 0.035))
    pad_x = max(9, round(12 * scale))
    pad_y = max(6, round(8 * scale))
    gap = max(5, round(6 * scale))
    max_box_w = panel_box.width - 2 * inset
    target_w = min(max_box_w, max(round(panel_box.width * 0.72), round(280 * scale)))
    if len(text) > 115:
        target_w = min(max_box_w, max(round(panel_box.width * 0.90), target_w))

    max_text_w = max(60, target_w - 2 * pad_x)
    max_text_h = max(24, round(panel_box.height * (0.34 if kind == "caption" else 0.30)))
    max_size = max(17, round(21 * scale))
    min_size = max(12, round(13 * scale))
    if kind == "dialogue":
        max_size = max(18, round(22 * scale))
        min_size = max(13, round(14 * scale))

    font, lines, line_h = _fit_lines(
        text,
        kind,
        max_text_w,
        max_text_h,
        draw,
        max_size=max_size,
        min_size=min_size,
    )
    leading = math.ceil(line_h * 1.18)
    text_h = leading * len(lines)
    text_w = max(math.ceil(draw.textlength(line, font=font)) for line in lines)
    box_w = min(max_box_w, max(text_w + 2 * pad_x, round(120 * scale)))
    box_h = text_h + 2 * pad_y

    if stack_box_heights and stack_total_h is not None:
        total_h = stack_total_h + gap * (stack_count - 1)
        preceding = sum(stack_box_heights[:stack_index]) + gap * stack_index
        x, start_y = _box_origin(
            panel_box,
            box_w,
            box_h,
            total_h,
            index=0,
            count=stack_count,
            vertical=vertical,
            horizontal=horizontal,
            inset=inset,
            gap=gap,
        )
        y = start_y + preceding
    else:
        x, y = _box_origin(
            panel_box,
            box_w,
            box_h,
            box_h,
            index=stack_index,
            count=stack_count,
            vertical=vertical,
            horizontal=horizontal,
            inset=inset,
            gap=gap,
        )

    x = max(panel_box.x1 + 4, min(x, panel_box.x2 - box_w - 4))
    y = max(panel_box.y1 + 4, min(y, panel_box.y2 - box_h - 4))

    fill = (248, 241, 220, 232) if kind == "caption" else (255, 255, 255, 242)
    outline = (28, 24, 20, 235)
    radius = max(1, round((2 if kind == "caption" else 18) * scale))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    rect = (x, y, x + box_w, y + box_h)
    odraw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=max(1, round(scale)))

    if kind == "dialogue":
        tail_x = x + round(box_w * 0.75)
        tail = [
            (tail_x - round(12 * scale), y + box_h - 1),
            (tail_x + round(12 * scale), y + box_h - 1),
            (min(panel_box.x2 - inset, tail_x + round(34 * scale)), min(panel_box.y2 - inset, y + box_h + round(30 * scale))),
        ]
        odraw.polygon(tail, fill=fill, outline=outline)

    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)
    text_y = y + pad_y
    for line in lines:
        draw.text((x + pad_x, text_y), line, font=font, fill=(20, 18, 16, 255))
        text_y += leading


def _measure_text_box(
    image: Image.Image,
    panel_box: Box,
    text: str,
    *,
    kind: str,
) -> int:
    draw = ImageDraw.Draw(image)
    page_w, page_h = image.size
    scale = min(page_w, page_h) / 1024
    inset = max(10, round(min(panel_box.width, panel_box.height) * 0.035))
    pad_x = max(9, round(12 * scale))
    pad_y = max(6, round(8 * scale))
    max_box_w = panel_box.width - 2 * inset
    target_w = min(max_box_w, max(round(panel_box.width * 0.72), round(280 * scale)))
    if len(text) > 115:
        target_w = min(max_box_w, max(round(panel_box.width * 0.90), target_w))
    max_text_w = max(60, target_w - 2 * pad_x)
    max_text_h = max(24, round(panel_box.height * (0.34 if kind == "caption" else 0.30)))
    font, lines, line_h = _fit_lines(
        text,
        kind,
        max_text_w,
        max_text_h,
        draw,
        max_size=max(17, round((21 if kind == "caption" else 22) * scale)),
        min_size=max(12, round((13 if kind == "caption" else 14) * scale)),
    )
    return math.ceil(line_h * 1.18) * len(lines) + 2 * pad_y


def _draw_sfx(image: Image.Image, panel_box: Box, sfx_items: list[str]) -> None:
    if not sfx_items:
        return
    draw = ImageDraw.Draw(image)
    scale = min(image.size) / 1024
    font = _load_font("sfx", max(15, round(18 * scale)))
    inset = max(10, round(min(panel_box.width, panel_box.height) * 0.04))
    y = panel_box.y2 - inset - round(22 * scale)
    for item in sfx_items:
        text = str(item).strip().upper()
        if not text:
            continue
        x = panel_box.x1 + inset
        draw.text(
            (x, y),
            text,
            font=font,
            fill=(250, 245, 220, 255),
            stroke_width=max(1, round(2 * scale)),
            stroke_fill=(25, 22, 20, 255),
        )
        y -= round(24 * scale)


def letter_page(image_path: Path, page: dict[str, Any], out_path: Path) -> list[Box]:
    source = Image.open(image_path).convert("RGBA")
    panels = [panel for panel in page.get("panels", []) if isinstance(panel, dict)]
    boxes = detect_panel_boxes(source, len(panels))
    for panel, panel_box in zip(panels, boxes, strict=False):
        caption = str(panel.get("caption", "")).strip()
        caption_parts = _caption_parts(caption, str(panel.get("lettering_notes", "")))
        vertical, horizontal = _placement(panel, "caption")
        if caption_parts:
            heights = [
                _measure_text_box(source, panel_box, part, kind="caption")
                for part in caption_parts
            ]
            for index, part in enumerate(caption_parts):
                _draw_text_box(
                    source,
                    panel_box,
                    part,
                    kind="caption",
                    vertical=vertical,
                    horizontal=horizontal,
                    stack_index=index,
                    stack_count=len(caption_parts),
                    stack_total_h=sum(heights),
                    stack_box_heights=heights,
                )

        for dialogue in _dialogue_lines(panel):
            vertical, horizontal = _placement(panel, "dialogue")
            _draw_text_box(
                source,
                panel_box,
                dialogue,
                kind="dialogue",
                vertical=vertical,
                horizontal=horizontal,
            )

        _draw_sfx(source, panel_box, [str(item) for item in panel.get("sfx") or []])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    source.convert("RGB").save(out_path)
    return boxes


def letter_run(
    run_dir: Path,
    *,
    storyboard_path: Path | None = None,
    generated_dir: Path | None = None,
    out_dir: Path | None = None,
) -> None:
    storyboard_path = storyboard_path or run_dir / "storyboard.json"
    generated_dir = generated_dir or run_dir / "generated_pages"
    out_dir = out_dir or run_dir / "lettered_pages"
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    pages = [page for page in data.get("pages", []) if isinstance(page, dict)]
    diagnostics: dict[str, Any] = {"pages": []}
    output_pages: list[Path] = []
    for page in pages:
        page_no = int(page.get("page_number") or 0)
        image_path = generated_dir / f"page_{page_no:03d}.png"
        out_path = out_dir / f"page_{page_no:03d}.png"
        boxes = letter_page(image_path, page, out_path)
        output_pages.append(out_path)
        diagnostics["pages"].append({
            "page_number": page_no,
            "source_image": str(image_path),
            "lettered_image": str(out_path),
            "detected_panel_boxes": [
                {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}
                for b in boxes
            ],
        })

    (out_dir / "lettering_layout.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n",
        encoding="utf-8",
    )
    if output_pages:
        images = [Image.open(path).convert("RGB") for path in output_pages]
        pdf_path = out_dir / "lettered_book.pdf"
        first, rest = images[0], images[1:]
        first.save(pdf_path, save_all=True, append_images=rest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--storyboard-json",
        type=Path,
        help="Storyboards/caption JSON to letter; defaults to run_dir/storyboard.json.",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        help="Directory containing page_###.png art; defaults to run_dir/generated_pages.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Directory for lettered output; defaults to run_dir/lettered_pages.",
    )
    args = parser.parse_args()
    letter_run(
        args.run_dir,
        storyboard_path=args.storyboard_json,
        generated_dir=args.generated_dir,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
