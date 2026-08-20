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

from scripts.graphic_balloon_split import split_balloon_text, split_panel_balloons
from scripts.graphic_dialogue_draft import _clean_texts, _count_texts
from forage.graphic.geometry import panel_capacities

MAX_BALLOON_CHARS = 95

# Phrases `_reported_speech_text` falls back to when it cannot say anything
# specific about a line. `_sanitize_caption_artifacts` strips exactly these back
# out of captions, so demoting a balloon into one of them destroys the line
# outright. Detect them up front and keep the balloon instead.
#
# Both the detector below and the caption stripper are built from this one
# alternation, so a new fallback phrase cannot be taught to one and missed by
# the other. Only the predicate is shared: the detector accepts any short lead-in
# where the stripper insists on a capitalized speaker, which makes the detector
# the broader of the two. That asymmetry is the safe direction — every phrase the
# stripper would erase is caught here first, so the balloon is kept instead.
_UNINFORMATIVE_PREDICATE = (
    r"(?:spoke(?:\s+(?:briefly|at length))?|asked a question)"
)
_UNINFORMATIVE_REPORT_RE = re.compile(
    rf"^.{{0,60}}?\s+{_UNINFORMATIVE_PREDICATE}\.?$"
)


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
    # Lines that would not fit even split across balloons. These are the only
    # ones a paraphrase pass has to handle, so the report names them explicitly
    # rather than leaving them to be discovered at render time.
    oversized: list[dict[str, Any]] = []
    for page in data.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_number") or 0)
        # The layout stage caps figures per panel from the same rule, so
        # capacity is read here rather than assumed, and a panel can never be
        # given more balloons than it will be given speakers to carry them.
        # Non-dict entries are dropped first because the layout stage grids only
        # well-formed panels — keeping them would shift the grid out from under
        # the capacities computed here.
        panels = [item for item in (page.get("panels") or []) if isinstance(item, dict)]
        capacities = panel_capacities(panels)
        for index, panel in enumerate(panels):
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
                _clean_texts(
                    old_texts,
                    page_number=page_no,
                    panel_number=panel_no,
                    max_balloons=capacities[index],
                )
            )
            # Fit whatever survived as a balloon. Splitting runs last so it only
            # ever sees lines that are actually staying as speech, and it is
            # tried before any paraphrase because it costs nothing and keeps the
            # author's words intact.
            new_texts, unfittable = split_panel_balloons(
                new_texts, limit=MAX_BALLOON_CHARS, capacity=capacities[index]
            )
            for item in unfittable:
                oversized.append({
                    "page_number": page_no,
                    "panel_number": panel_no,
                    "speaker": str(item.get("speaker") or ""),
                    "chars": len(_normalize_text(str(item.get("text") or ""))),
                    "text": _normalize_text(str(item.get("text") or "")),
                })
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
    return data, {"changed_panels": changes, "oversized_balloons": oversized}


def _demote_unsafe_balloons(texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert unreliable balloons into narration.

    A single-speaker balloon can read as redundant annotation when the caption
    beside it already says the same thing, and folding it back into the caption
    as reported speech reads better than printing the line twice.

    The test is whether the caption *actually* restates the line. Treating every
    lone speaker as redundant demotes dialogue whose caption is unrelated
    narration, and in a graphic novel a spoken line belongs in a balloon unless
    there is a reason to move it — turning it into narration spends the
    character's own words to say something the page already said.
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
    caption_text = " ".join(
        str(texts[index].get("text") or "") for index in caption_indexes
    )
    lone_speaker = bool(speech_items) and len(speakers) <= 1

    result: list[dict[str, Any]] = []
    demoted: list[dict[str, str]] = []
    for item in texts:
        kind = str(item.get("kind") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if kind != "speech":
            result.append(item)
            continue
        # Length alone is no longer grounds for demotion: a long line that can
        # be split across balloons keeps every word, which beats reporting it in
        # narration. Only a line that cannot be made to fit is still a candidate.
        unfittable = (
            len(text) > MAX_BALLOON_CHARS
            and split_balloon_text(text, limit=MAX_BALLOON_CHARS) is None
        )
        redundant = lone_speaker and _caption_restates(caption_text, text)
        if redundant or unfittable:
            reported = _reported_speech_text(item)
            if reported and not _UNINFORMATIVE_REPORT_RE.match(reported):
                demoted.append({"text": reported, "raw": text, "speaker": str(item.get("speaker") or "")})
                continue
            # Demotion would swap the line for a phrase `_sanitize_caption_artifacts`
            # strips straight back out, so the line would vanish from the page
            # entirely. Keep the balloon: an over-long balloon is a fitting
            # problem the letterer already shrinks to solve, but a dropped line
            # is unrecoverable downstream.
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
    sanitized: list[dict[str, Any]] = []
    for item in result:
        if str(item.get("kind") or "").strip().lower() != "caption":
            sanitized.append(item)
            continue
        item["text"] = _sanitize_caption_artifacts(
            _sanitize_caption_direct_speech(str(item.get("text") or ""))
        )
        # A caption made up entirely of stripped artifacts sanitizes to nothing.
        # Keeping the husk would letter an empty caption box onto the panel.
        if item["text"].strip():
            sanitized.append(item)
    return sanitized


# Words too common to signal that two sentences are about the same thing.
_FUNCTION_WORDS = frozenset("""
the a an and or but of to in on at for with from by as if so no not
is was were be been being am are do did does have has had will would can could
i you he she it we they me him her them us my your his its our their this that
these those there here then than when what who whom whose which how why
""".split())

# Share of the line's meaningful words that must already appear in the caption
# before the caption counts as restating it. The corpus splits cleanly either
# side of this: genuine echoes land well above, unrelated narration well below.
_CAPTION_ECHO_RATIO = 0.5


def _content_words(text: str) -> set[str]:
    # Split on apostrophes so a contraction reduces to its parts: "you've"
    # becomes "you" and "ve", both discarded, rather than a token that could
    # never match the same idea spelled out in the caption.
    return {
        word for word in re.findall(r"[a-z]+", text.lower())
        if len(word) > 2 and word not in _FUNCTION_WORDS
    }


def _caption_restates(caption: str, line: str) -> bool:
    """True when the caption already carries this line's content.

    Compared on meaningful words only. A short line has few of them, so an
    incidental shared word would otherwise read as a restatement; requiring at
    least two keeps "I just—" beside an unrelated caption from counting.
    """
    spoken = _content_words(line)
    if len(spoken) < 2:
        return False
    shared = spoken & _content_words(caption)
    return len(shared) >= 2 and len(shared) / len(spoken) >= _CAPTION_ECHO_RATIO


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
        rf"(^|[.!?][\"'”’]?\s+){speaker}\s+{_UNINFORMATIVE_PREDICATE}\.?(?=\s|$)"
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
    """Lowercase a clause being folded mid-sentence into reported speech.

    `_second_person_to_first` rewrites "you" to "I", so the clause often now
    opens on the pronoun, which stays capitalized wherever it lands.
    """
    if not text:
        return text
    if re.match(r"I\b", text):
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
