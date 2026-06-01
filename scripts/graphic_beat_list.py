"""Generate a source-grounded graphic-novel beat inventory.

This stage sits before graphic plot pacing, storyboard, art, and lettering. It
extracts the story operations in a chapter without choosing page layouts.

Example:
  python -m scripts.graphic_beat_list gatsby --assembled-chapter-number 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from forage.artifacts import load_book, write_json
from forage.json_parse import parse_llm_json
from forage.prompts import load_prompt

from scripts.graphic_novel_experiment import (
    _complete_json_with_retry,
    _excerpt_units,
    _published_abridgment_path,
)


BEAT_TYPES = {
    "orientation",
    "entrance",
    "relationship",
    "action",
    "dialogue_exchange",
    "revelation",
    "decision",
    "reaction",
    "transition",
    "setup",
    "payoff",
}

IMPORTANCE_VALUES = {"high", "medium", "low"}
TREATMENTS = {
    "beat",
    "supporting_context",
    "merged_into_adjacent_beat",
    "omit",
}
NON_VISIBLE_ACTOR_RE = re.compile(
    r"\b(?:"
    r"unseen|off[- ]?panel|offscreen|caller|voice|telephone|phone|bell|"
    r"doorbell|sound|noise|weather|storm|rain|wind|train|car|ship|boat|"
    r"building|house|room|road|map|diagram|letter|message|object"
    r")\b",
    re.IGNORECASE,
)


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _chapter_heading(chapter: dict[str, Any]) -> str:
    for key in ("raw_heading", "title", "id"):
        value = str(chapter.get(key) or "").strip()
        if value:
            return value
    return str(chapter.get("number") or "").strip()


def _assembled_chapter_excerpt(book: Any, chapter_number: str) -> tuple[str, Path, int, int]:
    path = _published_abridgment_path(book.book_id)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    chapters_path = book.work_dir / "chapters.json"
    metadata = json.loads(chapters_path.read_text(encoding="utf-8"))
    chapters = [
        chapter for chapter in metadata.get("chapters", [])
        if isinstance(chapter, dict) and chapter.get("kind") == "chapter"
    ]
    selected_index = None
    for index, chapter in enumerate(chapters):
        chapter_number_s = str(chapter_number)
        chapter_id_s = str(chapter.get("id") or "")
        if (
            str(chapter.get("number")) == chapter_number_s
            or chapter_id_s.lstrip("0") == chapter_number_s
            or str(index + 1) == chapter_number_s
        ):
            selected_index = index
            break
    if selected_index is None:
        raise ValueError(f"chapter {chapter_number} not found in {chapters_path}")

    selected_heading = _normalize_heading(_chapter_heading(chapters[selected_index]))
    following_headings = {
        _normalize_heading(_chapter_heading(chapter))
        for chapter in chapters[selected_index + 1:]
    }

    start_line = None
    for index, line in enumerate(lines):
        if _normalize_heading(line) == selected_heading:
            start_line = index
            break
    if start_line is None:
        raise ValueError(
            f"heading {_chapter_heading(chapters[selected_index])!r} not found in {path}"
        )

    end_line = len(lines)
    for index in range(start_line + 1, len(lines)):
        if _normalize_heading(lines[index]) in following_headings:
            end_line = index
            break

    prefix_words = sum(len(line.split()) for line in lines[: start_line + 1])
    excerpt = "\n".join(lines[start_line + 1:end_line]).strip()
    if not excerpt:
        raise ValueError(f"assembled chapter {chapter_number} is empty in {path}")
    start_word = prefix_words + 1
    end_word = start_word + len(excerpt.split()) - 1
    return excerpt, path, start_word, end_word


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _validate_beat_list(
    data: dict[str, Any],
    source_units: list[dict[str, Any]],
) -> dict[str, Any]:
    report: dict[str, Any] = {"warnings": [], "normalizations": []}
    if str(data.get("beat_contract_version")).strip() != "2":
        raise ValueError("beat list must declare beat_contract_version: 2")

    expected_ids = [int(unit["id"]) for unit in source_units]
    known_source_ids = set(expected_ids)

    treatments = data.get("source_unit_treatments")
    if not isinstance(treatments, list):
        raise ValueError("source_unit_treatments must be an array")
    treatment_ids: list[int] = []
    for item in treatments:
        if not isinstance(item, dict):
            raise ValueError("each source_unit_treatment must be an object")
        try:
            source_id = int(item.get("source_unit_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("source_unit_treatment missing numeric source_unit_id") from exc
        treatment = str(item.get("treatment") or "").strip()
        if treatment not in TREATMENTS:
            raise ValueError(
                f"source unit {source_id} has invalid treatment {treatment!r}"
            )
        treatment_ids.append(source_id)
        item["beat_ids"] = _string_items(item.get("beat_ids"))
    if treatment_ids != expected_ids:
        raise ValueError(
            "source_unit_treatments must cover source units exactly in order: "
            f"expected {expected_ids}, got {treatment_ids}"
        )

    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError("beats must be a non-empty array")

    beat_ids: list[str] = []
    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError("each beat must be an object")
        beat_id = str(beat.get("beat_id") or "").strip()
        if not beat_id:
            raise ValueError("each beat must have a beat_id")
        if beat_id in beat_ids:
            raise ValueError(f"duplicate beat_id {beat_id!r}")
        beat_ids.append(beat_id)
    known_beat_ids = set(beat_ids)
    canonical_beat_id = {beat_id.lower(): beat_id for beat_id in beat_ids}
    beat_source_index: dict[int, list[str]] = {}
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        raw_source_ids = beat.get("source_unit_ids")
        if not isinstance(raw_source_ids, list):
            continue
        for raw_source_id in raw_source_ids:
            try:
                source_id = int(raw_source_id)
            except (TypeError, ValueError):
                continue
            beat_source_index.setdefault(source_id, []).append(beat_id)

    for item in treatments:
        treatment = str(item.get("treatment") or "").strip()
        source_id = int(item["source_unit_id"])
        refs = [
            canonical_beat_id.get(ref.lower(), ref)
            for ref in _string_items(item.get("beat_ids"))
        ]
        unknown = [beat_id for beat_id in refs if beat_id not in known_beat_ids]
        if unknown:
            kept_refs = [beat_id for beat_id in refs if beat_id in known_beat_ids]
            inferred_refs = beat_source_index.get(source_id, [])
            report["warnings"].append({
                "source_unit_id": source_id,
                "field": "beat_ids",
                "dropped_unknown_ids": unknown,
                "inferred_beat_ids": inferred_refs,
            })
            refs = kept_refs or inferred_refs
            if not refs and treatment in {"beat", "merged_into_adjacent_beat"}:
                item["treatment"] = "supporting_context"
                treatment = "supporting_context"
                reason = str(item.get("reason") or "").strip()
                item["reason"] = (
                    f"{reason} Validator downgraded this unit because it "
                    f"referenced unknown beat IDs {unknown}."
                ).strip()
                report["normalizations"].append(
                    f"source unit {source_id} downgraded to supporting_context "
                    f"after unknown beat refs {unknown}"
                )
            else:
                report["normalizations"].append(
                    f"source unit {source_id} beat refs normalized from "
                    f"{unknown}"
                )
            item["beat_ids"] = refs
        if treatment in {"beat", "merged_into_adjacent_beat"} and not refs:
            raise ValueError(
                f"source unit {source_id} treatment {treatment!r} "
                "requires at least one beat_id"
            )

    prior_beat_ids: set[str] = set()
    previous_min_source_id = 0
    for beat in beats:
        beat_id = str(beat.get("beat_id") or "").strip()
        raw_source_ids = beat.get("source_unit_ids")
        if not isinstance(raw_source_ids, list) or not raw_source_ids:
            raise ValueError(f"beat {beat_id} must have source_unit_ids")
        source_ids: list[int] = []
        for raw_source_id in raw_source_ids:
            try:
                source_id = int(raw_source_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"beat {beat_id} has non-numeric source id") from exc
            if source_id not in known_source_ids:
                raise ValueError(f"beat {beat_id} references unknown source {source_id}")
            source_ids.append(source_id)
        if source_ids != sorted(source_ids):
            raise ValueError(f"beat {beat_id} source_unit_ids are out of order")
        if min(source_ids) < previous_min_source_id:
            raise ValueError(f"beat {beat_id} moves backward in source order")
        previous_min_source_id = min(source_ids)
        beat["source_unit_ids"] = source_ids

        beat_type = str(beat.get("beat_type") or "").strip()
        if beat_type not in BEAT_TYPES:
            raise ValueError(f"beat {beat_id} has invalid beat_type {beat_type!r}")
        importance = str(beat.get("importance") or "").strip()
        if importance not in IMPORTANCE_VALUES:
            raise ValueError(f"beat {beat_id} has invalid importance {importance!r}")
        for key in (
            "scene",
            "time",
            "actor",
            "action",
            "result",
            "reader_new_info",
        ):
            if not str(beat.get(key) or "").strip():
                raise ValueError(f"beat {beat_id} missing {key}")
        actor = str(beat.get("actor") or "").strip()
        if "/" in actor or NON_VISIBLE_ACTOR_RE.search(actor):
            raise ValueError(
                f"beat {beat_id} actor must be one visible living character "
                f"or narrator, got {actor!r}"
            )
        if not isinstance(beat.get("object"), str):
            raise ValueError(f"beat {beat_id} missing object string")
        for key in ("participants", "required_visuals", "evidence"):
            values = _string_items(beat.get(key))
            if not values:
                raise ValueError(f"beat {beat_id} missing {key}")
            beat[key] = values
        for key in ("required_context", "reference_dependencies"):
            value = beat.get(key)
            if value is None:
                beat[key] = []
            elif not isinstance(value, list):
                raise ValueError(f"beat {beat_id} {key} must be an array")
            else:
                beat[key] = _string_items(value)
        if not isinstance(beat.get("forbidden_visuals"), list):
            raise ValueError(f"beat {beat_id} forbidden_visuals must be an array")
        beat["forbidden_visuals"] = _string_items(beat.get("forbidden_visuals"))
        if not isinstance(beat.get("visualizable"), bool):
            raise ValueError(f"beat {beat_id} missing visualizable boolean")

        depends_on = _string_items(beat.get("depends_on"))
        unknown_depends = [
            depends_id for depends_id in depends_on
            if depends_id not in known_beat_ids
        ]
        if unknown_depends:
            raise ValueError(f"beat {beat_id} depends on unknown beats {unknown_depends}")
        future_depends = [
            depends_id for depends_id in depends_on
            if depends_id not in prior_beat_ids
        ]
        if future_depends:
            raise ValueError(
                f"beat {beat_id} depends on non-prior beats {future_depends}"
            )
        beat["depends_on"] = depends_on

        enables = _string_items(beat.get("enables"))
        kept_enables = [enabled for enabled in enables if enabled in known_beat_ids]
        dropped = [enabled for enabled in enables if enabled not in known_beat_ids]
        if dropped:
            report["warnings"].append({
                "beat_id": beat_id,
                "field": "enables",
                "dropped_unknown_ids": dropped,
            })
            report["normalizations"].append(
                f"{beat_id}.enables dropped unknown ids {dropped}"
            )
        beat["enables"] = kept_enables
        prior_beat_ids.add(beat_id)

    covered_by_beats = {
        source_id
        for beat in beats
        for source_id in beat.get("source_unit_ids", [])
        if isinstance(source_id, int)
    }
    beat_treated_ids = {
        int(item["source_unit_id"])
        for item in treatments
        if str(item.get("treatment")) in {"beat", "merged_into_adjacent_beat"}
    }
    missing_from_beats = sorted(beat_treated_ids - covered_by_beats)
    if missing_from_beats:
        raise ValueError(
            f"source units marked as beat material are not covered by beats: "
            f"{missing_from_beats}"
        )

    report["beat_count"] = len(beats)
    report["source_unit_count"] = len(source_units)
    report["supporting_context_units"] = sum(
        1 for item in treatments
        if item.get("treatment") == "supporting_context"
    )
    report["omitted_units"] = sum(
        1 for item in treatments if item.get("treatment") == "omit"
    )
    return report


def _markdown(data: dict[str, Any], *, source_path: Path, word_range: tuple[int, int]) -> str:
    lines: list[str] = []
    lines.append(f"# {data.get('title') or 'Graphic Beat List'}")
    lines.append("")
    lines.append(f"- Source: `{source_path}`")
    lines.append(f"- Word range: {word_range[0]}-{word_range[1]}")
    lines.append("")
    scope = str(data.get("adaptation_scope") or "").strip()
    if scope:
        lines.append("## Scope")
        lines.append("")
        lines.append(scope)
        lines.append("")

    lines.append("## Beats")
    lines.append("")
    for beat in data.get("beats", []) or []:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        action = str(beat.get("action") or "").strip()
        heading = beat_id if not action else f"{beat_id}: {action}"
        lines.append(f"### {heading}")
        lines.append("")
        for key, label in (
            ("source_unit_ids", "Source Units"),
            ("beat_type", "Beat Type"),
            ("scene", "Scene"),
            ("time", "Time"),
            ("participants", "Participants"),
            ("actor", "Actor"),
            ("object", "Object"),
            ("result", "Result"),
            ("reader_new_info", "Reader New Info"),
            ("depends_on", "Depends On"),
            ("enables", "Enables"),
            ("required_context", "Required Context"),
            ("reference_dependencies", "Reference Dependencies"),
            ("required_visuals", "Required Visuals"),
            ("forbidden_visuals", "Forbidden Visuals"),
            ("visualizable", "Visualizable"),
            ("importance", "Importance"),
        ):
            raw = beat.get(key)
            if isinstance(raw, list):
                value = ", ".join(str(item) for item in raw).strip()
            else:
                value = str(raw if raw is not None else "").strip()
            if value:
                lines.append(f"- **{label}:** {value}")
        evidence = beat.get("evidence")
        if isinstance(evidence, list) and evidence:
            lines.append("- **Evidence:**")
            for item in evidence:
                lines.append(f"  - {item}")
        notes = str(beat.get("notes") or "").strip()
        if notes:
            lines.append(f"- **Notes:** {notes}")
        lines.append("")

    treatments = data.get("source_unit_treatments") or []
    if isinstance(treatments, list) and treatments:
        lines.append("## Source Unit Treatments")
        lines.append("")
        for item in treatments:
            if not isinstance(item, dict):
                continue
            refs = item.get("beat_ids")
            ref_text = ", ".join(str(ref) for ref in refs) if isinstance(refs, list) else ""
            reason = str(item.get("reason") or "").strip()
            suffix = " ".join(part for part in (ref_text, reason) if part)
            lines.append(
                f"- **{item.get('source_unit_id', '?')}:** "
                f"`{item.get('treatment', '')}`"
                f"{' - ' + suffix if suffix else ''}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book_id")
    parser.add_argument("--name", default="beat_list")
    parser.add_argument("--assembled-chapter-number")
    parser.add_argument("--start-word", type=int, default=1)
    parser.add_argument("--max-words", type=int, default=1600)
    parser.add_argument(
        "--unit-mode",
        choices=["sentence", "paragraph"],
        default="paragraph",
    )
    parser.add_argument("--model")
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument(
        "--raw-response",
        type=Path,
        help="Validate/package an existing raw LLM response instead of calling a model.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    book = load_book(args.book_id)
    out_dir = book.work_dir / "graphic_novel" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.assembled_chapter_number:
        excerpt, source_path, start_word, end_word = _assembled_chapter_excerpt(
            book,
            args.assembled_chapter_number,
        )
        _, _, _, source_units = _excerpt_units(
            excerpt,
            1,
            max(1, len(excerpt.split())),
            args.unit_mode,
        )
    else:
        source_path = _published_abridgment_path(args.book_id)
        abridgment = source_path.read_text(encoding="utf-8")
        excerpt, start_word, end_word, source_units = _excerpt_units(
            abridgment,
            args.start_word,
            args.max_words,
            args.unit_mode,
        )

    (out_dir / "excerpt.txt").write_text(excerpt, encoding="utf-8")
    write_json(out_dir / "source_units.json", source_units)

    prompt = load_prompt("graphic_beat_list")
    model = args.model or prompt.config.get("model", "anthropic:claude-opus-4-7")
    max_output_tokens = (
        args.max_output_tokens
        if args.max_output_tokens is not None
        else int(prompt.config.get("max_tokens", 24000))
    )
    rendered = prompt.render(
        title=book.metadata.get("title", args.book_id),
        author=book.metadata.get("author", ""),
        source_units=source_units,
        start_word=start_word,
        end_word=end_word,
    )
    (out_dir / "beat_prompt.md").write_text(rendered, encoding="utf-8")
    write_json(out_dir / "run.json", {
        "book_id": args.book_id,
        "name": args.name,
        "source_path": str(source_path),
        "assembled_chapter_number": args.assembled_chapter_number,
        "start_word": start_word,
        "end_word": end_word,
        "unit_mode": args.unit_mode,
        "source_unit_count": len(source_units),
        "model": model,
        "max_output_tokens": max_output_tokens,
        "dry_run": args.dry_run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })

    if args.dry_run:
        print(f"wrote beat-list dry-run prompt to {out_dir / 'beat_prompt.md'}")
        return 0

    if args.raw_response:
        raw_path = args.raw_response
        if not raw_path.is_absolute():
            raw_path = Path.cwd() / raw_path
        raw_text = raw_path.read_text(encoding="utf-8")
        (out_dir / "beat_raw_response.txt").write_text(raw_text, encoding="utf-8")
        data = parse_llm_json(raw_text)
    else:
        data = _complete_json_with_retry(
            rendered=rendered,
            model=model,
            system=prompt.system,
            max_tokens=max_output_tokens,
            work_dir=book.work_dir,
            stage=f"graphic_beat_list:{args.book_id}:{args.name}",
            raw_path=out_dir / "beat_raw_response.txt",
        )
    report = _validate_beat_list(data, source_units)
    write_json(out_dir / "beat_list.json", data)
    write_json(out_dir / "beat_list_validation.json", report)
    (out_dir / "beat_list.md").write_text(
        _markdown(data, source_path=source_path, word_range=(start_word, end_word)),
        encoding="utf-8",
    )
    print(f"wrote beat list: {report['beat_count']} beats")
    print(f"source units: {report['source_unit_count']}")
    print(f"json: {out_dir / 'beat_list.json'}")
    print(f"markdown: {out_dir / 'beat_list.md'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
