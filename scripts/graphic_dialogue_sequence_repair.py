"""Repair existing multi-panel dialogue exchanges for setup/payoff coherence."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, write_json
from forage.json_parse import parse_llm_json
from forage.llm import complete
from forage.prompts import load_prompt
from scripts.graphic_dialogue_draft import _clean_texts, _parse_mapping


def _chapter_sources(paths: dict[int, Path]) -> list[dict[str, Any]]:
    return [
        {
            "chapter_number": chapter,
            "path": str(paths[chapter]),
            "text": paths[chapter].read_text(encoding="utf-8"),
        }
        for chapter in sorted(paths)
    ]


def _collect_sequences(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for page in storyboard.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            sequence_id = str(panel.get("source_expanded_sequence") or "").strip()
            if not sequence_id:
                continue
            group = grouped.setdefault(
                sequence_id,
                {
                    "source_expanded_sequence": sequence_id,
                    "source_chapter": panel.get("source_chapter"),
                    "panels": [],
                },
            )
            group["panels"].append({
                "page_number": page_no,
                "panel_number": int(panel.get("panel_number") or 0),
                "image": panel.get("image"),
                "texts": panel.get("texts") or [],
            })
    return list(grouped.values())


def _merge_updates(original: dict[str, Any], repaired: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(original)
    panel_index: dict[tuple[int, int], dict[str, Any]] = {}
    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if isinstance(panel, dict):
                panel_index[(page_no, int(panel.get("panel_number") or 0))] = panel

    updates: list[dict[str, Any]] = []
    for sequence in repaired.get("sequences", []) or []:
        if not isinstance(sequence, dict):
            continue
        for page in sequence.get("pages", []) or []:
            if not isinstance(page, dict):
                continue
            page_no = int(page.get("page_number") or 0)
            for panel_update in page.get("panels", []) or []:
                if not isinstance(panel_update, dict):
                    continue
                panel_no = int(panel_update.get("panel_number") or 0)
                panel = panel_index.get((page_no, panel_no))
                if panel is None:
                    raise ValueError(f"unknown panel update: page {page_no} panel {panel_no}")
                if not panel.get("source_expanded_sequence"):
                    raise ValueError(f"refusing to update non-expanded panel: page {page_no} panel {panel_no}")
                texts = _clean_texts(
                    panel_update.get("texts"),
                    page_number=page_no,
                    panel_number=panel_no,
                )
                panel["texts"] = texts
                updates.append({"page_number": page_no, "panel_number": panel_no})
    return data, {"updates": updates, "notes": repaired.get("notes") or []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--storyboard-json", type=Path, required=True)
    parser.add_argument("--chapter-source", action="append", default=[], metavar="N=PATH")
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--max-output-tokens", type=int)
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    sequences = _collect_sequences(storyboard)
    if not sequences:
        write_json(args.out_json, storyboard)
        return 0
    chapter_paths = _parse_mapping(args.chapter_source, label="--chapter-source")
    book = load_book(args.book_id)
    prompt = load_prompt("graphic_dialogue_sequence_repair")
    model = args.model or prompt.config.get("model", "openai:gpt-5")
    max_tokens = args.max_output_tokens or int(prompt.config.get("max_tokens", 8000))
    rendered = prompt.render(
        title=book.metadata.get("title", args.book_id),
        author=book.metadata.get("author", ""),
        chapter_sources_json=json.dumps(_chapter_sources(chapter_paths), indent=2, ensure_ascii=False),
        sequences_json=json.dumps(sequences, indent=2, ensure_ascii=False),
    )
    prompt_path = args.run_dir / "dialogue_sequence_repair_prompt.md"
    prompt_path.write_text(rendered, encoding="utf-8")
    resp = complete(
        prompt=rendered,
        model=model,
        system=prompt.system,
        max_tokens=max_tokens,
        work_dir=book.work_dir,
        stage=f"graphic_dialogue_sequence_repair:{args.book_id}:{args.run_dir.name}",
    )
    raw_path = args.run_dir / "dialogue_sequence_repair_raw_response.txt"
    raw_path.write_text(resp.text, encoding="utf-8")
    repaired = parse_llm_json(resp.text)
    data, report = _merge_updates(storyboard, repaired)
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "output_storyboard": str(args.out_json),
        "prompt": str(prompt_path),
        "raw_response": str(raw_path),
        "model": resp.model,
        "stop_reason": resp.stop_reason,
    })
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
