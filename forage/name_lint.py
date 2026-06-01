"""Mechanical lint for orphaned minor-character proper names.

The coherence critic is intentionally judgment-heavy and has missed a simple
bookkeeping invariant: if a removable/minor character's proper name survives in
the abridgment, the reader needs either a previous named introduction or a
local gloss. This module keeps that check deterministic.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .artifacts import Book, read_json, write_json


LONG_GAP_SEGMENTS = 2
LONG_GAP_WORDS = 2500

_TITLE_RE = re.compile(
    r"^(?:Mr|Mrs|Ms|Miss|Dr|Doctor|Sir|Lord|Lady|Baron|Prince|Princess|"
    r"Frau|Mlle|Mme)\.?\s+",
    re.IGNORECASE,
)
_PROFESSIONAL_TITLE_RE = re.compile(
    r"^(?:Dr|Doctor|Professor|Prof|Reverend|Rev|Captain|Capt|General|Gen|"
    r"Judge|Colonel|Col|Father|Rabbi)\.?\s+",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\(([^)]*)\)")
_ROLE_WORD_RE = re.compile(
    r"\b(?:sister|brother|mother|father|wife|husband|daughter|son|aunt|"
    r"uncle|cousin|friend|neighbou?r|photographer|clerk|secretary|butler|"
    r"chauffeur|driver|owner|proprietor|minister|priest|doctor|physician|"
    r"lawyer|judge|policeman|police|detective|servant|postman|waiter|"
    r"waitress|guest|girl|woman|man|boy|companion|student|teacher|professor|"
    r"host|hostess|relative|acquaintance|partner|assistant|employee|"
    r"employer|editor|publisher|artist|painter|singer|actor|actress|"
    r"prince|princess|baron|lord|lady|duke|duchess)\b",
    re.IGNORECASE,
)
_ROLEISH_PAREN_RE = re.compile(
    r"\b(?:representative|chauffeur|sister|brother|wife|husband|friend|"
    r"guest|minor|chapter|chapters|subplot|digression|owner|proprietor|"
    r"neighbou?r|clerk|secretary|driver|doctor|minister|artist)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class NameAlias:
    canonical: str
    alias: str
    appearances_summary: str
    reason_removable: str


@dataclass
class NameOccurrence:
    canonical: str
    alias: str
    segment_id: str
    segment_index: int
    start: int
    end: int
    line: int
    sentence: str
    sentence_start: int
    word_index: int
    has_gloss: bool
    gloss_reason: str | None
    appearances_summary: str
    reason_removable: str


def run_name_lint(
    book: Book,
    *,
    long_gap_segments: int = LONG_GAP_SEGMENTS,
    long_gap_words: int = LONG_GAP_WORDS,
) -> dict[str, Any]:
    """Scan current drafted segments and write `name_lint_report.json`.

    The inventory comes from cuts.json's `minor_characters`; this keeps the
    first version deliberately scoped to names the pipeline has already marked
    removable or safe to collapse to descriptors.
    """
    cuts_path = book.work_dir / "cuts.json"
    plan_path = book.work_dir / "plan.json"
    if not cuts_path.exists():
        raise FileNotFoundError(f"no cuts inventory at {cuts_path}")
    if not plan_path.exists():
        raise FileNotFoundError(f"no plan at {plan_path}")

    cuts = read_json(cuts_path)
    plan = read_json(plan_path)
    aliases = _minor_character_aliases(cuts)
    segment_ids = _lint_segment_ids(plan)

    occurrences_by_name: dict[str, list[NameOccurrence]] = defaultdict(list)
    segment_word_base = 0
    for seg_index, sid in enumerate(segment_ids):
        path = book.work_dir / "segments" / f"{sid}.md"
        if not path.exists():
            continue
        text = path.read_text()
        for occ in _find_occurrences(
            text=text,
            segment_id=sid,
            segment_index=seg_index,
            segment_word_base=segment_word_base,
            aliases=aliases,
        ):
            occurrences_by_name[occ.canonical].append(occ)
        segment_word_base += len(text.split())

    findings: list[dict[str, Any]] = []
    for canonical in sorted(occurrences_by_name):
        occurrences = sorted(
            occurrences_by_name[canonical],
            key=lambda o: (o.segment_index, o.start),
        )
        last_seen: NameOccurrence | None = None
        for occ in occurrences:
            occurrence_type = "first_mention"
            needs_gloss = last_seen is None
            gap_segments = None
            gap_words = None
            if last_seen is not None:
                gap_segments = occ.segment_index - last_seen.segment_index
                gap_words = occ.word_index - last_seen.word_index
                if gap_segments > long_gap_segments or gap_words > long_gap_words:
                    needs_gloss = True
                    occurrence_type = "long_gap_reentry"

            if needs_gloss and not occ.has_gloss:
                findings.append(_finding_from_occurrence(
                    occ,
                    occurrence_type=occurrence_type,
                    gap_segments=gap_segments,
                    gap_words=gap_words,
                ))
            last_seen = occ

    per_segment_counts = Counter(f["segment_id"] for f in findings)
    report = {
        "book_id": book.book_id,
        "segments_checked": len(segment_ids),
        "names_checked": len({a.canonical for a in aliases}),
        "aliases_checked": len(aliases),
        "long_gap_segments": long_gap_segments,
        "long_gap_words": long_gap_words,
        "findings_total": len(findings),
        "per_segment_counts": dict(per_segment_counts),
        "findings": findings,
    }
    write_json(book.work_dir / "name_lint_report.json", report)
    return report


def _minor_character_aliases(cuts: dict[str, Any]) -> list[NameAlias]:
    aliases: dict[str, NameAlias] = {}
    for item in cuts.get("minor_characters", []) or []:
        canonical = _clean_name(str(item.get("name", "")))
        if not canonical:
            continue
        appearances = str(item.get("appearances_summary", "") or "")
        reason = str(item.get("reason_removable", "") or "")
        for alias in _aliases_for_name(canonical):
            key = alias.lower()
            candidate = NameAlias(
                canonical=canonical,
                alias=alias,
                appearances_summary=appearances,
                reason_removable=reason,
            )
            existing = aliases.get(key)
            if existing is None or _prefer_alias_candidate(candidate, existing):
                aliases[key] = candidate
    # Longer aliases first, so overlap filtering keeps "Chester McKee" over
    # "Chester" if both are present at the same position.
    return sorted(aliases.values(), key=lambda a: (-len(a.alias), a.alias))


def _prefer_alias_candidate(candidate: NameAlias, existing: NameAlias) -> bool:
    cand_exact = candidate.canonical.lower() == candidate.alias.lower()
    existing_exact = existing.canonical.lower() == existing.alias.lower()
    if cand_exact != existing_exact:
        return cand_exact
    return len(candidate.canonical) < len(existing.canonical)


def _aliases_for_name(name: str) -> set[str]:
    out: set[str] = set()
    name = _clean_name(name)
    if not name:
        return out

    # Split obvious "A and B" paired entries.
    parts = re.split(r"\s+and\s+", name)
    if len(parts) > 1:
        for part in parts:
            out.update(_aliases_for_name(part))
        return out

    out.add(_strip_outer_quotes(name))
    no_parens = _clean_name(_PAREN_RE.sub("", name))
    if no_parens:
        out.add(_strip_outer_quotes(no_parens))

    for match in _PAREN_RE.finditer(name):
        inner = _clean_name(match.group(1))
        if _looks_like_alias(inner):
            out.add(_strip_outer_quotes(inner))
            first = _first_name_alias(inner)
            if first:
                out.add(first)

            suffix = _clean_name(name[match.end():])
            if suffix and len(inner.split()) == 1:
                combined = _clean_name(f"{inner} {suffix}")
                if _looks_like_alias(combined):
                    out.add(_strip_outer_quotes(combined))

    title_match = _TITLE_RE.match(no_parens)
    stripped_title = _TITLE_RE.sub("", no_parens).strip()
    if stripped_title and stripped_title != no_parens:
        # "Mr. Sloane" often later appears as just "Sloane". Other titles are
        # too collision-prone in nonfiction/classical prose: "Frau Wagner"
        # should not make every reference to the composer "Wagner" a hit.
        title = title_match.group(0).strip().rstrip(".").lower() if title_match else ""
        if title == "mr" and (
            not _PAREN_RE.search(name) or stripped_title.lower() not in {"mckee"}
        ):
            out.add(_strip_outer_quotes(stripped_title))

    if _has_quoted_nickname(name):
        tokens = _name_tokens(no_parens)
        if tokens:
            out.add(tokens[-1])
        nicknameless = _clean_name(re.sub(r"[\"'“”‘’]+", "", no_parens))
        if nicknameless:
            out.add(nicknameless)

    return {a for a in (_clean_name(a) for a in out) if _valid_alias(a)}


def _looks_like_alias(text: str) -> bool:
    if not text or _ROLEISH_PAREN_RE.search(text):
        return False
    return bool(re.search(r"[A-Z]", text))


def _first_name_alias(text: str) -> str | None:
    tokens = _name_tokens(text)
    if len(tokens) < 2:
        return tokens[0] if len(tokens) == 1 else None
    first = tokens[0]
    if first.rstrip(".") in {"Mr", "Mrs", "Ms", "Miss", "Dr", "Doctor"}:
        return None
    return first


def _valid_alias(alias: str) -> bool:
    if len(alias) < 3:
        return False
    if alias.lower() in {"the", "mrs", "miss", "doctor", "representative"}:
        return False
    return bool(re.search(r"[A-Za-z]", alias))


def _find_occurrences(
    *,
    text: str,
    segment_id: str,
    segment_index: int,
    segment_word_base: int,
    aliases: list[NameAlias],
) -> list[NameOccurrence]:
    claimed: list[tuple[int, int, str]] = []
    found: list[NameOccurrence] = []
    for alias in aliases:
        pattern = _alias_pattern(alias.alias)
        for match in pattern.finditer(text):
            if _overlaps_existing(match.start(), match.end(), claimed,
                                  alias.canonical):
                continue
            sentence_start, sentence = _sentence_at(text, match.start(),
                                                    match.end())
            rel_start = match.start() - sentence_start
            rel_end = match.end() - sentence_start
            has_gloss, gloss_reason = _has_local_gloss(
                sentence=sentence,
                rel_start=rel_start,
                rel_end=rel_end,
                alias=alias.alias,
            )
            claimed.append((match.start(), match.end(), alias.canonical))
            found.append(NameOccurrence(
                canonical=alias.canonical,
                alias=alias.alias,
                segment_id=segment_id,
                segment_index=segment_index,
                start=match.start(),
                end=match.end(),
                line=text.count("\n", 0, match.start()) + 1,
                sentence=sentence.strip(),
                sentence_start=sentence_start,
                word_index=segment_word_base + _word_count_before(
                    text, match.start()),
                has_gloss=has_gloss,
                gloss_reason=gloss_reason,
                appearances_summary=alias.appearances_summary,
                reason_removable=alias.reason_removable,
            ))
    return found


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"\s+")
    possessive = r"(?:['’]s)?" if re.search(r"[A-Za-z0-9]$", alias) else ""
    next_name_guard = (
        r"(?!\s+[A-Z][A-Za-z.-]+)" if len(alias.split()) == 1 else ""
    )
    return re.compile(rf"(?<!\w){escaped}{possessive}(?!\w){next_name_guard}",
                      re.IGNORECASE)


def _overlaps_existing(
    start: int,
    end: int,
    claimed: list[tuple[int, int, str]],
    canonical: str,
) -> bool:
    for c_start, c_end, c_name in claimed:
        if c_name == canonical and start < c_end and end > c_start:
            return True
    return False


def _has_local_gloss(
    *,
    sentence: str,
    rel_start: int,
    rel_end: int,
    alias: str,
) -> tuple[bool, str | None]:
    if _PROFESSIONAL_TITLE_RE.match(alias):
        return True, "professional_title"

    left = sentence[max(0, rel_start - 120):rel_start]
    right = sentence[rel_end:min(len(sentence), rel_end + 120)]

    if _after_name_gloss(right):
        return True, "appositive_after_name"
    if _before_name_gloss(left):
        return True, "role_before_name"
    return False, None


def _after_name_gloss(right: str) -> bool:
    return bool(re.match(
        r"\s*(?:['’]s)?\s*(?:,|--|—|-|\()\s*"
        r"(?:(?:the|a|an|his|her|their)\s+|"
        r"(?:[A-Z][A-Za-z]+['’]s)\s+)?"
        r"(?:\w+[\s-]+){0,5}"
        + _ROLE_WORD_RE.pattern,
        right,
        re.IGNORECASE,
    ))


def _before_name_gloss(left: str) -> bool:
    tail = left[-120:]
    # Direct role phrase: "Myrtle's sister Catherine" / "the sister, Catherine".
    direct = re.search(
        r"(?:(?:the|a|an|his|her|their)\s+|"
        r"(?:[A-Z][A-Za-z]+['’]s)\s+)?"
        r"(?:\w+[\s-]+){0,5}"
        + _ROLE_WORD_RE.pattern
        + r"\s*(?:,|:)?\s*[\"'“‘]?\s*$",
        tail,
        re.IGNORECASE,
    )
    if direct:
        return True

    # Direct address can introduce a previously described person:
    # "She turned to her companion: 'Wasn't it for you, Lucille?'"
    if ":" in tail[-80:]:
        before_colon = tail.rsplit(":", 1)[0]
        if _ROLE_WORD_RE.search(before_colon[-80:]):
            return True

    return False


def _sentence_at(text: str, start: int, end: int) -> tuple[int, str]:
    left = max(text.rfind("\n\n", 0, start), text.rfind(". ", 0, start),
               text.rfind("? ", 0, start), text.rfind("! ", 0, start))
    sent_start = 0 if left < 0 else left + (2 if text[left:left + 2] == "\n\n" else 1)
    right_candidates = [
        pos for pos in (
            text.find(". ", end),
            text.find("? ", end),
            text.find("! ", end),
            text.find("\n\n", end),
        ) if pos >= 0
    ]
    sent_end = min(right_candidates) + 1 if right_candidates else len(text)
    return sent_start, text[sent_start:sent_end]


def _finding_from_occurrence(
    occ: NameOccurrence,
    *,
    occurrence_type: str,
    gap_segments: int | None,
    gap_words: int | None,
) -> dict[str, Any]:
    reason = (
        f"{occ.alias!r} is the first surviving named mention of minor/cut "
        "character "
        f"{occ.canonical!r} and it lacks a local role/relationship gloss."
        if occurrence_type == "first_mention"
        else f"{occ.alias!r} re-enters after a long gap without a local gloss."
    )
    return {
        "class": "unglossed_name",
        "severity": "medium",
        "name": occ.canonical,
        "alias": occ.alias,
        "segment_id": occ.segment_id,
        "line": occ.line,
        "occurrence_type": occurrence_type,
        "gap_segments": gap_segments,
        "gap_words": gap_words,
        "draft_passage": occ.sentence,
        "reason": reason,
        "appearances_summary": occ.appearances_summary,
        "reason_removable": occ.reason_removable,
    }


def _lint_segment_ids(plan: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for segment in plan.get("segments", []) or []:
        if segment.get("diegetic_status") != "diegetic":
            continue
        if segment.get("skipped"):
            continue
        if int(segment.get("target_word_count", 0) or 0) == 0:
            continue
        ids.append(str(segment["id"]))
    return ids


def _word_count_before(text: str, offset: int) -> int:
    return sum(1 for _ in _WORD_RE.finditer(text[:offset]))


def _clean_name(value: str) -> str:
    value = value.replace("\u2011", "-").replace("\u2010", "-")
    value = re.sub(r"\s+", " ", value.strip())
    return value


def _strip_outer_quotes(value: str) -> str:
    return value.strip(" \"'“”‘’")


def _has_quoted_nickname(value: str) -> bool:
    return bool(re.search(r"[\"'“‘][^\"'”’]+[\"'”’]", value))


def _name_tokens(value: str) -> list[str]:
    return re.findall(r"[A-Z][A-Za-z.]*", value)
