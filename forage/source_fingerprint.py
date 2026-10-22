"""Source fingerprints for replay-cache provenance.

Replay-cache keys intentionally stay tied to the exact LLM request. Source
fingerprints are metadata that says which pipeline source files produced a
cached response, so audits can flag legacy or stale cache entries without
forcing paid LLM reruns.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .resources import resource_path, PACKAGE_DIR


ROOT = Path(__file__).resolve().parent.parent

COMMON_FILES = [
    "forage/artifacts.py",
    "forage/chapter_split.py",
    "forage/epub_reader.py",
    "forage/llm.py",
    "forage/prompts.py",
    "forage/source_fingerprint.py",
]

STAGE_FILES = {
    "target_revision": [
        "forage/target_revision.py",
        "prompts/preservation_plan.md",
        "prompts/draft_fixed_target.md",
        "prompts/revise_fixed_target.md",
    ],
    "align": [
        "forage/align.py",
        "prompts/align.md",
    ],
    "classify": [
        "forage/chapter_classifier.py",
        "prompts/classify_chapters.md",
    ],
    "coherence": [
        "forage/coherence.py",
        "forage/coherence_filter.py",
        "prompts/critic_coherence.md",
    ],
    "coherence-fix": [
        "forage/coherence_fix.py",
        "forage/coherence_filter.py",
        "prompts/coherence_fix_pair.md",
    ],
    "critic": [
        "forage/critics.py",
        "prompts/critic_signature.md",
    ],
    "critic:book": [
        "forage/book_critic.py",
        "prompts/critic_book.md",
    ],
    "cuts": [
        "forage/cuts.py",
        "prompts/prepass_cuts.md",
    ],
    "draft": [
        "forage/drafter.py",
        "forage/motif_ledger.py",
        "forage/text_norm.py",
        "prompts/draft_lean.md",
        "prompts/draft_segment.md",
        "spec/ABRIDGMENT_SPEC.md",
    ],
    "prepass": [
        "forage/prepass.py",
        "prompts/prepass.md",
    ],
    "prime": [
        "forage/prime.py",
        "prompts/prime.md",
    ],
    "reconsider": [
        "forage/reconsider.py",
        "prompts/reconsider_segment.md",
    ],
    "summarize": [
        "forage/summarizer.py",
        "prompts/summarize_synopsis.md",
        "prompts/summarize_merge.md",
    ],
}


def stage_fingerprint_group(stage: str) -> str:
    first = stage.split(":", 1)[0]
    if stage.startswith("critic:book"):
        return "critic:book"
    if first in {
        "draft",
        "draft_fallback",
        "draft_thinkretry",
        "regen",
        "regen_fallback",
        "regen_thinkretry",
    }:
        return "draft"
    if first.startswith("coherence_fix"):
        return "coherence-fix"
    return first


def _file_digest(rel_path: str) -> dict[str, Any]:
    path = (PACKAGE_DIR / rel_path.removeprefix("forage/")
            if rel_path.startswith("forage/") else resource_path(rel_path))
    if not path.exists():
        return {"path": rel_path, "sha256": None, "missing": True}
    return {
        "path": rel_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "missing": False,
    }


def source_fingerprint_for_stage(stage: str) -> dict[str, Any]:
    group = stage_fingerprint_group(stage)
    rel_paths = sorted(set(COMMON_FILES + STAGE_FILES.get(group, [])))
    files = [_file_digest(rel_path) for rel_path in rel_paths]
    h = hashlib.sha256()
    h.update(b"forage-source-fingerprint-v1\n")
    h.update(f"group={group}\n".encode())
    for item in files:
        h.update(item["path"].encode())
        h.update(b"\0")
        h.update((item["sha256"] or "MISSING").encode())
        h.update(b"\n")
    return {
        "version": 1,
        "group": group,
        "hash": h.hexdigest()[:32],
        "files": files,
    }


def compare_source_fingerprint(stage: str, stored: object) -> dict[str, Any]:
    current = source_fingerprint_for_stage(stage)
    if not isinstance(stored, dict):
        return {
            "status": "missing",
            "current": current,
            "stored": None,
        }
    if stored.get("version") != current["version"]:
        return {
            "status": "stale",
            "current": current,
            "stored": stored,
            "reason": "fingerprint version changed",
        }
    if stored.get("group") != current["group"]:
        return {
            "status": "stale",
            "current": current,
            "stored": stored,
            "reason": "stage group changed",
        }
    if stored.get("hash") != current["hash"]:
        return {
            "status": "stale",
            "current": current,
            "stored": stored,
            "reason": "source hash changed",
        }
    return {
        "status": "current",
        "current": current,
        "stored": stored,
    }
