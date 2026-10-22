"""Fixed-target planning and two-pass abridgment with measured revision feedback.

Outputs are review artifacts, never accepted production segments. Two chapter
calls are made: draft, then evaluate cuts and revise. A caller can inject its
provider adapter for bounded experiments; normal CLI calls use forage.llm.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Callable

from .artifacts import read_json, write_json
from .llm import LLMResponse, complete, require_complete_response
from .prompts import load_prompt

Generator = Callable[[dict], LLMResponse]
NOTE = re.compile(r"<!--\s*FORAGE_CHAPTER_NOTES\s*(.*?)\s*-->", re.S)
PLAN_FIELDS = {
    "id", "verbatim", "essential", "optional", "dependencies", "sections",
    "continuity_checks", "infeasible", "risks",
}


def words(text: str) -> int:
    return len(text.split())


def normalized(text: str) -> str:
    return " ".join(text.split()).translate(
        str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))


def paragraphs(text: str) -> list[str]:
    return re.split(r"\n\s*\n", text.strip()) if text.strip() else []


def fixed_target_audit(text: str) -> None:
    forbidden = r"(?i)\b(?:overage|overrun|tolerance|ceiling_words|target_range_words)\b|±|20% ceiling|target range|acceptance ceiling"
    if re.search(forbidden, text):
        raise ValueError("Unexpected target allowance framing in instructions")


def plan_target_audit(value) -> None:
    """Reject alternate length fields without censoring literal book language."""
    forbidden = {"ceiling_words", "target_range_words", "overage_words",
                 "overage_percent", "tolerance_percent"}
    if isinstance(value, dict):
        if forbidden.intersection(value):
            raise ValueError("Unexpected target allowance fields in plan")
        for child in value.values():
            plan_target_audit(child)
    elif isinstance(value, list):
        for child in value:
            plan_target_audit(child)


def parse_object(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def build_request(name: str, context: dict, *, model: str, stage: str,
                  max_tokens: int = 32000, **variables) -> dict:
    prompt = load_prompt(name)
    fixed_target_audit(prompt.body_template)
    return dict(
        prompt=prompt.render(context=json.dumps(context, ensure_ascii=False),
                             **variables),
        system=prompt.system, model=model, thinking="medium",
        max_tokens=max_tokens, stage=stage, cache=False,
    )


def planning_request(metadata: dict, full_source: str, chapters: list[dict],
                     *, model: str = "anthropic:claude-opus-5-5") -> dict:
    """chapters contain id/title/number/target_words/source; no book-specific code."""
    if not chapters or len({c["id"] for c in chapters}) != len(chapters):
        raise ValueError("Selected chapter IDs must be unique and nonempty")
    selected = []
    for chapter in chapters:
        target = chapter["target_words"]
        if type(target) is not int or target <= 0:
            raise ValueError("A chapter needs one positive integer word target")
        if not chapter["source"].strip() or normalized(chapter["source"]) not in normalized(full_source):
            raise ValueError("Selected chapter is absent from the full source")
        selected.append({
            **{k: chapter.get(k) for k in ("id", "title", "number", "target_words")},
            "source_words": words(chapter["source"]),
            "paragraphs": [{"paragraph": i, "text": p} for i, p in
                           enumerate(paragraphs(chapter["source"]), 1)],
        })
    return build_request("preservation_plan",
                         dict(book=metadata, full_source=full_source, selected_chapters=selected),
                         model=model, stage="target_revision:planning")


def _quote(quote: str, source: str) -> str:
    q, s = normalized(quote), normalized(source)
    if not q or q not in s:
        raise ValueError("Quote absent from source: " + q[:100])
    start = s.index(q)
    return " ".join(source.split())[start:start + len(q)]


def validate_plans(full_source: str, chapters: list[dict], generated: dict) -> list[dict]:
    """Validate evidence and allocate the exact target by largest remainder."""
    plans = deepcopy(generated["chapters"])
    if len(plans) != len(chapters) or {p["id"] for p in plans} != {c["id"] for c in chapters}:
        raise ValueError("Planner returned different or duplicate chapter IDs")
    output = []
    for chapter in chapters:
        plan = next(p for p in plans if p["id"] == chapter["id"])
        if set(plan) - PLAN_FIELDS:
            raise ValueError("Unknown preservation-plan fields")
        if plan["infeasible"] is not False:
            raise ValueError("Planner reports an infeasible preservation plan")
        if not plan["verbatim"] or len(plan["verbatim"]) > 8 or not 1 <= len(plan["essential"]) <= 12:
            raise ValueError("Invalid preservation tiers")
        if not plan["optional"] or not plan["continuity_checks"]:
            raise ValueError("Plan must include possible cuts and continuity checks")
        source, target = chapter["source"], chapter["target_words"]
        if type(target) is not int or target <= 0:
            raise ValueError("Invalid target")
        paras = paragraphs(source)
        for i, anchor in enumerate(plan["verbatim"], 1):
            n = anchor["paragraph"]
            if type(n) is not int or not 1 <= n <= len(paras):
                raise ValueError("Invalid source paragraph number")
            anchor["text"] = _quote(anchor["text"], paras[n - 1])
            anchor.update(id=f"V{i}", words=words(anchor["text"]))
        protected_words = sum(a["words"] for a in plan["verbatim"])
        if protected_words > target * .25:
            raise ValueError("Protected text exceeds the preservation-plan limit")
        full, local = normalized(full_source), normalized(source)
        if not local or local not in full:
            raise ValueError("Chapter absent from full source")
        start = full.index(local)
        for dep in plan["dependencies"]:
            dep["local_evidence"] = _quote(dep["local_evidence"], source)
            dep["other_evidence"] = _quote(dep["other_evidence"], full_source)
            q = normalized(dep["other_evidence"])
            if q not in full[:start] and q not in full[start + len(local):]:
                raise ValueError("Cross-chapter evidence occurs only locally")
        weights = [s["weight"] for s in plan["sections"]]
        if not 1 <= len(weights) <= 8 or any(
            type(w) not in (int, float) or not math.isfinite(w) or w <= 0 for w in weights
        ):
            raise ValueError("Invalid section weights")
        exact = [target * w / sum(weights) for w in weights]
        budgets = [math.floor(x) for x in exact]
        for i in sorted(range(len(exact)), key=lambda i: exact[i] - budgets[i], reverse=True)[:target - sum(budgets)]:
            budgets[i] += 1
        for section, budget in zip(plan["sections"], budgets):
            section["words"] = budget
        plan.update(target_words=target, protected_words=protected_words,
                    title=chapter.get("title", ""), number=chapter.get("number"),
                    voice_profile=generated["voice_profile"], book_context=generated["book_context"])
        plan_target_audit(plan)
        output.append(plan)
    return output


def split_response(text: str) -> tuple[str, dict]:
    matches = list(NOTE.finditer(text))
    if len(matches) != 1 or text[matches[0].end():].strip():
        raise ValueError("Expected one final reviewer-note comment")
    prose = text[:matches[0].start()].strip()
    notes = parse_object(matches[0].group(1))
    if not prose or prose == "CUT" or "<!--" in prose or "-->" in prose:
        raise ValueError("Expected complete prose without embedded metadata")
    return prose, notes


def measure(text: str, plan: dict) -> dict:
    count, target = words(text), plan["target_words"]
    return {
        "words": count, "target_words": target, "target_delta_words": count - target,
        "target_delta_percent": round(100 * (count / target - 1), 2),
        "target_matched": count == target,
        "protected": [{"id": a["id"], "present": normalized(a["text"]) in normalized(text)}
                      for a in plan["verbatim"]],
    }


def revision_request(metadata: dict, source: str, plan: dict, draft: str,
                     *, model: str = "anthropic:claude-opus-5-5") -> tuple[dict, dict]:
    measured = measure(draft, plan)
    numbered = [{"id": i, "words": words(p), "text": p,
                 "protected_ids": [a["id"] for a in plan["verbatim"]
                                   if normalized(a["text"]) in normalized(p)]}
                for i, p in enumerate(paragraphs(draft), 1)]
    assert sum(p["words"] for p in numbered) == measured["words"]
    context = dict(book=metadata, preservation_plan=plan, measurements=measured,
                   first_draft_paragraphs=numbered, original_source=source)
    request = build_request("revise_fixed_target", context, model=model,
                            stage=f"target_revision:revision:{plan['id']}",
                            target_words=plan["target_words"], actual_words=measured["words"],
                            difference_words=measured["target_delta_words"])
    return request, context


def measured_changes(before: str, after: str) -> dict:
    """Actual token edits; independent of any model claim about words saved."""
    a, b = before.split(), after.split()
    edits = [{"operation": tag, "removed_words": j - i, "added_words": l - k}
             for tag, i, j, k, l in SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
             if tag != "equal"]
    removed = sum(e["removed_words"] for e in edits)
    added = sum(e["added_words"] for e in edits)
    assert len(a) - removed + added == len(b)
    return dict(removed_words=removed, added_words=added,
                net_words_removed=removed - added, edits=edits)


def _review(notes: dict, paragraph_count: int) -> None:
    entries = notes.get("cut_evaluation")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Revision lacks a cut evaluation")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid cut evaluation")
        ids = entry.get("paragraph_ids")
        if not isinstance(ids, list) or not ids or any(
            type(i) is not int or not 1 <= i <= paragraph_count for i in ids
        ):
            raise ValueError("Cut evaluation refers to an invalid draft paragraph")
        if entry.get("action") not in {"cut", "compress", "keep", "restore"}:
            raise ValueError("Invalid cut evaluation action")
        if any(not isinstance(entry.get(k), str) or not entry[k].strip()
               for k in ("reason", "dependency_check")):
            raise ValueError("Cut evaluation lacks rationale or dependency check")
    if type(notes.get("infeasible")) is not bool:
        raise ValueError("Revision must explicitly report feasibility")


def run_chapter(*, metadata: dict, source: str, plan: dict, output_dir: Path,
                model: str = "anthropic:claude-opus-5-5",
                generate: Generator | None = None) -> dict:
    """Two bounded passes; retain failures and never overwrite an existing run."""
    target = plan["target_words"]
    if type(target) is not int or target <= 0 or not source.strip():
        raise ValueError("Source and positive integer target are required")
    plan_target_audit(plan)
    for a in plan["verbatim"]:
        _quote(a["text"], source)
    if sum(s["words"] for s in plan["sections"]) != target:
        raise ValueError("Section allocations do not sum to the target")
    if len({a["id"] for a in plan["verbatim"]}) != len(plan["verbatim"]):
        raise ValueError("Duplicate protected-passage IDs")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "source.md").write_text(source)
    write_json(output_dir / "plan.json", plan)
    generate = generate or (lambda req: complete(**req, work_dir=output_dir))

    def call(stage, request):
        write_json(output_dir / f"{stage}.input.json", request)
        write_json(output_dir / f"{stage}.started.json", {
            "request_sha256": hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()})
        response = generate(request)
        write_json(output_dir / f"{stage}.completion.json", asdict(response))
        require_complete_response(response, stage)
        text, notes = split_response(response.text)
        (output_dir / f"{stage}.md").write_text(text + "\n")
        write_json(output_dir / f"{stage}.notes.json", notes)
        return text, notes

    try:
        request = build_request("draft_fixed_target",
                                dict(book=metadata, preservation_plan=plan, original_source=source),
                                model=model, stage=f"target_revision:initial:{plan['id']}")
        initial, first_notes = call("initial", request)
        write_json(output_dir / "initial.checks.json", measure(initial, plan))
        request, feedback = revision_request(metadata, source, plan, initial, model=model)
        write_json(output_dir / "measured_feedback.json", feedback)
        revised, notes = call("revision", request)
        _review(notes, len(feedback["first_draft_paragraphs"]))
        final_checks = measure(revised, plan)
        write_json(output_dir / "revision.checks.json", final_checks)
        changes = measured_changes(initial, revised)
        write_json(output_dir / "measured_changes.json", changes)
        issues = []
        if not final_checks["target_matched"]:
            issues.append("Fixed target not matched; see measured difference")
        if not all(a["present"] for a in final_checks["protected"]):
            issues.append("Required exact text is missing")
        if notes["infeasible"]:
            issues.append("Model reports infeasible preservation requirements")
        result = {
            "status": "needs_review" if issues else "measured_checks_pass",
            "issues": issues, "initial": measure(initial, plan), "revision": final_checks,
            "measured_changes": changes, "cut_evaluation": notes["cut_evaluation"],
            "limits": "Counts and quote presence are verified; editorial rationales and semantic continuity still require review.",
        }
        write_json(output_dir / "result.json", result)
        return result
    except Exception as exc:
        write_json(output_dir / "failed.json", {"type": type(exc).__name__, "message": str(exc)})
        raise


def run_book(book, segment_ids: list[str], *, output_dir: Path,
             model: str = "anthropic:claude-opus-5-5",
             generate: Generator | None = None) -> dict:
    """Generate shared whole-book plans, then run both passes on each selection."""
    from .artifacts import segment_source_path
    production_plan = read_json(book.work_dir / "plan.json")
    selected = []
    if not segment_ids or len(set(segment_ids)) != len(segment_ids):
        raise ValueError("Select unique segment IDs")
    for sid in segment_ids:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
            raise ValueError("Invalid segment ID")
        segment = next((s for s in production_plan["segments"] if s["id"] == sid), None)
        path = segment_source_path(book, sid)
        if segment is None or path is None:
            raise ValueError(f"Missing segment/source: {sid}")
        selected.append(dict(id=sid, title=segment.get("title", ""), number=segment.get("number"),
                             source=path.read_text(), target_words=segment["target_word_count"]))
    full_source = book.source_text
    request = planning_request(book.metadata, full_source, selected, model=model)
    output_dir = Path(output_dir).resolve()
    # A caller must provide a new review-artifact directory.
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "planning.input.json", request)
    write_json(output_dir / "selected_chapters.json", selected)
    (output_dir / "full_source.txt").write_text(full_source)
    generate = generate or (lambda req: complete(**req, work_dir=output_dir))
    try:
        response = generate(request)
        write_json(output_dir / "planning.completion.json", asdict(response))
        require_complete_response(response, "planning")
        generated = parse_object(response.text)
        write_json(output_dir / "plan.raw.json", generated)
        plans = validate_plans(full_source, selected, generated)
        write_json(output_dir / "plans.json", plans)
        results = {}
        for chapter, plan in zip(selected, plans):
            results[chapter["id"]] = run_chapter(
                metadata=book.metadata, source=chapter["source"], plan=plan,
                output_dir=output_dir / chapter["id"], model=model, generate=generate)
        write_json(output_dir / "results.json", results)
        return results
    except Exception as exc:
        write_json(output_dir / "failed.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
