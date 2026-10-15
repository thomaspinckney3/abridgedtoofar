"""Resumable book production; previews never execute generators or adopt files.

Preparation uses a private pristine split, so skip relocation never poisons the
next split. Draft generation identity is separate from current accepted prose.
Context used by a draft is recorded once; later chapters/edits do not recursively
invalidate earlier requests. Regeneration requires changed generation inputs.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import shutil

from .artifacts import Book, read_json
from . import llm
from .align import align_chapter, _alignment_current, _split_paragraphs
from .assemble import assemble_book
from .audiobook import generate_audiobook, DEFAULT_MODEL, DEFAULT_OUTPUT_FORMAT
from .book_critic import run_book_critic
from .chapter_classifier import classify_chapters
from .chapter_split import split_to_disk
from .coherence import run_coherence, _coherence_segment_ids
from .coherence_fix import run_coherence_fixes
from .cuts import generate_cuts
from .drafter import draft_segment, _disk_draft_result
from .iterate import iterate_segment
from .lean_plan import build_lean_plan
from .media import target_revision, validate_media_manifest
from .prepare_skips import apply_skips
from .prompts import load_prompt
from .proofread import render_proofread_html
from .source_fingerprint import source_fingerprint_for_stage
from .summarizer import summarize_book
from .validate import validate_book
from .production_state import (atomic_json, book_lock, confined_path,
                               digest, inventory, load_state, now, save_state,
                               sha256_file, verify_inventory)

PROMPT_STAGES = {
    "classify": "classify_chapters", "summarize": "summarize_synopsis",
    "cuts": "prepass_cuts", "draft": "draft_lean", "regen": "draft_lean",
    "critic": "critic_signature", "critic:book": "critic_book",
    "coherence": "critic_coherence", "coherence_fix": "coherence_fix_pair",
    "align": "align",
}


def resolve_options(book: Book, options: dict | None = None) -> dict:
    options = dict(options or {})
    allowed = {"outputs", "adopt_existing", "model", "models", "iterate", "max_retries",
               "coherence", "coherence_fix", "coherence_fix_pairs", "repair_epoch",
               "checkpoint_before_media", "continue_revision",
               "audio_voice_id", "audio_model", "audio_format", "audio_max_chars",
               "audio_combine", "audio_context_chars", "audio_voice_settings", "audio_seed",
               "audio_language_code", "audio_normalization", "audio_stitch", "audio_enable_logging",
               "graphic_provider", "graphic_model", "graphic_storyboard_model", "graphic_style",
               "graphic_size", "graphic_quality", "graphic_chapters", "graphic_words_per_frame",
               "graphic_font_size", "graphic_caption_height"}
    unknown = set(options) - allowed
    if unknown:
        raise ValueError(f"unsupported production options: {', '.join(sorted(unknown))}")
    outputs = options.get("outputs", ["text"])
    if isinstance(outputs, str):
        outputs = outputs.split(",")
    outputs = sorted(set(outputs) | {"text"})
    if set(outputs) - {"text", "audio", "graphic"}:
        raise ValueError("outputs must be text, audio or graphic")
    result = {**options, "outputs": outputs, "iterate": options.get("iterate", False),
              "coherence": options.get("coherence", False),
              "coherence_fix": options.get("coherence_fix", True),
              "max_retries": options.get("max_retries", 1)}
    if not isinstance(result["max_retries"], int) or result["max_retries"] < 0:
        raise ValueError("max_retries must be a nonnegative integer")
    pairs = options.get("coherence_fix_pairs") or []
    if pairs and not result["coherence_fix"]:
        raise ValueError("selected repair pairs require coherence_fix")
    if any(not re.fullmatch(r"[A-Za-z0-9_]+-[A-Za-z0-9_]+", p) for p in pairs):
        raise ValueError("repair pairs must be segment IDs such as 001-002")
    result["coherence_fix_pairs"] = pairs
    continuation = options.get("continue_revision")
    if continuation and (not options.get("checkpoint_before_media") or not re.fullmatch(r"[0-9a-f]{64}", continuation)):
        raise ValueError("continue_revision requires checkpoint_before_media and a SHA-256 revision")
    supplied_models = options.get("models", {})
    if set(supplied_models) - set(PROMPT_STAGES):
        raise ValueError("unknown model stage")
    models = {}
    for stage, prompt_name in PROMPT_STAGES.items():
        requested = supplied_models.get(stage) or options.get("model") or load_prompt(prompt_name).config["model"]
        model = llm.resolve_model_for_stage(requested, stage)[0]
        if not re.fullmatch(r"(?:anthropic|openai):[^\s:]+", model):
            raise ValueError(f"invalid model for {stage}: {model}")
        models[stage.upper().replace(":", "_")] = model
    for main in ["DRAFT", "REGEN"]:
        models[main + "_THINKRETRY"] = models[main]
        fallback = os.environ.get("FORAGE_DRAFT_FALLBACK_MODEL") or ("openai:gpt-6-astra" if models[main].startswith("anthropic:") else "anthropic:claude-sonnet-5-5")
        models[main + "_FALLBACK"] = llm.resolve_model_for_stage(fallback, main.lower() + "_fallback")[0]
    models["COHERENCE_FIX_FALLBACK"] = llm.resolve_model_for_stage(os.environ.get("FORAGE_COHERENCE_FIX_FALLBACK_MODEL") or "openai:gpt-6-astra", "coherence_fix_fallback")[0]
    result["resolved_models"] = models
    audio = book.metadata.get("audiobook") or {}
    result["audio"] = {
        "voice_id": options.get("audio_voice_id", audio.get("voice_id")),
        "model_id": options.get("audio_model", audio.get("model_id") or os.environ.get("FORAGE_AUDIOBOOK_MODEL") or DEFAULT_MODEL),
        "output_format": options.get("audio_format", audio.get("output_format") or os.environ.get("FORAGE_AUDIOBOOK_OUTPUT_FORMAT") or DEFAULT_OUTPUT_FORMAT),
        "max_chars": options.get("audio_max_chars", audio.get("max_chars") or int(os.environ.get("FORAGE_AUDIOBOOK_MAX_CHARS", 9000))),
        "combine": options.get("audio_combine", True),
        "context_chars": options.get("audio_context_chars", 1200),
        "voice_settings": options.get("audio_voice_settings", audio.get("voice_settings")),
        "seed": options.get("audio_seed", audio.get("seed")),
        "language_code": options.get("audio_language_code", audio.get("language_code")),
        "apply_text_normalization": options.get("audio_normalization", "auto"),
        "stitch": options.get("audio_stitch", True),
        "enable_logging": options.get("audio_enable_logging", True),
    }
    if "audio" in outputs:
        if not result["audio"]["voice_id"]:
            raise ValueError("audio output requires audio_voice_id or metadata audiobook.voice_id")
        if result["audio"]["max_chars"] < 1000 or result["audio"]["context_chars"] < 0:
            raise ValueError("audio_max_chars must be >=1000; context_chars must be >=0")
        if not re.fullmatch(r"mp3_(?:22050_32|44100_(?:32|64|96|128|192))", result["audio"]["output_format"]):
            raise ValueError("integrated audio requires a supported MP3 format: mp3_22050_32 or mp3_44100_32/64/96/128/192")
    if "graphic" in outputs:
        from .graphic import graphic_settings
        result["graphic"] = graphic_settings(options)
        result["resolved_models"]["GRAPHIC_STORYBOARD"] = result["graphic"]["storyboard_model"]
    return result


def required_segments(plan: dict) -> list[dict]:
    return [s for s in plan["segments"] if s.get("diegetic_status") == "diegetic"
            and not s.get("skipped") and int(s.get("target_word_count", 0)) > 0]


def _valid_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("segments"), list) or not plan["segments"]:
        raise ValueError(f"plan refused or has no segments: {plan}")
    ids = []
    for segment in plan["segments"]:
        sid = segment.get("id")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
            raise ValueError("plan has invalid/duplicate segment IDs")
        ids.append(sid)
    if not required_segments(plan):
        raise ValueError("plan has no required draft segments")
    for gid, group in (plan.get("merged_groups") or {}).items():
        members = group.get("member_ids", [])
        if not re.fullmatch(r"[A-Za-z0-9_-]+", gid) or len(set(members)) != len(members) or any(m not in ids for m in members):
            raise ValueError("invalid plan merge group")
    return plan


def _editorial_patch(base, prepared, edited):
    """Apply only human changes to the pristine base, excluding derived skips."""
    if prepared == edited:
        return base
    if all(isinstance(value, dict) for value in (base, prepared, edited)):
        result = dict(base)
        for key in set(prepared) | set(edited):
            if key not in edited:
                result.pop(key, None)
            elif key not in prepared:
                result[key] = edited[key]
            else:
                result[key] = _editorial_patch(base.get(key), prepared[key], edited[key])
        return result
    if all(isinstance(value, list) for value in (base, prepared, edited)) and all(
            isinstance(item, dict) and "id" in item for value in (base, prepared, edited) for item in value):
        bases = {item["id"]: item for item in base}
        previous = {item["id"]: item for item in prepared}
        return [_editorial_patch(bases.get(item["id"]), previous.get(item["id"]), item) for item in edited]
    return edited


def _hash_optional(path):
    return sha256_file(path) if path.is_file() else None


def _stage_settings(config, stage):
    group = "critic:book" if stage == "book_critic" else stage
    key = group.upper().replace(":", "_")
    return {"model": config["resolved_models"].get(key),
            "source": source_fingerprint_for_stage(group)["hash"],
            "draft_thinking": os.environ.get("FORAGE_DRAFT_THINKING") if stage in {"draft", "regen"} else None,
            "fallback": config["resolved_models"].get(key + "_FALLBACK")}


class _Run:
    def __init__(self, book, config, *, execute):
        self.book, self.config, self.execute = book, config, execute
        self.root = book.work_dir
        self.base = Book(book.book_id, book.source_path, book.metadata, self.root / ".production" / "base")
        self.state = load_state(book)
        self.results = {}
        self.error = None

    def _paths(self, book, names):
        return inventory(self.root, [book.work_dir / n for n in names])

    def _input(self, name):
        record = self.state["stages"].get(name, {})
        return {"input": record.get("input"), "outputs": record.get("outputs")}

    def stage(self, name, inputs, action, *, dependencies=(), force=False):
        blocked = [dep for dep in dependencies if self.results.get(dep, {}).get("status") not in {"complete", "reused"}]
        if blocked:
            self.results[name] = {"status": "pending", "reason": "waiting for " + ", ".join(blocked)}
            return False
        signature = digest({"version": 1, "inputs": inputs})
        old = self.state["stages"].get(name, {})
        good = old.get("status") == "complete" and old.get("input") == signature and verify_inventory(self.root, old.get("outputs"))
        if good and not force:
            self.results[name] = {"status": "reused", "reason": "inputs and verified output bytes match", "metadata": old.get("metadata", {})}
            return True
        reason = ("explicit refresh" if force and good else "generation inputs changed" if old.get("input") and old.get("input") != signature else "outputs missing or changed" if old.get("status") == "complete" else "interrupted run is retryable" if old.get("status") == "running" else old.get("error") or "no successful production record")
        if not self.execute:
            self.results[name] = {"status": "failed" if old.get("status") == "failed" else "stale" if old else "pending", "reason": reason}
            return False
        record = {"version": 1, "status": "running", "input": signature, "started_at": now(), "outputs": old.get("outputs", []), "metadata": old.get("metadata", {})}
        self.state["stages"][name] = record
        save_state(self.book, self.state)
        logs = [(b.work_dir / "llm_calls.jsonl") for b in (self.book, self.base)]
        offsets = [p.stat().st_size if p.exists() else 0 for p in logs]
        try:
            outcome = action() or {}
            outputs = outcome["outputs"]
            if not verify_inventory(self.root, outputs):
                raise ValueError("stage returned missing or corrupt outputs")
            calls = []
            for path, offset in zip(logs, offsets):
                if path.exists():
                    with path.open() as stream:
                        stream.seek(offset)
                        calls.extend(json.loads(line) for line in stream if line.strip())
            if name in {"classify", "summarize", "cuts", "book_critic", "coherence"}:
                if any(c.get("stop_reason") not in {"stop", "end_turn", "stop_sequence"} for c in calls):
                    raise ValueError("provider returned incomplete output")
            record.update(status="complete", outputs=outputs, metadata=outcome.get("metadata", {}), completed_at=now(), calls=calls)
            self.results[name] = {"status": "complete", "reason": reason, "metadata": record["metadata"]}
            return True
        except Exception as error:
            record.update(status="failed", error=f"{type(error).__name__}: {error}", completed_at=now())
            self.results[name] = {"status": "failed", "reason": record["error"]}
            self.error = self.error or name
            return False
        finally:
            save_state(self.book, self.state)

    def preparation(self):
        split_config = self.book.source_path.parent / "split_config.json"
        source_input = {"source": sha256_file(self.book.source_path), "split_config": _hash_optional(split_config),
                        "algorithm": source_fingerprint_for_stage("split")["hash"]}
        def split():
            self.base.work_dir.mkdir(parents=True, exist_ok=True)
            split_to_disk(self.base)
            manifest = read_json(self.base.work_dir / "chapters.json")
            if "source" in manifest:
                manifest["source"] = self.book.source_path.name
                atomic_json(self.base.work_dir / "chapters.json", manifest)
            names = ["chapters.json"] + [f"chapters/{s['id']}.md" for s in manifest["chapters"]]
            if not manifest["chapters"]:
                raise ValueError("source contains no chapters")
            return {"outputs": self._paths(self.base, names)}
        self.stage("split", source_input, split)
        def classify():
            values = classify_chapters(self.base)
            ids = {s["id"] for s in read_json(self.base.work_dir / "chapters.json")["chapters"]}
            if set(values) != ids or any(v.get("status") not in {"diegetic", "extradiegetic", "toc_fragment", "cut_for_review"} for v in values.values()):
                raise ValueError("classification does not cover source chapters")
            return {"outputs": self._paths(self.base, ["chapter_classifications.json"])}
        metadata = self.book.metadata
        identity_metadata = {k: metadata.get(k) for k in ["title", "author"]}
        classifier_metadata = {**identity_metadata, "genre": metadata.get("genre")}
        cuts_metadata = {**identity_metadata, "force_keep_chapters": metadata.get("force_keep_chapters")}
        plan_metadata = {k: metadata.get(k) for k in ["title", "author", "force_keep_chapters", "modernization_level", "cultural_depth", "voice_driven_narrator", "indirection_budget_applies"]}
        self.stage("classify", [self._input("split"), classifier_metadata, _stage_settings(self.config, "classify")], classify, dependencies=["split"])
        def summarize():
            if not summarize_book(self.base).strip():
                raise ValueError("empty synopsis")
            return {"outputs": self._paths(self.base, ["book_synopsis.md"])}
        self.stage("summarize", [self._input("split"), self._input("classify"), identity_metadata, _stage_settings(self.config, "summarize")], summarize, dependencies=["classify"])
        def cuts():
            data = generate_cuts(self.base)
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError("cut planning failed")
            return {"outputs": self._paths(self.base, ["cuts.json"])}
        self.stage("cuts", [self._input("summarize"), cuts_metadata, _stage_settings(self.config, "cuts")], cuts, dependencies=["summarize"])
        def plan():
            _valid_plan(build_lean_plan(self.base))
            return {"outputs": self._paths(self.base, ["plan.json"])}
        self.stage("plan", [self._input("split"), self._input("classify"), self._input("cuts"), plan_metadata], plan, dependencies=["cuts"])
        base_identity = digest([self._input(s) for s in ["split", "classify", "summarize", "cuts", "plan"]])
        prior = self.state["stages"].get("preparation", {})
        overrides = dict(prior.get("metadata", {}).get("overrides", {})) if prior.get("metadata", {}).get("base_identity") == base_identity else {}
        expected = {item["path"]: item["sha256"] for item in prior.get("outputs", [])}
        override_error = None
        for name in ["cuts.json", "plan.json"]:
            path = self.root / name
            if prior.get("metadata", {}).get("base_identity") == base_identity and path.is_file() and expected.get(name) != sha256_file(path):
                try:
                    data = read_json(path)
                    if name == "plan.json":
                        data = _editorial_patch(prior["metadata"].get("unprepared_plan", read_json(self.base.work_dir / "plan.json")),
                                                prior["metadata"].get("prepared_plan", data), data)
                        _valid_plan(data)
                    elif not isinstance(data, dict):
                        raise ValueError("cuts must be a JSON object")
                    overrides[name] = data
                except (ValueError, TypeError, OSError) as error:
                    override_error = f"invalid edited {name}: {error}"
        def prepare():
            if override_error:
                raise ValueError(override_error)
            names = ["chapters.json", "chapter_classifications.json", "book_synopsis.md", "cuts.json", "plan.json"]
            manifest = read_json(self.base.work_dir / "chapters.json")
            names += [f"chapters/{c['id']}.md" for c in manifest["chapters"]]
            for name in names:
                target = confined_path(self.root, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.base.work_dir / name, target)
            # Fresh split must be the only source for relocation, including removed cuts.
            for orig in (self.root / "chapters").glob("*.md.orig"):
                orig.unlink()
            for name, value in overrides.items():
                atomic_json(self.root / name, value)
            unprepared_plan = read_json(self.root / "plan.json")
            result = apply_skips(self.book)
            if result.not_found:
                raise ValueError(f"cuts reference missing chapters: {result.not_found}")
            _valid_plan(read_json(self.root / "plan.json"))
            return {"outputs": self._paths(self.book, names), "metadata": {"base_identity": base_identity, "overrides": overrides,
                             "unprepared_plan": unprepared_plan, "prepared_plan": read_json(self.root / "plan.json")}}
        return self.stage("preparation", [base_identity, overrides, override_error], prepare, dependencies=["plan"])

    def _archive(self, names, signature):
        # Archive before invalidating a unit, including group cache and checks.
        existing = [self.root / n for n in names if (self.root / n).is_file()]
        if not existing:
            return
        ident = digest([signature, inventory(self.root, existing)])
        archive = self.root / ".production" / "draft_history" / ident
        for source in existing:
            dest = archive / source.relative_to(self.root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copyfile(source, dest)
            source.unlink()

    def drafts(self, plan):
        units = {}
        for segment in required_segments(plan):
            units.setdefault(segment.get("group_id") or segment["id"], []).append(segment)
        records = self.state.setdefault("draft_units", {})
        settings = _stage_settings(self.config, "draft")
        # Generation units may merge, split or be renamed when the plan changes.
        # Existing member provenance survives those unit-ID changes; unknown
        # legacy files still require explicit adoption.
        owners = {}
        for old_unit, record in records.items():
            known = {item["path"] for key in ("accepted", "generated")
                     for item in (record.get(key) or [])}
            known.update(f"segments/{sid}.md" for sid in record.get("members", []))
            for path in known:
                owners.setdefault(path, []).append(old_unit)
        failed = []
        for unit, segments in units.items():
            paths = [f"segments/{s['id']}.md" for s in segments]
            checks = [f"segments/{s['id']}.checks.json" for s in segments]
            inputs = {"preparation": self.state["stages"]["preparation"]["input"],
                      "segments": segments, "group": plan.get("merged_groups", {}).get(unit),
                      "source": self._paths(self.book, [f"chapters/{s['id']}.md" for s in segments]),
                      "plan": _hash_optional(self.root / "plan.json"), "cuts": _hash_optional(self.root / "cuts.json"), "settings": settings}
            signature = digest(inputs)
            previous = records.get(unit, {})
            valid = all(_disk_draft_result(self.root / "segments", s).status == "drafted" for s in segments)
            changed_inputs = previous.get("input") != signature
            unknown_existing = [path for path in paths if (self.root / path).exists() and path not in owners]
            # A recorded group may acquire a previously unowned member. Unit
            # provenance cannot authorize adopting or overwriting that chapter.
            if unknown_existing:
                if not self.config.get("adopt_existing"):
                    raise ValueError("legacy drafts lack provenance; use --adopt-existing after reviewing their source/settings")
                if not valid:
                    raise ValueError(f"cannot adopt {unit}: required drafts/checks are missing or incomplete")
                records[unit] = {"version": 1, "status": "complete", "input": signature,
                                 "origin": "user-adopted", "generated": None, "members": [s["id"] for s in segments],
                                 "accepted": self._paths(self.book, paths), "checks": self._paths(self.book, checks)}
                save_state(self.book, self.state)
                continue
            if previous.get("status") == "complete" and not changed_inputs and valid:
                previous["accepted"] = self._paths(self.book, paths)
                previous["checks"] = self._paths(self.book, checks)
                continue
            names = paths + checks + ([f"segments/{unit}.md"] if unit not in {s["id"] for s in segments} else [])
            self._archive(names, signature)
            from .drafter import build_draft_group_request, build_draft_segment_request
            if unit in plan.get("merged_groups", {}):
                request = build_draft_group_request(self.book, plan, unit).request
            else:
                segment = segments[0]
                source = (self.root / "chapters" / f"{segment['id']}.md").read_text()
                request = build_draft_segment_request(self.book, plan, segment["id"], source, len(source.split()))
            record = {"version": 1, "status": "running", "input": signature,
                      "request_sha256": digest(asdict(request)), "settings": settings,
                      "requested_model": request.active_model, "members": [s["id"] for s in segments],
                      "previous_units": sorted({owner for path in paths for owner in owners.get(path, [])}),
                      "context": {"prior_accepted": [r.get("accepted") for r in records.values() if r.get("status") == "complete"],
                                  "motif_ledger": _hash_optional(self.root / "motif_ledger.json")}, "origin": "provider-generated"}
            records[unit] = record
            save_state(self.book, self.state)
            log_path = self.root / "llm_calls.jsonl"
            log_offset = log_path.stat().st_size if log_path.exists() else 0
            try:
                for segment in segments:
                    result = draft_segment(self.book, plan, segment["id"])
                    if result.status != "drafted":
                        raise ValueError(f"draft {segment['id']} returned {result.status}")
                if not all(_disk_draft_result(self.root / "segments", s).status == "drafted" for s in segments):
                    raise ValueError(f"draft unit {unit} is incomplete")
                outputs = self._paths(self.book, paths)
                record.update(status="complete", generated=outputs, accepted=outputs, checks=self._paths(self.book, checks), generated_checks=self._paths(self.book, checks))
            except Exception as error:
                record.update(status="failed", error=str(error))
                failed.append(f"{unit}: {error}")
                break
            finally:
                if log_path.exists():
                    with log_path.open() as stream:
                        stream.seek(log_offset)
                        record["calls"] = [json.loads(line) for line in stream if line.strip()]
                save_state(self.book, self.state)
        if failed:
            raise ValueError("; ".join(failed))
        outputs = self._paths(self.book, [f"segments/{s['id']}.{suffix}" for s in required_segments(plan) for suffix in ("md", "checks.json")])
        return {"outputs": outputs, "metadata": {"generation": digest({u: {"input": records[u]["input"], "generated": records[u].get("generated")} for u in units})}}

    def quality(self, plan):
        results = {"iteration": [], "coherence": None, "repair": None}
        if self.config["iterate"]:
            for segment in required_segments(plan):
                r = iterate_segment(self.book, plan, segment["id"], max_retries=self.config["max_retries"])
                if r.final_verdict not in {"pass", "regenerate"}:
                    raise ValueError(f"iteration failed for {segment['id']}: {r.final_verdict}")
                results["iteration"].append(asdict(r))
        if self.config["coherence"] or self.config["coherence_fix"]:
            if len(_coherence_segment_ids(plan)) >= 2:
                report = run_coherence(self.book)
                if any(p.get("skipped") for p in report.get("per_pair", [])):
                    raise ValueError("coherence check contains skipped/failed pairs")
            else:
                report = {"book_id": self.book.book_id, "pairs_checked": 0, "findings": [], "per_pair": []}
                atomic_json(self.root / "coherence_report.json", report)
            results["coherence"] = report
        if self.config["coherence_fix"]:
            pairs = self.config["coherence_fix_pairs"]
            result = run_coherence_fixes(self.book, all_findings=not bool(pairs), pairs=pairs or None, max_retries=self.config["max_retries"])
            if result.get("pairs_failed") or result.get("pairs_rejected"):
                raise ValueError(f"coherence repair failed/rejected: {result}")
            results["repair"] = result
        if not all(_disk_draft_result(self.root / "segments", s).status == "drafted" for s in required_segments(plan)):
            raise ValueError("quality pass left incomplete drafts")
        atomic_json(self.root / "production_quality.json", results)
        return {"outputs": self._paths(self.book, ["production_quality.json"]), "metadata": {"iteration_hold": any(r["exhausted"] for r in results["iteration"])}}

    def audio(self, text_revision):
        result = generate_audiobook(self.book, input_path=self.root / "abridgment.txt", **self.config["audio"])
        if result.error_count or result.planned_count or result.generated_count + result.skipped_count != result.chunk_count or result.chunk_count <= 0:
            raise ValueError("audio narration is incomplete")
        if self.config["audio"]["combine"] and (result.combine_error or not result.combined_audio_path):
            raise ValueError(result.combine_error or "combined audiobook is missing")
        manifest = read_json(result.manifest_path)
        if manifest.get("dry_run") or len(manifest.get("chunks", [])) != result.chunk_count:
            raise ValueError("invalid audio manifest")
        targets, paths = [], []
        for chunk in manifest["chunks"]:
            if chunk.get("status") not in {"generated", "skipped"}:
                raise ValueError("audio manifest contains incomplete chunk")
            audio_path = Path(chunk["audio_path"])
            text_path = Path(chunk["text_path"])
            # Producer uses absolute paths; normalize only after confinement.
            audio_rel = audio_path.resolve().relative_to(self.root.resolve()).as_posix()
            text_rel = text_path.resolve().relative_to(self.root.resolve()).as_posix()
            if sha256_file(audio_path) != chunk.get("audio_sha256") or audio_path.stat().st_size != chunk.get("audio_size"):
                raise ValueError("audio manifest hash mismatch")
            target = {"id": f"audio-{chunk['id']}", "kind": "audio", "title": f"Audio chunk {chunk['id']}",
                      "path": audio_rel, "sha256": chunk["audio_sha256"], "text_path": text_rel,
                      "text_sha256": sha256_file(text_path), "text_revision": text_revision,
                      "request_sha256": chunk["request_sha256"], "duration_seconds": None,
                      "mime_type": {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "flac": "audio/flac", "m4a": "audio/mp4"}.get(audio_path.suffix.lstrip("."), "audio/wav")}
            target["revision"] = target_revision(target)
            targets.append(target)
            paths.extend([audio_rel, text_rel])
        if result.combined_audio_path:
            paths.append(result.combined_audio_path.resolve().relative_to(self.root.resolve()).as_posix())
        # Separate portable producer index; raw request log contains machine paths.
        portable = {"version": 1, "book_id": self.book.book_id, "text_revision": text_revision, "targets": targets}
        validate_media_manifest(portable, self.root)
        atomic_json(self.root / "audiobook" / "production_manifest.json", portable)
        paths += ["audiobook/production_manifest.json", "audiobook/audiobook_manifest.json"]
        return {"outputs": inventory(self.root, paths), "metadata": {"targets": targets, "provider": "elevenlabs", "settings": self.config["audio"]}}

    def run(self):
        prepared = self.preparation()
        if not prepared:
            for stage in ["drafting", "quality", "assembly", "book_critic", "validation", "alignment"] + [o for o in self.config["outputs"] if o != "text"] + ["snapshot"]:
                self.results[stage] = {"status": "pending", "reason": "waiting for current preparation"}
            if not self.state.get("draft_units") and any((self.root / "segments").glob("*.md")):
                self.results["drafting"]["reason"] = "legacy drafts lack provenance; execution requires --adopt-existing"
            return self.result()
        plan = _valid_plan(read_json(self.root / "plan.json"))
        current = [f"segments/{s['id']}.{suffix}" for s in required_segments(plan) for suffix in ("md", "checks.json")]
        # Human edits deliberately force validation/adoption of current prose, not generation.
        self.stage("drafting", [self._input("preparation"), _stage_settings(self.config, "draft")], lambda: self.drafts(plan), dependencies=["preparation"])
        if self.results["drafting"]["status"] not in {"complete", "reused"}:
            for stage in ["quality", "assembly", "book_critic", "validation", "alignment"] + [o for o in self.config["outputs"] if o != "text"] + ["snapshot"]:
                self.results[stage] = {"status": "pending", "reason": "waiting for complete required drafts"}
            return self.result()
        generation = self.state["stages"]["drafting"]["metadata"]["generation"]
        quality_settings = {k: self.config.get(k) for k in ["iterate", "max_retries", "coherence", "coherence_fix", "coherence_fix_pairs", "repair_epoch"]}
        quality_models = [_stage_settings(self.config, s) for s in ["regen", "critic", "coherence", "coherence_fix"]]
        self.stage("quality", [generation, quality_settings, quality_models], lambda: self.quality(plan), dependencies=["drafting"])
        if self.execute and self.results["quality"]["status"] in {"complete", "reused"}:
            # Repair owns the accepted result; it must not invalidate its original draft generation.
            for unit in self.state.get("draft_units", {}).values():
                if unit.get("status") == "complete" and all(i["path"] in current for i in unit.get("accepted", [])):
                    unit["accepted"] = inventory(self.root, [i["path"] for i in unit["accepted"]])
                    unit["checks"] = inventory(self.root, [i["path"] for i in unit["checks"]])
            self.state["stages"]["drafting"]["outputs"] = inventory(self.root, current)
            save_state(self.book, self.state)
        text_revision = digest({"version": 1, "book_id": self.book.book_id,
                                "plan": sha256_file(self.root / "plan.json"),
                                "drafts": inventory(self.root, [f"segments/{s['id']}.md" for s in required_segments(plan)])})
        def assembly():
            result = assemble_book(self.book, plan)
            if result.segments_missing or not result.abridgment_path or not result.plain_text_path:
                raise ValueError("assembly is incomplete")
            report = read_json(self.root / "assembly_report.json")
            for key in ["timestamp", "published_abridgment_path", "published_plain_text_path"]:
                report.pop(key, None)
            report.update(abridgment_path="abridgment.md", plain_text_path="abridgment.txt")
            atomic_json(self.root / "assembly_report.json", report)
            return {"outputs": self._paths(self.book, ["abridgment.md", "abridgment.txt", "assembly_report.json"])}
        self.stage("assembly", text_revision, assembly, dependencies=["quality"])
        def critic():
            report = run_book_critic(self.book)
            if report.get("is_partial") or report.get("verdict") not in {"ship", "hold"} or len(report.get("findings", [])) != report.get("synopsis_sentence_count"):
                raise ValueError("book critic returned an incomplete report")
            if [f.get("sentence") for f in report["findings"]] != list(range(1, report["synopsis_sentence_count"] + 1)) or any(f.get("status") not in {"present", "missing", "distorted"} for f in report["findings"]):
                raise ValueError("book critic returned an incomplete report")
            return {"outputs": self._paths(self.book, ["book_critic.json"]), "metadata": {"verdict": report["verdict"]}}
        self.stage("book_critic", [text_revision, self._input("summarize"), _stage_settings(self.config, "book_critic")], critic, dependencies=["assembly"])
        def validate():
            report = validate_book(self.book, plan)
            atomic_json(self.root / "validation_report.json", asdict(report))
            return {"outputs": self._paths(self.book, ["validation_report.json"])}
        self.stage("validation", text_revision, validate, dependencies=["assembly"])
        alignment_settings = _stage_settings(self.config, "align")
        previous_alignment_settings = self.state["stages"].get("alignment", {}).get("metadata", {}).get("settings")
        def alignment():
            paths = []
            for segment in required_segments(plan):
                sid = segment["id"]
                path = self.root / "alignments" / f"{sid}.json"
                source = _split_paragraphs((self.root / "chapters" / f"{sid}.md").read_text())
                draft = _split_paragraphs((self.root / "segments" / f"{sid}.md").read_text())
                if previous_alignment_settings != alignment_settings or not _alignment_current(path, source, draft):
                    result = align_chapter(self.book, sid)
                    if result.get("error"):
                        raise ValueError(f"alignment {sid} failed: {result['error']}")
                if not _alignment_current(path, source, draft):
                    raise ValueError(f"alignment {sid} is invalid")
                paths.append(f"alignments/{sid}.json")
            render_proofread_html(self.book)
            paths.append("proofread.html")
            return {"outputs": self._paths(self.book, paths), "metadata": {"settings": alignment_settings}}
        self.stage("alignment", [text_revision, self._input("preparation"), alignment_settings], alignment, dependencies=["assembly"])
        if self.config.get("checkpoint_before_media") and set(self.config["outputs"]) - {"text"}:
            approved = self.state.get("media_checkpoint")
            if self.config.get("continue_revision") == text_revision and self.execute:
                self.state["media_checkpoint"] = text_revision
                self.state["text_revision"] = text_revision
                save_state(self.book, self.state)
                approved = text_revision
            if approved != text_revision:
                self.results["checkpoint"] = {"status": "pending", "reason": f"media checkpoint for accepted revision {text_revision}; continue with --continue-revision {text_revision}"}
                for stage in [o for o in self.config["outputs"] if o != "text"] + ["snapshot"]:
                    self.results[stage] = {"status": "pending", "reason": "waiting for revision-bound media checkpoint"}
                result = self.result()
                result["text_revision"] = text_revision
                return result
            self.results["checkpoint"] = {"status": "complete", "reason": "accepted text revision acknowledged"}
        if "audio" in self.config["outputs"]:
            self.stage("audio", [text_revision, self.config["audio"]], lambda: self.audio(text_revision), dependencies=["assembly"])
        if "graphic" in self.config["outputs"]:
            def graphic():
                from .graphic import generate_graphic
                result = generate_graphic(self.book, text_revision=text_revision, options=self.config)
                return {"outputs": result["outputs"], "metadata": {**result.get("metadata", {}), "targets": result["targets"]}}
            self.stage("graphic", [text_revision, self.config["graphic"]], graphic, dependencies=["assembly"])
        deps = ["assembly", "book_critic", "validation", "alignment"] + [o for o in self.config["outputs"] if o != "text"]
        def snapshot():
            from .publication import snapshot_revision
            targets = [target for branch in ["audio", "graphic"] if branch in self.config["outputs"] for target in self.state["stages"][branch]["metadata"]["targets"]]
            index = {"version": 1, "book_id": self.book.book_id, "text_revision": text_revision, "targets": targets}
            validate_media_manifest(index, self.root)
            atomic_json(self.root / "media_manifest.json", index)
            names = ["plan.json", "chapters.json", "chapter_classifications.json", "book_synopsis.md", "cuts.json", "production_quality.json", "media_manifest.json"]
            names += current
            outputs = inventory(self.root, names)
            for stage in deps:
                outputs += self.state["stages"][stage]["outputs"]
            # Raw audio manifest stores machine-local paths; portable index and verified assets suffice.
            outputs = sorted({o["path"]: o for o in outputs if o["path"] != "audiobook/audiobook_manifest.json"}.values(), key=lambda x: x["path"])
            summary = {"status": "complete", "selected_outputs": self.config["outputs"],
                       "stages": {k: {"status": "complete"} for k in self.results},
                       "quality": {"book_critic": self.state["stages"]["book_critic"]["metadata"]["verdict"],
                                   **self.state["stages"]["quality"]["metadata"]}}
            result = snapshot_revision(self.book, text_revision=text_revision, outputs=outputs, media_index=index, stage_summary=summary, lock_held=True)
            self.state["text_revision"] = text_revision
            self.state["review_revision"] = result["revision"]
            return {"outputs": inventory(self.root, ["media_manifest.json", "review_current.json", f"publications/{result['revision']}/revision.json"] + [f"publications/{result['revision']}/{i['path']}" for i in result["outputs"]]), "metadata": {"revision": result["revision"], "text_revision": text_revision}}
        self.stage("snapshot", [text_revision, self.config["outputs"], [self._input(d) for d in deps]], snapshot, dependencies=deps)
        return self.result()

    def result(self):
        return {"book_id": self.book.book_id, "execute": self.execute, "outputs": self.config["outputs"],
                "success": all(v["status"] in {"complete", "reused"} for v in self.results.values()),
                "failed_stage": self.error, "stages": self.results,
                "text_revision": self.state.get("text_revision"), "review_revision": self.state.get("review_revision")}


def plan_production(book: Book, options: dict | None = None) -> dict:
    from .review_recovery import assert_review_applications_resolved
    assert_review_applications_resolved(book)
    config = resolve_options(book, options)
    return _Run(book, config, execute=False).run()


def _reusable_options(config: dict) -> dict:
    """Persist only supported, nonsecret operational settings for feedback sync."""
    options = {key: value for key, value in config.items()
               if key not in {"resolved_models", "audio", "graphic", "continue_revision", "adopt_existing"}}
    options["models"] = {stage: config["resolved_models"][stage.upper().replace(":", "_")]
                         for stage in PROMPT_STAGES}
    audio_names = {"model_id": "model", "output_format": "format",
                   "apply_text_normalization": "normalization"}
    if "audio" in config["outputs"]:
        options.update({"audio_" + audio_names.get(key, key): value
                        for key, value in config["audio"].items()})
    graphic_keys = {"provider", "model", "storyboard_model", "style", "size", "quality",
                    "chapters", "words_per_frame", "font_size", "caption_height"}
    options.update({"graphic_" + key: value for key, value in config.get("graphic", {}).items()
                    if key in graphic_keys})
    return options


def run_production(book: Book, options: dict | None = None, *, lock_held: bool = False) -> dict:
    """Run under the book lock, or compose inside a caller's existing lock."""
    config = resolve_options(book, options)
    with (nullcontext() if lock_held else book_lock(book)), llm.production_context(config["resolved_models"], book.work_dir.parent / ".replay_cache"):
        from .review_recovery import recover_review_applications
        recover_review_applications(book, lock_held=True)
        runner = _Run(book, config, execute=True)
        # Refuse legacy drafts before any paid preparation can overwrite context.
        if not runner.state.get("draft_units") and any((book.work_dir / "segments").glob("*.md")) and not config.get("adopt_existing"):
            raise ValueError("legacy drafts lack provenance; inspect and pass --adopt-existing")
        # A failed branch still owns a deliberate configuration request. Sync
        # retries must not silently revert to the previous successful selection.
        runner.state["requested_production_options"] = _reusable_options(config)
        save_state(book, runner.state)
        result = runner.run()
        if result["success"]:
            runner.state["production_options"] = _reusable_options(config)
            save_state(book, runner.state)
        return result
