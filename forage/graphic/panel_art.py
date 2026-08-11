"""Generate panel art from the prepared art-prompt jobs.

This is the step between planning a page and rendering it. `prepare_panel_art_
prompts` writes one job per panel — prompt, output filename, pixel size, quality
— and until now nothing in the repo consumed them; the jobs were handed to an
external image CLI, which is why a checkout has storyboards but no art.

Two properties matter more than speed here:

- **Resumable.** Image generation is the most expensive step in the pipeline, so
  a job whose file already exists is skipped. Re-running after a crash, or after
  regenerating three panels, costs only the missing panels.
- **Honest about failure.** A panel that fails is reported and left absent
  rather than substituted, because a silently missing panel becomes a blank
  rectangle in a finished page.

Quality defaults to `low`: panel art is iterated on constantly, and the layout
questions it answers — does the balloon cover the face, is the figure where the
layout staged it — are legible at low fidelity.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# The current image model. `gpt-image-2` is an alias for the dated snapshot, so
# pinning the alias picks up fixes without a code change.
DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_QUALITY = "low"
VALID_QUALITIES = ("low", "medium", "high", "auto")


@dataclass
class ArtJob:
    """One panel image to generate."""

    prompt: str
    out: str
    size: str = "1024x1024"
    quality: str = DEFAULT_QUALITY
    output_format: str = "png"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ArtJob":
        prompt = str(raw.get("prompt") or "").strip()
        out = str(raw.get("out") or "").strip()
        if not prompt or not out:
            raise ValueError(f"art job needs both 'prompt' and 'out': {raw!r}")
        quality = str(raw.get("quality") or DEFAULT_QUALITY).strip().lower()
        if quality not in VALID_QUALITIES:
            raise ValueError(f"invalid quality {quality!r} for {out}")
        return cls(
            prompt=prompt,
            out=out,
            size=str(raw.get("size") or "1024x1024"),
            quality=quality,
            output_format=str(raw.get("output_format") or "png"),
        )


@dataclass
class ArtReport:
    model: str
    generated: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "generated": self.generated,
            "skipped": self.skipped,
            "failed": self.failed,
            "counts": {
                "generated": len(self.generated),
                "skipped": len(self.skipped),
                "failed": len(self.failed),
            },
        }


def load_jobs(jobs_jsonl: Path) -> list[ArtJob]:
    """Read the JSONL written by the art-prompt stage."""
    jobs: list[ArtJob] = []
    for line_no, line in enumerate(
        jobs_jsonl.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            jobs.append(ArtJob.from_dict(json.loads(line)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{jobs_jsonl}:{line_no}: {exc}") from exc
    return jobs


def _openai_generator(model: str) -> Callable[[ArtJob], bytes]:
    """Return a callable that renders one job to image bytes."""
    import openai

    client = openai.OpenAI()

    def generate(job: ArtJob) -> bytes:
        response = client.images.generate(
            model=model,
            prompt=job.prompt,
            size=job.size,
            quality=job.quality,
            n=1,
        )
        payload = response.data[0]
        encoded = getattr(payload, "b64_json", None)
        if not encoded:
            raise RuntimeError(f"no image payload returned for {job.out}")
        return base64.b64decode(encoded)

    return generate


def generate_panel_art(
    jobs: list[ArtJob],
    out_dir: Path,
    *,
    model: str = DEFAULT_IMAGE_MODEL,
    quality: str | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
    generator: Callable[[ArtJob], bytes] | None = None,
) -> ArtReport:
    """Render each job to `out_dir`, skipping images that already exist.

    `generator` is injected by tests; production builds one bound to the image
    API. `dry_run` reports exactly what would be spent without spending it.
    """
    report = ArtReport(model=model)
    out_dir.mkdir(parents=True, exist_ok=True)

    pending: list[tuple[ArtJob, Path]] = []
    for job in jobs:
        target = out_dir / job.out
        if target.exists() and not overwrite:
            report.skipped.append({"out": job.out, "reason": "already generated"})
            continue
        pending.append((job, target))

    if dry_run or not pending:
        for job, _ in pending:
            report.generated.append({
                "out": job.out, "size": job.size,
                "quality": quality or job.quality, "dry_run": True,
            })
        return report

    render = generator or _openai_generator(model)
    for job, target in pending:
        effective = ArtJob(
            prompt=job.prompt, out=job.out, size=job.size,
            quality=quality or job.quality, output_format=job.output_format,
        )
        try:
            data = render(effective)
        except Exception as exc:  # noqa: BLE001 - reported, never substituted
            report.failed.append({"out": job.out, "error": f"{type(exc).__name__}: {exc}"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        report.generated.append({
            "out": job.out, "size": effective.size,
            "quality": effective.quality, "bytes": len(data),
        })
    return report


def estimate_cost(jobs: list[ArtJob], *, quality: str | None = None) -> dict[str, Any]:
    """Rough spend for a run, so a caller can be told before it is charged.

    Rates are per image from the published pricing table and vary with the long
    edge; anything unusual falls back to the square rate, which is the dearer of
    the two, so an estimate errs high rather than low.
    """
    rates = {
        "low": (0.006, 0.005),
        "medium": (0.053, 0.041),
        "high": (0.211, 0.165),
        "auto": (0.053, 0.041),
    }
    total = 0.0
    for job in jobs:
        tier = quality or job.quality
        square, oblong = rates.get(tier, rates["medium"])
        try:
            width, height = (int(v) for v in job.size.lower().split("x"))
        except ValueError:
            width = height = 1024
        total += square if width == height else oblong
    return {"images": len(jobs), "quality": quality, "estimated_usd": round(total, 4)}
