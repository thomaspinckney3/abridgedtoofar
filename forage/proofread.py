"""Proofreading HTML renderer.

Reads work/<book>/alignments/*.json and emits a single static HTML file at
work/<book>/proofread.html. For each chapter and draft paragraph, shows the
draft text and the source paragraph(s) it was aligned to, stacked.
"""

from __future__ import annotations

import difflib
import html
import json
import re
from pathlib import Path

from .artifacts import Book, read_json


_CSS = """
:root {
  --bg: #fafafa;
  --fg: #222;
  --muted: #666;
  --verbatim: #d9f2d0;
  --paraphrased: #e8f0fa;
  --compressed: #fff6d0;
  --unsupported: #f5d0d0;
  --border: #ddd;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: 'Georgia', serif;
       max-width: 1200px; margin: 2em auto; padding: 0 2em; line-height: 1.55; }
h1 { border-bottom: 2px solid var(--border); padding-bottom: 0.25em; }
h2 { margin-top: 2em; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }
h2 .meta { font-size: 0.7em; color: var(--muted); font-weight: normal; }
.legend { font-size: 0.85em; color: var(--muted); margin-bottom: 1em; }
.legend span { padding: 2px 8px; border-radius: 3px; margin-right: 6px; }
.block { margin: 1.2em 0; padding: 0.8em 1em; border-left: 4px solid var(--border);
         border-radius: 4px; }
.block.verbatim    { background: var(--verbatim); border-color: #7cb86c; }
.block.paraphrased { background: var(--paraphrased); border-color: #6a93c8; }
.block.compressed  { background: var(--compressed); border-color: #c8a84d; }
.block.unsupported { background: var(--unsupported); border-color: #c87070; }
.draft { font-size: 1.02em; }
.note { font-size: 0.8em; color: var(--muted); margin-bottom: 0.3em;
        text-transform: uppercase; letter-spacing: 0.04em; }
.source { margin-top: 0.8em; padding-left: 1em; border-left: 2px dotted #aaa;
          color: var(--muted); font-size: 0.92em; }
.source .para-id { display: inline-block; font-family: 'SF Mono', monospace;
                   font-size: 0.75em; color: #888; margin-right: 0.5em; }
ins { background: #d0f0d0; color: #1a4d1a; text-decoration: none;
      padding: 0 2px; border-radius: 2px; }
del { background: #f0d0d0; color: #7a1a1a; text-decoration: line-through;
      padding: 0 2px; border-radius: 2px; }
.diff-view { font-size: 0.95em; margin-top: 0.4em; padding: 0.5em 0.8em;
             background: rgba(255,255,255,0.5); border-radius: 3px;
             font-family: 'Georgia', serif; line-height: 1.6; }
.diff-label { font-size: 0.75em; color: var(--muted); text-transform: uppercase;
              letter-spacing: 0.04em; margin-top: 0.8em; }
.chapter-summary { font-size: 0.85em; color: var(--muted); margin-bottom: 1em; }
details.unused { margin: 2em 0; padding: 0.8em 1em; background: #f0f0f0;
                 border-radius: 4px; }
details.unused summary { cursor: pointer; font-weight: bold; color: var(--muted); }
.unused-para { margin: 0.6em 0; padding-left: 1em; color: var(--muted);
               font-size: 0.92em; border-left: 2px solid #bbb; }
"""


_TOKEN_RE = re.compile(r"\S+|\s+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _word_diff_html(source: str, draft: str) -> str:
    """Inline word-level diff rendered as HTML with <ins>/<del> markers.
    Only meaningful when source and draft are close in length + content."""
    a = _tokenize(source)
    b = _tokenize(draft)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_seg = "".join(a[i1:i2])
        b_seg = "".join(b[j1:j2])
        if tag == "equal":
            out.append(html.escape(a_seg))
        elif tag == "replace":
            if a_seg.strip():
                out.append(f"<del>{html.escape(a_seg)}</del>")
            if b_seg.strip():
                out.append(f"<ins>{html.escape(b_seg)}</ins>")
        elif tag == "delete":
            out.append(f"<del>{html.escape(a_seg)}</del>")
        elif tag == "insert":
            out.append(f"<ins>{html.escape(b_seg)}</ins>")
    return "".join(out)


def _should_word_diff(note_key: str, source: str, draft: str) -> bool:
    """Show word-level diff only when the two texts are close enough that a
    word-level view is readable. Skip when the edit is paragraph-scale."""
    if note_key not in ("verbatim", "paraphrased"):
        return False
    if not source.strip() or not draft.strip():
        return False
    # Length guardrail: if the two diverge by more than 40% in length the diff
    # becomes mostly insert/delete blocks and isn't useful.
    la, lb = len(source), len(draft)
    ratio = min(la, lb) / max(la, lb)
    if ratio < 0.6:
        return False
    # Similarity guardrail: if the sequences share less than ~50% of content
    # the diff view is noisier than a stacked view.
    sm = difflib.SequenceMatcher(a=_tokenize(source), b=_tokenize(draft), autojunk=False)
    if sm.ratio() < 0.5:
        return False
    return True


def _render_chapter(alignment: dict) -> str:
    sid = alignment["segment_id"]
    src_paras = alignment["source_paragraphs"]
    draft_paras = alignment["draft_paragraphs"]
    mapping = alignment["mapping"]

    # Bucket stats
    notes = [str(m.get("note", "")).split("—")[0].strip().lower() for m in mapping]
    counts = {k: notes.count(k) for k in ("verbatim", "paraphrased", "compressed", "unsupported")}
    used_src_ids: set[int] = set()
    for m in mapping:
        for i in m.get("source_paras", []) or []:
            if isinstance(i, int):
                used_src_ids.add(i)

    parts = [f'<h2>Chapter {sid} <span class="meta">— {len(draft_paras)} draft paras '
             f'from {len(src_paras)} source paras</span></h2>']
    stats = "  ·  ".join(f"{k}: {v}" for k, v in counts.items() if v > 0)
    parts.append(f'<div class="chapter-summary">{stats}</div>')

    for m in mapping:
        idx = m.get("draft_para")
        if not isinstance(idx, int) or idx < 0 or idx >= len(draft_paras):
            continue
        note_raw = str(m.get("note", "")).strip()
        note_key = note_raw.split("—")[0].strip().lower()
        if note_key not in ("verbatim", "paraphrased", "compressed", "unsupported"):
            note_key = "unsupported"

        src_idxs = [i for i in (m.get("source_paras") or []) if isinstance(i, int)]

        draft_text = draft_paras[idx]

        # Decide whether to show an inline word-diff instead of stacked view.
        concat_src = "\n\n".join(src_paras[si] for si in src_idxs
                                  if 0 <= si < len(src_paras))
        show_diff = (len(src_idxs) == 1
                     and _should_word_diff(note_key, concat_src, draft_text))

        parts.append(f'<div class="block {note_key}">')
        parts.append(f'  <div class="note">{html.escape(note_raw or note_key)} · draft [{idx}]</div>')

        if show_diff:
            diff_html = _word_diff_html(concat_src, draft_text)
            parts.append(f'  <div class="diff-label">source → draft (word diff)</div>')
            parts.append(f'  <div class="diff-view">{diff_html}</div>')
        else:
            parts.append(f'  <div class="draft">{html.escape(draft_text)}</div>')
            if src_idxs:
                parts.append('  <div class="source">')
                for si in src_idxs:
                    if 0 <= si < len(src_paras):
                        parts.append(f'    <div><span class="para-id">src [{si}]</span>'
                                     f'{html.escape(src_paras[si])}</div>')
                parts.append('  </div>')
        parts.append('</div>')

    # Collapsible section showing source paragraphs that no draft paragraph
    # references — i.e. what got cut.
    unused = [i for i in range(len(src_paras)) if i not in used_src_ids]
    if unused:
        parts.append(f'<details class="unused"><summary>{len(unused)} source paragraphs '
                     f'not mapped to any draft paragraph (cut material)</summary>')
        for si in unused:
            parts.append(f'  <div class="unused-para"><span class="para-id">src [{si}]</span>'
                         f'{html.escape(src_paras[si])}</div>')
        parts.append('</details>')

    return "\n".join(parts)


def render_proofread_html(book: Book) -> Path:
    """Read all alignments in work/<book>/alignments/ and emit
    work/<book>/proofread.html. Returns the output path."""
    align_dir = book.work_dir / "alignments"
    if not align_dir.exists():
        raise FileNotFoundError(f"no alignments dir — run align first ({align_dir})")

    alignment_files = sorted(align_dir.glob("*.json"))
    if not alignment_files:
        raise FileNotFoundError(f"no alignment files in {align_dir}")

    title = book.metadata.get("title", book.book_id)
    author = book.metadata.get("author", "")

    parts = [
        "<!DOCTYPE html>",
        f'<html><head><meta charset="utf-8"><title>Proofread: {html.escape(title)}</title>',
        f'<style>{_CSS}</style></head><body>',
        f'<h1>{html.escape(title)}{" — " + html.escape(author) if author else ""}</h1>',
        '<div class="legend">'
        '<span class="block verbatim" style="padding:1px 8px">verbatim</span>'
        '<span class="block paraphrased" style="padding:1px 8px">paraphrased</span>'
        '<span class="block compressed" style="padding:1px 8px">compressed</span>'
        '<span class="block unsupported" style="padding:1px 8px">unsupported</span>'
        '</div>',
    ]

    for p in alignment_files:
        alignment = json.loads(p.read_text())
        parts.append(_render_chapter(alignment))

    parts.append("</body></html>")
    out_path = book.work_dir / "proofread.html"
    out_path.write_text("\n".join(parts))
    return out_path
