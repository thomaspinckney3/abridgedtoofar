"""Prompt loading. Prompts live in prompts/<name>.md with YAML frontmatter.

Example:
    ---
    model: anthropic:claude-opus-5-5
    max_tokens: 8192
    ---
    You will receive stage-specific instructions after the cache break.

    {{source_text}}

    <!-- CACHE-BREAK -->

    Your task: ...

Split convention: everything before the `<!-- CACHE-BREAK -->` marker is the
cached prefix (book-scale context that's stable across stages); everything
after is the per-call tail. Prompts without the marker have no cached prefix.

Frontmatter keys are passed through as defaults; callers override per-call.
Both sides are rendered with Jinja2 using the variables passed to `render_blocks`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template

from .resources import resource_path

PROMPTS_DIR = resource_path("prompts/draft_lean.md").parent
CACHE_BREAK = "<!-- CACHE-BREAK -->"


@dataclass
class Prompt:
    name: str
    body_template: str                      # the per-call tail (always present)
    cached_template: str | None = None      # the cache prefix (optional)
    config: dict[str, Any] = field(default_factory=dict)
    system: str | None = None

    def render(self, **vars: Any) -> str:
        """Render a prompt as a single string (backward compatibility)."""
        if self.cached_template is None:
            return Template(self.body_template).render(**vars)
        # Concatenate without the marker for callers that don't use blocks.
        cached = Template(self.cached_template).render(**vars)
        body = Template(self.body_template).render(**vars)
        return cached + body

    def render_blocks(self, **vars: Any) -> tuple[str | None, str]:
        """Render and return (cached_prefix, body). cached_prefix is None when
        the prompt has no cache-break marker."""
        body = Template(self.body_template).render(**vars)
        if self.cached_template is None:
            return None, body
        cached = Template(self.cached_template).render(**vars)
        return cached, body


def load_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    raw = path.read_text()
    config: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            config = yaml.safe_load(raw[4:end]) or {}
            body = raw[end + 5:]
    system = config.pop("system", None)

    cached_template: str | None = None
    if CACHE_BREAK in body:
        cached_part, _, body = body.partition(CACHE_BREAK)
        cached_template = cached_part

    return Prompt(name=name, body_template=body, cached_template=cached_template,
                  config=config, system=system)
