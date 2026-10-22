"""Bounded detailed review of the four existing two-pass revisions."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

OUT = Path(__file__).resolve().parent
TRIAL = OUT.parent
ROOT = TRIAL.parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from forage.artifacts import read_json as read, write_json as save
from forage.coherence import _coherence_segment_ids
from forage.json_parse import parse_llm_json

SAMPLES = {"education": ["007", "027"], "secret_adversary": ["003", "009"]}
MODEL = "claude-sonnet-5-5"
CAP = 16000
AXES = {"causality_and_setup", "referents_and_scene", "dialogue",
        "qualification_and_facts", "viewpoint_and_revelation",
        "voice_and_rhythm", "interpretive_structure", "planned_dependencies"}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s):
    return " ".join(s.split()).translate(str.maketrans(
        {"‘": "'", "’": "'", "“": '"', "”": '"'}))


def client():
    import anthropic
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    return anthropic.Anthropic(
        max_retries=0, timeout=600,
        default_headers={"anthropic-workspace-id": workspace} if workspace else {},
    )


def verify(m):
    for root, field in [(ROOT, "original_hashes"), (OUT, "input_hashes")]:
        for rel, digest in m[field].items():
            assert sha(root / rel) == digest, f"Changed input: {rel}"


def prepare():
    assert not (OUT / "manifest.json").exists(), "Already prepared"
    m = {
        "status": "prepared", "prepared_at": stamp(), "model": MODEL,
        "authorization": "User requested the more detailed coherence/fidelity check described in recommendation #4.",
        "maximum_calls": 4, "max_output_tokens": CAP, "retries": 0,
        "cost_ceiling_usd": 2, "expected_cost_usd": "under $1",
        "rates_per_million": {"input": 2, "output": 10, "cache_write": 2.5, "cache_read": .1},
        "pricing_source": "https://platform.claude.com/docs/en/models/sonnet-5-5/overview",
        "method": (
            "New broader editorial rubric, not the existing structural-only coherence "
            "or signature prompt. One source-aware Sonnet review per selected chapter, "
            "with complete source, first draft, revision, immediate-neighbor sources/drafts, "
            "and sources/current drafts for every located plan dependency. Existing critic "
            "findings and assistant editorial judgments are withheld from the model."
        ),
        "limitations": [
            "One model response per chapter; not blinded, statistically validated, or a whole-book audit.",
            "Existing production neighbors/partners have mixed model and revision provenance.",
            "Source evidence and quoted spans are mechanically checked; semantic judgments need review.",
            "No regeneration, repair, production replacement, or publication is part of this run."
        ],
        "chapters": [], "original_hashes": {}, "input_hashes": {},
    }
    for p in TRIAL.rglob("*"):
        if p.is_file() and not p.is_relative_to(OUT):
            m["original_hashes"][str(p.relative_to(ROOT))] = sha(p)
    for book, selected in SAMPLES.items():
        work = ROOT / "work" / book
        for base in (work, ROOT / "books" / book):
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in {".md", ".txt", ".json", ".jsonl", ".html"}:
                    m["original_hashes"][str(p.relative_to(ROOT))] = sha(p)
        original = read(work / "plan.json")
        segments = {s["id"]: s for s in original["segments"]}
        included = _coherence_segment_ids(original)
        for sid in selected:
            folder = OUT / book / sid
            plan = read(TRIAL / book / sid / "plan.json")
            position = included.index(sid)
            neighbors = included[max(0, position - 1):position] + included[position + 1:position + 2]
            docs, provenance = {}, {}

            def add(current, variant):
                key = f"{book}/{current}/{variant}"
                if key in docs:
                    return key
                if current in selected and variant in {"source", "initial", "revision"}:
                    name = "draft" if variant == "revision" else variant
                    path = TRIAL / book / current / f"{name}.md"
                else:
                    path = work / ("chapters" if variant == "source" else "segments") / f"{current}.md"
                text = path.read_text()
                paragraphs = [{"paragraph": i, "text": " ".join(p.split())}
                              for i, p in enumerate(re.split(r"\n\s*\n", text.strip()), 1) if p.strip()]
                docs[key] = {
                    "title": segments[current]["title"],
                    "version": variant, "words": len(text.split()),
                    "paragraphs": paragraphs,
                }
                provenance[key] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
                destination = folder / "documents" / f"{current}.{variant}.md"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(path.read_bytes())
                return key

            central = {v: add(sid, v) for v in ["source", "initial", "revision"]}
            context = []
            for n in neighbors:
                variant = "revision" if n in selected else "production"
                context.append({"id": n, "source": add(n, "source"), "draft": add(n, variant)})
            deps = []
            for index, dep in enumerate(plan["dependencies"]):
                candidates = [
                    s["id"] for s in original["segments"]
                    if (work / "chapters" / f"{s['id']}.md").exists()
                    and norm(dep["other_evidence"]) in norm((work / "chapters" / f"{s['id']}.md").read_text())
                ]
                title_matches = [x for x in candidates if norm(segments[x]["title"]) == norm(dep["other_chapter"])]
                matches = title_matches or candidates
                assert len(matches) == 1, (book, sid, index, matches)
                other = matches[0]
                variant = "revision" if other in selected else "production"
                partner = {
                    "id": other, "title": segments[other]["title"],
                    "included_in_current_reading_sequence": other in included,
                    "source": add(other, "source"),
                    "draft": add(other, variant),
                    "draft_provenance": "selected_revision" if other in selected else "existing_production",
                }
                deps.append({"index": index, **dep, "partner": partner})
            inputs = {
                "central_chapter": f"{book}/{sid}", "metadata": read(TRIAL / book / "metadata.json"),
                "target_words": plan["target_words"], "central_documents": central,
                "plan": plan, "immediate_neighbors": context, "dependencies": deps,
                "documents": docs,
            }
            save(folder / "inputs.json", inputs)
            save(folder / "provenance.json", provenance)
            payload = {
                "model": MODEL, "max_tokens": CAP, "service_tier": "standard_only",
                "system": (OUT / "critic.txt").read_text(),
                "messages": [{"role": "user", "content": json.dumps(inputs, ensure_ascii=False)}],
            }
            save(folder / "request.json", payload)
            m["chapters"].append(f"{book}/{sid}")
    for p in OUT.rglob("*"):
        if p.is_file():
            m["input_hashes"][str(p.relative_to(OUT))] = sha(p)
    save(OUT / "manifest.json", m)
    print("Prepared four complete source/initial/revision/context audits.", flush=True)


def preflight():
    m = read(OUT / "manifest.json")
    verify(m)
    counts = {}
    api = client()
    for key in m["chapters"]:
        payload = read(OUT / key / "request.json")
        counts[key] = api.messages.count_tokens(
            model=payload["model"], system=payload["system"],
            messages=payload["messages"]).input_tokens
    maximum = ((sum(counts.values()) + 4 * 1024) * 2.5 + 4 * CAP * 10) / 1e6
    assert maximum < m["cost_ceiling_usd"]
    m.update(status="ready", input_tokens=counts, maximum_cost_usd=maximum)
    save(OUT / "manifest.json", m)
    print(json.dumps({"input_tokens": counts, "maximum_cost_usd": maximum}), flush=True)


def validate(key, result):
    inputs = read(OUT / key / "inputs.json")
    docs = inputs["documents"]
    assert result["chapter"] == key
    assert result["verdict"] in {"needs_repair", "editorial_review", "no_material_findings"}
    assert len(result["coverage"]) == 8 and {x["axis"] for x in result["coverage"]} == AXES
    assert len(result["dependencies"]) == len(inputs["dependencies"])
    assert {x["index"] for x in result["dependencies"]} == set(range(len(inputs["dependencies"])))
    evidence_checks = []
    for section in ["findings", "dependencies"]:
        for row_index, row in enumerate(result[section]):
            if section == "findings":
                assert row["axis"] in AXES
                assert row["priority"] in {"must_fix", "should_improve", "tradeoff"}
                assert row["origin"] in {"first_draft", "revision", "first_draft_worsened_by_revision", "unclear"}
            for e in row["evidence"]:
                paragraphs = docs.get(e["document"], {}).get("paragraphs", [])
                matching = [p for p in paragraphs if p["paragraph"] == e["paragraph"]]
                exact = bool(matching and e["quote"] in matching[0]["text"])
                normalized = bool(matching and norm(e["quote"]) in norm(matching[0]["text"]))
                locations = [p["paragraph"] for p in paragraphs if norm(e["quote"]) in norm(p["text"])]
                evidence_checks.append({
                    "section": section, "index": row_index, **e,
                    "exact": exact, "normalized": normalized, "actual_paragraphs": locations,
                })
    return {
        "schema": "pass",
        "evidence_total": len(evidence_checks),
        "exact_quotes_at_cited_paragraph": sum(e["exact"] for e in evidence_checks),
        "normalized_quotes_at_cited_paragraph": sum(e["normalized"] for e in evidence_checks),
        "evidence_needing_review": [e for e in evidence_checks if not e["normalized"]],
        "evidence_checks": evidence_checks,
    }


def run():
    m = read(OUT / "manifest.json")
    verify(m)
    assert m["status"] == "ready"
    assert not (OUT / "batch.started.json").exists()
    save(OUT / "batch.started.json", {"at": stamp(), "maximum_calls": 4})
    errors, costs = [], []
    for key in m["chapters"]:
        folder = OUT / key
        save(folder / "started.json", {"at": stamp(), "request_sha256": sha(folder / "request.json")})
        start = time.monotonic()
        try:
            with client().messages.stream(**read(folder / "request.json")) as stream:
                response = stream.get_final_message()
            usage = response.usage.model_dump(mode="json")
            text = "".join(b.text for b in response.content if b.type == "text")
            cost = (usage["input_tokens"] * 2 + usage["output_tokens"] * 10
                    + (usage.get("cache_creation_input_tokens") or 0) * 2.5
                    + (usage.get("cache_read_input_tokens") or 0) * .1) / 1e6
            costs.append(cost)
            save(folder / "response.json", {
                "id": response.id, "model": response.model, "stop_reason": response.stop_reason,
                "text": text, "usage": usage, "cost_usd": cost,
                "duration_s": time.monotonic() - start, "finished_at": stamp(),
            })
            assert response.model == MODEL and response.stop_reason == "end_turn" and text.strip()
            result = parse_llm_json(text)
            save(folder / "critic.json", result)
            checks = validate(key, result)
            save(folder / "validation.json", checks)
            print(key, "findings", len(result["findings"]), "quote checks needing review",
                  len(checks["evidence_needing_review"]), "USD", round(cost, 4), flush=True)
        except Exception as e:
            error = {"chapter": key, "type": type(e).__name__, "error": str(e)}
            save(folder / "error.json", error)
            errors.append(error)
            print(key, "error", type(e).__name__, flush=True)
    verify(m)
    m.update(status="critic_complete_awaiting_review" if not errors else "partial_with_errors",
             completed_calls=len(costs), cost_usd=round(sum(costs), 6),
             errors=errors, finished_at=stamp(), original_inputs_unchanged=True)
    save(OUT / "manifest.json", m)
    print(json.dumps({k: m[k] for k in ["status", "completed_calls", "cost_usd", "errors"]}), flush=True)


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare", "preflight", "run"])
    globals()[p.parse_args().action]()
