"""Forage CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .artifacts import load_book, read_json
from .assemble import assemble_book
from .chapter_split import split_to_disk
from .critics import run_critic
from .drafter import draft_all, draft_segment, ensure_chapters
from .book_critic import run_book_critic
from .chapter_classifier import classify_chapters
from .iterate import iterate_segment
from .lean_plan import build_lean_plan
from .llm import set_stream_sink
from .report import (COLUMNS, available_books, build_report, format_row)
from .summarizer import summarize_book
from .prepass import run_prepass
from .prime import run_prime
from .rebudget import rebudget
from .reconsider import reconsider_segment
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
    max_retries: int = typer.Option(2, help="Max regeneration attempts."),
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
    """Concatenate drafted segments into abridgment.md and write
    assembly_report.json with budget stats. Always emits; budget adherence
    is reported (overage %, over_target, over_ceiling flags) but does not
    gate output."""
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
    # Status is informational only now; abridgment.md is always emitted.
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
