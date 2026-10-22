"""Locate reviewed passages without treating an old paragraph number as identity.

Original anchors remain immutable. A generation decision may explicitly bind
one original passage to several revised paragraphs; those bindings are valid
only while their recorded text still matches. Ambiguous matches stay unplaced.
"""
from __future__ import annotations

import hashlib
import json
import re


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def anchor_hash(text: str) -> str:
    return hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


def chapter_hash(paras: list[str]) -> str:
    return hashlib.sha256(json.dumps(paras, ensure_ascii=False).encode()).hexdigest()


def make_binding(comment: dict, paras: list[str], indices: list[int], display_paragraph: int | None = None) -> dict:
    original = comment.get("reviewed_paragraph", comment.get("original_text"))
    anchor = comment.get("anchor")
    if not isinstance(original, str) or not anchor or anchor_hash(original) != anchor:
        raise ValueError("comment binding requires verified original text")
    if (not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(paras) for i in indices)
            or indices != sorted(set(indices))):
        raise ValueError("comment target paragraphs must be unique ordered final indices")
    if display_paragraph is None and indices:
        display_paragraph = indices[0]
    if ((indices and (type(display_paragraph) is not int or display_paragraph not in indices))
            or (not indices and display_paragraph is not None)):
        raise ValueError("display paragraph must belong to the corrected passage")
    return {"anchor": anchor, "original_text": original,
            "primary_target": indices.index(display_paragraph) if indices else None,
            "draft_para": comment.get("original_draft_para", comment.get("draft_para")),
            "chapter_hash": chapter_hash(paras),
            "targets": [{"draft_para": i, "text": paras[i]} for i in indices]}


def locate(comment: dict, paras: list[str], binding: dict | None = None) -> dict:
    """Return derived display locations; never change the original position."""
    current_hash = chapter_hash(paras)
    anchor = comment.get("anchor")
    original = comment.get("original_text", comment.get("reviewed_paragraph"))
    result = {"current_draft_para": None, "current_draft_paras": [],
              "attachment_status": "unplaced", "original_text": original,
              "stale": bool(anchor), "orphaned": not paras}
    verified = (isinstance(binding, dict) and binding.get("anchor") == anchor
                and binding.get("draft_para") == comment.get("draft_para")
                and isinstance(binding.get("original_text"), str)
                and bool(anchor) and anchor_hash(binding["original_text"]) == anchor)
    if verified and original is None:
        result["original_text"] = binding["original_text"]
    matches = [i for i, p in enumerate(paras) if anchor and anchor_hash(p) == anchor]
    idx = comment.get("draft_para")
    if (comment.get("chapter_anchor") == current_hash and type(idx) is int
            and idx in matches):
        matches = [idx]
    if len(matches) == 1 and (not verified or comment.get("chapter_anchor") == current_hash):
        result.update(current_draft_para=matches[0], current_draft_paras=matches,
                      attachment_status="exact", stale=False, orphaned=False)
        return result
    if verified:
        targets = binding.get("targets")
        if not isinstance(targets, list):
            return result
        if not targets:
            result.update(attachment_status="removed", orphaned=True)
            return result
        indices = []
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("text"), str):
                return result
            idx = target.get("draft_para")
            if (binding.get("chapter_hash") == current_hash and type(idx) is int
                    and 0 <= idx < len(paras) and paras[idx] == target["text"]):
                found = [idx]
            else:
                found = [i for i, p in enumerate(paras) if p == target["text"]]
            if len(found) != 1:
                return result
            indices.extend(found)
        if indices != sorted(set(indices)):
            return result
        primary = binding.get("primary_target", 0)
        if type(primary) is not int or not 0 <= primary < len(indices):
            return result
        result.update(current_draft_para=indices[primary], current_draft_paras=indices,
                      attachment_status="revised", orphaned=False,
                      stale=len(indices) != 1 or anchor_hash(paras[indices[0]]) != anchor)
        return result
    if len(matches) == 1:
        result.update(current_draft_para=matches[0], current_draft_paras=matches,
                      attachment_status="exact", stale=False, orphaned=False)
    if len(matches) > 1:
        result["attachment_status"] = "ambiguous"
    return result
