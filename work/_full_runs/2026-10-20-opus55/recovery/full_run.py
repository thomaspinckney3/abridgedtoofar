"""Resumable fixed-target text production in an isolated, versioned workspace.

Uses the existing target planner, two-pass prompts, alignment, book critic,
validator, proofreader and immutable publication format. Existing target and
chapter-inclusion decisions are inputs; fresh preservation plans are generated.
Provider responses are journaled before parsing, so parser recovery never
silently repeats a paid request. Only local review snapshots are produced.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time

from .artifacts import Book, load_book, read_json
from . import target_revision as tr
from .llm import LLMResponse, require_complete_response
from .production import required_segments
from .production_state import atomic_json, book_lock, digest, inventory
from .prompts import load_prompt

MODEL = "anthropic:claude-opus-5-5"
AXES = {
    "causality_and_setup", "referents_and_scene", "dialogue",
    "qualification_and_facts", "viewpoint_and_revelation", "voice_and_rhythm",
    "interpretive_structure", "planned_dependencies",
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **data):
    print(json.dumps({"at": stamp(), "event": event, **data}), flush=True)


def write(path, value):
    atomic_json(Path(path), value)


def texts(book):
    return {s["id"]: (book.work_dir / "chapters" / f"{s['id']}.md").read_text()
            for s in read_json(book.work_dir / "plan.json")["segments"]}


class Journal:
    """Explicit bounded transport with persistent exact-response reuse."""

    def __init__(self, root: Path, *, max_usd=200, max_calls=500, client=None,
                 retry_credit_errors=False):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_usd, self.max_calls = max_usd, max_calls
        self.retry_credit_errors = retry_credit_errors
        self.lock = threading.Lock()
        self.active = set()
        if client is None:
            import anthropic
            workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
            client = anthropic.Anthropic(
                max_retries=0,
                timeout=anthropic.Timeout(connect=30, read=600, write=120, pool=30),
                default_headers={"anthropic-workspace-id": workspace} if workspace else {},
            )
        self.client = client

    def totals(self):
        starts = list(self.root.rglob("started.json"))
        cost = reserve = 0
        complete = 0
        for p in starts:
            result = p.parent / "response.json"
            if result.exists():
                cost += read_json(result)["cost_usd"]
                complete += 1
            else:
                # Unknown billing after network loss remains reserved.
                reserve += read_json(p)["maximum_cost_usd"]
        return {"attempts": len(starts), "responses": complete,
                "cost_usd": round(cost, 6), "unsettled_reserve_usd": round(reserve, 6)}

    def __call__(self, **request):
        request.pop("work_dir", None)
        request["model"] = MODEL
        request.setdefault("thinking", "medium")
        # Alignment and whole-book reports may need more output than old defaults.
        request["max_tokens"] = max(request.get("max_tokens", 16000), 16000)
        key = digest(request)
        folder = self.root / key
        with self.lock:
            history = [folder] + sorted(folder.glob("attempt-*"))
            for previous in history:
                response_file = previous / "response.json"
                if response_file.exists():
                    return LLMResponse(**read_json(response_file)["completion"])
            latest = history[-1]
            if key in self.active:
                raise RuntimeError(f"Request already attempted without a settled response: {key}")
            if (latest / "started.json").exists():
                error_path = latest / "error.json"
                error = read_json(error_path) if error_path.exists() else {}
                if (not self.retry_credit_errors or
                        "credit balance is too low" not in error.get("error", "").lower()):
                    raise RuntimeError(f"Request already attempted without a settled response: {key}")
                # An explicit funded-account resume makes a NEW attempt. Keep
                # the previous attempt and its unknown billing reserve intact.
                folder = folder / f"attempt-{len(history) + 1:03d}"
            response_file = folder / "response.json"
            self.active.add(key)
        try:
            prefix = request.get("cached_prompt")
            content = [{"type": "text", "text": prefix,
                        "cache_control": {"type": "ephemeral"}}] if prefix else []
            content.append({"type": "text", "text": request["prompt"]})
            payload = {
                "model": MODEL.split(":", 1)[1],
                "system": request.get("system") or "Return the requested complete output.",
                "messages": [{"role": "user", "content": content}],
                "max_tokens": request["max_tokens"],
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": request["thinking"]},
                "service_tier": "standard_only",
            }
            count_payload = {k: v for k, v in payload.items()
                             if k not in {"max_tokens", "output_config", "service_tier"}}
            input_tokens = self.client.messages.count_tokens(**count_payload).input_tokens
            maximum = (input_tokens * 5 + payload["max_tokens"] * 20) / 1_000_000
            with self.lock:
                totals = self.totals()
                if totals["attempts"] >= self.max_calls or (
                    totals["cost_usd"] + totals["unsettled_reserve_usd"] + maximum > self.max_usd
                ):
                    raise RuntimeError("Run cost/call bound reached")
                folder.mkdir(parents=True, exist_ok=True)
                write(folder / "request.json", request)
                write(folder / "started.json", {
                    "at": stamp(), "stage": request.get("stage"), "input_tokens": input_tokens,
                    "maximum_cost_usd": maximum, "request_sha256": key,
                })
            emit("call_start", stage=request.get("stage"), input_tokens=input_tokens)
            started = time.monotonic()
            with self.client.messages.stream(**payload) as stream:
                result = stream.get_final_message()
            usage = result.usage.model_dump(mode="json")
            cost = (usage["input_tokens"] * 4 + usage["output_tokens"] * 20
                    + (usage.get("cache_creation_input_tokens") or 0) * 5
                    + (usage.get("cache_read_input_tokens") or 0) * .2) / 1_000_000
            response = LLMResponse(
                text="".join(c.text for c in result.content if c.type == "text"),
                model="anthropic:" + result.model, input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"], duration_s=time.monotonic() - started,
                stop_reason=result.stop_reason,
                cache_read_tokens=usage.get("cache_read_input_tokens"),
                cache_write_tokens=usage.get("cache_creation_input_tokens"),
            )
            write(response_file, {"id": result.id, "usage": usage, "cost_usd": cost,
                                  "at": stamp(), "completion": asdict(response)})
            if response.model != MODEL:
                raise ValueError("Provider returned an unexpected model")
            emit("call_end", stage=request.get("stage"), cost_usd=round(cost, 5),
                 stop_reason=result.stop_reason)
            return response
        except Exception as exc:
            if folder.exists():
                write(folder / "error.json", {"type": type(exc).__name__, "error": str(exc)})
            raise
        finally:
            with self.lock:
                self.active.discard(key)


def prepare(source_root: Path, output: Path, book_ids: list[str]):
    if output.exists():
        manifest = read_json(output / "run.json")
        if manifest["books"] != book_ids:
            raise ValueError("Existing run has different books")
        for item in manifest["inputs"]:
            if hashlib.sha256((source_root / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Original input changed: {item['path']}")
        return manifest
    # Validate all selected sources before creating the destination.
    pending = []
    inputs = []
    for bid in book_ids:
        original = load_book(bid, workspace=source_root, create=False)
        plan = read_json(original.work_dir / "plan.json")
        full = tr.normalized(original.source_text)
        chapters = {}
        changed = []
        for s in plan["segments"]:
            p = original.work_dir / "chapters" / f"{s['id']}.md"
            if not p.exists():
                raise ValueError(f"Missing source {bid}/{s['id']}")
            source = p.read_text()
            if tr.normalized(source) not in full:
                p = p.with_suffix(".md.orig")
                if not p.exists() or tr.normalized(p.read_text()) not in full:
                    raise ValueError(f"No pristine source for {bid}/{s['id']}")
                source = p.read_text()
                changed.append(s["id"])
            chapters[s["id"]] = source
            inputs += inventory(source_root, [p])
        inputs += inventory(source_root, [original.source_path,
                         original.source_path.parent / "metadata.json",
                         original.work_dir / "plan.json"])
        pending.append((original, plan, chapters, changed))
    output.mkdir(parents=True)
    details = {}
    for original, plan, chapters, changed in pending:
        bid = original.book_id
        dst = output / "books" / bid
        dst.mkdir(parents=True)
        shutil.copy2(original.source_path, dst / original.source_path.name)
        write(dst / "metadata.json", original.metadata)
        work = output / "work" / bid
        (work / "chapters").mkdir(parents=True)
        (work / "segments").mkdir()
        for sid, text in chapters.items():
            (work / "chapters" / f"{sid}.md").write_text(text)
        for name in ("chapters.json", "chapter_classifications.json", "cuts.json"):
            p = original.work_dir / name
            if p.exists():
                shutil.copy2(p, work / name)
        write(work / "original_plan.json", plan)
        # Keep chapter order, targets and omissions; replace old signatures below.
        plan["_meta"]["computed"]["target_word_count"] = sum(
            s["target_word_count"] for s in required_segments(plan))
        write(work / "plan.json", plan)
        for s in plan["segments"]:
            if s not in required_segments(plan):
                (work / "segments" / f"{s['id']}.md").write_text("")
                write(work / "segments" / f"{s['id']}.checks.json", {"status": "cut"})
        details[bid] = {"chapters": len(required_segments(plan)),
                        "target_words": sum(s["target_word_count"] for s in required_segments(plan)),
                        "discarded_synthetic_source_prefixes": changed}
    manifest = {"version": 1, "created_at": stamp(), "books": book_ids, "model": MODEL,
                "inputs": inputs, "details": details, "status": "prepared",
                "scope": "Full retained text, original targets/omissions; new local review revisions"}
    write(output / "run.json", manifest)
    return manifest


def validated_json(generate, request, validate, *, attempts=2):
    original = request["prompt"]
    for attempt in range(attempts):
        response = generate(**request)
        try:
            require_complete_response(response, request["stage"])
            value = tr.parse_object(response.text)
            return validate(value)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            if attempt + 1 == attempts:
                raise
            request = {**request, "stage": request["stage"] + ":corrected",
                       "prompt": original + "\n\nThe previous response failed validation: "
                       + str(exc) + "\nReturn a complete corrected response. Previous response:\n"
                       + response.text}


def parallel(items, fn, workers):
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, item): item for item in items}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append(str(exc))
                emit("unit_failed", error=str(exc))
    if errors:
        raise RuntimeError("; ".join(errors))


def planning(book, generate, workers):
    production = read_json(book.work_dir / "plan.json")
    selected = [
        dict(id=s["id"], title=s.get("title"), number=s.get("number"),
             target_words=s["target_word_count"],
             source=(book.work_dir / "chapters" / f"{s['id']}.md").read_text())
        for s in required_segments(production)
    ]
    full_source = book.source_text
    included = [s["id"] for s in selected]
    catalog = [{k: s.get(k) for k in ("id", "title", "skipped", "target_word_count")}
               for s in production["segments"]]

    def batch(chapters):
        name = "-".join(c["id"] for c in chapters)
        dest = book.work_dir / "preservation" / f"{name}.json"
        request = tr.planning_request(book.metadata, full_source, chapters)
        # Keep the full-book context identical across batches for provider caching.
        request["prompt"] = request["prompt"].replace(
            json.dumps(full_source, ensure_ascii=False),
            json.dumps("Complete original book is in the preceding source block."), 1)
        request["cached_prompt"] = "AUTHORITATIVE COMPLETE ORIGINAL BOOK:\n" + full_source
        request["prompt"] += ("\nChapter inclusion plan:\n" + json.dumps(catalog, ensure_ascii=False)
            + "\nKeep original targets and omission decisions. Dependencies on omitted "
              "chapters require locally sufficient context, not automatic restoration. "
              "Protect necessary setup across the actual retained reading order.")
        request["stage"] += ":" + book.book_id + ":" + name

        def validate(value):
            # Correct paragraph labels only when the exact quote identifies one
            # unique paragraph. Never alter a quote to make invented evidence fit.
            for item in value.get("chapters", []):
                chapter = next(c for c in chapters if c["id"] == item["id"])
                paras = tr.paragraphs(chapter["source"])
                for anchor in item.get("verbatim", []):
                    matches = [i for i, p in enumerate(paras, 1)
                               if tr.normalized(anchor["text"]) in tr.normalized(p)]
                    if len(matches) == 1:
                        anchor["paragraph"] = matches[0]
            return tr.validate_plans(full_source, chapters, value)

        plans = validated_json(generate, request, validate)
        write(dest, plans)
        for p in plans:
            write(book.work_dir / "preservation" / f"{p['id']}.json", p)
        emit("plans_ready", book=book.book_id, chapters=[p["id"] for p in plans])

    parallel([selected[i:i + 4] for i in range(0, len(selected), 4)], batch, workers)
    for s in production["segments"]:
        if s["id"] in included:
            plan = read_json(book.work_dir / "preservation" / f"{s['id']}.json")
            s["signatures"] = [{"passage_hint": a["text"], "why": a["purpose"]}
                               for a in plan["verbatim"]]
    write(book.work_dir / "plan.json", production)


def two_pass(book, sid, generate):
    folder = book.work_dir / "two_pass" / sid
    folder.mkdir(parents=True, exist_ok=True)
    plan = read_json(book.work_dir / "preservation" / f"{sid}.json")
    source = (book.work_dir / "chapters" / f"{sid}.md").read_text()
    request = tr.build_request("draft_fixed_target",
        dict(book=book.metadata, preservation_plan=plan, original_source=source),
        model=MODEL, stage=f"target_revision:initial:{book.book_id}:{sid}")

    def prose_call(label, req):
        response = generate(**req)
        require_complete_response(response, req["stage"])
        prose, notes = tr.split_response(response.text)
        (folder / f"{label}.md").write_text(prose + "\n")
        write(folder / f"{label}.notes.json", notes)
        write(folder / f"{label}.checks.json", tr.measure(prose, plan))
        return prose, notes

    initial, _ = prose_call("initial", request)
    request, context = tr.revision_request(book.metadata, source, plan, initial)
    request["stage"] += ":" + book.book_id
    write(folder / "measured_feedback.json", context)
    revision, notes = prose_call("revision", request)
    tr._review(notes, len(context["first_draft_paragraphs"]))
    write(folder / "measured_changes.json", tr.measured_changes(initial, revision))
    (folder / "draft.md").write_text(revision + "\n")
    emit("draft_ready", book=book.book_id, chapter=sid, initial=tr.words(initial),
         revised=tr.words(revision), target=plan["target_words"])


def evidence_check(evidence, documents):
    if not isinstance(evidence, list):
        raise ValueError("Evidence must be a list")
    for e in evidence:
        doc, number, quote = e["document"], e["paragraph"], e["quote"]
        if doc not in documents or type(number) is not int or not 1 <= number <= len(documents[doc]):
            raise ValueError(f"Invalid evidence document/paragraph: {doc}/{number}")
        if not tr.normalized(quote) or tr.normalized(quote) not in tr.normalized(documents[doc][number - 1]):
            raise ValueError(f"Evidence not found in {doc}/{number}: {quote[:100]}")


def review_context(book, sid, drafts):
    sources = texts(book)
    plan = read_json(book.work_dir / "preservation" / f"{sid}.json")
    order = [s["id"] for s in required_segments(read_json(book.work_dir / "plan.json"))]
    pos = order.index(sid)
    partners = set(order[max(0, pos - 1):pos + 2]) - {sid}
    dependencies = []
    for i, dep in enumerate(plan["dependencies"]):
        matches = [k for k, source in sources.items()
                   if k != sid and tr.normalized(dep["other_evidence"]) in tr.normalized(source)]
        partners.update(matches)
        dependencies.append({**dep, "index": i, "partner_ids": matches,
                             "omitted_partner_ids": [k for k in matches if k not in drafts]})
    documents = {sid + ".source": tr.paragraphs(sources[sid]),
                 sid + ".initial": tr.paragraphs((book.work_dir / "two_pass" / sid / "initial.md").read_text()),
                 sid + ".revision": tr.paragraphs(drafts[sid])}
    for partner in sorted(partners):
        documents[partner + ".source"] = tr.paragraphs(sources[partner])
        if partner in drafts:
            documents[partner + ".revision"] = tr.paragraphs(drafts[partner])
    context = {
        "central_chapter": sid, "book": book.metadata, "preservation_plan": plan,
        "actual_reading_order": order,
        "previous_included_chapter": order[pos - 1] if pos else None,
        "next_included_chapter": order[pos + 1] if pos + 1 < len(order) else None,
        "dependencies": dependencies,
        "documents": {k: [{"paragraph": i, "text": p} for i, p in enumerate(v, 1)]
                      for k, v in documents.items()},
        "draft_version": "All supplied revisions are the same frozen pass from this new run.",
    }
    return context, documents


def validate_review(value, sid, documents, dependency_count):
    if value["chapter"] != sid:
        raise ValueError("Wrong central chapter")
    if {c["axis"] for c in value["coverage"]} != AXES or len(value["coverage"]) != 8:
        raise ValueError("Review must cover all eight axes")
    if value["verdict"] not in {"needs_repair", "editorial_review", "no_material_findings"}:
        raise ValueError("Invalid review verdict")
    ids = set()
    for f in value["findings"]:
        if f["id"] in ids or f["priority"] not in {"must_fix", "should_improve", "tradeoff"}:
            raise ValueError("Invalid finding ID or priority")
        ids.add(f["id"])
        if f["axis"] not in AXES:
            raise ValueError("Invalid finding axis")
        evidence_check(f["evidence"], documents)
        cited = {e["document"] for e in f["evidence"]}
        if not {sid + ".source", sid + ".revision"} <= cited:
            raise ValueError("Every finding needs central source and revision evidence")
    if sorted(d["index"] for d in value["dependencies"]) != list(range(dependency_count)):
        raise ValueError("Review must assess every dependency once")
    for d in value["dependencies"]:
        evidence_check(d["evidence"], documents)
    return value


def review(book, sid, drafts, generate, label):
    context, documents = review_context(book, sid, drafts)
    request = tr.build_request("fidelity_review", context, model=MODEL,
                              stage=f"fidelity:{book.book_id}:{label}:{sid}", max_tokens=20000)
    result = validated_json(generate, request, lambda v: validate_review(
        v, sid, documents, len(context["dependencies"])))
    folder = book.work_dir / "fidelity" / label
    write(folder / f"{sid}.json", result)
    write(folder / f"{sid}.inputs.json", context)
    emit("review_ready", book=book.book_id, chapter=sid, pass_name=label,
         must_fix=sum(f["priority"] == "must_fix" for f in result["findings"]),
         should_improve=sum(f["priority"] == "should_improve" for f in result["findings"]))


def apply_replacements(text, replacements, plan):
    locations = []
    for replacement in replacements:
        old, new = replacement["old"], replacement["new"]
        if not isinstance(old, str) or not old or not isinstance(new, str) or text.count(old) != 1:
            raise ValueError("Replacement must match unique nonempty current draft text")
        if tr.words(old) > max(150, tr.words(text) * .4):
            raise ValueError("Repair must be local, not a chapter rewrite")
        start = text.index(old)
        locations.append((start, start + len(old), new))
    locations.sort()
    if any(a[1] > b[0] for a, b in zip(locations, locations[1:])):
        raise ValueError("Overlapping replacements")
    for start, end, new in reversed(locations):
        text = text[:start] + new + text[end:]
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
    if not text or "<!--" in text:
        raise ValueError("Invalid repaired prose")
    if not all(a["present"] for a in tr.measure(text, plan)["protected"]):
        raise ValueError("Repair loses a protected passage")
    return text


def repair(book, sid, drafts, generate, label):
    context, documents = review_context(book, sid, drafts)
    plan = context["preservation_plan"]
    report = read_json(book.work_dir / "fidelity" / label / f"{sid}.json")
    candidates = [f for f in report["findings"] if f["priority"] != "tradeoff"]
    text = drafts[sid]
    measurements = tr.measure(text, plan)
    target = plan["target_words"]
    folder = book.work_dir / "repairs" / label
    if not candidates and measurements["target_matched"] and all(a["present"] for a in measurements["protected"]):
        write(folder / f"{sid}.json", {"adjudications": [], "replacements": [],
                                      "remaining_concerns": [], "checks": measurements})
        (folder / f"{sid}.md").write_text(text + "\n")
        return
    context["candidate_findings"] = candidates
    context["measurements"] = measurements
    request = tr.build_request("fidelity_repair", context, model=MODEL,
        stage=f"fidelity_repair:{book.book_id}:{label}:{sid}", max_tokens=16000,
        target_words=target, actual_words=tr.words(text), difference_words=tr.words(text) - target)

    def validate(value):
        judgments = value["adjudications"]
        if sorted(a["id"] for a in judgments) != sorted(f["id"] for f in candidates):
            raise ValueError("Adjudicate every candidate exactly once")
        for a in judgments:
            if a["decision"] not in {"confirmed", "rejected", "uncertain"}:
                raise ValueError("Invalid adjudication")
            if not a.get("reason") or not a.get("evidence"):
                raise ValueError("Adjudication needs evidence and rationale")
            evidence_check(a["evidence"], documents)
        apply_replacements(text, value["replacements"], plan)
        return value

    result = validated_json(generate, request, validate)
    revised = apply_replacements(text, result["replacements"], plan)
    result["checks"] = tr.measure(revised, plan)
    result["measured_changes"] = tr.measured_changes(text, revised)
    write(folder / f"{sid}.json", result)
    (folder / f"{sid}.md").write_text(revised + "\n")
    emit("repair_ready", book=book.book_id, chapter=sid, pass_name=label,
         words=tr.words(revised), target=target, replacements=len(result["replacements"]))


def final_checks(book, drafts, label):
    checks = {}
    for sid, text in drafts.items():
        plan = read_json(book.work_dir / "preservation" / f"{sid}.json")
        report = read_json(book.work_dir / "fidelity" / label / f"{sid}.json")
        value = tr.measure(text, plan)
        value.update(status="drafted", model=MODEL, draft_words=tr.words(text),
                     segment_id=sid, review=report["verdict"],
                     unresolved_must_fix=[f for f in report["findings"] if f["priority"] == "must_fix"],
                     unresolved_should_improve=[f for f in report["findings"] if f["priority"] == "should_improve"])
        (book.work_dir / "segments" / f"{sid}.md").write_text(text + "\n")
        write(book.work_dir / "segments" / f"{sid}.checks.json", value)
        checks[sid] = value
    write(book.work_dir / "fixed_target_checks.json", checks)
    return checks


def finish(book, drafts, generate, workers, label):
    from .align import align_chapter, _alignment_current, _split_paragraphs
    from .assemble import assemble_book
    from .book_critic import run_book_critic
    from .proofread import render_proofread_html
    from .publication import snapshot_revision, verify_revision
    from .validate import validate_book

    checks = final_checks(book, drafts, label)
    plan = read_json(book.work_dir / "plan.json")
    assembled = assemble_book(book, plan)
    if assembled.segments_missing:
        raise ValueError("Assembly has missing chapters")
    # The legacy assembler's compatibility report must not imply a new allowance.
    report = read_json(book.work_dir / "assembly_report.json")
    for key in list(report):
        if "ceiling" in key or "overage" in key:
            report.pop(key)
    report["target_delta_words"] = sum(tr.words(t) for t in drafts.values()) - sum(
        s["target_word_count"] for s in required_segments(plan))
    report["length_policy"] = "One fixed target; every deviation is reported."
    write(book.work_dir / "assembly_report.json", report)
    critic = run_book_critic(book, generate=generate)
    write(book.work_dir / "validation_report.json", asdict(validate_book(book, plan)))

    def align(sid):
        path = book.work_dir / "alignments" / f"{sid}.json"
        src = _split_paragraphs((book.work_dir / "chapters" / f"{sid}.md").read_text())
        draft = _split_paragraphs(drafts[sid])
        if not _alignment_current(path, src, draft):
            align_chapter(book, sid, generate=generate)
        if not _alignment_current(path, src, draft):
            raise ValueError(f"Invalid final alignment: {sid}")
        emit("alignment_ready", book=book.book_id, chapter=sid)

    parallel(list(drafts), align, workers)
    render_proofread_html(book)
    revision = digest({"plan": plan, "drafts": drafts})
    media = {"version": 1, "book_id": book.book_id, "text_revision": revision, "targets": []}
    write(book.work_dir / "media_manifest.json", media)
    quality = {
        "model": MODEL, "book_critic": critic["verdict"],
        "chapters": len(checks),
        "exact_target_chapters": sum(c["target_matched"] for c in checks.values()),
        "missing_protected": sum(not a["present"] for c in checks.values() for a in c["protected"]),
        "unresolved_must_fix": sum(len(c["unresolved_must_fix"]) for c in checks.values()),
        "unresolved_should_improve": sum(len(c["unresolved_should_improve"]) for c in checks.values()),
        "review_status": "awaiting_human_review",
        "target_words": sum(c["target_words"] for c in checks.values()),
        "words": sum(c["words"] for c in checks.values()),
    }
    write(book.work_dir / "production_quality.json", quality)
    names = ["plan.json", "chapters.json", "chapter_classifications.json", "cuts.json",
             "book_synopsis.md", "abridgment.md", "abridgment.txt", "assembly_report.json",
             "book_critic.json", "validation_report.json", "proofread.html",
             "fixed_target_checks.json", "production_quality.json", "media_manifest.json"]
    names += [f"{directory}/{sid}.{suffix}" for sid in drafts
              for directory, suffix in [("segments", "md"), ("segments", "checks.json"),
                                        ("alignments", "json")]]
    names += [p.relative_to(book.work_dir).as_posix()
              for p in (book.work_dir / "fidelity" / label).glob("*.json")
              if not p.name.endswith(".inputs.json")]
    snapshot = snapshot_revision(book, text_revision=revision, outputs=inventory(book.work_dir, names),
        media_index=media, stage_summary={
            "status": "complete", "selected_outputs": ["text"], "quality": quality,
            "stages": {s: {"status": "complete"} for s in
                       ["preservation_planning", "two_pass", "fidelity_review", "repairs",
                        "final_review", "assembly", "book_critic", "validation", "alignment"]}},
        lock_held=True)
    verify_revision(book, snapshot["revision"])
    result = {**quality, "review_revision": snapshot["revision"],
              "text_revision": revision, "status": "complete"}
    write(book.work_dir / "full_run_result.json", result)
    emit("book_complete", book=book.book_id, **result)
    return result


def run_book(book, generate, workers):
    with book_lock(book):
        plan = read_json(book.work_dir / "plan.json")
        ids = [s["id"] for s in required_segments(plan)]
        # Fresh whole-source synopsis, used only as a check, never as source prose.
        prompt = load_prompt("summarize_synopsis")
        request = dict(prompt=prompt.render(n_sentences=30, note="", source=book.source_text),
                       model=MODEL, max_tokens=16000, stage=f"summarize:{book.book_id}")
        response = generate(**request)
        require_complete_response(response, "synopsis")
        (book.work_dir / "book_synopsis.md").write_text(response.text.strip() + "\n")
        planning(book, generate, workers)
        parallel(ids, lambda sid: two_pass(book, sid, generate), workers)
        drafts = {sid: (book.work_dir / "two_pass" / sid / "draft.md").read_text().strip() for sid in ids}
        # Freeze a complete pass before reviewing any neighbor or dependency.
        for label in ("initial_review", "repair_review"):
            parallel(ids, lambda sid: review(book, sid, drafts, generate, label), workers)
            parallel(ids, lambda sid: repair(book, sid, drafts, generate, label), workers)
            drafts = {sid: (book.work_dir / "repairs" / label / f"{sid}.md").read_text().strip()
                      for sid in ids}
        parallel(ids, lambda sid: review(book, sid, drafts, generate, "final_review"), workers)
        return finish(book, drafts, generate, workers, "final_review")


def run(output, workers=4, max_usd=200, max_calls=600, retry_credit_errors=False):
    manifest = read_json(output / "run.json")
    generate = Journal(output / "calls", max_usd=max_usd, max_calls=max_calls,
                       retry_credit_errors=retry_credit_errors)
    manifest.update(status="running", started_at=manifest.get("started_at") or stamp(),
                    max_usd=max_usd, max_calls=max_calls, workers=workers)
    write(output / "run.json", manifest)
    results, errors = {}, {}
    for bid in manifest["books"]:
        try:
            results[bid] = run_book(load_book(bid, workspace=output), generate, workers)
        except Exception as exc:
            errors[bid] = {"type": type(exc).__name__, "error": str(exc)}
            emit("book_failed", book=bid, **errors[bid])
        manifest.update(results=results, errors=errors, usage=generate.totals())
        write(output / "run.json", manifest)
    manifest.update(status="failed" if errors else "complete", finished_at=stamp(),
                    usage=generate.totals())
    write(output / "run.json", manifest)
    emit("run_finished", status=manifest["status"], usage=manifest["usage"])
    return manifest


def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--books", nargs="+", default=["education", "secret_adversary"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-usd", type=float, default=200)
    parser.add_argument("--max-calls", type=int, default=600)
    parser.add_argument("--retry-credit-errors", action="store_true",
                        help="After funding the account, make new attempts for saved credit-balance errors.")
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.workspace.resolve(), args.output.resolve(), args.books), indent=2))
    else:
        result = run(args.output.resolve(), args.workers, args.max_usd, args.max_calls,
                     args.retry_credit_errors)
        if result["status"] != "complete":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
