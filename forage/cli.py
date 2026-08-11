"""Forage CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .artifacts import load_book, read_json
from .assemble import assemble_book
from .audiobook import (DEFAULT_MAX_CHARS, DEFAULT_MODEL,
                        DEFAULT_OUTPUT_FORMAT, AudiobookError,
                        generate_audiobook)
from .chapter_split import split_to_disk
from .critics import run_critic
from .drafter import draft_all, draft_segment, ensure_chapters
from .book_critic import run_book_critic
from .cache_audit import (audit_book_cache, audit_replay_cache_files,
                          summarize_stage_verdicts)
from .chapter_classifier import classify_chapters
from .coherence import run_coherence
from .coherence_adjudicate import run_coherence_adjudication
from .coherence_fix import run_coherence_fixes
from .cuts import generate_cuts
from .iterate import iterate_segment
from .lean_plan import build_lean_plan
from .llm import set_stream_sink
from .name_lint import run_name_lint
from .report import (COLUMNS, available_books, build_report, format_row)
from .summarizer import summarize_book
from .prepass import run_prepass
from .prime import run_prime
from .rebudget import rebudget
from .reconsider import reconsider_segment
from .review_apply import apply_review_feedback
from .validate import validate_book

load_dotenv()

app = typer.Typer(
    name="forage",
    help="Faithful book abridgment pipeline.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

# Graphic-novel stages live in their own group so `forage graphic --help` maps
# that pipeline without crowding the prose commands.
from .graphic.cli import app as _graphic_app  # noqa: E402

app.add_typer(_graphic_app, name="graphic")


@app.command()
def split(book_id: str) -> None:
    """Deterministically split the source into chapters via heuristics.
    Writes work/<book>/chapters.json + chapters/NNN.md. Zero LLM cost."""
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    console.print("[bold]splitting...[/bold]")
    chapters = split_to_disk(book)
    from collections import Counter
    kinds = Counter(c.kind for c in chapters)
    total_w = sum(len(c.text.split()) for c in chapters)
    header = Table.grid(padding=(0, 1))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("chapters", str(len(chapters)))
    header.add_row("total_words", str(total_w))
    header.add_row("kinds", ", ".join(f"{k}={v}" for k, v in kinds.items()))
    console.print(Panel(header, title="split"))
    t = Table()
    t.add_column("id")
    t.add_column("kind", width=10)
    t.add_column("num", width=6)
    t.add_column("title", max_width=40)
    t.add_column("words", justify="right")
    for c in chapters:
        t.add_row(c.id, c.kind, str(c.number or "—"),
                  c.title[:40] or "—", str(len(c.text.split())))
    console.print(t)


@app.command()
def prime(
    book_id: str,
    search: bool = typer.Option(
        False, "--search/--no-search",
        help="Let Claude use the web_search tool to ground signatures in published criticism."),
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run the prime stage: surface example signature passages from the book.
    Writes work/<book-id>/prime.json, which the pre-pass picks up as a seed.

    With --search, Claude uses web_search to ground critical/cultural signatures
    in actual published criticism. Adds ~$0.10-0.20 per book in search + tokens.
    """
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    console.print(f"[dim]work:  [/dim] {book.work_dir}")
    console.print(f"[bold]running prime{' with web_search' if search else ''}...[/bold]")
    if stream:
        console.rule("[dim]raw stream[/dim]")
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)
    data = run_prime(book, search=search)
    if stream:
        sys.stdout.write("\n")
    _render_prime(data)


def _render_prime(data: dict) -> None:
    console.rule(f"[bold]prime examples ({len(data.get('examples', []))})[/bold]")
    for ex in data.get("examples", []):
        console.print(
            f"  [{ex.get('origin','?')}/{ex.get('category','?')}] "
            f"[dim]({ex.get('segment_hint','?')})[/dim] "
            f"{ex.get('passage_hint','')[:100]}"
        )
    if data.get("notes"):
        console.print(Panel(data["notes"], title="notes"))


@app.command()
def prepass(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run the pre-pass stage on BOOK_ID and print the resulting plan."""
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    console.print(f"[dim]work:  [/dim] {book.work_dir}")
    console.print("[bold]running pre-pass...[/bold]")
    if stream:
        console.rule("[dim]raw stream[/dim]")
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)
    plan = run_prepass(book)
    if stream:
        sys.stdout.write("\n")
        console.rule("[dim]parsed plan[/dim]")
    _render_plan(plan)


@app.command()
def classify(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run the LLM chapter classifier on BOOK_ID. Decides which candidate
    segments from the splitter are diegetic (keep) vs extradiegetic (cut).
    Writes work/<book>/chapter_classifications.json. The lean planner reads
    this file to override its kind-based heuristic when present.
    """
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk); sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    result = classify_chapters(book)
    if stream:
        sys.stdout.write("\n")
    from collections import Counter
    counts = Counter(v["status"] for v in result.values())
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim"); tally.add_column()
    tally.add_row("candidates", str(len(result)))
    for s in ("diegetic", "extradiegetic", "toc_fragment", "cut_for_review"):
        if counts.get(s):
            tally.add_row(s, str(counts[s]))
    console.print(Panel(tally, title="classify"))
    non_d = [(cid, v) for cid, v in sorted(result.items())
             if v["status"] != "diegetic"]
    if non_d:
        t = Table(title="non-diegetic candidates", show_lines=False)
        t.add_column("id"); t.add_column("status"); t.add_column("reason")
        for cid, v in non_d:
            t.add_row(cid, v["status"], (v.get("reason") or "")[:60])
        console.print(t)


@app.command()
def summarize(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Produce a 15-sentence book synopsis used as ground truth by the
    book-level critic. Uses chunked chaining (partial synopses + merge) for
    books that exceed GPT-5's input context.
    Writes work/<book>/book_synopsis.md.
    """
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk); sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    text = summarize_book(book)
    if stream:
        sys.stdout.write("\n")
    console.rule("[bold]synopsis[/bold]")
    console.print(text)


@app.command(name="book-critique")
def book_critique_cmd(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Verify each synopsis sentence against the assembled abridgment.
    Reads work/<book>/book_synopsis.md and either `abridgment.md` (if
    present) or a concatenation of `segments/NNN.md` (partial mode).
    Writes work/<book>/book_critic.json.
    """
    book = load_book(book_id)
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk); sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    result = run_book_critic(book)
    if stream:
        sys.stdout.write("\n")
    color = "green" if result["verdict"] == "ship" else "red"
    console.rule(f"[bold {color}]book critic: {result['verdict'].upper()}"
                 + (" [PARTIAL]" if result.get("is_partial") else "")
                 + f"[/bold {color}]")
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim"); tally.add_column()
    tally.add_row("sentences", str(result["synopsis_sentence_count"]))
    for k, v in result["counts"].items():
        tally.add_row(k, str(v))
    console.print(Panel(tally, title="counts"))
    t = Table(title="per-sentence verdicts", show_lines=False)
    t.add_column("#", width=3)
    t.add_column("status", width=10)
    t.add_column("note / evidence", max_width=90)
    sev_color = {"present": "green", "missing": "red", "distorted": "yellow"}
    for f in result["findings"]:
        s = f.get("status", "?")
        line = (f.get("note") or f.get("evidence", ""))[:200]
        t.add_row(str(f.get("sentence", "?")),
                  f"[{sev_color.get(s, 'white')}]{s}[/{sev_color.get(s, 'white')}]",
                  line)
    console.print(t)


@app.command()
def plan(book_id: str) -> None:
    """Build a deterministic lean plan (no LLM unless classify step has been
    run): chapter splits + proportional per-chapter targets derived from the
    book-level compression formula. Picks up `chapter_classifications.json`
    if `forage classify` has been run for this book.
    Writes work/<book>/plan.json.
    """
    book = load_book(book_id)
    console.print(f"[dim]source:[/dim] {book.source_path}")
    console.print("[bold]building lean plan...[/bold]")
    plan = build_lean_plan(book)
    _render_plan(plan)


@app.command()
def show(book_id: str) -> None:
    """Show the current plan for BOOK_ID."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red] — run `forage plan {book_id}` (lean, free) or `forage prepass {book_id}` (LLM) first")
        raise typer.Exit(code=1)
    plan = json.loads(plan_path.read_text())
    _render_plan(plan)


def _render_plan(plan: dict) -> None:
    if plan.get("refusal"):
        r = plan["refusal"]
        console.print(Panel(
            f"[bold red]REFUSED[/bold red]\n{r.get('reason')}\n{r.get('detail', '')}",
            title=plan.get("book_id", "?"),
        ))
        return

    meta = plan.get("_meta", {}).get("computed", {})
    header = Table.grid(padding=(0, 1))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("book_id", plan.get("book_id", "?"))
    header.add_row("title", str(plan.get("title", "?")))
    header.add_row("author", str(plan.get("author", "?")))
    header.add_row("structural_classification", str(plan.get("structural_classification", "?")))
    header.add_row("modernization_level", str(plan.get("modernization_level", "?")))
    header.add_row("cultural_depth", str(plan.get("cultural_depth", "?")))
    header.add_row("source_words", str(meta.get("source_word_count", "?")))
    header.add_row("target_words", str(meta.get("target_word_count", "?")))
    header.add_row("target_hours", str(meta.get("target_hours", "?")))
    header.add_row("ratio", str(meta.get("overall_compression_ratio", "?")))
    header.add_row("segments", str(len(plan.get("segments", []))))
    header.add_row("motifs", str(len(plan.get("motifs", []))))
    console.print(Panel(header, title="plan"))

    segs = plan.get("segments", [])
    if segs:
        t = Table(title="segments", show_lines=False)
        t.add_column("id")
        t.add_column("title", max_width=40)
        t.add_column("role")
        t.add_column("diegetic")
        t.add_column("src", justify="right")
        t.add_column("tgt", justify="right")
        t.add_column("rel", justify="right")
        t.add_column("sigs", justify="right")
        for s in segs:
            t.add_row(
                str(s.get("id", "?")),
                str(s.get("title", ""))[:60],
                str(s.get("role", "")),
                str(s.get("diegetic_status", "")),
                str(s.get("source_word_count_est", "")),
                str(s.get("target_word_count", "")),
                f"{s.get('relative_compression', ''):.2f}" if isinstance(s.get("relative_compression"), (int, float)) else "",
                str(len(s.get("signatures", []))),
            )
        console.print(t)

    motifs = plan.get("motifs", [])
    if motifs:
        m = Table(title="motifs")
        m.add_column("name")
        m.add_column("description", max_width=80)
        for mo in motifs:
            m.add_row(str(mo.get("name", "")), str(mo.get("description", "")))
        console.print(m)

    if plan.get("plan_notes"):
        console.print(Panel(plan["plan_notes"], title="plan_notes"))


@app.command()
def draft(
    book_id: str,
    segment: str = typer.Option(None, help="Segment id (e.g. 002) — omit to draft all."),
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Draft one or all segments of BOOK_ID from its plan.json."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red] — run `forage plan {book_id}` (lean, free) or `forage prepass {book_id}` (LLM) first")
        raise typer.Exit(code=1)
    plan = read_json(plan_path)

    console.print("[bold]ensuring chapter split...[/bold]")
    manifest = ensure_chapters(book)
    console.print(f"[dim]{manifest['total_chapters']} chapters; {manifest['total_words']} words[/dim]")

    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)

    if segment is not None:
        _run_one(book, plan, segment, stream=stream)
    else:
        for s in plan["segments"]:
            _run_one(book, plan, s["id"], stream=stream)


def _run_one(book, plan, segment_id: str, *, stream: bool) -> None:
    seg = next((s for s in plan["segments"] if s["id"] == segment_id), None)
    title = seg.get("title", "?") if seg else "?"
    console.rule(f"[bold]{segment_id}[/bold] — {title}")
    if stream:
        console.rule("[dim]raw stream[/dim]")
    result = draft_segment(book, plan, segment_id)
    if stream:
        sys.stdout.write("\n")
    _render_draft(result)


def _render_draft(r) -> None:
    style = {
        "drafted": "green", "cut": "yellow",
        "skipped_extract_fail": "red", "error": "red",
    }.get(r.status, "white")
    header = Table.grid(padding=(0, 1))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("segment", r.segment_id)
    header.add_row("title", r.title)
    header.add_row("status", f"[{style}]{r.status}[/{style}]")
    header.add_row("source_words", str(r.source_words))
    header.add_row("target_words", str(r.target_words))
    header.add_row("draft_words", str(r.draft_words))
    if r.target_words:
        delta = (r.draft_words - r.target_words) / r.target_words * 100
        header.add_row("delta", f"{delta:+.1f}%")
    header.add_row("signatures",
                   f"{r.signature_hits}/{r.signature_hits + len(r.signature_misses)} matched")
    if r.signature_misses:
        ambig = sum(1 for m in r.signature_misses if m.get("ambiguous"))
        lines = [f"[{m['score']}] {m['hint'][:50]}" for m in r.signature_misses[:3]]
        header.add_row("missed", "; ".join(lines) + (f" ({ambig} ambig)" if ambig else ""))
    if r.message:
        header.add_row("note", r.message)
    console.print(Panel(header, title=f"draft {r.segment_id}"))


@app.command()
def iterate(
    book_id: str,
    segment: str = typer.Argument(..., help="Segment id, e.g. 002"),
    max_retries: int = typer.Option(1, help="Max regeneration attempts."),
    redraft_first: bool = typer.Option(False, "--redraft-first",
                                       help="Re-draft from scratch before the first critic pass."),
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run the draft → critique → regenerate loop until the critic passes or
    the retry budget is exhausted."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red] — run `forage plan {book_id}` (lean, free) or `forage prepass {book_id}` (LLM) first")
        raise typer.Exit(code=1)
    plan = read_json(plan_path)
    ensure_chapters(book)

    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)

    console.rule(f"[bold]iterate {book_id}/{segment}[/bold]")
    result = iterate_segment(book, plan, segment,
                             max_retries=max_retries,
                             redraft_first=redraft_first)
    if stream:
        sys.stdout.write("\n")

    _render_iterate(result)


def _render_iterate(r) -> None:
    color = "green" if r.final_verdict == "pass" else "red"
    console.rule(f"[bold {color}]iteration {r.final_verdict.upper()}[/bold {color}]"
                 + (" (budget exhausted)" if r.exhausted else ""))
    t = Table(show_lines=False)
    t.add_column("#", width=3)
    t.add_column("kind", width=8)
    t.add_column("summary")
    for i, step in enumerate(r.steps, 1):
        t.add_row(str(i), step.kind, step.summary)
    console.print(t)


@app.command()
def critique(
    book_id: str,
    segment: str = typer.Argument(..., help="Segment id, e.g. 002"),
    critic: str = typer.Option("signature", help="Critic name (signature is the only one wired for now)."),
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run an adversarial critic on a segment's draft. Writes findings to
    work/<book>/segments/NNN.critic_<name>.json."""
    book = load_book(book_id)
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule(f"[dim]{critic} critic — {book_id}/{segment}[/dim]")
    result = run_critic(book, segment, critic)
    if stream:
        sys.stdout.write("\n")
    _render_critic(result)


def _render_critic(r) -> None:
    color = "green" if r.verdict == "pass" else "red"
    console.rule(f"[bold {color}]{r.critic} critic: {r.verdict}[/bold {color}]")
    if r.summary:
        console.print(f"[dim]summary:[/dim] {r.summary}")
    if not r.findings:
        console.print("[dim]no findings[/dim]")
        return
    t = Table(show_lines=True)
    t.add_column("sev", width=6)
    t.add_column("class", width=22)
    t.add_column("source", max_width=50)
    t.add_column("treatment", width=12)
    t.add_column("suggested fix", max_width=50)
    sev_color = {"high": "red", "medium": "yellow", "low": "dim"}
    for f in r.findings:
        s = f.get("severity", "?")
        t.add_row(
            f"[{sev_color.get(s, 'white')}]{s}[/{sev_color.get(s, 'white')}]",
            f.get("class", ""),
            (f.get("source_passage", "") or "")[:200],
            f.get("draft_treatment", ""),
            (f.get("suggested_fix", "") or "")[:200],
        )
    console.print(t)


@app.command()
def reconsider(
    book_id: str,
    segment: str = typer.Argument(..., help="Segment id, e.g. 002"),
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Re-identify signatures for one segment (cheap; doesn't touch plan.json)."""
    book = load_book(book_id)
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    result = reconsider_segment(book, segment)
    if stream:
        sys.stdout.write("\n")
    diff_path = book.work_dir / "segments" / f"{segment}.signatures.json"
    diff = json.loads(diff_path.read_text())
    _render_signature_diff(segment, diff)


def _render_signature_diff(segment_id: str, diff: dict) -> None:
    prev = diff["previous"]
    new = diff["new"]
    console.rule(f"[bold]signatures for {segment_id}[/bold]")
    console.print(f"[dim]role:[/dim]  {diff['role_previous']} → {diff['role_new']}")
    console.print(f"[bold]previous ({len(prev)})[/bold]")
    for s in prev:
        console.print(f"  [{s.get('origin')}/{s.get('category')}] {s.get('passage_hint', '')[:90]}")
    console.print(f"[bold]new ({len(new)})[/bold]")
    for s in new:
        console.print(f"  [{s.get('origin')}/{s.get('category')}] {s.get('passage_hint', '')[:90]}")
    if diff.get("notes_new"):
        console.print(Panel(diff["notes_new"], title="new notes"))


@app.command()
def assemble(book_id: str) -> None:
    """Concatenate drafted segments into final book artifacts and write
    assembly_report.json with budget stats. Always emits when content exists;
    budget adherence is reported (overage %, over_target, over_ceiling flags)
    but does not gate output."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red]")
        raise typer.Exit(code=1)
    plan = read_json(plan_path)
    result = assemble_book(book, plan)
    _render_assembly(result)


def _render_assembly(r) -> None:
    status = ("[red]OVER CEILING[/red]" if r.over_ceiling
              else "[yellow]OVER TARGET[/yellow]" if r.over_budget
              else "[green]WITHIN BUDGET[/green]")
    # Status is informational only now; final artifacts are emitted whenever
    # drafted content exists.
    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row("book_id", r.book_id)
    summary.add_row("book_target", f"{r.book_target}")
    summary.add_row("book_ceiling (+20%)", f"{r.book_ceiling}")
    summary.add_row("total_drafted", f"{r.total_drafted}")
    if r.book_target:
        delta = (r.total_drafted - r.book_target) / r.book_target * 100
        summary.add_row("delta vs target", f"{delta:+.1f}%")
    summary.add_row("status", status)
    summary.add_row("segments_drafted", f"{r.segments_drafted}/{r.segments_total}")
    summary.add_row("segments_cut", f"{r.segments_cut}")
    summary.add_row("segments_missing", f"{r.segments_missing}")
    if getattr(r, "plain_text_path", None):
        summary.add_row("plain_text", str(r.plain_text_path))
    if getattr(r, "published_plain_text_path", None):
        summary.add_row("published_text", str(r.published_plain_text_path))
    console.print(Panel(summary, title="assembly"))

    if r.segments_missing or r.total_drafted > r.book_target:
        t = Table(title="segments (drafted, over-budget first)", show_lines=False)
        t.add_column("id")
        t.add_column("title", max_width=36)
        t.add_column("role")
        t.add_column("tgt", justify="right")
        t.add_column("got", justify="right")
        t.add_column("Δ%", justify="right")
        t.add_column("status")
        drafted = [s for s in r.per_segment if s.status == "drafted"]
        drafted.sort(key=lambda s: -(
            (s.drafted - s.target) / s.target if s.target else 0))
        for s in drafted[:30]:
            d = (s.drafted - s.target) / s.target * 100 if s.target else 0
            t.add_row(s.id, s.title[:36], s.role, str(s.target),
                      str(s.drafted), f"{d:+.0f}", s.status)
        missing = [s for s in r.per_segment if s.status != "drafted"]
        if missing:
            t.add_section()
            for s in missing[:10]:
                t.add_row(s.id, s.title[:36], s.role, str(s.target),
                          "—", "—", s.status)
        console.print(t)


@app.command()
def audiobook(
    book_id: str,
    voice_id: str | None = typer.Option(
        None, "--voice-id",
        help="ElevenLabs voice id. Overrides books/<book>/metadata.json.",
    ),
    input_path: Path | None = typer.Option(
        None, "--input",
        help="Text file to narrate. Defaults to books/<book>/abridgment.txt.",
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir",
        help="Output directory. Defaults to work/<book>/audiobook/.",
    ),
    model: str | None = typer.Option(
        None, "--model",
        help="ElevenLabs model id. Defaults to metadata audiobook.model, "
             f"FORAGE_AUDIOBOOK_MODEL, or {DEFAULT_MODEL}.",
    ),
    output_format: str | None = typer.Option(
        None, "--output-format",
        help="ElevenLabs output format. Defaults to metadata "
             "audiobook.output_format, FORAGE_AUDIOBOOK_OUTPUT_FORMAT, or "
             f"{DEFAULT_OUTPUT_FORMAT}.",
    ),
    max_chars: int | None = typer.Option(
        None, "--max-chars",
        help="Maximum text characters per API request. Defaults to metadata "
             "audiobook.max_chars, FORAGE_AUDIOBOOK_MAX_CHARS, or 9000.",
    ),
    context_chars: int | None = typer.Option(
        None, "--context-chars",
        help="Neighbor text sent for cross-chunk prosody context. Defaults to "
             "metadata audiobook.context_chars or 1200.",
    ),
    stability: float | None = typer.Option(
        None, "--stability",
        help="Optional ElevenLabs voice stability setting.",
    ),
    similarity_boost: float | None = typer.Option(
        None, "--similarity-boost",
        help="Optional ElevenLabs similarity_boost setting.",
    ),
    style: float | None = typer.Option(
        None, "--style",
        help="Optional ElevenLabs style setting.",
    ),
    speed: float | None = typer.Option(
        None, "--speed",
        help="Optional ElevenLabs speed setting.",
    ),
    speaker_boost: bool = typer.Option(
        True, "--speaker-boost/--no-speaker-boost",
        help="Send use_speaker_boost in voice settings.",
    ),
    seed: int | None = typer.Option(
        None, "--seed",
        help="Optional deterministic generation seed.",
    ),
    language_code: str | None = typer.Option(
        None, "--language-code",
        help="Optional language code for multilingual models.",
    ),
    text_normalization: str = typer.Option(
        "auto", "--text-normalization",
        help="ElevenLabs apply_text_normalization value.",
    ),
    enable_logging: bool = typer.Option(
        True, "--enable-logging/--zero-retention",
        help="Disable logging only for accounts that support zero retention; "
             "request-id stitching is disabled with --zero-retention.",
    ),
    stitch: bool = typer.Option(
        True, "--stitch/--no-stitch",
        help="Send neighboring text and prior request ids for long-form flow.",
    ),
    combine: bool = typer.Option(
        True, "--combine/--no-combine",
        help="Use ffmpeg to concatenate generated MP3 chunks when available.",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite",
        help="Regenerate chunk audio even if files already exist.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Write chunk text and manifest without calling ElevenLabs.",
    ),
    limit: int | None = typer.Option(
        None, "--limit",
        help="Generate only the first N chunks; useful for paid smoke tests.",
    ),
    timeout: float = typer.Option(
        120.0, "--timeout",
        help="Per-request timeout in seconds.",
    ),
    retries: int = typer.Option(
        2, "--retries",
        help="Retries for 429/5xx and transient network failures.",
    ),
) -> None:
    """Generate an ElevenLabs audiobook from an assembled abridgment.

    Outputs chunk text, per-chunk audio, and audiobook_manifest.json under
    work/<book>/audiobook/. For MP3 output, --combine also publishes
    books/<book>/audiobook.mp3 when ffmpeg is available.
    """
    book = load_book(book_id)
    try:
        config = _audiobook_config(book.metadata)
    except AudiobookError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    settings = _voice_settings(
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
        speed=speed,
        speaker_boost=speaker_boost,
    )
    try:
        resolved_voice = voice_id or config.get("voice_id")
        resolved_model = (
            model
            or config.get("model")
            or os.environ.get("FORAGE_AUDIOBOOK_MODEL")
            or DEFAULT_MODEL
        )
        resolved_format = (
            output_format
            or config.get("output_format")
            or os.environ.get("FORAGE_AUDIOBOOK_OUTPUT_FORMAT")
            or DEFAULT_OUTPUT_FORMAT
        )
        resolved_max_chars = (
            max_chars
            or _int_config(config.get("max_chars"), "audiobook.max_chars")
            or _int_env("FORAGE_AUDIOBOOK_MAX_CHARS", DEFAULT_MAX_CHARS)
        )
        resolved_context_chars = (
            context_chars
            if context_chars is not None
            else _int_config(
                config.get("context_chars"), "audiobook.context_chars"
            )
            or 1200
        )
    except AudiobookError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[dim]source:[/dim] {input_path or 'abridgment.txt'}")
    console.print(f"[dim]voice: [/dim] {resolved_voice or 'unset'}")
    console.print(f"[dim]model: [/dim] {resolved_model}")
    try:
        result = generate_audiobook(
            book,
            voice_id=resolved_voice,
            input_path=input_path,
            output_dir=output_dir,
            model_id=resolved_model,
            output_format=resolved_format,
            max_chars=resolved_max_chars,
            context_chars=resolved_context_chars,
            voice_settings=settings,
            seed=seed,
            language_code=language_code,
            apply_text_normalization=text_normalization,
            enable_logging=enable_logging,
            stitch=stitch,
            combine=combine,
            overwrite=overwrite,
            dry_run=dry_run,
            limit=limit,
            timeout=timeout,
            retries=retries,
        )
    except AudiobookError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    _render_audiobook(result, dry_run=dry_run)
    if result.error_count:
        raise typer.Exit(code=1)


def _audiobook_config(metadata: dict) -> dict:
    raw = metadata.get("audiobook") or {}
    if not isinstance(raw, dict):
        raise AudiobookError("metadata field 'audiobook' must be an object")
    return raw


def _int_config(value, field: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise AudiobookError(f"metadata field {field} must be an integer") from e


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as e:
        raise AudiobookError(f"environment variable {name} must be an integer") from e


def _voice_settings(
    *,
    stability: float | None,
    similarity_boost: float | None,
    style: float | None,
    speed: float | None,
    speaker_boost: bool,
) -> dict | None:
    settings: dict[str, float | bool] = {"use_speaker_boost": speaker_boost}
    if stability is not None:
        settings["stability"] = stability
    if similarity_boost is not None:
        settings["similarity_boost"] = similarity_boost
    if style is not None:
        settings["style"] = style
    if speed is not None:
        settings["speed"] = speed
    return settings


def _render_audiobook(r, *, dry_run: bool) -> None:
    title = "audiobook dry run" if dry_run else "audiobook"
    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row("book_id", r.book_id)
    summary.add_row("source", str(r.source_path))
    summary.add_row("output", str(r.output_dir))
    summary.add_row("manifest", str(r.manifest_path))
    summary.add_row("chunks", str(r.chunk_count))
    summary.add_row("characters", str(r.total_chars))
    summary.add_row("generated", str(r.generated_count))
    summary.add_row("skipped", str(r.skipped_count))
    summary.add_row("planned", str(r.planned_count))
    summary.add_row("errors", str(r.error_count))
    if r.combined_audio_path:
        summary.add_row("combined_audio", str(r.combined_audio_path))
    if r.published_audio_path:
        summary.add_row("published_audio", str(r.published_audio_path))
    console.print(Panel(summary, title=title))


@app.command(name="rebudget")
def rebudget_cmd(
    book_id: str,
    apply: bool = typer.Option(True, "--apply/--dry-run",
                               help="Write new targets to plan.json (default) or just report."),
) -> None:
    """Reallocate per-segment targets so the book total hits book_target."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red]")
        raise typer.Exit(code=1)
    plan = read_json(plan_path)
    assembly = assemble_book(book, plan)
    result = rebudget(book, plan, assembly, apply=apply)
    _render_rebudget(result)


def _render_rebudget(r) -> None:
    header = Table.grid(padding=(0, 1))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("book_id", r.book_id)
    header.add_row("book_target", str(r.book_target))
    header.add_row("total_before", str(r.total_before))
    header.add_row("total_after_target", str(r.total_after_target))
    header.add_row("applied", str(r.applied))
    header.add_row("reason", r.reason)
    console.print(Panel(header, title="rebudget"))

    to_redraft = [x for x in r.reallocations if x.needs_redraft]
    if to_redraft:
        t = Table(title="segments needing redraft")
        t.add_column("id")
        t.add_column("title", max_width=36)
        t.add_column("old tgt", justify="right")
        t.add_column("got", justify="right")
        t.add_column("new tgt", justify="right")
        for x in to_redraft:
            t.add_row(x.id, x.title[:36], str(x.old_target),
                      str(x.draft_words), str(x.new_target))
        console.print(t)


@app.command()
def cuts(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Produce a 'cuts inventory' identifying removable characters,
    subplots, and digressions. Inverse framing of signature preservation —
    enumerates what can be cut rather than what must be kept. Writes
    work/<book>/cuts.json. Pulls in book_synopsis.md as an authoritative
    shape-of-the-book anchor if present.
    """
    book = load_book(book_id)
    console.print(f"[dim]book:[/dim] {book.book_id}")
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk); sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    data = generate_cuts(book)
    if stream:
        sys.stdout.write("\n")
    # Summary counts.
    console.rule("[bold]cuts inventory[/bold]")
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim"); tally.add_column()
    tally.add_row("minor_characters", str(len(data.get("minor_characters", []))))
    tally.add_row("subplots", str(len(data.get("subplots", []))))
    tally.add_row("digressions", str(len(data.get("digressions", []))))
    console.print(Panel(tally, title="counts"))
    if data.get("minor_characters"):
        t = Table(title="minor characters", show_lines=False)
        t.add_column("name"); t.add_column("appearances", max_width=35)
        t.add_column("reason removable", max_width=60)
        for c in data["minor_characters"]:
            t.add_row(c.get("name", ""),
                      c.get("appearances_summary", "")[:100],
                      c.get("reason_removable", "")[:120])
        console.print(t)
    if data.get("subplots"):
        t = Table(title="subplots", show_lines=False)
        t.add_column("name", max_width=40); t.add_column("chapter span", width=16)
        t.add_column("reason removable", max_width=60)
        for s in data["subplots"]:
            t.add_row(s.get("name", "")[:80],
                      s.get("chapter_span", "")[:20],
                      s.get("reason_removable", "")[:120])
        console.print(t)
    if data.get("digressions"):
        t = Table(title="digressions", show_lines=False)
        t.add_column("chapters", width=14); t.add_column("topic", max_width=40)
        t.add_column("reason removable", max_width=60)
        for d in data["digressions"]:
            chs = ",".join(d.get("chapter_ids", []))
            t.add_row(chs[:16], d.get("topic", "")[:60],
                      d.get("reason_removable", "")[:120])
        console.print(t)


@app.command(name="name-lint")
def name_lint_cmd(
    book_id: str,
    long_gap_segments: int = typer.Option(
        2,
        help="Require a fresh local gloss after more than this many segments."),
    long_gap_words: int = typer.Option(
        2500,
        help="Require a fresh local gloss after more than this many words."),
) -> None:
    """Mechanically flag minor/cut proper names whose first surviving mention
    or long-gap re-entry lacks a local role/relationship gloss. Writes
    work/<book>/name_lint_report.json.
    """
    book = load_book(book_id)
    report = run_name_lint(
        book,
        long_gap_segments=long_gap_segments,
        long_gap_words=long_gap_words,
    )
    console.rule(f"[bold]name-lint: {report['findings_total']} findings[/bold]")
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim")
    tally.add_column()
    tally.add_row("segments_checked", str(report["segments_checked"]))
    tally.add_row("names_checked", str(report["names_checked"]))
    tally.add_row("aliases_checked", str(report["aliases_checked"]))
    tally.add_row("long_gap_segments", str(report["long_gap_segments"]))
    tally.add_row("long_gap_words", str(report["long_gap_words"]))
    console.print(Panel(tally, title="counts"))
    if not report["findings"]:
        console.print("[green]no orphaned minor-character names detected[/green]")
        return

    table = Table(show_lines=True)
    table.add_column("seg")
    table.add_column("line", justify="right")
    table.add_column("name")
    table.add_column("type", width=16)
    table.add_column("passage", max_width=80)
    for finding in report["findings"]:
        table.add_row(
            str(finding.get("segment_id", "?")),
            str(finding.get("line", "?")),
            str(finding.get("alias") or finding.get("name") or "?"),
            str(finding.get("occurrence_type", "")),
            str(finding.get("draft_passage", ""))[:220],
        )
    console.print(table)


@app.command(name="prepare-skips")
def prepare_skips_cmd(book_id: str) -> None:
    """Apply cuts.json's `skippable_chapters` directives to the source.
    Inserts kernel paragraphs into target chapters and zeros target_word_count
    on skipped chapters. Backs up modified sources as `<id>.md.orig`. Free —
    no LLM calls."""
    from .prepare_skips import apply_skips
    book = load_book(book_id)
    summary = apply_skips(book)
    console.rule(f"[bold]prepare-skips {book_id}[/bold]")
    console.print(f"chapters skipped (target=0): {len(summary.skipped)}")
    if summary.skipped:
        console.print(f"  {', '.join(summary.skipped)}")
    console.print(f"kernels inserted: {len(summary.kernels_inserted)}")
    for k in summary.kernels_inserted:
        console.print(f"  {k['from']} → {k['to']} ({k['position']}, "
                      f"{k['kernel_words']}w)")
    if summary.not_found:
        console.print(f"[yellow]not in plan: {', '.join(summary.not_found)}[/yellow]")
    console.print(f"backups created: {len(summary.backup_paths)}")


@app.command(name="revert-skips")
def revert_skips_cmd(book_id: str) -> None:
    """Restore chapter sources from `.orig` backups and reset plan.json's
    target_word_counts. Reverses `prepare-skips`."""
    from .prepare_skips import revert_skips
    book = load_book(book_id)
    n = revert_skips(book)
    console.print(f"restored {n} chapter source files; plan.json reset")


@app.command()
def coherence(
    book_id: str,
    stream: bool = typer.Option(True, help="Stream raw LLM output as it arrives."),
) -> None:
    """Run the structural coherence critic on every adjacent pair of diegetic
    chapters. Strict gate — only flags non-parseable sentences, dangling
    references, broken logical pivots, missing definitional glosses,
    unattributed dialogue, and mid-scene jumps. Writes
    work/<book>/coherence_report.json. ~100% precision, ~55% recall.
    Intended for human review — does NOT auto-feed regen.
    """
    book = load_book(book_id)
    console.print(f"[dim]book:[/dim] {book.book_id}")
    if stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk); sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")
    report = run_coherence(book)
    if stream:
        sys.stdout.write("\n")
    console.rule(f"[bold]coherence: {report['findings_total']} findings across "
                 f"{report['pairs_checked']} pairs[/bold]")
    # Summary counts.
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim"); tally.add_column()
    tally.add_row("pairs_checked", str(report["pairs_checked"]))
    tally.add_row("findings_total", str(report["findings_total"]))
    if report.get("findings_invalid"):
        tally.add_row("findings_invalid", str(report["findings_invalid"]))
    raw_total = report.get("findings_raw_total", report["findings_total"])
    if raw_total != report.get("findings_total"):
        tally.add_row("findings_raw_total", str(raw_total))
    for k, v in report["class_counts"].items():
        tally.add_row(k, str(v))
    console.print(Panel(tally, title="counts"))
    valid_findings = [f for f in report["findings"] if f.get("valid", True)]
    if not valid_findings:
        console.print("[green]no structural coherence damage detected[/green]")
        return
    t = Table(show_lines=True)
    t.add_column("seg")
    t.add_column("class", width=22)
    t.add_column("draft passage (trunc)", max_width=60)
    t.add_column("source context (trunc)", max_width=60)
    for f in valid_findings:
        t.add_row(
            str(f.get("segment_id", "?")),
            f.get("class", ""),
            (f.get("draft_passage") or "")[:120],
            (f.get("source_has") or "")[:120],
        )
    console.print(t)


@app.command(name="coherence-adjudicate")
def coherence_adjudicate(
    book_id: str,
    include_low_confidence: bool = typer.Option(
        False,
        "--include-low-confidence",
        help="Mark low-confidence valid findings as repair candidates."),
) -> None:
    """Filter coherence_report.json into repair-ready findings.

    Writes work/<book>/coherence_adjudication_report.json. This stage rejects
    stale findings, duplicates, and mechanically unsupported claims before
    coherence-fix consumes the report.
    """
    book = load_book(book_id)
    report = run_coherence_adjudication(
        book,
        include_low_confidence=include_low_confidence,
    )
    console.rule(f"[bold]coherence-adjudicate: {report['book_id']}[/bold]")

    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim")
    tally.add_column()
    tally.add_row("findings seen", str(report["findings_seen"]))
    tally.add_row("valid findings", str(report["valid_findings"]))
    tally.add_row("repair candidates", str(report["repair_candidates"]))
    for key, value in report.get("verdict_counts", {}).items():
        tally.add_row(key, str(value))
    console.print(Panel(tally, title="adjudication"))

    candidates = [f for f in report["findings"] if f.get("repair_candidate")]
    if not candidates:
        console.print("[green]no repair candidates after adjudication[/green]")
        return

    t = Table(title="repair candidates", show_lines=False)
    t.add_column("pair")
    t.add_column("seg")
    t.add_column("class", width=18)
    t.add_column("priority", width=8)
    t.add_column("reason", max_width=34)
    t.add_column("draft passage", max_width=70)
    for f in candidates:
        adj = f.get("adjudication", {})
        t.add_row(
            str(f.get("pair", "")),
            str(f.get("segment_id", "")),
            str(f.get("class", "")),
            str(adj.get("repair_priority", "")),
            str(adj.get("reason", "")),
            (f.get("draft_passage") or "")[:140],
        )
    console.print(t)


@app.command(name="coherence-fix")
def coherence_fix(
    book_id: str,
    pair: list[str] = typer.Option([], "--pair", "-p",
                                   help="Only process these pairs (format NNN-NNN). "
                                        "Repeatable."),
    all_findings: bool = typer.Option(
        True,
        "--all-findings/--selected-pairs",
        help="Process all findings from coherence_report.json (default). "
             "Use --selected-pairs to restrict to --pair entries.",
    ),
    segment: str = typer.Option(None, "--segment", "-s",
                               help="Only process findings for this segment id "
                                    "across both neighboring chapters."),
    include_name_lint: bool = typer.Option(
        False,
        "--include-name-lint",
        help="Merge deterministic name-lint findings into coherence-fix input."),
    name_lint_only: bool = typer.Option(
        False,
        "--name-lint-only",
        help="Repair only deterministic name-lint findings."),
    use_adjudication: bool = typer.Option(
        False,
        "--use-adjudication",
        help="Consume coherence_adjudication_report.json repair candidates instead of raw coherence_report.json findings."),
    max_retries: int = typer.Option(1, help="Max repair retries on parse/validation errors."),
    dry_run: bool = typer.Option(False, "--dry-run",
                                help="Render repair plan without writing drafts."),
) -> None:
    """Apply coherence findings by doing constrained local repairs on target pairs.
    Writes revised drafts to segments/NNN.md for successful findings.
    """
    book = load_book(book_id)
    if name_lint_only:
        include_name_lint = True
    if not all_findings and not pair and not name_lint_only:
        raise typer.BadParameter("selected-pairs mode requires at least one --pair")
    report = run_coherence_fixes(
        book,
        all_findings=all_findings,
        pairs=pair or None,
        segment=segment,
        include_name_lint=include_name_lint,
        name_lint_only=name_lint_only,
        use_adjudication=use_adjudication,
        max_retries=max_retries,
        dry_run=dry_run,
    )

    console.rule(f"[bold]coherence-fix: {report['book_id']}[/bold]")

    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim")
    tally.add_column()
    tally.add_row("findings seen", str(report.get("findings_seen", 0)))
    tally.add_row("findings selected", str(report.get("findings_selected", 0)))
    tally.add_row("findings filtered", str(report.get("findings_filtered", 0)))
    if report.get("include_name_lint"):
        tally.add_row("name-lint seen", str(report.get("name_lint_findings_seen", 0)))
        tally.add_row("name-lint mapped", str(report.get("name_lint_findings_mapped", 0)))
    if report.get("use_adjudication"):
        tally.add_row("adjudication seen", str(report.get("adjudication_findings_seen", 0)))
        tally.add_row("adjudication candidates", str(report.get("adjudication_repair_candidates", 0)))
    tally.add_row("pairs processed", str(report["pairs_processed"]))
    tally.add_row("pairs applied", str(report["pairs_applied"]))
    tally.add_row("pairs no-change", str(report["pairs_no_change"]))
    tally.add_row("pairs rejected", str(report.get("pairs_rejected", 0)))
    tally.add_row("pairs failed", str(report["pairs_failed"]))
    tally.add_row("pairs no findings", str(report["pairs_no_findings"]))
    console.print(Panel(tally, title="coherence-fix summary"))
    if not report["pairs"]:
        console.print("[yellow]no pairs found for requested scope[/yellow]")
        return

    t = Table(title="pairs", show_lines=False)
    t.add_column("pair")
    t.add_column("status", width=12)
    t.add_column("findings", justify="right")
    t.add_column("changed", max_width=28)
    t.add_column("attempts", justify="right")
    for p in report["pairs"]:
        changed = ", ".join(p.get("changed_segments", []))
        t.add_row(
            p["pair"],
            p["status"],
            str(p.get("findings", 0)),
            changed or "—",
            str(p.get("attempts", 0)),
        )
    console.print(t)


@app.command()
def cache_audit(
    book_id: str | None = typer.Argument(
        None,
        help="Book id to audit; omit for replay-cache file integrity only.",
    ),
    coherence: bool = typer.Option(
        False,
        "--coherence",
        help="Also audit current coherence pair requests.",
    ),
) -> None:
    """Audit replay-cache coverage for current prompt/model requests.
    This only renders prompts and reads cache files; it makes no LLM calls.
    """
    integrity = audit_replay_cache_files()
    invalid = integrity.get("invalid", [])
    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row("cache files", str(integrity.get("total", 0)))
    summary.add_row("valid", str(integrity.get("valid", 0)))
    summary.add_row("fingerprinted", str(integrity.get("fingerprinted", 0)))
    summary.add_row("unfingerprinted", str(integrity.get("unfingerprinted", 0)))
    summary.add_row("stale fingerprints", str(integrity.get("stale_fingerprint", 0)))
    summary.add_row("invalid", str(len(invalid)))
    console.print(Panel(summary, title="replay-cache integrity"))

    if invalid:
        t_invalid = Table(title="invalid replay-cache files")
        t_invalid.add_column("path", overflow="fold")
        t_invalid.add_column("error", overflow="fold")
        for item in invalid[:20]:
            if isinstance(item, dict):
                t_invalid.add_row(item.get("path", "?"),
                                  item.get("error", "invalid cache file"))
            else:
                t_invalid.add_row(str(item), "invalid cache file")
        console.print(t_invalid)
        if len(invalid) > 20:
            console.print(f"[yellow]showing 20 of {len(invalid)} invalid files[/yellow]")

    if not book_id:
        return

    book = load_book(book_id)
    rows = audit_book_cache(book, include_coherence=coherence)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1

    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim")
    tally.add_column()
    for status in ("hit", "miss", "no-call", "blocked", "unsupported"):
        if status in counts:
            tally.add_row(status, str(counts[status]))
    console.print(Panel(tally, title=f"cache audit: {book.book_id}"))

    status_style = {
        "hit": "green",
        "miss": "red",
        "no-call": "cyan",
        "blocked": "yellow",
        "stale-risk": "yellow",
        "source-stale": "yellow",
        "source-untracked": "yellow",
        "unsupported": "dim",
        "current": "green",
        "stale": "yellow",
        "missing": "yellow",
        "n/a": "dim",
    }
    verdict_table = Table(title="stage verdicts")
    verdict_table.add_column("stage")
    verdict_table.add_column("cache")
    verdict_table.add_column("pipeline-safe")
    verdict_table.add_column("source")
    verdict_table.add_column("counts", overflow="fold")
    verdict_table.add_column("note", overflow="fold")
    for verdict in summarize_stage_verdicts(rows):
        counts_text = " ".join(
            f"{status}={count}"
            for status, count in sorted(verdict.counts.items())
        )
        cache_style = status_style.get(verdict.cache, "")
        pipeline_style = status_style.get(verdict.pipeline, "")
        cache_text = (f"[{cache_style}]{verdict.cache}[/{cache_style}]"
                      if cache_style else verdict.cache)
        pipeline_text = (f"[{pipeline_style}]{verdict.pipeline}[/{pipeline_style}]"
                         if pipeline_style else verdict.pipeline)
        source_style = status_style.get(verdict.source, "")
        source_text = (f"[{source_style}]{verdict.source}[/{source_style}]"
                       if source_style else verdict.source)
        verdict_table.add_row(
            verdict.stage,
            cache_text,
            pipeline_text,
            source_text,
            counts_text,
            verdict.note,
        )
    console.print(verdict_table)

    t = Table(title="current LLM request cache coverage")
    t.add_column("stage")
    t.add_column("request")
    t.add_column("status", width=12)
    t.add_column("source", width=14)
    t.add_column("model", overflow="fold")
    t.add_column("cache key", overflow="fold")
    t.add_column("note", overflow="fold")
    for row in rows:
        style = status_style.get(row.status, "")
        t.add_row(
            row.stage,
            row.request,
            f"[{style}]{row.status}[/{style}]" if style else row.status,
            row.fingerprint or "—",
            row.model or "—",
            row.key or "—",
            row.note or "",
        )
    console.print(t)


@app.command()
def report(book_id: str = typer.Argument(None)) -> None:
    """Standard per-book results row: source/final words, actual
    compression, over-ceiling flag, book-critic verdict. Reads existing
    artifacts only — no LLM calls.

    With BOOK_ID: single-book row. Without: all books in work/.
    """
    ids = [book_id] if book_id else available_books()
    if not ids:
        console.print("[yellow]no books have pipeline output under work/[/yellow]")
        raise typer.Exit(code=0)
    t = Table(show_header=True, header_style="bold")
    for c in COLUMNS:
        t.add_column(c)
    notes: list[tuple[str, str]] = []
    for bid in ids:
        try:
            r = build_report(bid)
        except FileNotFoundError as e:
            console.print(f"[yellow]{bid}: {e}[/yellow]")
            continue
        row = format_row(r)
        t.add_row(*row)
        for n in r.notes:
            notes.append((bid, n))
    console.print(t)
    if notes:
        console.rule("[dim]notes[/dim]")
        for bid, n in notes:
            console.print(f"  [dim]{bid}:[/dim] {n}")


@app.command()
def proofread(book_id: str,
              render_only: bool = typer.Option(False, "--render-only",
                  help="Skip alignment calls; render HTML from existing alignments/")) -> None:
    """Align each draft chapter to its source (paragraph-level), then emit a
    static HTML viewer at work/<book>/proofread.html. Alignments are cached
    per chapter — re-running resumes from where it stopped."""
    from .align import align_book
    from .proofread import render_proofread_html

    book = load_book(book_id)
    if not render_only:
        console.rule(f"[bold]align {book_id}[/bold]")
        summary = align_book(book)
        console.print(f"aligned: {len(summary['aligned'])}  "
                      f"skipped: {len(summary['skipped'])}  "
                      f"errors: {len(summary['errors'])}")
        for sid, reason in summary['errors']:
            console.print(f"  [red]{sid}:[/red] {reason}")
    out = render_proofread_html(book)
    console.print(f"[green]wrote[/green] {out}")


@app.command(name="review-apply")
def review_apply_cmd(
    book_id: str,
    segment: list[str] = typer.Option(
        [], "--segment", "-s",
        help="Only consider this chapter id. Repeatable. Recommended for testing."),
    edits: Path | None = typer.Option(
        None, "--edits",
        help="Published edits overlay. Defaults to work/<book>/editorial/edits.json."),
    max_segments: int | None = typer.Option(
        None, "--max-segments",
        help="Limit the number of chapters processed in this run."),
    include_book_comments: bool = typer.Option(
        True, "--include-book-comments/--no-book-comments",
        help="Consider book-level comments for each selected chapter."),
    apply_: bool = typer.Option(
        False, "--apply",
        help="Call the LLM and update drafts plus the feedback ledger. "
             "Omit for zero-cost planning."),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Call the LLM but do not write drafts, reports, or the ledger. "
             "Requires --apply."),
    stream: bool = typer.Option(
        True, "--stream/--no-stream",
        help="Stream raw LLM output when --apply is used."),
) -> None:
    """Apply public review feedback as a constrained LLM repair pass.

    By default this only reports pending feedback and makes no model calls.
    Use --apply for the paid pass. Applied and skipped feedback are both
    recorded in work/<book>/editorial/review_apply_ledger.json.
    """
    if max_segments is not None and max_segments < 1:
        raise typer.BadParameter("--max-segments must be at least 1")
    if dry_run and not apply_:
        raise typer.BadParameter("--dry-run only has meaning with --apply")
    book = load_book(book_id)
    if apply_ and stream:
        def _sink(chunk: str) -> None:
            sys.stdout.write(chunk)
            sys.stdout.flush()
        set_stream_sink(_sink)
        console.rule("[dim]raw stream[/dim]")

    report = apply_review_feedback(
        book,
        segment_ids=segment or None,
        edits_path=edits,
        max_segments=max_segments,
        include_book_comments=include_book_comments,
        plan_only=not apply_,
        dry_run=dry_run,
    )
    if apply_ and stream:
        sys.stdout.write("\n")
    _render_review_apply(report)


def _render_review_apply(report: dict) -> None:
    mode = "plan-only" if report.get("plan_only") else (
        "dry-run" if report.get("dry_run") else "apply")
    console.rule(f"[bold]review-apply: {report['book_id']}[/bold]")
    tally = Table.grid(padding=(0, 1))
    tally.add_column(style="dim")
    tally.add_column()
    tally.add_row("mode", mode)
    tally.add_row("edits", report.get("edits_path", ""))
    tally.add_row("ledger", report.get("ledger_path", ""))
    tally.add_row("segments considered", str(report.get("segments_considered", 0)))
    tally.add_row("segments planned", str(report.get("segments_planned", 0)))
    tally.add_row("pending feedback", str(report.get("pending_feedback", 0)))
    tally.add_row("already used", str(report.get("already_used_feedback", 0)))
    if not report.get("plan_only"):
        tally.add_row("segments applied", str(report.get("segments_applied", 0)))
        tally.add_row("segments no-change", str(report.get("segments_no_change", 0)))
        tally.add_row("segments failed", str(report.get("segments_failed", 0)))
    console.print(Panel(tally, title="review-apply summary"))
    if report.get("needs_segment_for_book_comments"):
        console.print(
            "[yellow]book-level feedback exists, but no chapter comments selected "
            "a target; rerun with --segment to test it against specific chapters[/yellow]")

    rows = report.get("segments", [])
    if not rows:
        console.print("[yellow]no pending feedback for the requested scope[/yellow]")
        return

    t = Table(title="chapters", show_lines=False)
    t.add_column("chapter")
    if report.get("plan_only"):
        t.add_column("pending", justify="right")
        t.add_column("used", justify="right")
        t.add_column("total", justify="right")
        t.add_column("scopes")
        for row in rows:
            scopes = _review_scope_summary(row.get("pending", []))
            t.add_row(
                row["segment_id"],
                str(row.get("pending_count", 0)),
                str(row.get("used_count", 0)),
                str(row.get("total_count", 0)),
                scopes or "—",
            )
    else:
        t.add_column("status", width=12)
        t.add_column("feedback", justify="right")
        t.add_column("words", justify="right")
        t.add_column("changed")
        for row in rows:
            words = ""
            if "before_words" in row and "after_words" in row:
                words = f"{row['before_words']}->{row['after_words']}"
            t.add_row(
                row["segment_id"],
                row.get("status", ""),
                str(row.get("feedback_count", 0)),
                words,
                "yes" if row.get("changed") else "no",
            )
    console.print(t)


def _review_scope_summary(items: list[dict]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        scope = str(item.get("scope") or "?")
        counts[scope] = counts.get(scope, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


@app.command()
def serve(host: str = typer.Option("127.0.0.1", help="Bind address. Use 0.0.0.0 in a container."),
          port: int = typer.Option(8000, help="Port to listen on."),
          reload: bool = typer.Option(False, "--reload", help="Restart on code changes.")) -> None:
    """Run the editorial review web app: the proofread alignment view, plus a
    comment queue that publishes to work/<book>/editorial/edits.json.

    Reading is public. Commenting needs FORAGE_REVIEW_TOKEN; publishing needs
    FORAGE_ADMIN_TOKEN. When the review token is unset one is generated and
    printed here — nothing can be written without it. Zero LLM cost."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is not installed[/red] — pip install 'uvicorn[standard]' fastapi")
        raise typer.Exit(code=1)

    from .webapp.auth import AuthConfig, AuthConfigError
    from .webapp.store import ArtifactStore, ReviewStore

    try:
        auth = AuthConfig.from_env()
    except AuthConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    artifacts = ArtifactStore()
    reviews = ReviewStore()

    console.rule("[bold]forage serve[/bold]")
    console.print(f"artifacts  {artifacts.work_dir}")
    console.print(f"review db  {reviews.db_path}")
    console.print(f"books      {', '.join(artifacts.book_ids()) or '(none aligned yet)'}")
    if "FORAGE_REVIEW_TOKEN" in auth.generated:
        console.print(f"[yellow]review token[/yellow] {auth.review_token}  "
                      f"[dim](generated — set FORAGE_REVIEW_TOKEN to keep it stable)[/dim]")
    console.print("admin      " + ("enabled via FORAGE_ADMIN_TOKEN"
                                   if auth.admin_enabled
                                   else "[dim]disabled — publishing is unavailable "
                                        "until FORAGE_ADMIN_TOKEN is set[/dim]"))
    if "FORAGE_SECRET_KEY" in auth.generated:
        console.print("[dim]FORAGE_SECRET_KEY unset — sessions end when this process does[/dim]")
    console.print(f"[green]listening on[/green] http://{host}:{port}")

    if reload:
        # The reloader re-imports in a subprocess, so generated values have to
        # survive into it or sign-in breaks on every restart.
        os.environ.setdefault("FORAGE_REVIEW_TOKEN", auth.review_token)
        os.environ.setdefault("FORAGE_SECRET_KEY", auth.secret_key.decode())
        uvicorn.run("forage.webapp.app:get_app", factory=True,
                    host=host, port=port, reload=True)
    else:
        from .webapp.app import create_app
        uvicorn.run(create_app(artifacts, reviews, auth), host=host, port=port)


@app.command()
def validate(book_id: str) -> None:
    """Mechanical validation: fuzzy signature preservation, motif concordance,
    style distribution. Zero LLM cost."""
    book = load_book(book_id)
    plan_path = book.work_dir / "plan.json"
    if not plan_path.exists():
        console.print(f"[red]no plan at {plan_path}[/red]")
        raise typer.Exit(code=1)
    plan = read_json(plan_path)
    report = validate_book(book, plan)
    _render_validation(report)


def _render_validation(r) -> None:
    # Summary
    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row("book_id", r.book_id)
    summary.add_row("book_target", f"{r.book_target}")
    summary.add_row("total_drafted", f"{r.total_drafted}")
    if r.book_target:
        delta = (r.total_drafted - r.book_target) / r.book_target * 100
        summary.add_row("delta vs target", f"{delta:+.1f}%")
    drafted = sum(1 for s in r.per_segment if s.status == "drafted")
    summary.add_row("segments", f"{drafted}/{len(r.per_segment)} drafted")
    summary.add_row("signatures", f"{r.signature_hits}/{r.signature_total} hits"
                    + (f" ({r.signature_ambiguous} ambiguous)"
                       if r.signature_ambiguous else ""))
    summary.add_row("motifs depleted", f"{r.depleted_motifs}/{len(r.book_motif)}")
    if r.book_style and r.book_style.flags:
        summary.add_row("style flags", "; ".join(r.book_style.flags))
    console.print(Panel(summary, title="validation"))

    # Per-segment signature status (show misses only to keep concise)
    problematic = [s for s in r.per_segment
                   if s.signature and s.signature.misses]
    if problematic:
        t = Table(title=f"signature misses ({len(problematic)} segments)")
        t.add_column("id")
        t.add_column("title", max_width=30)
        t.add_column("hits", justify="right")
        t.add_column("miss samples (score)", max_width=60)
        for sv in problematic:
            sr = sv.signature
            samples = [f"{m['hint'][:35]} ({m['score']})" for m in sr.misses[:2]]
            t.add_row(sv.segment_id, sv.title[:30],
                      f"{sr.hits}/{sr.total}",
                      "; ".join(samples))
        console.print(t)

    # Motif concordance
    if r.book_motif:
        t = Table(title="motif concordance (drafted segments only)")
        t.add_column("motif")
        t.add_column("source", justify="right")
        t.add_column("draft", justify="right")
        t.add_column("retention", justify="right")
        t.add_column("flag")
        for m in r.book_motif:
            if m.retention is None:
                ret = "—"
            else:
                ret = f"{m.retention*100:.0f}%"
            flag = "[red]DEPLETED[/red]" if m.depleted else ""
            t.add_row(m.name[:42], str(m.source_count),
                      str(m.draft_count), ret, flag)
        console.print(t)

    # Style distribution (book-level)
    if r.book_style:
        s, d = r.book_style.source, r.book_style.draft
        t = Table(title="style distribution (drafted segments vs source)")
        t.add_column("metric")
        t.add_column("source", justify="right")
        t.add_column("draft", justify="right")
        t.add_column("Δ%", justify="right")
        rows = [
            ("sentences", s.sentences, d.sentences),
            ("avg sent length", round(s.avg_sent_len, 1), round(d.avg_sent_len, 1)),
            ("median sent length", s.median_sent_len, d.median_sent_len),
            ("long sents %", round(s.long_sent_pct, 1), round(d.long_sent_pct, 1)),
            ("semicolons / 1k", round(s.semicolons_per_1k, 1), round(d.semicolons_per_1k, 1)),
            ("em-dashes / 1k", round(s.em_dashes_per_1k, 1), round(d.em_dashes_per_1k, 1)),
            ("vocab richness", round(s.vocab_richness, 3), round(d.vocab_richness, 3)),
        ]
        for name, sv, dv in rows:
            delta = (dv - sv) / sv * 100 if sv else 0.0
            t.add_row(name, str(sv), str(dv), f"{delta:+.0f}%")
        console.print(t)


if __name__ == "__main__":
    app()
