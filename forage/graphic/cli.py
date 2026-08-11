"""`forage graphic` — the graphic-novel pipeline as commands.

Mounted onto the main app as a sub-command group, so the graphic stages are
discoverable the same way the prose stages are (`forage graphic --help`) rather
than living as loose `python -m scripts.*` invocations.

Commands are grouped by cost, and the help text says which is which: the
lettering and layout stages are free and deterministic, `art` is the one that
spends real money, and it refuses to do so without `--yes`.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from forage.artifacts import write_json
from forage.graphic.panel_art import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_QUALITY,
    VALID_QUALITIES,
    estimate_cost,
    generate_panel_art,
    load_jobs,
)

app = typer.Typer(
    name="graphic",
    help="Graphic-novel pipeline: layout, lettering, panel art, composition.",
    no_args_is_help=True,
)
console = Console()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def letter(
    storyboard: Path = typer.Argument(..., help="Storyboard JSON to letter."),
    out_json: Path = typer.Option(..., "--out-json", help="Where to write the result."),
    out_report: Path = typer.Option(None, "--out-report", help="Optional report path."),
) -> None:
    """Apply the deterministic lettering policy. Free, no LLM.

    Demotes unsafe balloons, splits over-long lines across linked balloons, and
    reports any line that still will not fit for `forage graphic summarize`.
    """
    from scripts.apply_graphic_lettering_policy import apply_lettering_policy

    data, report = apply_lettering_policy(_load(storyboard))
    write_json(out_json, data)
    if out_report:
        write_json(out_report, report)
    oversized = len(report.get("oversized_balloons") or [])
    console.print(
        f"lettered [bold]{len(report.get('changed_panels') or [])}[/] panels; "
        f"{oversized} line(s) still over budget"
    )


@app.command()
def layout(
    storyboard: Path = typer.Argument(..., help="Lettered storyboard JSON."),
    out_json: Path = typer.Option(..., "--out-json"),
    out_report: Path = typer.Option(None, "--out-report"),
    rough_dir: Path = typer.Option(None, "--rough-dir",
                                   help="Also write rough-in thumbnail PNGs here."),
) -> None:
    """Plan panel, balloon, figure and face boxes. Free, no LLM."""
    from scripts.apply_graphic_thumbnail_layout import (
        apply_thumbnail_layout,
        render_thumbnail_pages,
    )

    data, report = apply_thumbnail_layout(_load(storyboard))
    write_json(out_json, data)
    if out_report:
        write_json(out_report, report)
    if rough_dir:
        pages = render_thumbnail_pages(data, rough_dir)
        console.print(f"wrote {len(pages)} rough-in page(s) to {rough_dir}")
    warnings = report.get("warnings") or []
    console.print(
        f"laid out [bold]{report.get('panels_processed', 0)}[/] panel(s)"
        + (f"; [yellow]{len(warnings)} warning(s)[/]" if warnings else "")
    )


@app.command()
def art(
    jobs_jsonl: Path = typer.Argument(..., help="Jobs written by the art-prompt stage."),
    out_dir: Path = typer.Option(..., "--out-dir", help="Where panel images are written."),
    quality: str = typer.Option(DEFAULT_QUALITY, "--quality",
                                help=f"One of {', '.join(VALID_QUALITIES)}."),
    model: str = typer.Option(DEFAULT_IMAGE_MODEL, "--model"),
    overwrite: bool = typer.Option(False, "--overwrite",
                                   help="Regenerate images that already exist."),
    yes: bool = typer.Option(False, "--yes",
                             help="Confirm the spend. Without it this only estimates."),
    out_report: Path = typer.Option(None, "--out-report"),
) -> None:
    """Generate panel art. COSTS MONEY — estimates unless you pass --yes.

    Images that already exist are skipped, so re-running after a failure pays
    only for the panels still missing.
    """
    if quality not in VALID_QUALITIES:
        raise typer.BadParameter(f"quality must be one of {', '.join(VALID_QUALITIES)}")

    jobs = load_jobs(jobs_jsonl)
    pending = [job for job in jobs if not (out_dir / job.out).exists() or overwrite]
    estimate = estimate_cost(pending, quality=quality)

    table = Table(title="panel art")
    table.add_column("images to generate", justify="right")
    table.add_column("already present", justify="right")
    table.add_column("quality")
    table.add_column("estimated cost", justify="right")
    table.add_row(str(len(pending)), str(len(jobs) - len(pending)), quality,
                  f"${estimate['estimated_usd']:.4f}")
    console.print(table)

    if not yes:
        console.print("[yellow]estimate only — pass --yes to generate[/]")
        raise typer.Exit(0)

    report = generate_panel_art(jobs, out_dir, model=model, quality=quality,
                                overwrite=overwrite)
    if out_report:
        write_json(out_report, report.as_dict())
    counts = report.as_dict()["counts"]
    console.print(
        f"generated [bold]{counts['generated']}[/], skipped {counts['skipped']}, "
        f"[red]failed {counts['failed']}[/]" if counts["failed"]
        else f"generated [bold]{counts['generated']}[/], skipped {counts['skipped']}"
    )
    if report.failed:
        for failure in report.failed:
            console.print(f"  [red]{failure['out']}[/]: {failure['error']}")
        raise typer.Exit(1)


@app.command()
def summarize(
    storyboard: Path = typer.Argument(..., help="Lettered storyboard JSON."),
    book_id: str = typer.Option(..., "--book-id"),
    run_dir: Path = typer.Option(..., "--run-dir"),
    out_json: Path = typer.Option(..., "--out-json"),
    out_report: Path = typer.Option(None, "--out-report"),
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="List the lines that would be sent, and stop."),
) -> None:
    """Compress lines that cannot be split to fit. COSTS MONEY (one LLM call).

    Only lines that failed both lossless options reach this stage.
    """
    from scripts.graphic_balloon_summarize import collect_oversized, main as _main

    targets = collect_oversized(_load(storyboard))
    if not targets:
        console.print("nothing to compress — every line fits or splits")
        write_json(out_json, _load(storyboard))
        raise typer.Exit(0)
    console.print(f"{len(targets)} line(s) need compression")
    argv = [str(run_dir), "--book-id", book_id, "--storyboard-json", str(storyboard),
            "--out-json", str(out_json)]
    if out_report:
        argv += ["--out-report", str(out_report)]
    if dry_run:
        argv.append("--dry-run")
    import sys
    saved, sys.argv = sys.argv, ["graphic-summarize", *argv]
    try:
        _main()
    finally:
        sys.argv = saved
