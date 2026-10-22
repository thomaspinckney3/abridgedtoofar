"""Prime stage: surface example signature passages before the pre-pass.

The cached prefix in prompts/prime.md is identical to prompts/prepass.md's
cached prefix by design, so running `prime` immediately followed by `prepass`
on the same book costs one cache-write (prime) plus one cache-read (prepass)
instead of two cache-writes.

If `search=True`, the Anthropic server-side `web_search` tool is enabled so
Claude can ground signature candidates in actual published criticism rather
than relying solely on cultural recall.
"""

from __future__ import annotations

from .artifacts import Book, write_json, write_text
from .json_parse import parse_llm_json
from .llm import complete
from .prompts import load_prompt


# Anthropic server-side web_search tool definition.
# See https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool
WEB_SEARCH_TOOL: dict = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 6,
}


def run_prime(book: Book, *, search: bool = False) -> dict:
    prompt = load_prompt("prime")
    cached, body = prompt.render_blocks(
        book_id=book.book_id,
        genre=book.metadata.get("genre", "unknown"),
        source_text=book.source_text,
        search_enabled=search,
    )

    resp = complete(
        prompt=body,
        cached_prompt=cached,
        model=prompt.config.get("model", "anthropic:claude-opus-5-5"),
        system=prompt.system,
        max_tokens=prompt.config.get("max_tokens", 8000),
        temperature=prompt.config.get("temperature"),
        tools=[WEB_SEARCH_TOOL] if search else None,
        work_dir=book.work_dir,
        stage="prime:search" if search else "prime",
    )

    write_text(book.work_dir / "prime.raw.md", resp.text)
    data = parse_llm_json(resp.text)
    write_json(book.work_dir / "prime.json", data)
    return data


