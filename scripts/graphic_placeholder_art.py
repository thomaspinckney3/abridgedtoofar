"""Stand-in panel art that draws the layout's own figure and face boxes.

The point is to test the compositor and letterer without paying the image API.
Real art answers "did the model keep the reserved zone clear?"; this answers the
prior question, "does the pipeline itself put a balloon where it planned a
face?" — because the placeholder puts each face exactly where the layout said
it would be, at the size the art job asked for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

out_dir = Path(sys.argv[1])
storyboard = json.loads(Path(sys.argv[2]).read_text())
jobs = [json.loads(line) for line in Path(sys.argv[3]).read_text().splitlines() if line.strip()]
out_dir.mkdir(parents=True, exist_ok=True)

sizes = {job["out"]: job["size"] for job in jobs}
made = 0

for page in storyboard.get("pages") or []:
    for panel in page.get("panels") or []:
        name = panel.get("image")
        if not name or name not in sizes:
            continue
        width, height = (int(part) for part in sizes[name].split("x"))
        image = Image.new("RGB", (width, height), (214, 222, 230))
        draw = ImageDraw.Draw(image)

        # A horizon line, so crop-vs-contain fitting is visible at a glance.
        draw.rectangle([0, int(height * 0.62), width, height], fill=(196, 186, 168))

        layout = panel.get("thumbnail_layout") or {}
        for figure in layout.get("figures") or []:
            body = figure.get("body_box") or {}
            face = figure.get("face_box") or {}
            if body:
                draw.rectangle(
                    [body["x"] * width, body["y"] * height,
                     (body["x"] + body["w"]) * width, (body["y"] + body["h"]) * height],
                    fill=(120, 146, 178), outline=(40, 60, 90), width=3,
                )
            if face:
                # Magenta: if a balloon lands on this in the composed page, the
                # pipeline covered a face it planned itself.
                draw.rectangle(
                    [face["x"] * width, face["y"] * height,
                     (face["x"] + face["w"]) * width, (face["y"] + face["h"]) * height],
                    fill=(226, 62, 148), outline=(90, 20, 60), width=3,
                )
                draw.text((face["x"] * width + 6, face["y"] * height + 6),
                          str(figure.get("character") or "")[:18], fill=(255, 255, 255))

        image.save(out_dir / name)
        made += 1

print(f"wrote {made} placeholder panels to {out_dir}")
