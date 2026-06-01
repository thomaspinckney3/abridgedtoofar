"""Validity and dedupe helpers for coherence findings."""

from __future__ import annotations

import re
from typing import Any


_FALSE_VALID_VALUES = {
    "0",
    "false",
    "invalid",
    "no",
    "not valid",
    "not_valid",
}
_TRUE_VALID_VALUES = {
    "1",
    "true",
    "valid",
    "yes",
}

_NOT_VALID_RE = re.compile(
    r"\b(?:not|isn't|is not)\s+(?:a\s+)?valid\s+finding\b"
)
_NOT_CONFUSED_RE = re.compile(
    r"\bnot\s+(?:actually|genuinely|seriously)\s+confused\b"
)
_LESS_ORNAMENTED_RE = re.compile(
    r"\b(?:merely|just|only)\s+(?:be\s+)?(?:reading\s+)?"
    r"a\s+less[- ]ornamented\s+version\b"
)
_STILL_STANDS_RE = re.compile(
    r"\b(?:still\s+parses|stands\s+on\s+its\s+own)\b"
)
_CAN_INFER_RE = re.compile(
    r"\breader\s+(?:can|could|would)\s+infer\b"
)


def coerce_valid_field(value: Any) -> bool | None:
    """Return a boolean for explicit validity values, or None if absent."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = _normalize_text(value).strip(" .,:;!?'\"")
        if normalized in _FALSE_VALID_VALUES:
            return False
        if normalized in _TRUE_VALID_VALUES:
            return True
    return None


def self_rejection_reason(finding: dict[str, Any]) -> str | None:
    """Identify critic rows that explicitly reject themselves."""
    text = _normalize_text(" ".join([
        str(finding.get("valid", "")),
        str(finding.get("gate_test_answer", "")),
        str(finding.get("class", "")),
    ]))
    if not text:
        return None
    if _NOT_VALID_RE.search(text):
        return "self_rejected:not_valid_finding"
    if _NOT_CONFUSED_RE.search(text):
        return "self_rejected:not_confused"
    if _has_unnegated_rejection(_LESS_ORNAMENTED_RE, text):
        return "self_rejected:less_ornamented"
    if _has_unnegated_rejection(_STILL_STANDS_RE, text):
        return "self_rejected:still_parses"
    if _CAN_INFER_RE.search(text):
        return "self_rejected:reader_can_infer"
    return None


def finding_validity(finding: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (is_valid, invalid_reason) for a coherence finding."""
    explicit = coerce_valid_field(finding.get("valid"))
    if explicit is False:
        return False, "explicit_valid_false"

    rejection = self_rejection_reason(finding)
    if rejection:
        return False, rejection

    return True, None


def normalize_finding_validity(finding: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with a normalized boolean `valid` field."""
    normalized = dict(finding)
    valid, reason = finding_validity(normalized)
    normalized["valid"] = valid
    if reason:
        normalized["invalid_reason"] = reason
    else:
        normalized.pop("invalid_reason", None)
    return normalized


def finding_dedupe_key(finding: dict[str, Any]) -> tuple[str, str]:
    """Key repeated findings by target segment and damaged draft passage."""
    scope = str(finding.get("segment_id") or finding.get("pair") or "")
    passage = _normalize_text(finding.get("draft_passage") or "")
    if finding.get("name_lint") and finding.get("alias"):
        passage = f"{_normalize_text(finding.get('alias'))}: {passage}"
    if not passage:
        passage = _normalize_text(" ".join([
            str(finding.get("class", "")),
            str(finding.get("source_has", "")),
            str(finding.get("gate_test_answer", "")),
        ]))
    return scope, passage


def _normalize_text(value: Any) -> str:
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
    }.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def _has_unnegated_rejection(pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 24):match.start()]
        if re.search(
            r"\b(?:not|no longer|does not|doesn't|cannot|can't)\s+$",
            prefix,
        ):
            continue
        return True
    return False
