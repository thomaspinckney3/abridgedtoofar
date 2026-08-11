"""Compress spoken lines that cannot be lettered, keeping the plot action.

This is the last resort in the fitting chain, and the only paid one. A line
reaches it having already failed the two lossless options: it does not fit one
balloon, and `graphic_balloon_split` could not break it across two without a
piece still overflowing.

Compression is lossy by definition, so what survives has to be chosen rather
than trimmed. A graphic novel moves on action — the art already carries setting,
weather, and faces — so the rule is to keep what the character *does* by
speaking (decide, demand, reveal, refuse) and drop what the page is showing
anyway. That judgement is the prompt's job; this module's job is to make sure
the model's answer is safe to put in a character's mouth.

Every returned line is checked before it is accepted:

- it fits the balloon;
- it introduces no name the original line did not have;
- it is not empty, and not just a fragment of the original.

Anything failing those checks is rejected and the original line is left alone,
so a bad response degrades to the pre-existing behaviour rather than quietly
putting invented words on the page.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import load_book, write_json
from forage.json_parse import parse_llm_json
from forage.llm import complete
from forage.prompts import load_prompt

from scripts.apply_graphic_lettering_policy import MAX_BALLOON_CHARS
from scripts.graphic_balloon_split import split_balloon_text

PROMPT_NAME = "graphic_balloon_summarize"

# Ordinary words whose capitalization only ever means "start of a sentence".
_COMMON_OPENERS = frozenset("""
the a an and or but if so it he she they we i you me him her them us my your his
this that these those there here what when where who how why yes no not never
of to in on at for with from by as is was were be been am are do did does done
have has had will would can could should may might must let don't didn't it's
well now then just only very much more most every all some any one two
""".split())


def _normalize(text: Any) -> str:
    return " ".join(str(text or "").split())


def _all_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _capitalized_words(text: str) -> set[str]:
    """Capitalized words that are not ordinary sentence-openers.

    Deliberately not a name detector. Whether a capitalized word *is* a name is
    ambiguous — "Terrible" opening a sentence is not, "Gatsby" opening one is —
    and guessing wrong either waves through an invented character or blocks a
    valid compression. Asking instead whether the word is new vocabulary avoids
    the judgement: a name carried over from the original appears in it, and one
    the model made up does not.
    """
    # Match only the leading letter run, so a contraction reduces the same way
    # `_all_words` reduces it: "I'm" yields nothing rather than an "i'm" token
    # that could never match the original's "i" and "m".
    return {
        word.lower() for word in re.findall(r"\b([A-Z][a-z]+)", text)
        if word.lower() not in _COMMON_OPENERS
    }


def collect_oversized(
    storyboard: dict[str, Any], *, limit: int = MAX_BALLOON_CHARS
) -> list[dict[str, Any]]:
    """Balloons that neither fit nor split, in stable page/panel order."""
    found: list[dict[str, Any]] = []
    for page in storyboard.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels") or []:
            if not isinstance(panel, dict):
                continue
            panel_no = int(panel.get("panel_number") or 0)
            for order, item in enumerate(panel.get("texts") or []):
                if not isinstance(item, dict):
                    continue
                if str(item.get("kind") or "").strip().lower() not in {"speech", "thought"}:
                    continue
                text = _normalize(item.get("text"))
                if len(text) <= limit:
                    continue
                if split_balloon_text(text, limit=limit) is not None:
                    continue
                found.append({
                    "id": f"p{page_no}.panel{panel_no}.text{order}",
                    "page_number": page_no,
                    "panel_number": panel_no,
                    "text_index": order,
                    "speaker": str(item.get("speaker") or ""),
                    "kind": str(item.get("kind") or "speech"),
                    "text": text,
                    "source_evidence": str(item.get("source_evidence") or ""),
                })
    return found


def validate_compression(
    original: str, compressed: str, *, limit: int = MAX_BALLOON_CHARS
) -> str | None:
    """Return the reason `compressed` is unusable, or None when it is fine."""
    candidate = _normalize(compressed)
    if not candidate:
        return "empty"
    if len(candidate) > limit:
        return f"still {len(candidate)} chars, over the {limit} limit"
    invented = _capitalized_words(candidate) - _all_words(original)
    if invented:
        return f"introduces names absent from the line: {sorted(invented)}"
    if candidate.lower() == _normalize(original).lower():
        return "unchanged"
    return None


def apply_compressions(
    storyboard: dict[str, Any],
    targets: list[dict[str, Any]],
    responses: dict[str, dict[str, Any]],
    *,
    limit: int = MAX_BALLOON_CHARS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply accepted compressions; leave rejected lines untouched."""
    data = deepcopy(storyboard)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    by_location = {
        (target["page_number"], target["panel_number"], target["text_index"]): target
        for target in targets
    }
    for page in data.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels") or []:
            if not isinstance(panel, dict):
                continue
            panel_no = int(panel.get("panel_number") or 0)
            for order, item in enumerate(panel.get("texts") or []):
                target = by_location.get((page_no, panel_no, order))
                if not target:
                    continue
                answer = responses.get(target["id"])
                if not isinstance(answer, dict):
                    rejected.append({**target, "reason": "no response for this line"})
                    continue
                compressed = _normalize(answer.get("text"))
                reason = validate_compression(target["text"], compressed, limit=limit)
                if reason:
                    rejected.append({**target, "reason": reason, "returned": compressed})
                    continue
                kind = str(answer.get("kind") or "speech").strip().lower()
                if kind not in {"speech", "thought", "caption"}:
                    kind = "speech"
                item["text"] = compressed
                # The uncompressed line is kept so the loss stays auditable.
                item["summarized_from"] = target["text"]
                if answer.get("dropped"):
                    item["lettering_notes"] = str(answer["dropped"])
                if kind == "caption":
                    item["kind"] = "caption"
                    item.pop("speaker", None)
                    item.pop("balloon_zone", None)
                    item.setdefault("caption_zone", "top_left")
                applied.append({**target, "compressed": compressed, "kind": kind})
    return data, {"applied": applied, "rejected": rejected}


def _responses_by_id(payload: Any) -> dict[str, dict[str, Any]]:
    lines = payload.get("lines") if isinstance(payload, dict) else None
    if not isinstance(lines, list):
        return {}
    return {
        str(entry.get("id")): entry
        for entry in lines
        if isinstance(entry, dict) and entry.get("id")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--storyboard-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--max-chars", type=int, default=MAX_BALLOON_CHARS)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the lines that would be sent and exit without calling the model.",
    )
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    targets = collect_oversized(storyboard, limit=args.max_chars)
    if not targets or args.dry_run:
        report = {
            "source_storyboard": str(args.storyboard_json),
            "candidates": targets,
            "called_model": False,
        }
        if not args.dry_run:
            write_json(args.out_json, storyboard)
            report["output_storyboard"] = str(args.out_json)
        if args.out_report:
            write_json(args.out_report, report)
        print(json.dumps(report, indent=2))
        return 0

    book = load_book(args.book_id)
    prompt = load_prompt(PROMPT_NAME)
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_tokens = args.max_output_tokens or int(prompt.config.get("max_tokens", 4000))
    rendered = prompt.render(
        title=book.metadata.get("title", args.book_id),
        author=book.metadata.get("author", ""),
        max_chars=args.max_chars,
        lines_json=json.dumps(
            [
                {k: t[k] for k in ("id", "speaker", "text", "source_evidence")}
                for t in targets
            ],
            indent=2,
            ensure_ascii=False,
        ),
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = args.run_dir / "balloon_summarize_prompt.md"
    prompt_path.write_text(rendered, encoding="utf-8")

    resp = complete(
        prompt=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_tokens,
        work_dir=book.work_dir,
        stage=f"graphic_balloon_summarize:{args.book_id}:{args.run_dir.name}",
    )
    raw_path = args.run_dir / "balloon_summarize_raw_response.txt"
    raw_path.write_text(resp.text, encoding="utf-8")

    data, report = apply_compressions(
        storyboard, targets, _responses_by_id(parse_llm_json(resp.text)),
        limit=args.max_chars,
    )
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "output_storyboard": str(args.out_json),
        "prompt": str(prompt_path),
        "raw_response": str(raw_path),
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "called_model": True,
    })
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
