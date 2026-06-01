"""Select the best available graphic-novel frame candidates using QA reports.

Usage:
  python -m scripts.graphic_select_candidate_frames \
      work/mobydick/graphic_novel/action_spine_v3/chapter_003 \
      --candidate initial:candidate_frames_initial:image_qa_report_initial.json \
      --candidate repair1:candidate_frames_repair1:image_qa_report_repaired.json \
      --candidate repair2:candidate_frames_repair2:image_qa_report_repaired_pass2.json

Each candidate is NAME:IMAGE_DIR:QA_REPORT. Relative paths are resolved under
RUN_DIR. The selected image for each frame is copied into selected_frames/ and
the selected per-frame QA records are written to image_qa_report_selected.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEVERITY_WEIGHTS = {
    "blocker": 100,
    "major": 10,
    "minor": 1,
}

CATEGORY_PENALTIES = {
    "readable_text": 50,
    "unsupported_content": 20,
    "literalized_metaphor": 20,
}


@dataclass(frozen=True)
class Candidate:
    name: str
    image_dir: Path
    report_path: Path
    order: int


def _resolve(run_dir: Path, path: str) -> Path:
    result = Path(path)
    if not result.is_absolute():
        result = run_dir / result
    return result


def _parse_candidate(run_dir: Path, raw: str, order: int) -> Candidate:
    parts = raw.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError(
            f"candidate must be NAME:IMAGE_DIR:QA_REPORT, got {raw!r}"
        )
    name, image_dir, report_path = parts
    return Candidate(
        name=name,
        image_dir=_resolve(run_dir, image_dir),
        report_path=_resolve(run_dir, report_path),
        order=order,
    )


def _score(frame_report: dict[str, Any]) -> tuple[int, int, int]:
    findings = [
        finding
        for finding in frame_report.get("findings", []) or []
        if isinstance(finding, dict)
    ]
    weighted_score = sum(
        SEVERITY_WEIGHTS.get(str(finding.get("severity", "")).lower(), 0)
        + CATEGORY_PENALTIES.get(str(finding.get("category", "")).lower(), 0)
        for finding in findings
    )
    severe_count = sum(
        1
        for finding in findings
        if str(finding.get("severity", "")).lower() in {"blocker", "major"}
    )
    return weighted_score, severe_count, len(findings)


def _load_reports(candidate: Candidate) -> dict[int, dict[str, Any]]:
    data = json.loads(candidate.report_path.read_text(encoding="utf-8"))
    reports: dict[int, dict[str, Any]] = {}
    for frame_report in data.get("frames", []) or []:
        if not isinstance(frame_report, dict):
            continue
        frame_no = int(frame_report.get("frame_number") or 0)
        if frame_no > 0:
            reports[frame_no] = frame_report
    return reports


def select_frames(
    run_dir: Path,
    *,
    candidates: list[Candidate],
    out_dir: Path | None = None,
    out_report: Path | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        raise ValueError("at least one candidate is required")
    out_dir = out_dir or run_dir / "selected_frames"
    out_report = out_report or run_dir / "image_qa_report_selected.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    reports_by_candidate = {
        candidate.name: _load_reports(candidate) for candidate in candidates
    }
    frame_numbers = sorted({
        frame_no
        for reports in reports_by_candidate.values()
        for frame_no in reports
    })

    selected: list[dict[str, Any]] = []
    selected_reports: list[dict[str, Any]] = []
    for frame_no in frame_numbers:
        available: list[tuple[tuple[int, int, int, int], Candidate, dict[str, Any]]] = []
        for candidate in candidates:
            frame_report = reports_by_candidate[candidate.name].get(frame_no)
            image_path = candidate.image_dir / f"frame_{frame_no:03d}.png"
            if frame_report is None or not image_path.exists():
                continue
            weighted_score, severe_count, finding_count = _score(frame_report)
            available.append(
                (
                    (weighted_score, severe_count, finding_count, candidate.order),
                    candidate,
                    frame_report,
                )
            )
        if not available:
            raise FileNotFoundError(f"no available candidate image/report for frame {frame_no}")
        key, candidate, frame_report = min(available, key=lambda item: item[0])
        source = candidate.image_dir / f"frame_{frame_no:03d}.png"
        target = out_dir / source.name
        shutil.copy2(source, target)
        frame_report = dict(frame_report)
        frame_report["selected_candidate"] = candidate.name
        frame_report["selection_score"] = {
            "weighted_score": key[0],
            "severe_count": key[1],
            "finding_count": key[2],
        }
        selected_reports.append(frame_report)
        selected.append({
            "frame_number": frame_no,
            "selected_candidate": candidate.name,
            "source_image": str(source),
            "selected_image": str(target),
            "weighted_score": key[0],
            "severe_count": key[1],
            "finding_count": key[2],
        })

    out_report.write_text(
        json.dumps({"frames": selected_reports}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "selection_manifest.json").write_text(
        json.dumps({"frames": selected}, indent=2) + "\n",
        encoding="utf-8",
    )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="Candidate as NAME:IMAGE_DIR:QA_REPORT. May be repeated.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for selected frame images. Defaults to RUN_DIR/selected_frames.",
    )
    parser.add_argument(
        "--out-report",
        type=Path,
        default=None,
        help="Selected QA report path. Defaults to RUN_DIR/image_qa_report_selected.json.",
    )
    args = parser.parse_args()
    candidates = [
        _parse_candidate(args.run_dir, raw, index)
        for index, raw in enumerate(args.candidate)
    ]
    selected = select_frames(
        args.run_dir,
        candidates=candidates,
        out_dir=args.out_dir,
        out_report=args.out_report,
    )
    for frame in selected:
        print(
            f"frame_{frame['frame_number']:03d}: "
            f"{frame['selected_candidate']} "
            f"score={frame['weighted_score']} severe={frame['severe_count']}"
        )


if __name__ == "__main__":
    main()
