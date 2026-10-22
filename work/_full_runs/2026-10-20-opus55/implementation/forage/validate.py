"""Validation stage: mechanical checks against source and plan.

All checks are pure Python — no LLM calls. Outputs are deterministic,
reviewable, and cheap. Per spec: text-derivable properties flow through
tooling, not LLM inference.

Three check families are wired:
  1. Fuzzy signature preservation — for each segment's plan signatures,
     is the passage_hint present in the drafted text? (uses text_norm.)
  2. Motif concordance — for each book motif, counts indicative-phrase
     occurrences in source and draft; flags depletion relative to the
     segment's own compression ratio.
  3. Style distribution — sentence length stats, punctuation density,
     vocabulary richness. Source vs draft, per-segment and book-level.

The validation report is a structured dict; the CLI renders it as tables.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import Book, segment_source_path
from .text_norm import count_phrases, fuzzy_contains

# Thresholds
MOTIF_DEPLETION_RATIO = 0.5   # flag when retention < compression * THIS
STYLE_SENT_LEN_DRIFT = 0.20   # flag >20% drift in avg sentence length
STYLE_PUNCT_DRIFT = 0.40      # flag >40% drift in punctuation density


# ============================================================
# Per-segment signature check
# ============================================================

@dataclass
class SegmentSigReport:
    segment_id: str
    title: str
    total: int
    hits: int
    misses: list[dict]      # {hint, score, ambiguous}
    ambiguous_count: int


def check_segment_signatures(segment: dict, draft_text: str) -> SegmentSigReport:
    sigs = segment.get("signatures", [])
    hits = 0
    misses: list[dict] = []
    for sig in sigs:
        hint = sig.get("passage_hint", "").strip()
        if not hint:
            continue
        r = fuzzy_contains(hint, draft_text, threshold=85, prefix_words=8)
        if r.present:
            hits += 1
        else:
            misses.append({
                "hint": hint[:120],
                "score": r.score,
                "ambiguous": r.ambiguous,
            })
    return SegmentSigReport(
        segment_id=segment["id"], title=segment.get("title", ""),
        total=len(sigs), hits=hits, misses=misses,
        ambiguous_count=sum(1 for m in misses if m["ambiguous"]),
    )


# ============================================================
# Motif concordance
# ============================================================

@dataclass
class MotifReport:
    name: str
    phrases: int
    source_count: int
    draft_count: int
    retention: float | None   # drf/src, None if src==0
    depleted: bool


def check_motifs(motifs: list[dict], source_text: str, draft_text: str,
                 compression_ratio: float) -> list[MotifReport]:
    reports: list[MotifReport] = []
    # Expected baseline retention = compression (e.g. if draft is 25% the
    # length of source, motifs appearing at normal density would retain ~25%).
    # Flag when retention is below compression * MOTIF_DEPLETION_RATIO.
    threshold_retention = compression_ratio * MOTIF_DEPLETION_RATIO
    for motif in motifs:
        phrases = motif.get("indicative_phrases", [])
        src = sum(count_phrases(p, source_text) for p in phrases)
        drf = sum(count_phrases(p, draft_text) for p in phrases)
        retention: float | None
        depleted = False
        if src == 0:
            retention = None
        else:
            retention = drf / src
            depleted = retention < threshold_retention
        reports.append(MotifReport(
            name=motif.get("name", ""), phrases=len(phrases),
            source_count=src, draft_count=drf,
            retention=retention, depleted=depleted,
        ))
    return reports


# ============================================================
# Style distribution
# ============================================================

@dataclass
class StyleStats:
    tokens: int
    sentences: int
    avg_sent_len: float
    median_sent_len: float
    long_sent_pct: float
    semicolons_per_1k: float
    em_dashes_per_1k: float
    vocab_richness: float

    @staticmethod
    def from_text(text: str) -> "StyleStats":
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        sents = [s for s in sents if len(s.split()) >= 3]
        lengths = [len(s.split()) for s in sents]
        toks = re.findall(r"\b\w+\b", text.lower())
        n_tok = max(len(toks), 1)
        # Em-dash count: unicode em-dash OR a literal `--` that is NOT part
        # of a longer run of hyphens (Gutenberg texts use long `--------`
        # bars as decorative separators; those aren't em-dashes).
        em_dash_count = (text.count('—')
                         + len(re.findall(r'(?<!-)--(?!-)', text)))
        return StyleStats(
            tokens=len(toks),
            sentences=len(sents),
            avg_sent_len=sum(lengths) / len(lengths) if lengths else 0.0,
            median_sent_len=(sorted(lengths)[len(lengths) // 2]
                             if lengths else 0.0),
            long_sent_pct=(sum(1 for l in lengths if l > 30)
                           / len(lengths) * 100 if lengths else 0.0),
            semicolons_per_1k=text.count(';') / n_tok * 1000,
            em_dashes_per_1k=em_dash_count / n_tok * 1000,
            vocab_richness=(len(set(toks)) / n_tok) if toks else 0.0,
        )


@dataclass
class StyleReport:
    source: StyleStats
    draft: StyleStats
    flags: list[str]  # descriptive flags for noteworthy drifts


def _pct_delta(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return (b - a) / a


def check_style(source_text: str, draft_text: str) -> StyleReport:
    s = StyleStats.from_text(source_text)
    d = StyleStats.from_text(draft_text)
    flags: list[str] = []
    # Voice-flattening: draft's avg sentence length dropped significantly
    if s.avg_sent_len > 0:
        delta = _pct_delta(s.avg_sent_len, d.avg_sent_len)
        if delta < -STYLE_SENT_LEN_DRIFT:
            flags.append(f"avg_sent_len dropped {delta*100:+.0f}% (voice flattening risk)")
    # Punctuation erasure: distinctive marks dropping in relative density
    if s.semicolons_per_1k > 0.5:
        delta = _pct_delta(s.semicolons_per_1k, d.semicolons_per_1k)
        if delta < -STYLE_PUNCT_DRIFT:
            flags.append(f"semicolon density dropped {delta*100:+.0f}%")
    if s.em_dashes_per_1k > 0.5:
        delta = _pct_delta(s.em_dashes_per_1k, d.em_dashes_per_1k)
        if delta < -STYLE_PUNCT_DRIFT:
            flags.append(f"em-dash density dropped {delta*100:+.0f}%")
    return StyleReport(source=s, draft=d, flags=flags)


# ============================================================
# Top-level: validate_book
# ============================================================

@dataclass
class SegmentValidation:
    segment_id: str
    title: str
    status: str                     # "drafted" | "cut" | "not_drafted" | "extract_fail"
    source_words: int
    draft_words: int
    signature: SegmentSigReport | None


@dataclass
class ValidationReport:
    book_id: str
    book_target: int
    total_drafted: int
    per_segment: list[SegmentValidation] = field(default_factory=list)
    book_motif: list[MotifReport] = field(default_factory=list)
    book_style: StyleReport | None = None
    signature_hits: int = 0
    signature_total: int = 0
    signature_ambiguous: int = 0
    depleted_motifs: int = 0


def validate_book(book: Book, plan: dict) -> ValidationReport:
    seg_dir = book.work_dir / "segments"
    source_words = plan.get("_meta", {}).get("computed", {}).get(
        "source_word_count", plan.get("source_word_count", 0))
    book_target = plan.get("_meta", {}).get("computed", {}).get(
        "target_word_count", plan.get("target_word_count", 0))

    report = ValidationReport(
        book_id=book.book_id, book_target=book_target, total_drafted=0,
    )

    drafted_texts: list[str] = []
    drafted_sources: list[str] = []

    for seg in plan.get("segments", []):
        sid = seg["id"]
        src_path = segment_source_path(book, sid)
        drf_path = seg_dir / f"{sid}.md"
        source = src_path.read_text() if src_path else ""
        if not drf_path.exists():
            report.per_segment.append(SegmentValidation(
                segment_id=sid, title=seg.get("title", ""),
                status="not_drafted",
                source_words=len(source.split()),
                draft_words=0, signature=None))
            continue
        draft = drf_path.read_text()
        if draft.strip() == "":
            report.per_segment.append(SegmentValidation(
                segment_id=sid, title=seg.get("title", ""),
                status="cut",
                source_words=len(source.split()),
                draft_words=0, signature=None))
            continue
        draft_words = len(draft.split())
        report.total_drafted += draft_words
        sig_report = check_segment_signatures(seg, draft)
        report.signature_hits += sig_report.hits
        report.signature_total += sig_report.total
        report.signature_ambiguous += sig_report.ambiguous_count
        report.per_segment.append(SegmentValidation(
            segment_id=sid, title=seg.get("title", ""), status="drafted",
            source_words=len(source.split()), draft_words=draft_words,
            signature=sig_report,
        ))
        drafted_sources.append(source)
        drafted_texts.append(draft)

    # Book-level style + motif concordance on the corpus of drafted text
    if drafted_sources and drafted_texts:
        src_corpus = "\n".join(drafted_sources)
        drf_corpus = "\n".join(drafted_texts)
        corpus_ratio = (len(drf_corpus.split()) / len(src_corpus.split())
                        if src_corpus.split() else 0.0)
        report.book_motif = check_motifs(
            plan.get("motifs", []), src_corpus, drf_corpus, corpus_ratio)
        report.depleted_motifs = sum(1 for m in report.book_motif if m.depleted)
        report.book_style = check_style(src_corpus, drf_corpus)
    return report
