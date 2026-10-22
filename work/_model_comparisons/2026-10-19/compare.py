"""Isolated four-chapter trial using Forage's actual drafting requests.

prepare makes no generation calls; run executes only the six frozen requests.
Historical final abridgments are comparators, not a controlled old-model trial.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from forage import llm
from forage.artifacts import Book
from forage.drafter import (build_draft_group_request,
                           build_draft_segment_request, _extract_chapter_notes)

MODELS = {"opus55": "anthropic:claude-opus-5-5",
          "sonnet55": "anthropic:claude-sonnet-5-5"}
SAMPLES = {"gatsby": ["001", "002"], "mobydick": ["004", "005"]}
RATES = {"opus55": [4, 20, 5, .20], "sonnet55": [2, 10, 2.5, .10]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read(path):
    return json.loads(path.read_text())


def stamp():
    return datetime.now(timezone.utc).isoformat()


def prepare():
    if (OUT / "manifest.json").exists():
        raise SystemExit("Already prepared; refusing to overwrite frozen inputs.")
    manifest = {
        "status": "prepared_awaiting_cost_approval", "prepared_at": stamp(),
        "scope": "Historical final-output comparison; one first draft per model. "
                 "Not an isolated causal old-versus-new model benchmark.",
        "pipeline": "Forage draft_lean request builders and chapter-note parser; "
                    "existing classifications, plans, cuts and chapter inputs frozen.",
        "excluded": "No regeneration, paid judging, coherence repair, fallback, "
                    "retry, assembly, review decisions, or publication.",
        "models": MODELS, "rates_usd_per_million": RATES,
        "rate_columns": ["input", "output_including_thinking", "cache_write_5m", "cache_read"],
        "pricing_source": "https://platform.claude.com/docs/en/models/overview",
        "expected_cost_usd": [2, 5], "authorized_batch_ceiling_usd": 10,
        "rubric": ["source fidelity and causal completeness", "authorial voice",
                   "dialogue paragraphing and attribution", "within/between-chapter continuity",
                   "word-budget compliance (not a quality score)", "latency and billed tokens"],
        "limitations": ["Four chapters, two books, one sample per model, no statistical claim.",
                        "Historical final versions have prior repair passes and older prompts.",
                        "New-model comparison uses identical prompts but normal model-specific reasoning settings.",
                        "No independent paid judge; qualitative review is by the coding assistant."],
        "live_hashes": {}, "chapters": [], "requests": [],
    }
    for book_id, ids in SAMPLES.items():
        src = ROOT / "work" / book_id
        base = OUT / book_id / "baseline"
        base.mkdir(parents=True)
        for name in ["plan.json", "cuts.json", "book_synopsis.md"]:
            shutil.copy2(src / name, base / name)
        shutil.copy2(ROOT / "books" / book_id / "metadata.json", base / "metadata.json")
        plan = read(base / "plan.json")
        logs = [json.loads(line) for line in (src / "llm_calls.jsonl").read_text().splitlines() if line.strip()]
        lineage = [r for r in logs if r.get("stage", "").split(":")[0] in
                   {"draft", "draft_fallback", "regen", "coherence_fix", "coherence_fix_fallback"}
                   and any(sid in r["stage"] for sid in ids)]
        save(base / "historical_generation_log.json", lineage)
        for sid in ids:
            segment = next(s for s in plan["segments"] if s["id"] == sid)
            for subdir in ["chapters", "segments"]:
                dest = base / subdir / f"{sid}.md"
                dest.parent.mkdir(exist_ok=True)
                shutil.copy2(src / subdir / f"{sid}.md", dest)
                original = src / subdir / f"{sid}.md"
                manifest["live_hashes"][str(original.relative_to(ROOT))] = sha(original)
            manifest["chapters"].append({"book": book_id, "id": sid,
                "title": segment["title"], "target_words": segment["target_word_count"],
                "source_words": len((base / "chapters" / f"{sid}.md").read_text().split()),
                "baseline_words": len((base / "segments" / f"{sid}.md").read_text().split()),
                "baseline_sha256": sha(base / "segments" / f"{sid}.md")})
        for filename in ["plan.json", "cuts.json", "abridgment.md", "abridgment.txt"]:
            p = src / filename
            if p.exists():
                manifest["live_hashes"][str(p.relative_to(ROOT))] = sha(p)
        for filename in ["abridgment.md", "abridgment.txt"]:
            p = ROOT / "books" / book_id / filename
            if p.exists():
                manifest["live_hashes"][str(p.relative_to(ROOT))] = sha(p)
        book = Book(book_id, ROOT / "books" / book_id / f"{book_id}.txt",
                    read(base / "metadata.json"), base)
        for label, model in MODELS.items():
            with llm.production_context({"DRAFT": model}, OUT / "replay_cache"):
                requests = []
                if book_id == "mobydick":
                    build = build_draft_group_request(book, plan, "g002")
                    assert [m["id"] for m in build.members] == ids
                    requests.append((build.request, ids))
                else:
                    for sid in ids:
                        source = (base / "chapters" / f"{sid}.md").read_text()
                        requests.append((build_draft_segment_request(book, plan, sid, source,
                                         len(source.split())), [sid]))
            for request, members in requests:
                data = asdict(request)
                assert data["active_model"] == model
                key = f"{book_id}-{request.request_id}-{label}"
                path = OUT / "requests" / f"{key}.json"
                save(path, data)
                chars = len((request.system or "") + (request.cached_prompt or "") + request.prompt)
                # Generous byte/character upper estimate; replaced by API token count below.
                estimate = round(chars / 3)
                manifest["requests"].append({"key": key, "book": book_id,
                    "members": members, "variant": label, "model": model,
                    "request_path": str(path.relative_to(OUT)), "sha256": sha(path),
                    "max_tokens": request.max_tokens, "thinking": request.thinking,
                    "estimated_input_tokens": estimate})
    # Models get byte-identical prompt text. Only runtime/model settings differ.
    for book, rid in [("gatsby", "001"), ("gatsby", "002"), ("mobydick", "g002")]:
        a, b = [read(OUT / "requests" / f"{book}-{rid}-{label}.json") for label in MODELS]
        for key in ["prompt", "cached_prompt", "system", "temperature", "cache"]:
            assert a[key] == b[key], (book, rid, key)
    save(OUT / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ["status", "chapters", "requests"]}, indent=2))


def count_tokens():
    """Anthropic count_tokens is a free preflight, with no text generation."""
    import anthropic
    manifest = read(OUT / "manifest.json")
    client = anthropic.Anthropic(max_retries=0, default_headers={
        "anthropic-workspace-id": os.environ["ANTHROPIC_WORKSPACE_ID"]})
    for item in manifest["requests"]:
        r = read(OUT / item["request_path"])
        result = client.messages.count_tokens(model=r["active_model"].split(":", 1)[1],
            system=r["system"], messages=[{"role": "user", "content":
                (r["cached_prompt"] or "") + r["prompt"]}])
        item["counted_input_tokens"] = result.input_tokens
        rates = RATES[item["variant"]]
        # Conservatively price the whole input as a cache write.
        item["maximum_cost_usd"] = round((result.input_tokens * rates[2] +
                                           r["max_tokens"] * rates[1]) / 1e6, 6)
        print(item["key"], result.input_tokens, item["maximum_cost_usd"], flush=True)
    manifest["maximum_batch_cost_usd"] = round(sum(i["maximum_cost_usd"] for i in manifest["requests"]), 6)
    save(OUT / "manifest.json", manifest)


def verify_live(manifest):
    for path, digest in manifest["live_hashes"].items():
        if sha(ROOT / path) != digest:
            raise RuntimeError(f"Live artifact changed: {path}")


def run(approved):
    import anthropic
    if not approved:
        raise SystemExit("Run requires --approved after explicit batch approval.")
    manifest = read(OUT / "manifest.json")
    assert manifest["maximum_batch_cost_usd"] <= manifest["authorized_batch_ceiling_usd"]
    verify_live(manifest)
    manifest["status"] = "running"
    manifest.setdefault("started_at", stamp())
    save(OUT / "manifest.json", manifest)
    os.environ["FORAGE_REPLAY"] = "1"
    # Both the SDK and Forage otherwise transparently retry. Keep this batch bounded.
    original_client = anthropic.Anthropic
    with patch.object(anthropic, "Anthropic", partial(original_client, max_retries=0)), \
         patch.object(llm, "_with_retries", lambda fn, **kwargs: fn()):
        for item in manifest["requests"]:
            dest = OUT / item["book"] / item["variant"]
            response_path = dest / f"{item['key']}.response.json"
            if item.get("result", {}).get("status") == "failed":
                print("Recorded failure; no retry", item["key"], flush=True)
                continue
            if response_path.exists():
                print("Already recorded", item["key"], flush=True)
                continue
            # A started-but-unrecorded request is ambiguous; never silently repeat it.
            marker = dest / f"{item['key']}.started.json"
            if marker.exists():
                raise RuntimeError(f"Previous attempt needs inspection: {marker}")
            p = OUT / item["request_path"]
            assert sha(p) == item["sha256"], "Frozen request changed"
            r = read(p)
            save(marker, {"started_at": stamp(), "request": item["key"]})
            print("START", item["key"], "thinking", r["thinking"], flush=True)
            try:
                with llm.production_context({"DRAFT": item["model"]}, OUT / "replay_cache"):
                    resp = llm.complete(**{key: r[key] for key in ["prompt", "system", "max_tokens",
                        "temperature", "cache", "cached_prompt", "thinking", "stage"]},
                        model=item["model"], work_dir=dest)
                save(response_path, asdict(resp))
                assert resp.model == item["model"]
                llm.require_complete_response(resp, item["key"])
                if len(item["members"]) > 1:
                    parts = re.split(r"(?m)^(?:##\s*)?(?:Sub-)?Chapter\s+(?:\d+|[IVXLCDM]+)\b[^\n]*$",
                                     resp.text.strip())[1:]
                    if len(parts) != len(item["members"]):
                        raise ValueError("Merged response chapter count differs; inspect saved raw response")
                else:
                    parts = [resp.text.strip()]
                for sid, text in zip(item["members"], parts):
                    prose, notes = _extract_chapter_notes(text.strip())
                    (dest / "segments").mkdir(exist_ok=True)
                    (dest / "segments" / f"{sid}.md").write_text(prose.strip() + "\n")
                    save(dest / "segments" / f"{sid}.notes.json", notes)
                rates = RATES[item["variant"]]
                cost = sum((n or 0) * rate for n, rate in zip(
                    [resp.input_tokens, resp.output_tokens, resp.cache_write_tokens, resp.cache_read_tokens], rates)) / 1e6
                item["result"] = {"status": "complete", "cost_usd": round(cost, 6),
                    "duration_s": round(resp.duration_s, 2), "stop_reason": resp.stop_reason,
                    "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
                    "cache_read_tokens": resp.cache_read_tokens, "cache_write_tokens": resp.cache_write_tokens}
                print("DONE", item["key"], json.dumps(item["result"]), flush=True)
            except Exception as exc:
                item["result"] = {"status": "failed", "error_type": type(exc).__name__,
                                  "error": str(exc), "cost_usd": None,
                                  "billing_note": "No final provider usage received; cost unknown."}
                manifest["status"] = "running_with_failures"
                save(OUT / "manifest.json", manifest)
                print("FAILED", item["key"], type(exc).__name__, flush=True)
            save(OUT / "manifest.json", manifest)
    verify_live(manifest)
    manifest["status"] = "generated_pending_assessment"
    manifest["completed_at"] = stamp()
    manifest["live_artifacts_unchanged"] = True
    manifest["recorded_generation_cost_usd"] = round(sum((i.get("result", {}).get("cost_usd") or 0)
                                                        for i in manifest["requests"]), 6)
    manifest["unpriced_failed_requests"] = [i["key"] for i in manifest["requests"]
                                           if i.get("result", {}).get("status") == "failed"]
    manifest["total_cost_upper_bound_usd"] = round(manifest["recorded_generation_cost_usd"] +
        sum(i["maximum_cost_usd"] for i in manifest["requests"] if i["key"] in manifest["unpriced_failed_requests"]), 6)
    save(OUT / "manifest.json", manifest)
    print("BATCH COMPLETE; recorded cost", manifest["recorded_generation_cost_usd"],
          "unpriced failures", len(manifest["unpriced_failed_requests"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "count", "run"])
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=True)
    if args.command == "prepare":
        prepare()
    elif args.command == "count":
        count_tokens()
    else:
        run(args.approved)
