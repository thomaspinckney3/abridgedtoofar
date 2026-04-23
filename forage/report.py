"""Book-level reporting stage: read existing pipeline artifacts and print a
standard per-book results row.

Reads (per book):
  - chapters.json         — source word totals and diegetic chapter count
  - plan.json             — book target / ceiling from compression formula
  - assembly_report.json  — total drafted words + budget flags
  - book_critic.json      — synopsis-verification verdict + counts

Produces a uniform row with:
  Chapters (drafted/total) | Source→Final | Compression (actual vs target)
  | Over ceiling | Book critic verdict

No LLM calls. Safe to re-run at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import load_book, read_json


@dataclass
class BookReport:
    book_id: str
    source_words: int
    final_words: int
    book_target: int
    book_ceiling: int
    diegetic_chapters: int       # count of diegetic segments per classifier
    chapters_drafted: int        # segments with non-empty draft
    over_ceiling_pct: float | None    # None if under target entirely
    critic_verdict: str | None
    critic_present: int
    critic_total: int
    notes: list[str]             # any "pipeline incomplete" annotations

    @property
    def compression_ratio(self) -> float | None:
        return (self.source_words / self.final_words) if self.final_words else None

    @property
    def target_ratio(self) -> float | None:
        return (self.source_words / self.book_target) if self.book_target else None


def build_report(book_id: str) -> BookReport:
    book = load_book(book_id)
    w = book.work_dir

    notes: list[str] = []

    # Source word count — prefer diegetic total from plan meta, fall back to
    # summing all chapters from the manifest (pre-classifier state).
    plan_path = w / "plan.json"
    chapters_path = w / "chapters.json"
    book_target = 0
    book_ceiling = 0
    source_words = 0
    diegetic_chapters = 0
    if plan_path.exists():
        plan = read_json(plan_path)
        meta = plan.get("_meta", {}).get("computed", {})
        book_target = int(meta.get("target_word_count", 0) or 0)
        book_ceiling = int(book_target * 1.2) if book_target else 0
        source_words = int(meta.get("source_word_count", 0) or 0)
        diegetic_chapters = sum(1 for s in plan.get("segments", [])
                                if s.get("diegetic_status") == "diegetic")
    elif chapters_path.exists():
        m = read_json(chapters_path)
        source_words = int(m.get("total_words", 0) or 0)
        diegetic_chapters = int(m.get("total_chapters", 0) or 0)
        notes.append("no plan.json; using raw chapter manifest")

    # Assembly report.
    report_path = w / "assembly_report.json"
    final_words = 0
    chapters_drafted = 0
    over_ceiling_pct: float | None = None
    if report_path.exists():
        ar = read_json(report_path)
        final_words = int(ar.get("total_drafted", 0) or 0)
        chapters_drafted = int(ar.get("segments_drafted", 0) or 0)
        if ar.get("over_ceiling") and book_ceiling:
            over_ceiling_pct = (final_words - book_ceiling) / book_ceiling * 100
        # Only flag "partial" when DIEGETIC chapters are missing —
        # extradiegetic segments are intentionally cut and not drafting them
        # is the correct outcome, not incomplete work.
        if diegetic_chapters and chapters_drafted < diegetic_chapters:
            missing_diegetic = diegetic_chapters - chapters_drafted
            notes.append(f"partial: {missing_diegetic} of {diegetic_chapters} "
                         f"diegetic chapters not drafted")
    else:
        notes.append("no assembly yet — run `forage assemble`")

    # Book critic.
    critic_path = w / "book_critic.json"
    critic_verdict = None
    critic_present = 0
    critic_total = 0
    if critic_path.exists():
        bc = read_json(critic_path)
        critic_verdict = bc.get("verdict")
        critic_total = int(bc.get("synopsis_sentence_count", 0) or 0)
        critic_present = int(bc.get("counts", {}).get("present", 0) or 0)
        if bc.get("is_partial"):
            notes.append("book critic ran against partial abridgment")
    else:
        notes.append("no book critic run yet — run `forage book-critique`")

    return BookReport(
        book_id=book_id,
        source_words=source_words,
        final_words=final_words,
        book_target=book_target,
        book_ceiling=book_ceiling,
        diegetic_chapters=diegetic_chapters,
        chapters_drafted=chapters_drafted,
        over_ceiling_pct=over_ceiling_pct,
        critic_verdict=critic_verdict,
        critic_present=critic_present,
        critic_total=critic_total,
        notes=notes,
    )


def format_row(r: BookReport) -> tuple[str, ...]:
    """Return a tuple of strings matching the standard report columns."""
    chapters = (f"{r.chapters_drafted}/{r.diegetic_chapters}"
                if r.diegetic_chapters else "—")
    transform = (f"{r.source_words:,} → {r.final_words:,}"
                 if r.final_words else f"{r.source_words:,} → —")
    # Compression is only meaningful when the book is complete — partial
    # drafts divide source over incomplete output and produce inflated
    # apparent ratios.
    is_complete = (r.diegetic_chapters
                   and r.chapters_drafted >= r.diegetic_chapters)
    if is_complete and r.compression_ratio and r.target_ratio:
        compression = f"{r.compression_ratio:.2f}× (vs {r.target_ratio:.2f}×)"
    elif r.final_words and not is_complete:
        compression = "(partial)"
    elif r.compression_ratio:
        compression = f"{r.compression_ratio:.2f}×"
    else:
        compression = "—"
    if r.over_ceiling_pct is not None:
        over = f"+{r.over_ceiling_pct:.0f}%"
    elif r.final_words and r.book_ceiling and r.final_words <= r.book_ceiling:
        over = "under"
    else:
        over = "—"
    if r.critic_verdict:
        critic = f"{r.critic_verdict} {r.critic_present}/{r.critic_total}"
    else:
        critic = "—"
    return (r.book_id, chapters, transform, compression, over, critic)


COLUMNS = ("book", "chapters", "source → final",
           "compression (vs target)", "over ceiling", "book critic")


def available_books() -> list[str]:
    """List books with at least a plan.json or chapters.json in work/."""
    work_dir = Path(__file__).resolve().parent.parent / "work"
    if not work_dir.is_dir():
        return []
    return sorted(
        p.name for p in work_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and ((p / "plan.json").exists() or (p / "chapters.json").exists())
    )
