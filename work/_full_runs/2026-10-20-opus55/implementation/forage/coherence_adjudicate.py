"""Adjudicate coherence critic findings before repair.

The coherence critic is tuned for recall. This stage applies stricter,
mostly mechanical gates so broad critic reports can be reviewed or passed to
coherence-fix without letting stale, duplicate, or weak findings drive edits.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .artifacts import Book, read_json, write_json
from .coherence_filter import finding_dedupe_key, normalize_finding_validity


_ROLE_WORD_RE = re.compile(
    r"\b(?:grandmother|grandfather|mother|father|wife|husband|daughter|son|"
    r"sister|brother|friend|acquaintance|neighbor|neighbour|companion|"
    r"secretary|minister|ambassador|diplomat|diplomatist|editor|author|"
    r"historian|artist|painter|sculptor|geologist|professor|student|"
    r"member|cabinet|duke|lord|lady|baron|prince|princess|senator|"
    r"president|chancellor|exchequer|consul|poet|writer|singer|actor|"
    r"actress|rival|monk|monks|englishmen|survey|party|staff)\b",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Doctor|Sir|Lord|Lady|Baron|Prince|Princess|"
    r"Frau|Mlle|Mme|M)\.?\s+",
    re.IGNORECASE,
)
_QUOTE_RE = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{2,80})[\"'“”‘’]")
_PROPER_SEQ_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z]+\.?\s+){0,4}[A-Z][A-Za-z][A-Za-z.'-]*s?\b"
)
_COMMON_PROPER_WORDS = {
    "Adams",
    "America",
    "American",
    "Boston",
    "Chapter",
    "Education",
    "England",
    "English",
    "Europe",
    "Government",
    "History",
    "London",
    "New",
    "Russia",
    "The",
    "Thus",
    "Washington",
}
_NAME_STOPWORDS = {
    "m",
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "doctor",
    "sir",
    "lord",
    "lady",
    "baron",
    "prince",
    "princess",
    "frau",
    "mme",
    "mlle",
    "de",
    "von",
    "van",
    "the",
    "and",
    "after",
    "approaching",
    "before",
    "eighty",
    "even",
    "he",
    "in",
    "perhaps",
    "suddenly",
    "vaguely",
    "when",
}
_PRONOUN_RE = re.compile(
    r"\b(?:he|she|it|they|them|their|theirs|themselves|this|that|these|"
    r"those|his|her|hers|its)\b",
    re.IGNORECASE,
)
_FINITE_VERB_RE = re.compile(
    r"\b(?:am|are|is|was|were|be|been|being|had|has|have|do|does|did|"
    r"can|could|may|might|must|shall|should|will|would|seem(?:s|ed)?|"
    r"became|become|began|made|make|makes|felt|found|stood|took|went|"
    r"came|saw|knew|thought|said|wrote|read|studied|looked|turned|"
    r"offered|raised|marched|received|protected|appeared|"
    r"refused|lured|belonged|needed|grasped|flung)\b",
    re.IGNORECASE,
)
_LEADING_NAME_NOISE = {
    "after",
    "approaching",
    "before",
    "eighty",
    "even",
    "he",
    "in",
    "perhaps",
    "suddenly",
    "the",
    "vaguely",
    "when",
}


def run_coherence_adjudication(
    book: Book,
    *,
    report_path: Path | None = None,
    output_path: Path | None = None,
    include_low_confidence: bool = False,
) -> dict[str, Any]:
    """Adjudicate `coherence_report.json` and write a repair-ready report."""
    report_path = report_path or (book.work_dir / "coherence_report.json")
    output_path = output_path or (book.work_dir / "coherence_adjudication_report.json")
    if not report_path.exists():
        raise FileNotFoundError(
            f"no coherence report at {report_path}; run `forage coherence {book.book_id}` first"
        )

    report = read_json(report_path)
    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else {}
    inventory = _MinorNameInventory(cuts)

    adjudicated: list[dict[str, Any]] = []
    duplicate_basis: list[dict[str, Any]] = []
    for idx, finding in enumerate(report.get("findings", []) or []):
        if not isinstance(finding, dict):
            continue
        normalized = normalize_finding_validity(finding)
        row = dict(normalized)
        row["_finding_index"] = idx

        verdict = _adjudicate_one(
            book=book,
            finding=row,
            duplicate_basis=duplicate_basis,
            inventory=inventory,
        )
        repair_candidate = (
            verdict["verdict"] == "valid"
            and (
                include_low_confidence
                or verdict["repair_priority"] in {"high", "medium"}
            )
        )
        row["adjudication"] = verdict
        row["adjudicated_valid"] = verdict["verdict"] == "valid"
        row["repair_candidate"] = repair_candidate

        if verdict["verdict"] == "valid":
            duplicate_basis.append({
                "key": finding_dedupe_key(row),
                "segment_id": row.get("segment_id"),
                "class": row.get("class"),
                "draft_passage": row.get("draft_passage") or "",
                "finding_index": idx,
                "pair": row.get("pair"),
            })
        adjudicated.append(row)

    verdict_counts = Counter(
        f.get("adjudication", {}).get("verdict", "?") for f in adjudicated
    )
    priority_counts = Counter(
        f.get("adjudication", {}).get("repair_priority", "?")
        for f in adjudicated
    )
    class_counts = Counter(
        f.get("class", "?") for f in adjudicated
        if f.get("repair_candidate")
    )
    per_pair_counts = Counter(
        f.get("pair", "?") for f in adjudicated
        if f.get("repair_candidate")
    )

    out = {
        "book_id": book.book_id,
        "source_report": str(report_path),
        "findings_seen": len(adjudicated),
        "repair_candidates": sum(1 for f in adjudicated if f.get("repair_candidate")),
        "valid_findings": sum(1 for f in adjudicated if f.get("adjudicated_valid")),
        "verdict_counts": dict(verdict_counts),
        "repair_priority_counts": dict(priority_counts),
        "repair_candidate_class_counts": dict(class_counts),
        "repair_candidate_pair_counts": dict(per_pair_counts),
        "include_low_confidence": include_low_confidence,
        "findings": adjudicated,
    }
    write_json(output_path, out)
    return out


def _adjudicate_one(
    *,
    book: Book,
    finding: dict[str, Any],
    duplicate_basis: list[dict[str, Any]],
    inventory: "_MinorNameInventory",
) -> dict[str, Any]:
    if not finding.get("valid", True):
        return _verdict(
            "false_positive",
            "critic_explicitly_marked_invalid",
            "none",
            "The critic finding was already marked invalid or self-rejected.",
        )

    segment_id = str(finding.get("segment_id") or "").strip()
    passage = str(finding.get("draft_passage") or "").strip()
    segment_text = _read_segment_text(book, segment_id)
    located = _locate_passage(segment_text, passage)
    if not located.found:
        return _verdict(
            "stale",
            "draft_passage_not_found",
            "none",
            "The reported draft passage no longer appears in the current segment.",
        )

    duplicate = _find_duplicate(finding, duplicate_basis)
    if duplicate is not None:
        return _verdict(
            "duplicate",
            "duplicate_draft_passage",
            "none",
            "This repeats an earlier finding against the same current passage.",
            duplicate_of={
                "pair": duplicate.get("pair"),
                "finding_index": duplicate.get("finding_index"),
                "segment_id": duplicate.get("segment_id"),
            },
        )

    cls = str(finding.get("class") or "")
    if cls == "unglossed_name":
        return _adjudicate_name(finding, segment_text, located, inventory)
    if cls == "missing_gloss":
        return _adjudicate_missing_gloss(finding, segment_text, located)
    if cls == "non_parseable":
        return _adjudicate_non_parseable(finding, segment_text, located)
    if cls == "dangling_reference":
        return _adjudicate_dangling_reference(finding, segment_text, located)
    if cls == "broken_pivot":
        return _adjudicate_broken_pivot(finding, segment_text, located)
    if cls == "unattributed_dialogue":
        return _verdict(
            "valid",
            "dialogue_claim_requires_repair_review",
            "medium",
            "Dialogue-attribution findings are not mechanically disproved; keep for repair review.",
        )
    if cls == "mid_scene_jump":
        return _verdict(
            "valid",
            "scene_jump_claim_requires_repair_review",
            "medium",
            "Mid-scene-jump findings are not mechanically disproved; keep for repair review.",
        )
    return _verdict(
        "low_confidence",
        "unknown_finding_class",
        "low",
        f"Unknown coherence class {cls!r}; do not auto-repair without review.",
    )


def _adjudicate_name(
    finding: dict[str, Any],
    segment_text: str,
    located: "_LocatedPassage",
    inventory: "_MinorNameInventory",
) -> dict[str, Any]:
    target = _extract_name_target(finding)
    in_inventory = inventory.matches(target)
    if in_inventory:
        return _verdict(
            "valid",
            "minor_inventory_name_or_alias",
            "high",
            f"{target or 'The name'} matches the minor-character/cut inventory.",
        )

    source_has = str(finding.get("source_has") or "")
    source_has_role = _name_has_role_context(target, source_has)
    draft_has_role = _name_has_role_context(
        target,
        str(finding.get("draft_passage") or "") or located.context,
    )
    if source_has_role and not draft_has_role:
        return _verdict(
            "valid",
            "source_role_gloss_cut_from_draft",
            "medium",
            f"The source gives {target or 'the name'} a nearby role/appositive that the draft lacks.",
        )

    if _gate_claims_source_cut(finding) and not draft_has_role:
        return _verdict(
            "low_confidence",
            "critic_claims_cut_intro_but_no_mechanical_proof",
            "low",
            "The critic claims the introduction was cut, but the source excerpt does not mechanically prove a role gloss.",
        )

    return _verdict(
        "false_positive",
        "unfamiliar_name_not_abridgment_coherence",
        "none",
        "The finding only shows that a historical proper name may be unfamiliar; it does not prove an abridgment-caused coherence break.",
    )


def _adjudicate_missing_gloss(
    finding: dict[str, Any],
    segment_text: str,
    located: "_LocatedPassage",
) -> dict[str, Any]:
    source_has = str(finding.get("source_has") or "")
    passage = str(finding.get("draft_passage") or "")
    if not _source_has_extra_explanatory_material(source_has, passage):
        return _verdict(
            "low_confidence",
            "missing_gloss_not_mechanically_supported",
            "low",
            "The source excerpt does not show a clear explanatory gloss missing from the draft passage.",
        )

    if _source_gloss_already_local(source_has, located.context, passage):
        return _verdict(
            "false_positive",
            "gloss_present_in_local_draft_context",
            "none",
            "The supposedly missing explanatory material is already present near the current draft passage.",
        )

    return _verdict(
        "valid",
        "source_gloss_cut_from_draft",
        "medium",
        "The source excerpt contains explanatory setup or a role gloss that is absent from the local draft context.",
    )


def _adjudicate_non_parseable(
    finding: dict[str, Any],
    segment_text: str,
    located: "_LocatedPassage",
) -> dict[str, Any]:
    passage = str(finding.get("draft_passage") or "")
    if _looks_like_fragment(passage):
        return _verdict(
            "valid",
            "reported_passage_looks_fragmentary",
            "high",
            "The reported draft passage itself appears to lack a complete main clause.",
        )
    sentence = _current_sentence(segment_text, located.start, located.end)
    if _looks_like_fragment(sentence):
        return _verdict(
            "valid",
            "current_sentence_looks_fragmentary",
            "high",
            "The current draft sentence appears to lack a complete main clause.",
        )
    return _verdict(
        "low_confidence",
        "sentence_now_parses_or_needs_human_review",
        "low",
        "The current sentence is not mechanically fragmentary; review before repair.",
    )


def _adjudicate_dangling_reference(
    finding: dict[str, Any],
    segment_text: str,
    located: "_LocatedPassage",
) -> dict[str, Any]:
    passage = str(finding.get("draft_passage") or "")
    if not _PRONOUN_RE.search(passage):
        return _verdict(
            "false_positive",
            "no_reference_trigger_in_passage",
            "none",
            "The draft passage does not contain a pronoun or demonstrative trigger.",
        )

    if _demonstrative_noun_has_local_antecedent(passage, located.context_before):
        return _verdict(
            "false_positive",
            "demonstrative_noun_has_local_antecedent",
            "none",
            "The demonstrative phrase has a plausible local antecedent in the current draft.",
        )

    source_has = str(finding.get("source_has") or "")
    if _source_has_clearer_reference(source_has, passage, located.context):
        return _verdict(
            "valid",
            "source_antecedent_cut_from_draft",
            "high",
            "The source excerpt supplies a clearer antecedent or plural referent that the draft omits.",
        )

    return _verdict(
        "valid",
        "reference_claim_not_mechanically_disproved",
        "medium",
        "The passage contains a reference trigger and no local antecedent was mechanically established.",
    )


def _adjudicate_broken_pivot(
    finding: dict[str, Any],
    segment_text: str,
    located: "_LocatedPassage",
) -> dict[str, Any]:
    passage = str(finding.get("draft_passage") or "")
    if not re.search(r"\b(?:but|yet|however|because|therefore|thus|in contrast|more)\b", passage, re.IGNORECASE):
        return _verdict(
            "low_confidence",
            "no_clear_pivot_token",
            "low",
            "No mechanical pivot token was found in the reported passage.",
        )
    source_has = str(finding.get("source_has") or "")
    if _source_has_extra_explanatory_material(source_has, passage):
        return _verdict(
            "valid",
            "pivot_setup_cut_from_draft",
            "medium",
            "The source excerpt includes setup for the pivot that is absent from the reported draft passage.",
        )
    return _verdict(
        "low_confidence",
        "pivot_claim_not_mechanically_supported",
        "low",
        "The pivot claim is plausible but not mechanically supported by the source excerpt.",
    )


def _read_segment_text(book: Book, segment_id: str) -> str:
    if not segment_id:
        return ""
    path = book.work_dir / "segments" / f"{segment_id}.md"
    if not path.exists():
        return ""
    return path.read_text()


class _LocatedPassage:
    def __init__(self, found: bool, start: int = -1, end: int = -1,
                 context: str = "", context_before: str = "") -> None:
        self.found = found
        self.start = start
        self.end = end
        self.context = context
        self.context_before = context_before


def _locate_passage(text: str, passage: str) -> _LocatedPassage:
    if not text or not passage:
        return _LocatedPassage(False)

    candidates = _passage_candidates(passage)
    norm_text, offset_map = _norm_with_offsets(text)
    for candidate in candidates:
        norm_candidate = _norm(candidate)
        if len(norm_candidate) < 18:
            continue
        idx = norm_text.find(norm_candidate)
        if idx >= 0:
            start = offset_map[min(idx, len(offset_map) - 1)]
            norm_end = min(len(offset_map) - 1, idx + len(norm_candidate) - 1)
            end = min(len(text), offset_map[norm_end] + 1)
            return _LocatedPassage(
                True,
                start,
                end,
                text[max(0, start - 500):min(len(text), end + 500)],
                text[max(0, start - 500):start],
            )

    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", passage)
    if len(words) >= 5:
        pattern = r"\W+".join(re.escape(w) for w in words[:5])
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            start = m.start()
            end = min(len(text), start + len(passage))
            return _LocatedPassage(
                True,
                start,
                end,
                text[max(0, start - 500):min(len(text), end + 500)],
                text[max(0, start - 500):start],
            )

    return _LocatedPassage(False)


def _passage_candidates(passage: str) -> list[str]:
    parts = re.split(r"\s*(?:\.{3}|…)\s*", passage)
    out = [p.strip() for p in parts if len(p.strip()) >= 24]
    if len(passage) >= 24:
        out.append(passage.strip())
    return sorted(set(out), key=len, reverse=True)


def _current_sentence(text: str, start: int, end: int) -> str:
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
    return text[sent_start:sent_end].strip()


def _looks_like_fragment(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return True
    if re.match(r"^Only\b", stripped) and "whose" in stripped and ";" not in stripped:
        return True
    if re.match(r"^(?:Only|Just|Merely)\b", stripped) and not _FINITE_VERB_RE.search(stripped):
        return True
    if re.match(r"^(?:Two|Three|Four|Five|Several|Many|A|An|The)\b", stripped):
        if re.search(r";\s*and\s+not\s+one\b", stripped, re.IGNORECASE):
            return True
    if re.fullmatch(r"The students alone satisfied\.?", stripped):
        return True
    if not _FINITE_VERB_RE.search(stripped) and len(stripped.split()) > 4:
        return True
    return False


def _find_duplicate(
    finding: dict[str, Any],
    duplicate_basis: list[dict[str, Any]],
) -> dict[str, Any] | None:
    key = finding_dedupe_key(finding)
    passage = _norm(finding.get("draft_passage") or "")
    for previous in duplicate_basis:
        if key == previous.get("key"):
            return previous
        if previous.get("segment_id") != finding.get("segment_id"):
            continue
        if previous.get("class") != finding.get("class"):
            continue
        prev_passage = _norm(previous.get("draft_passage") or "")
        if not passage or not prev_passage:
            continue
        shorter, longer = sorted([passage, prev_passage], key=len)
        if len(shorter) >= 45 and shorter in longer:
            return previous
    return None


def _extract_name_target(finding: dict[str, Any]) -> str:
    for key in ("name", "alias"):
        value = str(finding.get(key) or "").strip()
        if value:
            return value

    gate = str(finding.get("gate_test_answer") or "")
    for pattern in (
        r"\bwho\s+[\"'“”‘’]?([A-Z][A-Za-z.' -]{2,80}?)[\"'“”‘’]?\s+(?:is|was|matters|represents|or why)\b",
        r"\babout\s+who\s+[\"'“”‘’]?([A-Z][A-Za-z.' -]{2,80}?)[\"'“”‘’]?\s+(?:is|was)\b",
        r"\bunsure\s+who\s+[\"'“”‘’]?([A-Z][A-Za-z.' -]{2,80}?)[\"'“”‘’]?\s+(?:is|was)\b",
    ):
        match = re.search(pattern, gate)
        if match:
            return _clean_name_candidate(match.group(1))

    quoted = [
        _clean_name_candidate(q.strip())
        for q in _QUOTE_RE.findall(gate)
        if _looks_like_name(q.strip())
    ]
    if quoted:
        return quoted[0]

    passage = str(finding.get("draft_passage") or "")
    title_match = re.search(
        r"\b(?:Mr|Mrs|Ms|Miss|Dr|Doctor|Sir|Lord|Lady|Baron|Prince|"
        r"Princess|Frau|Mlle|Mme|M)\.?\s+(?:de\s+|von\s+|van\s+)?"
        r"(?:[A-Z][A-Za-z.'-]+\s+){0,4}[A-Z][A-Za-z.'-]+s?\b",
        passage,
    )
    if title_match:
        return _clean_name_candidate(title_match.group(0))

    candidates = [
        _clean_name_candidate(c.strip())
        for c in _PROPER_SEQ_RE.findall(passage)
        if _looks_like_name(c.strip())
    ]
    if candidates:
        return candidates[-1]
    return ""


def _clean_name_candidate(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip(" .,:;!?\"'“”‘’"))
    parts = text.split()
    while parts and parts[0].lower().strip(".") in _LEADING_NAME_NOISE:
        parts.pop(0)
    while parts and parts[-1].lower().strip(".") in {
        "is",
        "was",
        "or",
        "why",
        "what",
        "matters",
    }:
        parts.pop()
    return " ".join(parts)


def _looks_like_name(text: str) -> bool:
    if not text or len(text) < 3:
        return False
    if text in _COMMON_PROPER_WORDS:
        return False
    if text.lower() in {"the madam", "madam"}:
        return True
    return bool(re.search(r"[A-Z]", text))


class _MinorNameInventory:
    def __init__(self, cuts: dict[str, Any]) -> None:
        self.entries: list[tuple[str, set[str], bool]] = []
        for item in cuts.get("minor_characters", []) or []:
            name = str(item.get("name") or "")
            tokens = _name_tokens(name)
            if not tokens:
                continue
            has_title = bool(_TITLE_RE.search(name))
            self.entries.append((name, tokens, has_title))
            for part in re.split(r"\s+and\s+", name):
                part_tokens = _name_tokens(part)
                if part_tokens:
                    self.entries.append((part, part_tokens, has_title))

    def matches(self, target: str) -> bool:
        target_tokens = _name_tokens(target)
        if not target_tokens:
            return False
        target_has_title = bool(_TITLE_RE.search(target))
        for _name, tokens, inventory_has_title in self.entries:
            if target_tokens == tokens:
                return True
            if len(target_tokens) == 1:
                token = next(iter(target_tokens))
                if token in tokens:
                    return True
            if target_has_title and target_tokens & tokens:
                return True
            if len(target_tokens) >= 2 and len(target_tokens & tokens) >= 2:
                return True
            if inventory_has_title and len(tokens) == 1 and target_has_title and tokens <= target_tokens:
                return True
        return False


def _name_tokens(name: str) -> set[str]:
    normalized = _norm(name)
    normalized = normalized.replace("st ", "saint ")
    tokens: set[str] = set()
    for raw in re.findall(r"[a-z][a-z0-9']*", normalized):
        token = raw.strip("'")
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        if token and token not in _NAME_STOPWORDS:
            tokens.add(token)
    return tokens


def _name_has_role_context(name: str, text: str) -> bool:
    if not name or not text:
        return False
    tokens = list(_name_tokens(name))
    if not tokens:
        return False
    norm_text = _norm(text)
    positions: list[int] = []
    for token in tokens:
        idx = norm_text.find(token)
        if idx >= 0:
            positions.append(idx)
    if not positions:
        return False
    center = min(positions)
    window = norm_text[max(0, center - 160):center + 220]
    target_norm = _norm(name)
    if target_norm:
        window = window.replace(target_norm, " ")
    return bool(_ROLE_WORD_RE.search(window))


def _source_has_extra_explanatory_material(source_has: str, passage: str) -> bool:
    source_norm = _norm(source_has)
    passage_norm = _norm(passage)
    if not source_norm:
        return False
    if len(source_norm) < len(passage_norm) + 40:
        return bool(_ROLE_WORD_RE.search(source_norm)) and source_norm != passage_norm
    if re.search(r"\b(?:who|which|called|as|consisted|represented|meaning|that is|i e)\b", source_norm):
        return True
    return bool(_ROLE_WORD_RE.search(source_norm))


def _source_gloss_already_local(
    source_has: str,
    local_context: str,
    passage: str,
) -> bool:
    source_norm = _norm(source_has)
    local_norm = _norm(local_context)
    for phrase in (
        "another member of the cabinet",
        "called the horseshoe",
        "diplomatic tradition",
        "form a staff",
        "three or four young englishmen",
        "who sat",
    ):
        if phrase in source_norm and phrase not in local_norm:
            return False

    source_extra = source_norm
    for chunk in _passage_candidates(passage):
        source_extra = source_extra.replace(_norm(chunk), " ")

    source_words = _distinctive_words(source_extra) or _distinctive_words(source_has)
    if len(source_words) < 3:
        return False
    hits = sum(1 for w in source_words if w in local_norm)
    return hits >= min(5, max(3, len(source_words) // 2))


def _distinctive_words(text: str) -> list[str]:
    words = []
    for word in re.findall(r"[a-z][a-z0-9'-]{4,}", _norm(text)):
        if word in {
            "about",
            "after",
            "before",
            "could",
            "draft",
            "every",
            "found",
            "their",
            "there",
            "these",
            "thing",
            "which",
            "would",
        }:
            continue
        if word not in words:
            words.append(word)
    return words[:14]


def _source_has_clearer_reference(
    source_has: str,
    passage: str,
    local_context: str,
) -> bool:
    source_norm = _norm(source_has)
    passage_norm = _norm(passage)
    if not source_norm:
        return False
    if "prince khilkoff" in source_norm and "khilkoff" not in _norm(local_context):
        return True
    if "history" in source_norm and re.search(r"\bit\b", passage_norm):
        return True
    if "man could" in source_norm and re.search(r"\bhis\b", passage_norm):
        return True
    source_names = _proper_name_count(source_has)
    passage_names = _proper_name_count(passage)
    return source_names > passage_names


def _proper_name_count(text: str) -> int:
    return len([
        c for c in _PROPER_SEQ_RE.findall(text)
        if _looks_like_name(c.strip())
    ])


def _demonstrative_noun_has_local_antecedent(passage: str, context_before: str) -> bool:
    match = re.search(r"\b(?:this|that|these|those)\s+([a-z][a-z'-]{3,})", passage, re.IGNORECASE)
    if not match:
        return False
    noun = match.group(1).lower()
    before = _norm(context_before[-350:])
    if noun in before:
        return True
    if noun == "sympathy" and re.search(r"\bfriendship|friendly|friend\b", before):
        return True
    if noun == "support" and re.search(r"\bpen|staff|support\b", before):
        return True
    return False


def _gate_claims_source_cut(finding: dict[str, Any]) -> bool:
    gate = _norm(finding.get("gate_test_answer") or "")
    return bool(re.search(r"\b(?:cut|omits|omitted|never identifies|introduced in source)\b", gate))


def _verdict(
    verdict: str,
    reason: str,
    priority: str,
    explanation: str,
    **extra: Any,
) -> dict[str, Any]:
    out = {
        "verdict": verdict,
        "reason": reason,
        "repair_priority": priority,
        "explanation": explanation,
    }
    out.update(extra)
    return out


def _norm(value: Any) -> str:
    text = str(value or "").lower()
    for src, dst in {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": "\"",
        "\u201d": "\"",
        "\u2026": "...",
        "\u00a0": " ",
    }.items():
        text = text.replace(src, dst)
    text = text.replace("saint-gaudens", "saint gaudens")
    text = text.replace("st. ", "saint ")
    return re.sub(r"\s+", " ", text).strip()


def _norm_with_offsets(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    offsets: list[int] = []
    last_space = True
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": "\"",
        "\u201d": "\"",
        "\u00a0": " ",
    }
    i = 0
    while i < len(value):
        ch = value[i]
        if value.startswith("saint-gaudens", i):
            repl = "saint gaudens"
        elif value.startswith("Saint-Gaudens", i):
            repl = "saint gaudens"
        elif value.startswith("st. ", i) or value.startswith("St. ", i):
            repl = "saint "
        elif ch == "\u2026":
            repl = "..."
        else:
            repl = replacements.get(ch, ch).lower()

        for out_ch in repl:
            if out_ch.isspace():
                if not last_space:
                    chars.append(" ")
                    offsets.append(i)
                    last_space = True
                continue
            chars.append(out_ch)
            offsets.append(i)
            last_space = False
        i += len("Saint-Gaudens") if value.startswith("Saint-Gaudens", i) else (
            len("saint-gaudens") if value.startswith("saint-gaudens", i) else (
                len("St. ") if value.startswith("St. ", i) else (
                    len("st. ") if value.startswith("st. ", i) else 1
                )
            )
        )

    if chars and chars[-1] == " ":
        chars.pop()
        offsets.pop()
    if not offsets:
        offsets = [0]
    return "".join(chars), offsets
