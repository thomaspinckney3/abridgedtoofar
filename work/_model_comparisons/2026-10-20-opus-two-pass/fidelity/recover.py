"""Complete truncated audits with compact output and explicit medium effort.

Retains all central texts and all partner/neighbor drafts. Context-source
documents are excerpts around the cited dependency evidence. Original attempts
are preserved and charged to the same $2 total ceiling.
"""
import argparse
from copy import deepcopy
import json
import time
from run import OUT, ROOT, CAP, MODEL, client, load_dotenv, norm, read, save, sha, stamp, validate, verify


def budget():
    m = read(OUT / "manifest.json")
    total = 0
    for key in m["chapters"]:
        response = OUT / key / "response.json"
        total += (read(response)["cost_usd"] if response.exists() else
                  ((m["input_tokens"][key] + 1024) * 2 + CAP * 10) / 1e6)
    for p in OUT.glob("*/*/recovery/preflight.json"):
        response = p.parent / "response.json"
        total += read(response)["cost_usd"] if response.exists() else read(p)["maximum_cost_usd"]
    return total


def prepare(key):
    folder = OUT / key / "recovery"
    assert not folder.exists()
    assert read(OUT / key / "response.json")["stop_reason"] == "max_tokens"
    inp = deepcopy(read(OUT / key / "inputs.json"))
    central = inp["central_documents"]
    for doc_id, doc in inp["documents"].items():
        if doc["version"] != "source" or doc_id == central["source"]:
            continue
        needles = [norm(d["other_evidence"]) for d in inp["dependencies"]
                   if d["partner"]["source"] == doc_id]
        kept = [p for p in doc["paragraphs"] if any(q in norm(p["text"]) for q in needles)]
        doc["paragraphs"] = kept
        doc["excerpted"] = True
        doc["scope"] = "Only source paragraphs supporting supplied dependencies. Empty if none. Draft remains complete."
    inp["context_scope_note"] = (
        "Central source/initial/revision and ALL neighbor/partner drafts are complete. "
        "Other source chapters contain only cited dependency paragraphs; do not infer "
        "absence from these excerpts. No prior critic findings are supplied."
    )
    prompt = (OUT / "critic.txt").read_text() + """

OUTPUT BOUND FOR THIS AUDIT: use at most SIX distinct findings, ranked by
importance. Keep the entire JSON under 1800 words. Use 1-2 short quotations
per finding, 8-20 words each, and concise fields. Cover all eight axes and all
dependencies briefly. No need to quote every version: describe origin after
comparing them. Include central source and revision evidence for findings.
Where an earlier draft supports origin, add a brief third quote only if needed.
Do not repeat the same issue under different headings. Assess the entire
chapter, including its latter half. This is a fresh complete audit.
"""
    request = {"model": MODEL, "max_tokens": 8000, "service_tier": "standard_only",
               "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
               "system": prompt,
               "messages": [{"role": "user", "content": json.dumps(inp, ensure_ascii=False)}]}
    tokens = client().messages.count_tokens(
        **{k: request[k] for k in ["model", "system", "messages", "thinking"]}).input_tokens
    maximum = ((tokens + 1024) * 2 + 8000 * 10) / 1e6
    assert budget() + maximum <= 2, (budget(), maximum)
    save(folder / "inputs.json", inp)
    save(folder / "request.json", request)
    save(folder / "preflight.json", {"input_tokens": tokens, "maximum_cost_usd": maximum,
                                    "reason": "Original completed at output cap with incomplete JSON."})
    print(key, "recovery input", tokens, "reserved total USD", round(budget(), 6), flush=True)


def run(key):
    folder = OUT / key / "recovery"
    assert not (folder / "started.json").exists()
    assert budget() <= 2
    verify(read(OUT / "manifest.json"))
    save(folder / "started.json", {"at": stamp(), "request_sha256": sha(folder / "request.json")})
    start = time.monotonic()
    with client().messages.stream(**read(folder / "request.json")) as stream:
        response = stream.get_final_message()
    usage = response.usage.model_dump(mode="json")
    text = "".join(b.text for b in response.content if b.type == "text")
    cost = (usage["input_tokens"] * 2 + usage["output_tokens"] * 10
            + (usage.get("cache_creation_input_tokens") or 0) * 2.5
            + (usage.get("cache_read_input_tokens") or 0) * .1) / 1e6
    save(folder / "response.json", {
        "id": response.id, "model": response.model, "stop_reason": response.stop_reason,
        "text": text, "usage": usage, "cost_usd": cost,
        "duration_s": time.monotonic() - start, "finished_at": stamp(),
    })
    assert response.stop_reason == "end_turn" and response.model == MODEL
    result = json.loads(text)
    save(folder / "critic.json", result)
    checks = validate(key, result)  # Original full documents retain paragraph numbering.
    save(folder / "validation.json", checks)
    print(key, "recovery complete", len(result["findings"]), "findings;",
          len(checks["evidence_needing_review"]), "quote checks need review; USD", round(cost, 6), flush=True)


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare", "run"])
    p.add_argument("chapter")
    args = p.parse_args()
    globals()[args.action](args.chapter)
