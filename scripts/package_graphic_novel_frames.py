"""Package lettered graphic-novel frames into review deliverables.

Usage:
  python -m scripts.package_graphic_novel_frames \
      work/mobydick/graphic_novel/action_spine_v3 \
      --chapters 1-4 \
      --lettered-dir-name final_lettered_frames \
      --out-prefix final_lettered_chapters_001_004

Writes a combined PDF, a contact sheet, and a manifest in RUN_DIR.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, JpegImagePlugin  # noqa: F401


def _parse_chapter_numbers(value: str) -> list[int]:
    numbers: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"invalid chapter range: {part}")
            numbers.extend(range(start, end + 1))
        else:
            numbers.append(int(part))
    if not numbers:
        raise ValueError("no chapters specified")
    return numbers


def _load_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _collect_frames(
    run_dir: Path,
    *,
    chapters: list[int],
    lettered_dir_name: str,
) -> list[tuple[int, int, Path]]:
    frames: list[tuple[int, int, Path]] = []
    for chapter in chapters:
        lettered_dir = run_dir / f"chapter_{chapter:03d}" / lettered_dir_name
        if not lettered_dir.exists():
            raise FileNotFoundError(f"missing lettered frame directory: {lettered_dir}")
        for path in sorted(lettered_dir.glob("frame_*.png")):
            frame_no = int(path.stem.split("_")[-1])
            frames.append((chapter, frame_no, path))
    if not frames:
        raise ValueError("no lettered frame images found")
    return frames


def package_frames(
    run_dir: Path,
    *,
    chapters: list[int],
    lettered_dir_name: str,
    out_prefix: str,
    contact_cols: int = 4,
    thumb_width: int = 360,
    thumb_height: int = 270,
) -> dict[str, object]:
    frames = _collect_frames(
        run_dir,
        chapters=chapters,
        lettered_dir_name=lettered_dir_name,
    )

    images = [Image.open(path).convert("RGB") for _, _, path in frames]
    combined_pdf = run_dir / f"{out_prefix}.pdf"
    images[0].save(combined_pdf, save_all=True, append_images=images[1:])

    label_h = 28
    pad = 16
    rows = math.ceil(len(frames) / contact_cols)
    sheet = Image.new(
        "RGB",
        (
            contact_cols * thumb_width + (contact_cols + 1) * pad,
            rows * (thumb_height + label_h) + (rows + 1) * pad,
        ),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    font = _load_font(16)

    for index, (chapter, frame_no, path) in enumerate(frames):
        row, col = divmod(index, contact_cols)
        x = pad + col * (thumb_width + pad)
        y = pad + row * (thumb_height + label_h + pad)
        image = Image.open(path).convert("RGB")
        thumb = ImageOps.contain(image, (thumb_width, thumb_height))
        tile = Image.new("RGB", (thumb_width, thumb_height), (245, 245, 245))
        tile.paste(thumb, ((thumb_width - thumb.width) // 2, (thumb_height - thumb.height) // 2))
        sheet.paste(tile, (x, y))
        draw.text(
            (x, y + thumb_height + 5),
            f"Chapter {chapter}, frame {frame_no}",
            fill=(0, 0, 0),
            font=font,
        )

    contact_sheet = run_dir / f"{out_prefix}_contact_sheet.png"
    sheet.save(contact_sheet)

    manifest = {
        "combined_pdf": str(combined_pdf.resolve()),
        "contact_sheet": str(contact_sheet.resolve()),
        "frames": [
            {
                "chapter": chapter,
                "frame": frame_no,
                "path": str(path.resolve()),
            }
            for chapter, frame_no, path in frames
        ],
    }
    manifest_path = run_dir / f"{out_prefix}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest["manifest"] = str(manifest_path.resolve())
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--chapters", required=True)
    parser.add_argument("--lettered-dir-name", default="lettered_frames")
    parser.add_argument("--out-prefix", required=True)
    parser.add_argument("--contact-cols", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=360)
    parser.add_argument("--thumb-height", type=int, default=270)
    args = parser.parse_args(argv)

    manifest = package_frames(
        args.run_dir,
        chapters=_parse_chapter_numbers(args.chapters),
        lettered_dir_name=args.lettered_dir_name,
        out_prefix=args.out_prefix,
        contact_cols=args.contact_cols,
        thumb_width=args.thumb_width,
        thumb_height=args.thumb_height,
    )
    print(manifest["combined_pdf"])
    print(manifest["contact_sheet"])
    print(manifest["manifest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
