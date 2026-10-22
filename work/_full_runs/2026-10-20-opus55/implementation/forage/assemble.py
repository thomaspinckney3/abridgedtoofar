"""Assembly stage: concatenate segment drafts into final book artifacts +
budget report.

Pure local operation — no LLM. Runs any time after the drafter has produced
at least some segment files. Missing, extract-failed, or cut segments are
reported and skipped in the final text.

Always writes abridgment.md and a UTF-8 plain-text abridgment.txt under work/
when any drafted content exists, publishes both artifacts under books/<book>/,
and writes assembly_report.json with per-stage stats: segments
drafted/cut/missing, total drafted words, book target/ceiling, overage (words
and %), over_target/over_ceiling flags. Budget adherence is reported, not
enforced — downstream stages (book critic, validate) decide whether the
produced abridgment is acceptable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, write_json


@dataclass
class SegmentStatus:
    id: str
    title: str
    role: str
    diegetic_status: str
    target: int
    drafted: int | None  # None when no draft on disk
    status: str           # "drafted" | "cut" | "not_drafted" | "extract_fail"


@dataclass
class AssemblyResult:
    book_id: str
    book_target: int
    book_ceiling: int          # target * 1.2
    total_drafted: int
    segments_total: int
    segments_drafted: int
    segments_cut: int
    segments_missing: int
    over_budget: bool          # total_drafted > book_target
    over_ceiling: bool         # total_drafted > book_ceiling
    abridgment_path: Path | None
    plain_text_path: Path | None
    published_abridgment_path: Path | None
    published_plain_text_path: Path | None
    per_segment: list[SegmentStatus]


def assemble_book(book: Book, plan: dict) -> AssemblyResult:
    seg_dir = book.work_dir / "segments"

    # Extraction status tells us which segments failed source extraction.
    ext_index_path = seg_dir / "_extractions.json"
    ext_errors: dict[str, str] = {}
    if ext_index_path.exists():
        import json
        data = json.loads(ext_index_path.read_text())
        ext_errors = {sid: r.get("error")
                      for sid, r in data.items() if r.get("error")}

    parts: list[str] = []
    per_segment: list[SegmentStatus] = []
    total_drafted = 0
    drafted = cut = missing = 0

    for s in plan.get("segments", []):
        sid = s["id"]
        title = s.get("title", "")
        role = s.get("role", "")
        diegetic = s.get("diegetic_status", "")
        target = int(s.get("target_word_count", 0) or 0)

        draft_path = seg_dir / f"{sid}.md"
        checks_path = seg_dir / f"{sid}.checks.json"
        draft_words: int | None = None
        status: str

        # Consult checks.json for the drafter's recorded status. If it says
        # "error" or "truncated", trust that over the file's mere presence.
        checks_status: str | None = None
        if checks_path.exists():
            try:
                import json
                checks_status = json.loads(checks_path.read_text()).get("status")
            except Exception:
                checks_status = None

        # prepare-skips marks a chapter skipped=True after relocating its
        # kernel into a neighbor; target_word_count is zeroed and the drafter
        # writes an empty file. Classify as cut regardless of any stale
        # checks.json (e.g. an "error" status from a pre-skip run).
        if s.get("skipped"):
            status = "cut"
            draft_words = 0
            cut += 1
        elif sid in ext_errors:
            status = "extract_fail"
            missing += 1
        elif checks_status in ("error", "truncated"):
            # Drafter failure or truncation — count as missing, not a valid draft.
            status = checks_status
            missing += 1
        elif s.get("group_id") and checks_status not in ("drafted", "cut"):
            # Group splits are valid only with completion records from their
            # shared response. Legacy or damaged metadata cannot certify them.
            status = "not_drafted"
            missing += 1
        elif diegetic == "extradiegetic" and target == 0:
            # Extradiegetic target-zero segments are intentionally cut even if
            # the draft loop never materialized an empty placeholder file.
            status = "cut"
            draft_words = 0
            cut += 1
        elif not draft_path.exists():
            status = "not_drafted"
            missing += 1
        else:
            text = draft_path.read_text()
            if text.strip() == "" and checks_status == "drafted":
                status = "not_drafted"
                missing += 1
            elif text.strip() == "":
                # Empty draft == extradiegetic cut by drafter.
                status = "cut"
                draft_words = 0
                cut += 1
            else:
                draft_words = len(text.split())
                total_drafted += draft_words
                drafted += 1
                parts.append(_with_segment_heading(s, text))
                status = "drafted"

        per_segment.append(SegmentStatus(
            id=sid, title=title, role=role, diegetic_status=diegetic,
            target=target, drafted=draft_words, status=status,
        ))

    meta = plan.get("_meta", {}).get("computed", {})
    book_target = int(meta.get("target_word_count",
                               plan.get("target_word_count", 0)) or 0)
    book_ceiling = int(book_target * 1.2)
    over_ceiling = total_drafted > book_ceiling
    over_budget = total_drafted > book_target
    partial = missing > 0

    # Write final book artifacts whenever we have drafted content. The work/
    # files remain pipeline artifacts; the copies under books/<book>/ are the
    # published deliverables.
    abridgment_path = book.work_dir / "abridgment.md"
    plain_text_path = book.work_dir / "abridgment.txt"
    publish_dir = book.source_path.parent
    published_abridgment_path = publish_dir / "abridgment.md"
    published_plain_text_path = publish_dir / "abridgment.txt"
    budget_report_path = book.work_dir / "assembly_report.json"
    wrote_abridgment: Path | None = None
    wrote_plain_text: Path | None = None
    wrote_published_abridgment: Path | None = None
    wrote_published_plain_text: Path | None = None
    if parts:
        assembled = "\n".join(parts)
        plain_text = _plain_text_export(assembled)
        abridgment_path.write_text(assembled, encoding="utf-8")
        plain_text_path.write_text(
            plain_text,
            encoding="utf-8",
            newline="\n",
        )
        published_abridgment_path.write_text(assembled, encoding="utf-8")
        published_plain_text_path.write_text(
            plain_text,
            encoding="utf-8",
            newline="\n",
        )
        wrote_abridgment = abridgment_path
        wrote_plain_text = plain_text_path
        wrote_published_abridgment = published_abridgment_path
        wrote_published_plain_text = published_plain_text_path
    overage = total_drafted - book_target
    over_ceiling_by = total_drafted - book_ceiling
    overage_pct = (overage / book_target * 100) if book_target else 0
    write_json(budget_report_path, {
        "book_id": book.book_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "book_target": book_target,
        "book_ceiling": book_ceiling,
        "total_drafted": total_drafted,
        "over_target": over_budget,
        "over_ceiling": over_ceiling,
        "partial": partial,
        "segments_total": len(plan.get("segments", [])),
        "segments_drafted": drafted,
        "segments_cut": cut,
        "segments_missing": missing,
        "overage_words": overage,
        "over_ceiling_words": over_ceiling_by,
        "overage_pct": round(overage_pct, 1),
        "abridgment_path": str(abridgment_path) if wrote_abridgment else None,
        "plain_text_path": str(plain_text_path) if wrote_plain_text else None,
        "plain_text_encoding": "utf-8" if wrote_plain_text else None,
        "published_abridgment_path": (
            str(published_abridgment_path)
            if wrote_published_abridgment else None
        ),
        "published_plain_text_path": (
            str(published_plain_text_path)
            if wrote_published_plain_text else None
        ),
    })
    # Remove any stale halt.json left over from the previous fail-loud
    # regime so downstream tooling doesn't read obsolete state.
    halt_path = book.work_dir / "halt.json"
    if halt_path.exists():
        halt_path.unlink()

    return AssemblyResult(
        book_id=book.book_id,
        book_target=book_target,
        book_ceiling=book_ceiling,
        total_drafted=total_drafted,
        segments_total=len(plan.get("segments", [])),
        segments_drafted=drafted,
        segments_cut=cut,
        segments_missing=missing,
        over_budget=total_drafted > book_target,
        over_ceiling=over_ceiling,
        abridgment_path=wrote_abridgment,
        plain_text_path=wrote_plain_text,
        published_abridgment_path=wrote_published_abridgment,
        published_plain_text_path=wrote_published_plain_text,
        per_segment=per_segment,
    )


def _plain_text_export(text: str) -> str:
    """Convert the assembled markdown-ish artifact into plain UTF-8 text."""
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.rstrip()
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            lines.append(heading if heading else "")
        elif stripped.startswith(">"):
            quote = stripped[1:].lstrip()
            lines.append(f"{indent}{quote}" if quote else "")
        else:
            lines.append(line)

    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _with_segment_heading(segment: dict, text: str) -> str:
    """Prepend a deterministic chapter/section heading for assembled output."""
    body = text.rstrip()
    heading = _segment_heading(segment)
    if not heading:
        return body + "\n"
    body = _strip_existing_leading_heading(body, heading, segment)
    return f"## {heading}\n\n{body}\n"


def _segment_heading(segment: dict) -> str:
    raw = str(segment.get("raw_heading") or "").strip()
    title = str(segment.get("title") or "").strip()
    number = str(segment.get("number") or "").strip()
    kind = str(segment.get("kind") or "").strip()

    if raw:
        heading = raw
    elif title:
        heading = title
    elif number:
        heading = f"Chapter {number}" if kind == "chapter" else number
    else:
        return ""

    if title and not _same_heading_text(title, heading):
        title_lower = _normalize_heading(title)
        heading_lower = _normalize_heading(heading)
        if title_lower and title_lower not in heading_lower:
            heading = f"{heading} - {title}"
    return heading


def _strip_existing_leading_heading(text: str, heading: str, segment: dict) -> str:
    lines = text.splitlines()
    first_index = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_index is None:
        return ""
    first = lines[first_index].strip()
    candidates = {
        heading,
        str(segment.get("raw_heading") or "").strip(),
        str(segment.get("title") or "").strip(),
    }
    is_markdown_heading = first.startswith("#")
    is_known_plain_heading = any(
        _same_heading_text(first, c) for c in candidates if c
    )
    if not is_markdown_heading and not is_known_plain_heading:
        return text

    new_lines = lines[:first_index] + lines[first_index + 1:]
    while first_index < len(new_lines) and not new_lines[first_index].strip():
        del new_lines[first_index]
    return "\n".join(new_lines).strip()


def _same_heading_text(a: str, b: str) -> bool:
    return _normalize_heading(a) == _normalize_heading(b)


def _normalize_heading(text: str) -> str:
    import re

    text = text.strip().lstrip("#").strip().lower()
    text = re.sub(r"[_*`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .:-")
