"""Book synopsis stage: produce a 15-sentence plot synopsis used as
ground truth by the book-level critic.

Chunked chaining for books that exceed the drafter model's input context:
split diegetic source at chapter boundaries into N roughly equal chunks,
produce a partial synopsis per chunk, then merge into one 15-sentence
synopsis of the whole book.
"""

from __future__ import annotations

import math

from .artifacts import Book, read_json
from .chapter_split import split_to_disk
from .llm import complete
from .prompts import load_prompt

TOKENS_PER_WORD = 1.4  # empirical for English prose on OpenAI tokenizers
MAX_INPUT_TOKENS = 260_000  # conservative headroom under GPT-5's 272k limit
PROMPT_OVERHEAD_TOKENS = 500
MAX_CHUNK_WORDS = int((MAX_INPUT_TOKENS - PROMPT_OVERHEAD_TOKENS) / TOKENS_PER_WORD)
TARGET_SENTENCES = 15


def summarize_book(book: Book) -> str:
    """Produce a 15-sentence plot synopsis of `book`. Writes the result to
    `work/<book>/book_synopsis.md` and returns the text.
    """
    manifest_path = book.work_dir / "chapters.json"
    if not manifest_path.exists():
        split_to_disk(book)
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters", [])

    # Prefer classifier verdicts when present — front/TOC get filtered out.
    cls_path = book.work_dir / "chapter_classifications.json"
    classifications = read_json(cls_path) if cls_path.exists() else {}

    chapter_sources: list[dict] = []
    total_words = 0
    for c in chapters:
        status = classifications.get(c["id"], {}).get("status", "diegetic")
        if status in ("extradiegetic", "toc_fragment"):
            continue
        p = book.work_dir / "chapters" / f"{c['id']}.md"
        if not p.exists():
            continue
        text = p.read_text()
        words = len(text.split())
        chapter_sources.append({"id": c["id"], "text": text, "words": words})
        total_words += words

    if not chapter_sources:
        raise RuntimeError(f"no diegetic chapters found for {book.book_id}")

    n_chunks = max(1, math.ceil(total_words / MAX_CHUNK_WORDS))

    if n_chunks == 1:
        synopsis = _single_synopsis(book, chapter_sources,
                                    n_sentences=TARGET_SENTENCES)
    else:
        chunks = _chunk_chapters(chapter_sources, n_chunks)
        per_chunk = max(3, math.ceil(TARGET_SENTENCES / n_chunks) + 1)
        partials = []
        for i, chunk in enumerate(chunks, 1):
            partials.append(_single_synopsis(
                book, chunk, n_sentences=per_chunk,
                note=f"(part {i} of {n_chunks})",
                stage_suffix=f"part{i}",
            ))
        synopsis = _merge_synopses(book, partials)

    out_path = book.work_dir / "book_synopsis.md"
    out_path.write_text(synopsis.strip() + "\n")
    return synopsis


def _chunk_chapters(chapter_sources: list[dict], n_chunks: int) -> list[list[dict]]:
    """Split chapters into n_chunks roughly-equal-word-count groups, always
    at chapter boundaries (never mid-chapter).
    """
    if n_chunks <= 1:
        return [chapter_sources]
    total = sum(c["words"] for c in chapter_sources)
    target_per_chunk = total / n_chunks

    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_words = 0
    for c in chapter_sources:
        current.append(c)
        current_words += c["words"]
        if current_words >= target_per_chunk and len(chunks) < n_chunks - 1:
            chunks.append(current)
            current = []
            current_words = 0
    if current:
        chunks.append(current)
    while len(chunks) < n_chunks:
        chunks.append([])
    return chunks


def _single_synopsis(book: Book, chapter_sources: list[dict], *,
                     n_sentences: int, note: str = "",
                     stage_suffix: str = "") -> str:
    source_block = "\n\n".join(c["text"] for c in chapter_sources)
    prompt = load_prompt("summarize_synopsis")
    rendered = prompt.render(n_sentences=n_sentences, note=note,
                             source=source_block)
    stage = f"summarize:{book.book_id}"
    if stage_suffix:
        stage = f"{stage}:{stage_suffix}"
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-5"),
        max_tokens=prompt.config.get("max_tokens", 8000),
        cache=False,
        work_dir=book.work_dir,
        stage=stage,
    )
    return resp.text.strip()


def _merge_synopses(book: Book, partials: list[str]) -> str:
    prompt = load_prompt("summarize_merge")
    rendered = prompt.render(
        partials=partials,
        target_sentences=TARGET_SENTENCES,
        book={"title": book.metadata.get("title", book.book_id),
              "author": book.metadata.get("author", "?")},
    )
    resp = complete(
        prompt=rendered,
        model=prompt.config.get("model", "openai:gpt-5"),
        max_tokens=prompt.config.get("max_tokens", 4000),
        cache=False,
        work_dir=book.work_dir,
        stage=f"summarize:{book.book_id}:merge",
    )
    return resp.text.strip()
