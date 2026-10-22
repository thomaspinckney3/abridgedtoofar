"""Tolerant JSON parsing for LLM outputs.

LLMs occasionally emit malformed JSON — most often unescaped `"` inside a
string value (e.g. a verbatim quotation inside a passage_hint), but also
trailing commas, missing commas, truncated output, or prose around the JSON.
The tiered parser here tries to recover from each of these without masking
true failures.

Tiers:
  1. Strict `json.loads` on the stripped text (fast path).
  2. Strip markdown code fences and retry.
  3. Slice from first `{` to last `}` (drops stray prose before/after).
  4. Fall back to `json_repair` (handles unescaped quotes etc.).
  5. Raise with context — fail loud rather than return garbage.
"""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_llm_json(text: str) -> dict:
    stripped = text.strip()
    # Tier 2 preprocessing: strip markdown code fence if wrapping the payload.
    fence = _FENCE_RE.match(stripped)
    if fence:
        stripped = fence.group(1).strip()

    # Tier 1: strict
    try:
        return _require_dict(json.loads(stripped))
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 3: slice between outermost braces
    start = stripped.find("{")
    end = stripped.rfind("}")
    candidate = stripped[start:end + 1] if start >= 0 and end >= 0 else stripped
    try:
        return _require_dict(json.loads(candidate))
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 4: json-repair — handles LLM-specific brokenness
    try:
        from json_repair import loads as repair_loads
    except ImportError as e:  # pragma: no cover
        raise ValueError(
            f"could not parse JSON from {len(stripped)} chars and "
            f"json-repair is not installed"
        ) from e
    try:
        repaired = repair_loads(candidate)
        return _require_dict(repaired)
    except Exception as e:
        raise ValueError(
            f"could not parse JSON from {len(stripped)} chars even with "
            f"json-repair fallback: {e}"
        ) from e


def _require_dict(obj: Any) -> dict:
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    return obj
