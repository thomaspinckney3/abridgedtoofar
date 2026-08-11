"""Tests for the panel-art generation stage.

No test here calls an image API — the generator is injected. What is worth
pinning is the spending behaviour: this is the most expensive step in the
pipeline, so "skip what already exists", "never substitute a failure", and
"report the bill before incurring it" are the properties that matter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forage.graphic.panel_art import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_QUALITY,
    ArtJob,
    estimate_cost,
    generate_panel_art,
    load_jobs,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"fake"


def _jobs(*names: str, quality: str = "low", size: str = "1024x1024") -> list[ArtJob]:
    return [
        ArtJob(prompt=f"a panel of {n}", out=n, size=size, quality=quality)
        for n in names
    ]


def _recorder():
    seen: list[str] = []

    def generate(job: ArtJob) -> bytes:
        seen.append(job.out)
        return PNG

    return generate, seen


def test_the_default_model_is_current_and_quality_is_low() -> None:
    assert DEFAULT_IMAGE_MODEL == "gpt-image-2"
    assert DEFAULT_QUALITY == "low"


# --- spending behaviour -----------------------------------------------------


def test_existing_images_are_not_regenerated(tmp_path: Path) -> None:
    """The resume property: rerunning after a crash pays only for what is
    missing, not for the whole page again."""
    (tmp_path / "a.png").write_bytes(PNG)
    generate, seen = _recorder()

    report = generate_panel_art(_jobs("a.png", "b.png"), tmp_path, generator=generate)

    assert seen == ["b.png"], "an existing panel must not be paid for twice"
    assert [s["out"] for s in report.skipped] == ["a.png"]
    assert [g["out"] for g in report.generated] == ["b.png"]


def test_overwrite_forces_regeneration(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(PNG)
    generate, seen = _recorder()

    generate_panel_art(_jobs("a.png"), tmp_path, generator=generate, overwrite=True)

    assert seen == ["a.png"]


def test_dry_run_spends_nothing(tmp_path: Path) -> None:
    generate, seen = _recorder()

    report = generate_panel_art(
        _jobs("a.png", "b.png"), tmp_path, generator=generate, dry_run=True
    )

    assert seen == []
    assert not list(tmp_path.glob("*.png"))
    assert all(entry["dry_run"] for entry in report.generated)


def test_a_failed_panel_is_reported_and_left_absent(tmp_path: Path) -> None:
    """A substituted or empty file becomes a blank rectangle in a finished page,
    so failure has to stay visible."""
    def generate(job: ArtJob) -> bytes:
        if job.out == "b.png":
            raise RuntimeError("content policy")
        return PNG

    report = generate_panel_art(_jobs("a.png", "b.png", "c.png"), tmp_path,
                                generator=generate)

    assert not (tmp_path / "b.png").exists()
    assert (tmp_path / "a.png").exists() and (tmp_path / "c.png").exists()
    assert [f["out"] for f in report.failed] == ["b.png"]
    assert "content policy" in report.failed[0]["error"]


def test_one_failure_does_not_abandon_the_rest(tmp_path: Path) -> None:
    def generate(job: ArtJob) -> bytes:
        if job.out == "a.png":
            raise RuntimeError("boom")
        return PNG

    report = generate_panel_art(_jobs("a.png", "b.png"), tmp_path, generator=generate)

    assert len(report.failed) == 1 and len(report.generated) == 1


def test_quality_override_applies_to_every_job(tmp_path: Path) -> None:
    seen: list[str] = []

    def generate(job: ArtJob) -> bytes:
        seen.append(job.quality)
        return PNG

    generate_panel_art(_jobs("a.png", "b.png", quality="high"), tmp_path,
                       generator=generate, quality="low")

    assert seen == ["low", "low"]


# --- cost estimation --------------------------------------------------------


def test_cost_is_estimated_before_spending() -> None:
    estimate = estimate_cost(_jobs("a.png", "b.png"), quality="low")

    assert estimate["images"] == 2
    assert estimate["estimated_usd"] == pytest.approx(0.012, abs=1e-6)


def test_higher_quality_costs_more() -> None:
    jobs = _jobs("a.png")
    low = estimate_cost(jobs, quality="low")["estimated_usd"]
    high = estimate_cost(jobs, quality="high")["estimated_usd"]

    assert high > low * 10


def test_an_unparseable_size_still_estimates() -> None:
    jobs = [ArtJob(prompt="p", out="a.png", size="not-a-size", quality="low")]

    assert estimate_cost(jobs)["estimated_usd"] > 0


# --- job loading ------------------------------------------------------------


def test_jobs_round_trip_from_the_prepare_stage(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    path.write_text(
        json.dumps({"prompt": "a dock at night", "out": "page_001_panel_001.png",
                    "size": "1536x1024", "quality": "low", "output_format": "png"})
        + "\n\n"  # blank lines are tolerated
    )

    jobs = load_jobs(path)

    assert len(jobs) == 1
    assert jobs[0].out == "page_001_panel_001.png"
    assert jobs[0].size == "1536x1024"


@pytest.mark.parametrize("bad", [
    {"out": "a.png"},                                  # no prompt
    {"prompt": "p"},                                   # no output name
    {"prompt": "p", "out": "a.png", "quality": "ultra"},  # unknown quality
])
def test_a_malformed_job_is_rejected_with_its_line_number(
    tmp_path: Path, bad: dict
) -> None:
    path = tmp_path / "jobs.jsonl"
    path.write_text(json.dumps(bad) + "\n")

    with pytest.raises(ValueError, match="jobs.jsonl:1"):
        load_jobs(path)
