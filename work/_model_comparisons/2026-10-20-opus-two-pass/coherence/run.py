"""Run the existing pair critic on frozen revision + production-neighbor triples.

The critic/prompt/parsing are unchanged. A recording transport disables retries,
enforces the preflight request, and saves provider usage/text without hidden
thinking. No draft, production report, or original experiment file is modified.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
TRIAL = OUT.parent
ROOT = TRIAL.parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from forage.artifacts import Book, read_json as read, write_json as save
from forage import coherence
from forage.llm import LLMResponse, resolve_model_for_stage
from forage.prompts import load_prompt

SAMPLES = {"education": ["007", "027"], "secret_adversary": ["003", "009"]}
MODEL = "anthropic:claude-sonnet-5-5"
PRICING = "https://platform.claude.com/docs/en/models/sonnet-5-5/overview"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def client():
    import anthropic
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    return anthropic.Anthropic(
        max_retries=0, timeout=600,
        default_headers={"anthropic-workspace-id": workspace} if workspace else {},
    )


def book_for(group):
    book_id = group["book"]
    return Book(book_id, TRIAL / book_id / "full_source.txt",
                read(TRIAL / book_id / "metadata.json"), OUT / group["path"])


def prepare():
    if (OUT / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    prompt = load_prompt("critic_coherence")
    assert resolve_model_for_stage(prompt.config["model"], "coherence")[0] == MODEL
    m = {
        "status": "preparing", "prepared_at": stamp(),
        "authorization": "User: 'do that', explicitly requesting coherence critic on the redrafted chapters.",
        "model": MODEL, "maximum_calls": 8, "retries": 0,
        "max_output_tokens": prompt.config["max_tokens"],
        "thinking": "Unchanged pipeline/provider default",
        "cost_ceiling_usd": 2, "pricing_source": PRICING,
        "rates_per_million": {"input": 2, "output": 10, "cache_write": 2.5, "cache_read": .1},
        "cuts_context": (
            "No production cuts.json supplied: the revisions were generated from the new "
            "preservation plans, not the old cuts prepass. This also leaves the prompt's "
            "conditional authorized-cut seam exemption inactive."
        ),
        "method": (
            "Unchanged forage.coherence.run_coherence and critic_coherence prompt on four "
            "isolated three-chapter windows. Center is exact second-pass revision; neighbors "
            "are current production drafts. Each window has two genuine adjacent reading-order pairs."
        ),
        "limitations": [
            "This is a structural coherence critic, not a style or completeness critic.",
            "Immediate neighbors are existing production drafts with different generation provenance.",
            "Each pair sees only its two chapters; earlier context can require manual adjudication.",
            "One critic sample per pair; no automatic prose repairs or publication."
        ],
        "groups": [], "input_hashes": {}, "frozen_hashes": {},
    }
    # Snapshot all original experiment files, plus production textual artifacts.
    for p in TRIAL.rglob("*"):
        if p.is_file() and not p.is_relative_to(OUT):
            m["input_hashes"][str(p.relative_to(ROOT))] = sha(p)
    for b in SAMPLES:
        for base in (ROOT / "books" / b, ROOT / "work" / b):
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in {".md", ".txt", ".json", ".jsonl", ".html"}:
                    m["input_hashes"][str(p.relative_to(ROOT))] = sha(p)
    for rel in ["forage/coherence.py", "forage/coherence_filter.py", "prompts/critic_coherence.md"]:
        dest = OUT / "implementation" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    for b, sids in SAMPLES.items():
        original_plan = read(ROOT / "work" / b / "plan.json")
        ids = coherence._coherence_segment_ids(original_plan)
        segments = {s["id"]: s for s in original_plan["segments"]}
        for sid in sids:
            index = ids.index(sid)
            window = ids[max(0, index - 1):index + 2]
            assert len(window) == 3 and window[1] == sid
            group = {"book": b, "selected": sid, "title": segments[sid]["title"],
                     "path": f"{b}/{sid}", "window": window, "pairs": [], "origins": {}}
            folder = OUT / group["path"]
            for current in window:
                source = (TRIAL / b / current / "source.md" if current == sid else
                          ROOT / "work" / b / "chapters" / f"{current}.md")
                draft = (TRIAL / b / current / "draft.md" if current == sid else
                         ROOT / "work" / b / "segments" / f"{current}.md")
                assert source.read_text().strip() and draft.read_text().strip()
                if current == sid:
                    assert sha(draft) == sha(TRIAL / b / sid / "two_pass/revision.md")
                group["origins"][current] = {
                    "source": str(source.relative_to(ROOT)),
                    "draft": str(draft.relative_to(ROOT)),
                    "version": "two_pass_revision" if current == sid else "production_neighbor",
                }
                for kind, origin in [("chapters", source), ("segments", draft)]:
                    destination = folder / kind / f"{current}.md"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origin, destination)
            save(folder / "plan.json", {**original_plan, "segments": [segments[x] for x in window]})
            for a, bnext in zip(window, window[1:]):
                pair = f"{a}-{bnext}"
                rendered = prompt.render(
                    n=a, n_plus_1=bnext, cuts=None,
                    src_n=(folder / "chapters" / f"{a}.md").read_text(),
                    src_np1=(folder / "chapters" / f"{bnext}.md").read_text(),
                    draft_n=(folder / "segments" / f"{a}.md").read_text(),
                    draft_np1=(folder / "segments" / f"{bnext}.md").read_text(),
                )
                payload = {"model": MODEL.split(":", 1)[1],
                           "max_tokens": prompt.config["max_tokens"],
                           "messages": [{"role": "user", "content": rendered}],
                           "service_tier": "standard_only"}
                save(folder / "requests" / f"{pair}.json", payload)
                group["pairs"].append(pair)
            m["groups"].append(group)
    for p in OUT.rglob("*"):
        if p.is_file():
            m["frozen_hashes"][str(p.relative_to(OUT))] = sha(p)
    save(OUT / "manifest.json", m)
    print("Prepared 4 windows / 8 genuine adjacent pairs.", flush=True)


def verify(m):
    for root, key in [(ROOT, "input_hashes"), (OUT, "frozen_hashes")]:
        for name, digest in m[key].items():
            assert sha(root / name) == digest, f"Changed: {name}"


def preflight():
    m = read(OUT / "manifest.json")
    verify(m)
    counts = {}
    api = client()
    for group in m["groups"]:
        for pair in group["pairs"]:
            rel = f"{group['path']}/requests/{pair}.json"
            payload = read(OUT / rel)
            counts[rel] = api.messages.count_tokens(
                model=payload["model"], messages=payload["messages"]).input_tokens
    # Cache-write rate and 1024-token margin are conservative even with cache off.
    maximum = ((sum(counts.values()) + 8 * 1024) * 2.5 + 8 * m["max_output_tokens"] * 10) / 1e6
    assert maximum < m["cost_ceiling_usd"]
    m.update(status="ready", input_token_counts=counts, maximum_cost_usd=maximum)
    save(OUT / "manifest.json", m)
    print(json.dumps({"input_tokens": sum(counts.values()), "maximum_usd": maximum}), flush=True)


def recorded_complete(**kwargs):
    folder = kwargs["work_dir"]
    pair = kwargs["stage"].rsplit(":", 1)[1]
    request = folder / "requests" / f"{pair}.json"
    payload = read(request)
    assert kwargs["prompt"] == payload["messages"][0]["content"]
    assert kwargs["model"] == MODEL and kwargs["max_tokens"] == payload["max_tokens"]
    assert kwargs["cache"] is False
    started = folder / "responses" / f"{pair}.started.json"
    if started.exists():
        raise RuntimeError("Pair already attempted; no automatic retry")
    save(started, {"started_at": stamp(), "request_sha256": sha(request)})
    start = time.monotonic()
    try:
        with client().messages.stream(**payload) as stream:
            response = stream.get_final_message()
        usage = response.usage.model_dump(mode="json")
        text = "".join(block.text for block in response.content if block.type == "text")
        cost = (usage["input_tokens"] * 2 + usage["output_tokens"] * 10
                + (usage.get("cache_creation_input_tokens") or 0) * 2.5
                + (usage.get("cache_read_input_tokens") or 0) * .1) / 1e6
        result = LLMResponse(
            text, "anthropic:" + response.model, usage["input_tokens"], usage["output_tokens"],
            time.monotonic() - start, response.stop_reason,
            usage.get("cache_read_input_tokens"), usage.get("cache_creation_input_tokens"),
        )
        save(folder / "responses" / f"{pair}.json",
             {**asdict(result), "id": response.id, "usage": usage,
              "cost_usd": cost, "finished_at": stamp()})
        assert result.model == MODEL and result.is_complete
        print(f"{folder.relative_to(OUT)}/{pair}: complete, ${cost:.4f}", flush=True)
        return result
    except Exception as e:
        save(folder / "responses" / f"{pair}.error.json",
             {"type": type(e).__name__, "error": str(e), "at": stamp()})
        raise


def run():
    m = read(OUT / "manifest.json")
    verify(m)
    assert m["status"] == "ready" and m["maximum_cost_usd"] < m["cost_ceiling_usd"]
    if (OUT / "batch.started.json").exists():
        raise RuntimeError("Batch already attempted")
    save(OUT / "batch.started.json", {"at": stamp(), "maximum_calls": 8})
    reports = []
    with patch.object(coherence, "complete", recorded_complete):
        for group in m["groups"]:
            result = coherence.run_coherence(book_for(group))
            assert result["pairs_checked"] == 2
            assert not any("skipped" in row for row in result["per_pair"])
            reports.append({"group": group["path"], **result})
            print(group["path"], "raw findings:", result["findings_raw_total"], flush=True)
    verify(m)
    responses = [p for p in OUT.glob("*/*/responses/*.json")
                 if not p.name.endswith((".started.json", ".error.json"))]
    assert len(responses) == 8
    m.update(status="critic_complete_awaiting_review", finished_at=stamp(),
             completed_calls=len(responses),
             cost_usd=round(sum(read(p)["cost_usd"] for p in responses), 6),
             inputs_unchanged=True)
    save(OUT / "coherence_report.json", {"reports": reports})
    save(OUT / "manifest.json", m)
    print(json.dumps({k: m[k] for k in ["status", "completed_calls", "cost_usd"]}), flush=True)


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "preflight", "run"])
    args = parser.parse_args()
    globals()[args.action]()
