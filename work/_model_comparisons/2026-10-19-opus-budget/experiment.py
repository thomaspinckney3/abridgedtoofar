"""One approved, isolated Opus Gatsby II revision experiment. No publication."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = OUT.parent / "2026-10-19"
GPT = OUT.parent / "2026-10-19-gpt"
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from forage.drafter import _extract_chapter_notes


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def normalize(text):
    return " ".join(text.translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'})).split())


def prepare():
    if (OUT / "manifest.json").exists():
        raise SystemExit("Already frozen; refusing to overwrite inputs.")
    copies = {
        "source.md": OLD / "gatsby/baseline/chapters/002.md",
        "existing.md": OLD / "gatsby/baseline/segments/002.md",
        "opus_before.md": OLD / "gatsby/opus55/segments/002.md",
        "sonnet.md": OLD / "gatsby/sonnet55/segments/002.md",
        "astra.md": GPT / "gatsby/astra/segments/002.md",
        "sol.md": GPT / "gatsby/sol61/segments/002.md",
    }
    (OUT / "inputs").mkdir(parents=True)
    for name, path in copies.items():
        shutil.copy2(path, OUT / "inputs" / name)
    source = (OUT / "inputs/source.md").read_text()
    paragraphs = re.split(r"\n\s*\n", source.strip())

    def span(pid, start=None, end=None):
        text = " ".join(paragraphs[pid - 1].split())
        if start:
            text = text[text.index(start):]
        if end:
            text = text[:text.index(end) + len(end)]
        return text

    protected = [
        ("V1", "Ashes as a grotesque landscape", 1, span(1, "This is a valley", "powdery air.")),
        ("V2", "Nick’s speculative, comic account of the oculist", 2, span(2, "Evidently", "moved away.")),
        ("V3", "Nick’s pastoral Fifth Avenue detour", 44, span(44)),
        ("V4", "Drunken retrospective framing", 52, span(52, end="cheerful sun.")),
        ("V5", "Myrtle’s expanding social performance", 56, span(56, "Her laughter", "smoky air.")),
        ("V6", "Nick within and without", 119, span(119, "I wanted to get out")),
        ("V7", "Myrtle narrates meeting Tom in her own voice", 121, span(121)),
        ("V8", "Abrupt, unembellished violence", 127, span(127)),
        ("V9", "Elliptical bedroom and station ending", 135, "\n\n".join(span(n) for n in [135, 136, 137])),
    ]
    protected = [{"id": key, "purpose": reason, "source_paragraph": pid,
                  "text": text, "words": len(text.split())} for key, reason, pid, text in protected]
    plan = {
        "created_before_revision": True,
        "author": "Coding assistant, using the source and earlier comparison findings; no paid planning call.",
        "target_words": 2300, "target_range_words": [2185, 2415], "ceiling_words": 2760,
        "counting": "Whitespace word count of prose; reviewer comment excluded, optional chapter title included.",
        "verbatim": protected,
        "protected_words": sum(x["words"] for x in protected),
        "essential": [
            "Ash valley and disembodied Eckleburg eyes, including their physical appearance and brooding effect; the V2 sentence is protected, not the entire eyes paragraph.",
            "Tom forces Nick off the train; introduce George Wilson and Myrtle, their marriage and garage, Tom’s dominance (including the car-sale threat), and Myrtle’s vitality against Wilson’s ash-grey passivity.",
            "Myrtle arranges to meet Tom, uses visiting her sister as cover, and rides in another railway car to conceal the affair.",
            "Dog purchase and Tom’s coarse assertion about its sex; Nick attempts to leave and is pressed into visiting the apartment.",
            "Crowded pretentious apartment, whisky, arrival of Myrtle’s sister and the photographer couple; Myrtle changes clothes and manner.",
            "Keep one brief Gatsby rumor exchange identifying Gatsby as Nick’s neighbor. Other party chatter can be cut.",
            "Myrtle’s contempt for Wilson and class aspirations, with a compact source-backed account of the borrowed wedding suit.",
            "Retain a short part of Myrtle’s later dress/shopping speech as direct dialogue: enough address/repetition/list-making to enact her affected importance, not merely report what she buys. The full shopping list is not mandatory.",
            "Daisy-name dispute motivates Tom’s blow; preserve Myrtle’s defiance in direct speech, then V8, pain and aftermath, Nick leaving with the photographer, and the unexpanded elliptical ending V9.",
            "Speakers and surviving names remain identifiable. Either retain Catherine/McKee introductions or consistently use roles; do not leave an isolated Chester/Lucille reference.",
            "If the lather-wiping callback survives, retain the initial lather detail; if the Gasoline Pump joke survives, retain the photographer’s request for work that prompts it. Either complete unit may be omitted.",
            "Source overrides errors in the first draft: the source excludes Catherine from those drinking whisky. Preserve that exception or remove the universal ‘all present’ claim."
        ],
        "optional": [
            "Repeated approach/railway/garage description beyond the scene’s essential geography and dominant images; subsidiary shops, Nick’s fantasy about apartments over the garage.",
            "Italian child’s torpedoes, repeated travel logistics, clothing/purchase/taxi details, and most dog bargaining. Keep the dog and Tom’s coarse exchange.",
            "Apartment floor plan, secondary furnishings, magazine/book inventory, dog-biscuit/elevator-boy logistics; retain one coherent piece of apartment satire rather than every detail.",
            "Extended minor-character descriptions, photography/light/pose discussion, the Gasoline Pump exchange as a complete unit, and Mrs. McKee’s marriage anecdote.",
            "Catherine’s Catholic lie and Monte Carlo/Europe/West discussion are optional complete units. If the Catholic lie is cut, also cut Nick’s otherwise unmotivated rebuttal; do not preserve it merely because the previous draft did.",
            "Repeated party exchanges and extended shopping list items, repeated drunken crowd movements and articles of aid, provided transitions and the protected ending remain intelligible."
        ],
        "suggested_scene_allocations": [
            {"scene": "Ashes, eyes, and train halt", "words": 200},
            {"scene": "Garage meeting and concealed departure", "words": 390},
            {"scene": "New York, dog, Fifth Avenue and arrival", "words": 240},
            {"scene": "Apartment, company, and Myrtle’s transformation", "words": 330},
            {"scene": "Party gossip and Myrtle’s marriage", "words": 350},
            {"scene": "Within-and-without and meeting Tom", "words": 330},
            {"scene": "Shopping speech and drunken transition", "words": 140},
            {"scene": "Violence, aftermath, elevator and elliptical ending", "words": 320},
        ],
        "acceptance": [
            "A complete chapter ending, not a token-truncated response.",
            "All nine protected spans present, allowing only whitespace and straight/curly quotation-mark normalization.",
            "Report target-range compliance and ceiling compliance separately. Under-ceiling alone is not target compliance.",
            "No new causal/attribution gaps or unsupported facts in manual source-aware review.",
            "Compare source wording, retained unprotected style, dialogue performance, and continuity; do not turn overlap into a quality score."
        ],
        "limits": [
            "One chapter and one revision sample, with an assistant-authored plan informed by prior outputs.",
            "Tests a combined editorial workflow, not a one-variable prompt ablation or an autonomous planning stage.",
            "Revises an existing Opus draft; the old GPT and Anthropic samples were first drafts.",
            "The protected excerpts influence wording-overlap measurements; also measure overlap excluding their five-word sequences."
        ]
    }
    assert sum(s["words"] for s in plan["suggested_scene_allocations"]) == 2300
    assert all(normalize(v["text"]) in normalize(source) for v in protected)
    save(OUT / "preservation_plan.json", plan)
    original = (OUT / "inputs/opus_before.md").read_text()
    assert len(original.split()) == 3187
    system = read(OLD / "requests/gatsby-002-opus55-medium.json")["system"]
    intro = """# Operative specification for this editorial experiment

Revise the existing abridgment of The Great Gatsby, Chapter II, by F. Scott Fitzgerald.
The complete source is authoritative for facts and wording. The existing draft is an input to edit, not a preservation mandate.
This operational specification replaces the earlier broad design spec for this experiment.

The existing prose is exactly 3,187 whitespace-separated words. Target 2,300 words: remove approximately 887 net words (27.8% of the draft).
Aim for 2,185–2,415 words (within 5% of target). The absolute acceptance ceiling is 2,760 words; this ceiling is NOT the target.
Reviewer-note words do not count. The allocations below sum to 2,300 and may trade words between scenes; the total target still applies.

Use the three preservation tiers below. Only the listed VERBATIM spans are mandatory as exact text; a whole chapter, scene, or surrounding paragraph is not thereby protected.
ESSENTIAL material must retain its function and causal connections but can be shortened. OPTIONAL material is available for removal before shortening protected material.
Preserve the style of retained material by cutting whole optional sentences, exchanges, and examples first. Retain characteristic sentence rhythms, qualifications, images, period vocabulary, punctuation, and source-backed dialogue.
Do not turn all distinctive dialogue into narrated summary. Avoid replacing a coherent image with fragments of many images. Use minimal source-backed bridges where cuts require them.
Keep the source order, first-person voice, standard dialogue paragraphs and clear attribution. Do not invent speech, psychology, causal explanations, or an explanation of the ambiguous ending.
Straight versus curly quotation marks and whitespace may differ in protected spans; their words and other punctuation must survive. Titles are optional.

Do not silently exceed the ceiling or drop required material to conceal a conflict. If the contract cannot fit, return a complete best effort and explicitly state INFEASIBLE in the reviewer note with the specific conflicting requirements. Do not truncate the ending.
Do not claim an exact word count unless you have measured it with a tool; no counting tool is provided in this call. We will count the returned prose mechanically.

# Frozen preservation plan
"""
    body = intro + json.dumps(plan, indent=2, ensure_ascii=False)
    body += "\n\n# Complete original chapter\n\n" + source
    body += "\n\n# Existing Opus draft to revise — 3,187 words\n\n" + original
    body += """\n\n# Output contract
Return only the complete revised chapter and exactly one final comment in the format below.
The acceptable_changes list must identify the actual cuts or compressions, so the revision is inspectable. Risks must state any unmet requirement or infeasibility; do not hide an overrun behind a general appeal to signature density.
<!-- FORAGE_CHAPTER_NOTES
{
  "summary": "Brief editorial description of the revision.",
  "acceptable_changes": ["Concrete cut or compression and its reason."],
  "risks": ["Specific remaining concern, or an explicit infeasibility explanation."],
  "review_focus": ["A specific passage or transition to inspect."]
}
-->
"""
    payload = {"model": "claude-opus-5-5", "system": system,
               "messages": [{"role": "user", "content": body}],
               "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
               "max_tokens": 32000, "service_tier": "standard_only"}
    save(OUT / "request.json", payload)
    (OUT / "request.txt").write_text(body)
    manifest = {
        "status": "prepared", "prepared_at": stamp(),
        "authorization": "User explicitly approved this proposed Gatsby II experiment in the current conversation.",
        "maximum_generation_calls": 1, "retries": 0,
        "model": "claude-opus-5-5", "effort": "medium", "max_output_tokens": 32000,
        "rates_usd_per_million": {"input": 4, "output": 20, "cache_write_5m": 5, "cache_read": .2},
        "pricing_source": "https://platform.claude.com/docs/en/models/opus-5-5/overview",
        "expected_cost_usd": [.15, .40], "experiment_cost_ceiling_usd": .85,
        "scope": "Single isolated editorial revision with a bounded preservation plan; not a production pipeline change or publication.",
        "limitations": plan["limits"],
        "live_hashes": read(OLD / "manifest.json")["live_hashes"],
        "original_input_hashes": {str(path): sha(path) for path in copies.values()},
        "frozen_hashes": {str(path.relative_to(OUT)): sha(path) for path in
                           [*list((OUT / "inputs").glob("*.md")), OUT / "preservation_plan.json", OUT / "request.json", OUT / "request.txt"]}
    }
    verify(manifest)
    save(OUT / "manifest.json", manifest)
    print("Frozen protected words:", plan["protected_words"], "; prompt words:", len(body.split()))


def verify(manifest):
    for mapping, root in [(manifest["live_hashes"], ROOT),
                          (manifest["frozen_hashes"], OUT),
                          (manifest["original_input_hashes"], Path("/"))]:
        for path, digest in mapping.items():
            assert sha(root / path) == digest, f"Artifact changed: {path}"


def client():
    import anthropic
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    return anthropic.Anthropic(max_retries=0, timeout=600,
        default_headers={"anthropic-workspace-id": workspace} if workspace else {})


def count():
    manifest = read(OUT / "manifest.json")
    verify(manifest)
    request = read(OUT / "request.json")
    result = client().messages.count_tokens(**{key: request[key] for key in ["model", "system", "messages", "thinking"]})
    manifest["counted_input_tokens"] = result.input_tokens
    # Reserve 1,024 extra input tokens, priced conservatively as cache writes.
    manifest["maximum_cost_usd"] = round(((result.input_tokens + 1024) * 5 + 32000 * 20) / 1e6, 6)
    assert manifest["maximum_cost_usd"] <= manifest["experiment_cost_ceiling_usd"]
    save(OUT / "manifest.json", manifest)
    print("Input tokens", result.input_tokens, "; maximum cost USD", manifest["maximum_cost_usd"])


def run(approved):
    if not approved:
        raise SystemExit("Only run after explicit approval of this experiment.")
    manifest = read(OUT / "manifest.json")
    verify(manifest)
    assert manifest["maximum_cost_usd"] <= manifest["experiment_cost_ceiling_usd"]
    if (OUT / "started.json").exists():
        raise SystemExit("Already attempted; no automatic repeat of an ambiguous or completed request.")
    save(OUT / "started.json", {"started_at": stamp(), "request_sha256": sha(OUT / "request.json")})
    manifest["status"] = "running"
    save(OUT / "manifest.json", manifest)
    start = time.monotonic()
    result = {"status": "failed", "cost_usd": None}
    try:
        with client().messages.stream(**read(OUT / "request.json")) as stream:
            response = stream.get_final_message()
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage.model_dump(mode="json")
        save(OUT / "response.json", {"id": response.id, "model": response.model,
              "stop_reason": response.stop_reason, "usage": usage, "text": text})
        cost = (usage["input_tokens"] * 4 + usage["output_tokens"] * 20 +
                (usage.get("cache_creation_input_tokens") or 0) * 5 +
                (usage.get("cache_read_input_tokens") or 0) * .2) / 1e6
        result.update({"cost_usd": round(cost, 6), "usage": usage, "model": response.model,
                       "stop_reason": response.stop_reason})
        assert response.model == manifest["model"]
        assert response.stop_reason == "end_turn", "Incomplete provider response; retained for inspection."
        prose, notes = _extract_chapter_notes(text)
        assert prose.strip() and notes
        (OUT / "revision.md").write_text(prose.strip() + "\n")
        save(OUT / "revision.notes.json", notes)
        plan = read(OUT / "preservation_plan.json")
        n = len(prose.split())
        checks = {"words": n, "target_words": 2300, "target_delta_percent": round(100 * (n / 2300 - 1), 2),
                  "within_target_range": 2185 <= n <= 2415, "under_ceiling": n <= 2760,
                  "protected": [{"id": v["id"], "present": normalize(v["text"]) in normalize(prose)} for v in plan["verbatim"]],
                  "reported_infeasible": "INFEASIBLE" in json.dumps(notes),
                  "manual_review": "pending"}
        save(OUT / "checks.json", checks)
        result["status"] = "complete"
        result["words"] = n
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result["duration_s"] = round(time.monotonic() - start, 2)
    manifest["result"] = result
    manifest["status"] = "generated_awaiting_assessment" if result["status"] == "complete" else "failed_no_retry"
    manifest["finished_at"] = stamp()
    verify(manifest)
    save(OUT / "manifest.json", manifest)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    load_dotenv(ROOT / ".env", override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "count", "run", "verify"])
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare": prepare()
    elif args.action == "count": count()
    elif args.action == "verify":
        verify(read(OUT / "manifest.json"))
        print("Frozen inputs, original comparators, and live book hashes verified.")
    else: run(args.approved)
