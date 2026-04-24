"""Critic stage: adversarial LLM passes that hunt for failure classes.

For MVP, only the signature critic is wired. Runner is generic so additional
critics (voice, pacing, thematic, fact-fidelity) drop in by adding a prompt
file and registering a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import Book, read_json, segment_source_path, write_json
from .json_parse import parse_llm_json
from .llm import complete
from .prompts import load_prompt


@dataclass
class CriticResult:
    segment_id: str
    critic: str
    verdict: str  # "pass" or "regenerate"
    summary: str
    findings: list[dict]


CRITICS = {
    "signature": "critic_signature",
}


def run_critic(book: Book, segment_id: str, critic_name: str) -> CriticResult:
    prompt_name = CRITICS.get(critic_name)
    if prompt_name is None:
        raise ValueError(f"unknown critic {critic_name!r}; known: {list(CRITICS)}")

    plan = read_json(book.work_dir / "plan.json")
    segment = next((s for s in plan["segments"] if s["id"] == segment_id), None)
    if segment is None:
        raise ValueError(f"no segment {segment_id!r} in plan")

    seg_dir = book.work_dir / "segments"
    source_path = segment_source_path(book, segment_id)
    draft_path = seg_dir / f"{segment_id}.md"
    if source_path is None:
        raise FileNotFoundError(f"no chapter source for {segment_id}; "
                                f"run `forage split {book.book_id}` first")
    if not draft_path.exists():
        raise FileNotFoundError(f"no draft at {draft_path}; run draft first")

    segment_source = source_path.read_text()
    draft = draft_path.read_text()

    cuts_path = book.work_dir / "cuts.json"
    cuts = read_json(cuts_path) if cuts_path.exists() else None

    prompt = load_prompt(prompt_name)
    rendered = prompt.render(
        book={
            "title": plan.get("title", book.book_id),
            "author": plan.get("author", "?"),
            "genre": book.metadata.get("genre", "unknown"),
        },
        plan={
            "voice_driven_narrator": plan.get("voice_driven_narrator", "?"),
            "indirection_budget_applies": plan.get("indirection_budget_applies", "?"),
            "modernization_level": plan.get("modernization_level", "?"),
            "plan_notes": plan.get("plan_notes", ""),
        },
        segment=segment,
        segment_source=segment_source,
        draft=draft,
        cuts=cuts,
    )

    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "anthropic:claude-opus-4-7"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 8000),
        temperature=prompt.config.get("temperature"),
        cache=True,
        work_dir=book.work_dir,
        stage=f"critic:{critic_name}:{book.book_id}:{segment_id}",
    )

    data = parse_llm_json(resp.text)
    write_json(seg_dir / f"{segment_id}.critic_{critic_name}.json", data)
    return CriticResult(
        segment_id=segment_id,
        critic=critic_name,
        verdict=data.get("verdict", "pass"),
        summary=data.get("summary", ""),
        findings=data.get("findings", []),
    )


