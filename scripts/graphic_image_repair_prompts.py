"""Create image-regeneration prompts from graphic image QA findings.

Usage:
  python -m scripts.graphic_image_repair_prompts \
      work/mobydick/graphic_novel/action_spine_v3/chapter_003

Reads storyboard.json, image_prompts/frame_###.txt, and image_qa_report.json,
then writes repair_image_prompts/frame_###.txt for frames with major/blocker
findings by default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SEVERITIES = {"blocker", "major"}


def _findings_for_repair(
    findings: list[dict[str, Any]],
    severities: set[str],
) -> list[dict[str, Any]]:
    return [
        finding
        for finding in findings
        if str(finding.get("severity", "")).strip().lower() in severities
    ]


def write_repair_prompts(
    run_dir: Path,
    *,
    severities: set[str] = DEFAULT_SEVERITIES,
    out_dir: Path | None = None,
    report_path: Path | None = None,
) -> list[Path]:
    report_path = report_path or run_dir / "image_qa_report.json"
    prompt_dir = run_dir / "image_prompts"
    out_dir = out_dir or run_dir / "repair_image_prompts"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for frame_report in report.get("frames", []) or []:
        if not isinstance(frame_report, dict):
            continue
        frame_no = int(frame_report.get("frame_number") or 0)
        findings = _findings_for_repair(
            [
                finding
                for finding in frame_report.get("findings", []) or []
                if isinstance(finding, dict)
            ],
            severities,
        )
        if frame_no <= 0 or not findings:
            continue
        base_path = prompt_dir / f"frame_{frame_no:03d}.txt"
        base = base_path.read_text(encoding="utf-8")
        lines = [
            base.rstrip(),
            "",
            "QA repair requirements for this regeneration:",
        ]
        for index, finding in enumerate(findings, 1):
            lines.append(
                f"{index}. {finding.get('severity')} "
                f"{finding.get('category')}: {finding.get('finding')}"
            )
            visible = str(finding.get("visible_evidence", "")).strip()
            if visible:
                lines.append(f"   Visible failure to avoid: {visible}")
            repair = str(finding.get("repair_prompt", "")).strip()
            if repair:
                lines.append(f"   Repair instruction: {repair}")
        lines.append("")
        lines.append(
            "Regenerate the frame from scratch following the base prompt and "
            "all repair requirements. Keep the same story moment and style. "
            "No readable text, no captions, no speech balloons, no labels, "
            "and no watermark."
        )
        lines.append(
            "Do not introduce new violations while fixing the listed issues: "
            "preserve the requested caption zone as clean negative space, keep "
            "recurring characters and props consistent with the continuity "
            "notes, and omit optional background props when their exact form "
            "or placement is likely to cause confusion."
        )
        out_path = out_dir / f"frame_{frame_no:03d}.txt"
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        written.append(out_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--include-minor",
        action="store_true",
        help="Also generate repair prompts for minor findings.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="QA report to read. Defaults to RUN_DIR/image_qa_report.json.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for generated repair prompts. Defaults to RUN_DIR/repair_image_prompts.",
    )
    args = parser.parse_args()
    severities = set(DEFAULT_SEVERITIES)
    if args.include_minor:
        severities.add("minor")
    paths = write_repair_prompts(
        args.run_dir,
        severities=severities,
        out_dir=args.out_dir,
        report_path=args.report,
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
