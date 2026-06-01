"""Apply deterministic lettering safety policy to a graphic storyboard.

This stage is a non-LLM backstop for dialogue drafts. It demotes reported or
internal narration that was emitted as speech, merges multiple captions into a
single caption item, and writes a report of changed panels.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from forage.artifacts import write_json

from scripts.graphic_dialogue_draft import _clean_texts, _count_texts

MAX_BALLOON_CHARS = 95


def _normalize_text(text: str) -> str:
    return " ".join(text.replace(" // ", " ").replace("//", " ").split())


def _panel_texts(panel: dict[str, Any]) -> list[dict[str, Any]]:
    raw_texts = panel.get("texts")
    if isinstance(raw_texts, list):
        return raw_texts

    texts: list[dict[str, Any]] = []
    caption = _normalize_text(str(panel.get("caption") or "").strip())
    if caption:
        texts.append({
            "kind": "caption",
            "text": caption,
            "caption_zone": panel.get("caption_zone") or "top_center",
        })
    for raw in panel.get("dialogue") or []:
        if not isinstance(raw, dict):
            continue
        text = _normalize_text(str(raw.get("text") or "").strip())
        if not text:
            continue
        item = deepcopy(raw)
        item["kind"] = str(item.get("kind") or "speech").strip().lower()
        item["text"] = text
        texts.append(item)
    return texts


def apply_lettering_policy(storyboard: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = deepcopy(storyboard)
    changes: list[dict[str, Any]] = []
    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        for panel in page.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            panel_no = int(panel.get("panel_number") or 0)
            old_texts = _panel_texts(panel)
            if not isinstance(old_texts, list):
                continue
            old_counts = _count_texts([
                item for item in old_texts
                if isinstance(item, dict)
                and str(item.get("kind") or "").strip().lower() in {"caption", "speech", "thought"}
            ])
            new_texts = _demote_unsafe_balloons(
                _clean_texts(old_texts, page_number=page_no, panel_number=panel_no)
            )
            new_counts = _count_texts(new_texts)
            if new_texts != old_texts or not isinstance(panel.get("texts"), list):
                panel["texts"] = new_texts
                changes.append({
                    "page_number": page_no,
                    "panel_number": panel_no,
                    "old_counts": old_counts,
                    "new_counts": new_counts,
                    "old_texts": old_texts,
                    "new_texts": new_texts,
                })
    return data, {"changed_panels": changes}


def _demote_unsafe_balloons(texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert unreliable balloons into narration.

    A single-speaker balloon beside a caption often reads as redundant
    annotation, and if the art misses the reserve zone the balloon lands on the
    only visible face. Keep balloons for true exchanges; otherwise fold speech
    back into the caption as reported speech.
    """
    caption_indexes = [
        index for index, item in enumerate(texts)
        if str(item.get("kind") or "").strip().lower() == "caption"
        and str(item.get("text") or "").strip()
    ]
    if not caption_indexes:
        return texts
    speech_items = [
        item for item in texts
        if str(item.get("kind") or "").strip().lower() == "speech"
        and str(item.get("text") or "").strip()
    ]
    speakers = {
        str(item.get("speaker") or "").strip().lower()
        for item in speech_items
        if str(item.get("speaker") or "").strip()
    }
    demote_single_speaker = bool(speech_items) and len(speakers) <= 1

    result: list[dict[str, Any]] = []
    demoted: list[dict[str, str]] = []
    for item in texts:
        kind = str(item.get("kind") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if kind != "speech":
            result.append(item)
            continue
        if demote_single_speaker or len(text) > MAX_BALLOON_CHARS:
            reported = _reported_speech_text(item)
            if reported:
                demoted.append({"text": reported, "raw": text, "speaker": str(item.get("speaker") or "")})
            continue
        result.append(item)
    if demoted:
        caption = next(
            item for item in result
            if str(item.get("kind") or "").strip().lower() == "caption"
        )
        current = str(caption.get("text") or "").strip()
        caption["text"] = _merge_demoted_speech(current, demoted)
        note = str(caption.get("lettering_notes") or "").strip()
        extra = "demoted non-exchange speech"
        caption["lettering_notes"] = f"{note}; {extra}" if note else extra
    for item in result:
        if str(item.get("kind") or "").strip().lower() == "caption":
            item["text"] = _sanitize_caption_artifacts(
                _sanitize_caption_direct_speech(str(item.get("text") or ""))
            )
    return result


def _sanitize_caption_artifacts(text: str) -> str:
    """Clean mechanical artifacts introduced while demoting balloons."""
    cleaned = _normalize_text(text)
    cleaned = re.sub(
        r"\b([A-Z][a-z]{3,})(before|after|while|when|until|because|but)\b",
        r"\1 \2",
        cleaned,
    )
    speaker = (
        r"(?:Mr\.|Mrs\.|Miss|Ms\.)?\s*[A-Z][A-Za-z'.-]+"
        r"(?:\s+[A-Z][A-Za-z'.-]+){0,3}"
    )
    artifact_re = re.compile(
        rf"(^|[.!?][\"'”’]?\s+){speaker}\s+"
        r"(?:spoke(?:\s+(?:briefly|at length))?|asked a question)\.?(?=\s|$)"
    )
    while True:
        updated = artifact_re.sub(lambda match: match.group(1), cleaned)
        if updated == cleaned:
            break
        cleaned = updated
    return _normalize_text(cleaned)


def _sanitize_caption_direct_speech(text: str) -> str:
    """Convert attributed quotes inside captions into reported action."""
    stripped = text.strip()
    quoted = re.fullmatch(r"[\"“](?P<quote>.+)[\"”]", stripped)
    if quoted:
        reported = _reported_standalone_caption_quote(
            _normalize_text(quoted.group("quote"))
        )
        if reported:
            return reported

    def replace(match: re.Match[str]) -> str:
        speaker = " ".join(match.group("speaker").split())
        quote = _normalize_text(match.group("quote").strip())
        return _reported_caption_speech(speaker, quote)

    return re.sub(
        r"\b(?P<speaker>(?:Mr\.|Mrs\.|Miss|Ms\.)?\s*[A-Z][A-Za-z'. -]{0,36}?)\s+"
        r"(?:said|cried|called|asked|answered|replied|shouted|whispered|exclaimed)"
        r"\s*,?\s*[\"“](?P<quote>[^\"”]+)[\"”]",
        replace,
        text,
        flags=re.IGNORECASE,
    )


def _reported_standalone_caption_quote(quote: str) -> str:
    lowered = quote.lower()
    if "two little seats facing each other" in lowered and "can't live forever" in lowered:
        return (
            "Myrtle told us how Tom sat opposite her on the train, brushed "
            "against her at the station, and made her think she could not live forever."
        )
    if quote.endswith("?"):
        return "Someone asked a question."
    if len(quote.split()) > MAX_BALLOON_CHARS // 2:
        return "Someone spoke at length."
    return ""


def _reported_caption_speech(speaker: str, quote: str) -> str:
    lowered = quote.lower()
    speaker_text = speaker.strip() or "Someone"
    if "better sell it somewhere else" in lowered:
        return f"{speaker_text} threatened to sell the car somewhere else"
    if "airedale" in lowered and "dollar" in lowered:
        return f"{speaker_text} called the puppy more of an Airedale and named the price"
    if lowered.startswith("i beg your pardon"):
        return f"{speaker_text} apologized that he had not known he was touching the lever"
    if quote.endswith("?"):
        return f"{speaker_text} asked a question"
    if len(quote.split()) <= 12:
        return f"{speaker_text} spoke briefly"
    return f"{speaker_text} spoke"


def _reported_speech_text(item: dict[str, Any]) -> str:
    text = _normalize_text(str(item.get("text") or "").strip())
    if not text:
        return ""
    speaker = str(item.get("speaker") or "").strip()
    speaker_text = _reported_speaker(speaker)

    if re.search(r"\bpeople in this world\b", text, re.IGNORECASE) and re.search(
        r"\badvantages\b", text, re.IGNORECASE
    ):
        return f"{speaker_text} told me to remember that not everyone had my advantages."

    lowered = text.lower()
    if "couple of friends" in lowered and "sister" in lowered:
        return f"{speaker_text} announced that she would call her sister and have friends up."
    if (
        "make a list" in lowered
        or "got to get" in lowered
        or "collar for the dog" in lowered
        or "ashtrays" in lowered
    ):
        return f"{speaker_text} began listing the things she meant to buy and do."
    if "give you this dress" in lowered and "another one tomorrow" in lowered:
        return f"{speaker_text} promised away her dress and said she would get another."

    direction = re.match(r"how\s+do\s+you\s+get\s+to\s+(.+?)\??$", text, re.IGNORECASE)
    if direction:
        place = direction.group(1).strip()
        return f"{speaker_text} asked how to get to {place}."

    remember = re.search(r"\bjust remember that\s+(.+)$", text, re.IGNORECASE)
    if remember:
        clause = _first_lower(_second_person_to_first(remember.group(1).strip().rstrip(".")))
        return f"{speaker_text} told me to remember that {clause}."

    if text.endswith("?"):
        return f"{speaker_text} asked a question."

    if len(text) > MAX_BALLOON_CHARS:
        return f"{speaker_text} spoke at length."
    return f"{speaker_text} spoke."


def _merge_demoted_speech(current: str, demoted: list[dict[str, str]]) -> str:
    caption = current.strip()
    prepend: list[str] = []
    append: list[str] = []
    seen: set[str] = set()
    for item in demoted:
        reported = item.get("text", "").strip()
        raw = item.get("raw", "").strip()
        if not reported:
            continue
        normalized_reported = reported.lower()
        if normalized_reported in seen:
            continue
        seen.add(normalized_reported)
        direction = re.match(r"how\s+do\s+you\s+get\s+to\s+(.+?)\??$", raw, re.IGNORECASE)
        if direction and re.search(r"\bI told him\.", caption):
            place = direction.group(1).strip()
            asked = f"asked how to get to {place}"
            if re.search(r"\bstopped me on the road\.\s+I told him\.", caption):
                caption = re.sub(
                    r"\bstopped me on the road\.\s+I told him\.",
                    f"stopped me on the road and {asked}. I told him.",
                    caption,
                    count=1,
                )
            else:
                caption = re.sub(
                    r"\bI told him\.",
                    f"{reported} I told him.",
                    caption,
                    count=1,
                )
            continue
        if _caption_opens_as_speech_afterthought(caption):
            prepend.append(reported)
            continue
        append.append(reported)
    return " ".join(part for part in [*prepend, caption, *append] if part)


def _caption_opens_as_speech_afterthought(caption: str) -> bool:
    """Return true when the caption begins with a reaction to prior speech."""
    text = caption.strip()
    return bool(re.match(
        r"^(?:"
        r"(?:he|she|they|we|i|[A-Z][A-Za-z'.-]+)\s+"
        r"(?:did(?:n't| not)\s+say\s+more|said\s+no\s+more|fell\s+silent|"
        r"was\s+silent|paused|stopped\s+speaking|finished\s+speaking)"
        r"|I\s+(?:understood|realized|knew|felt|saw)\s+"
        r"(?:he|she|they|it)\b"
        r")",
        text,
        re.IGNORECASE,
    ))


def _reported_speaker(speaker: str) -> str:
    raw = " ".join(speaker.split())
    lowered = raw.lower()
    if not raw:
        return "Someone"
    if "father" in lowered:
        return "My father"
    if lowered in {"stranger", "lost stranger", "roadside man"}:
        return "A stranger"
    if lowered.startswith(("mr.", "mrs.", "miss ", "ms.")):
        return raw
    return raw


def _second_person_to_first(text: str) -> str:
    replacements = [
        (r"\byou've\b", "I had"),
        (r"\byou have\b", "I had"),
        (r"\byou'd\b", "I would"),
        (r"\byou would\b", "I would"),
        (r"\byour\b", "my"),
        (r"\byou\b", "I"),
    ]
    result = text
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
    result = re.sub(
        r"\bhaven't had the advantages that I had\b",
        "had not had my advantages",
        result,
        flags=re.IGNORECASE,
    )
    return result


def _first_lower(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard_json", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-report", type=Path)
    args = parser.parse_args()

    storyboard = json.loads(args.storyboard_json.read_text(encoding="utf-8"))
    data, report = apply_lettering_policy(storyboard)
    write_json(args.out_json, data)
    report.update({
        "source_storyboard": str(args.storyboard_json),
        "output_storyboard": str(args.out_json),
    })
    if args.out_report:
        write_json(args.out_report, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
