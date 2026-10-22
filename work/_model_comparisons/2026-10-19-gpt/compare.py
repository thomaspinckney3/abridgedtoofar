"""Frozen drafting-stage GPT trial. Preparation/counting do not generate text.

The run command requires separate human batch approval. No live book mutations,
automatic retries, fallback, paid judging, or repair passes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRIOR = OUT.parent / "2026-10-19"
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from forage.drafter import _extract_chapter_notes

MODELS = {"astra": "gpt-6-astra", "sol61": "gpt-6.1-sol"}
RATES = {"astra": {"input": 10, "cached_input": 1, "cache_write": 12.5, "output": 50},
         "sol61": {"input": 2, "cached_input": .1, "cache_write": 2.5, "output": 10}}


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def prepare():
    if (OUT / "manifest.json").exists():
        raise SystemExit("Inputs already frozen; refusing to overwrite.")
    prior = read(PRIOR / "manifest.json")
    manifest = {
        "status": "prepared_awaiting_cost_approval", "prepared_at": stamp(),
        "prior_comparison": str(PRIOR), "models": MODELS,
        "pipeline": "Identical frozen Forage draft_lean system/prompt/cached_prompt, "
                    "flattened as in forage.llm._openai; existing chapter-note parser. "
                    "Benchmark-only SDK adapter explicitly sets medium reasoning and disables retries.",
        "scope": "Drafting-stage trial, not a complete production pipeline run.",
        "limitations": prior["limitations"] + [
            "Same reasoning label does not imply equal reasoning compute across providers.",
            "GPT requests use medium reasoning and 32,000 total output tokens including reasoning.",
            "Prior Anthropic trial changed Opus effort after a timeout; retained as historical evidence."],
        "rates_usd_per_million": RATES,
        "pricing_sources": ["https://developers.openai.com/api/docs/models/" + m for m in MODELS.values()],
        "proposed_batch_ceiling_usd": 7, "expected_cost_usd": [2, 4],
        "chapters": prior["chapters"], "rubric": prior["rubric"],
        "live_hashes": prior["live_hashes"], "requests": [], "input_hashes": {},
    }
    for book in ["gatsby", "mobydick"]:
        shutil.copytree(PRIOR / book / "baseline", OUT / book / "baseline")
        for variant in ["opus55", "sonnet55"]:
            shutil.copytree(PRIOR / book / variant, OUT / book / variant)
    for name in ["preflight_assessment.json", "assessment.json", "manifest.json"]:
        dest = "preflight_assessment.json" if name.startswith("preflight") else "anthropic_" + name
        shutil.copy2(PRIOR / name, OUT / dest)
    for old in prior["requests"]:
        if old["variant"] != "sonnet55":
            continue
        source_path = PRIOR / old["request_path"]
        frozen = read(source_path)
        for variant, model in MODELS.items():
            key = old["key"].replace("sonnet55", variant)
            messages = []
            if frozen["system"]:
                messages.append({"role": "system", "content": frozen["system"]})
            messages.append({"role": "user", "content":
                (frozen["cached_prompt"] or "") + frozen["prompt"]})
            assert frozen["temperature"] is None
            payload = {"model": model, "messages": messages,
                       "max_completion_tokens": 32000, "reasoning_effort": "medium",
                       "service_tier": "default", "store": False}
            path = OUT / "requests" / (key + ".json")
            save(path, payload)
            manifest["requests"].append({
                "key": key, "book": old["book"], "members": old["members"],
                "variant": variant, "model": model,
                "request_path": str(path.relative_to(OUT)), "sha256": sha(path),
                "source_request": str(source_path), "source_sha256": sha(source_path),
                "max_tokens": 32000, "reasoning_effort": "medium",
            })
    for path in OUT.rglob("*"):
        if path.is_file() and path.name != "compare.py":
            manifest["input_hashes"][str(path.relative_to(OUT))] = sha(path)
    verify(manifest)
    save(OUT / "manifest.json", manifest)
    print("Prepared", len(manifest["requests"]), "requests; no generation calls.")


def verify(manifest):
    for path, digest in manifest["live_hashes"].items():
        assert sha(ROOT / path) == digest, f"Live artifact changed: {path}"
    for path, digest in manifest["input_hashes"].items():
        assert sha(OUT / path) == digest, f"Frozen input changed: {path}"
    for item in manifest["requests"]:
        assert sha(OUT / item["request_path"]) == item["sha256"]
        assert sha(Path(item["source_request"])) == item["source_sha256"]


def count_tokens():
    import openai
    client = openai.OpenAI(max_retries=0, timeout=60)
    manifest = read(OUT / "manifest.json")
    verify(manifest)
    for item in manifest["requests"]:
        if "counted_input_tokens" in item:
            continue
        request = read(OUT / item["request_path"])
        result = client.responses.input_tokens.count(
            model=request["model"], input=request["messages"], reasoning={"effort": "medium"})
        item["counted_input_tokens"] = result.input_tokens
        # Responses and Chat use different framing; reserve an extra 1,024 tokens.
        budget_input = result.input_tokens + 1024
        rate = RATES[item["variant"]]
        item["maximum_cost_usd"] = round((budget_input * rate["cache_write"] +
                                          32000 * rate["output"]) / 1e6, 6)
        save(OUT / "manifest.json", manifest)
        print(item["key"], result.input_tokens, item["maximum_cost_usd"], flush=True)
    manifest["maximum_batch_cost_usd"] = round(sum(
        item["maximum_cost_usd"] for item in manifest["requests"]), 6)
    assert manifest["maximum_batch_cost_usd"] <= manifest["proposed_batch_ceiling_usd"]
    save(OUT / "manifest.json", manifest)
    print("Maximum batch USD", manifest["maximum_batch_cost_usd"])


def usage_cost(usage, variant):
    rate = RATES[variant]
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") or 0
    written = details.get("cache_write_tokens") or 0
    uncached = usage["prompt_tokens"] - cached - written
    assert uncached >= 0, "Unexpected provider usage accounting; inspect raw response."
    return round((uncached * rate["input"] + cached * rate["cached_input"] +
                  written * rate["cache_write"] + usage["completion_tokens"] * rate["output"]) / 1e6, 6)


def run(approved):
    if not approved:
        raise SystemExit("Explicit approval for this six-request batch is required before --approved.")
    import openai
    manifest = read(OUT / "manifest.json")
    assert manifest["maximum_batch_cost_usd"] <= manifest["proposed_batch_ceiling_usd"]
    verify(manifest)
    client = openai.OpenAI(max_retries=0, timeout=600)
    manifest["status"] = "running"
    manifest.setdefault("approval_recorded_at", stamp())
    save(OUT / "manifest.json", manifest)
    for item in manifest["requests"]:
        if "result" in item:
            continue
        dest = OUT / item["book"] / item["variant"]
        marker = dest / (item["key"] + ".started.json")
        if marker.exists():
            raise RuntimeError(f"Ambiguous previous request; inspect before proceeding: {marker}")
        request = read(OUT / item["request_path"])
        assert sha(OUT / item["request_path"]) == item["sha256"]
        save(marker, {"started_at": stamp(), "request": item["key"]})
        start = time.monotonic()
        result = {"status": "failed", "cost_usd": None}
        print("START", item["key"], flush=True)
        try:
            response = client.chat.completions.create(**request)
            raw = response.model_dump(mode="json")
            save(dest / (item["key"] + ".response.json"), raw)
            usage = raw["usage"]
            result.update({"returned_model": raw["model"], "usage": usage,
                           "output_tokens": usage["completion_tokens"],
                           "cost_usd": usage_cost(usage, item["variant"]),
                           "request_id": response._request_id})
            choice = response.choices[0]
            result["stop_reason"] = choice.finish_reason
            assert choice.finish_reason == "stop", "Incomplete response; raw response retained."
            assert choice.message.content, "Empty response; raw response retained."
            text = choice.message.content.strip()
            if len(item["members"]) > 1:
                parts = re.split(r"(?m)^(?:##\s*)?(?:Sub-)?Chapter\s+(?:\d+|[IVXLCDM]+)\b[^\n]*$", text)[1:]
                assert len(parts) == len(item["members"]), "Merged chapter count differs."
            else:
                parts = [text]
            for sid, part in zip(item["members"], parts):
                prose, notes = _extract_chapter_notes(part.strip())
                assert prose.strip(), "Parsed chapter is empty."
                (dest / "segments").mkdir(exist_ok=True)
                (dest / "segments" / (sid + ".md")).write_text(prose.strip() + "\n")
                save(dest / "segments" / (sid + ".notes.json"), notes)
            result["status"] = "complete"
        except Exception as exc:
            result.update({"error_type": type(exc).__name__, "error": str(exc),
                           "billing_note": "Unknown when provider usage is unavailable; no retry."})
        result["duration_s"] = round(time.monotonic() - start, 2)
        item["result"] = result
        save(OUT / "manifest.json", manifest)
        print("DONE", item["key"], result["status"], result["cost_usd"], result["duration_s"], flush=True)
    verify(manifest)
    manifest["status"] = "completed" if all(i["result"]["status"] == "complete" for i in manifest["requests"]) else "completed_with_failures"
    manifest["recorded_generation_cost_usd"] = round(sum(i["result"]["cost_usd"] or 0 for i in manifest["requests"]), 6)
    manifest["total_cost_upper_bound_usd"] = round(sum(i["result"]["cost_usd"] if i["result"]["cost_usd"] is not None else i["maximum_cost_usd"] for i in manifest["requests"]), 6)
    manifest["finished_at"] = stamp()
    save(OUT / "manifest.json", manifest)


if __name__ == "__main__":
    load_dotenv(ROOT / ".env", override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "count", "verify", "run"])
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "count":
        count_tokens()
    elif args.command == "verify":
        verify(read(OUT / "manifest.json"))
        print("Frozen inputs and live book hashes verified.")
    else:
        run(args.approved)
