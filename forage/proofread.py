"""Proofreading HTML renderer.

Reads work/<book>/alignments/*.json and emits a single static HTML file at
work/<book>/proofread.html. For each chapter and draft paragraph, shows the
draft text and the source paragraph(s) it was aligned to, stacked.
"""

from __future__ import annotations

import difflib
from collections import defaultdict, deque
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
.source-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.source ins, .legend ins { text-decoration: underline; text-underline-offset: 0.15em; }
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
_QUOTE_NORMALIZE = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u00a0": " ",
})


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _visual_diff_key(text: str) -> str:
    """Collapse differences that render as editorial noise in the galley."""
    return " ".join(text.translate(_QUOTE_NORMALIZE).split())


def _token_diff_key(token: str) -> str:
    """Normalize a single diff token without erasing word boundaries."""
    normalized = token.translate(_QUOTE_NORMALIZE)
    if not normalized.strip():
        return " "
    return normalized


def _token_diff_keys(tokens: list[str]) -> list[str]:
    return [_token_diff_key(token) for token in tokens]


def word_diff_html(source: str, draft: str) -> str:
    """Inline word-level diff rendered as HTML with <ins>/<del> markers.
    Only meaningful when source and draft are close in length + content."""
    if _visual_diff_key(source) == _visual_diff_key(draft):
        return html.escape(draft)

    a = _tokenize(source)
    b = _tokenize(draft)
    sm = difflib.SequenceMatcher(a=_token_diff_keys(a),
                                 b=_token_diff_keys(b),
                                 autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_seg = "".join(a[i1:i2])
        b_seg = "".join(b[j1:j2])
        if tag == "equal":
            out.append(html.escape(b_seg))
        elif tag == "replace":
            # Whitespace-only differences (e.g. source has \n, draft has space)
            # are visual noise — render the draft's whitespace unchanged rather
            # than wrapping empty <del>/<ins>, which would drop the whitespace
            # entirely.
            if (_visual_diff_key(a_seg) == _visual_diff_key(b_seg)
                    or (not a_seg.strip() and not b_seg.strip())):
                out.append(html.escape(b_seg or a_seg))
            else:
                if a_seg.strip():
                    out.append(f"<del>{html.escape(a_seg)}</del>")
                if b_seg.strip():
                    out.append(f"<ins>{html.escape(b_seg)}</ins>")
        elif tag == "delete":
            if a_seg.strip():
                out.append(f"<del>{html.escape(a_seg)}</del>")
            else:
                out.append(html.escape(a_seg))
        elif tag == "insert":
            if b_seg.strip():
                out.append(f"<ins>{html.escape(b_seg)}</ins>")
            else:
                out.append(html.escape(b_seg))
    return "".join(out)


def should_word_diff(note_key: str, source: str, draft: str) -> bool:
    """Show word-level diff only when the two texts are close enough that a
    word-level view is readable. Skip when the edit is paragraph-scale."""
    if note_key not in ("verbatim", "paraphrased"):
        return False
    if not source.strip() or not draft.strip():
        return False
    # Straight vs curly quotes/apostrophes and source line wrapping are not
    # useful review diffs. Suppress those no-op highlights entirely.
    if _visual_diff_key(source) == _visual_diff_key(draft):
        return False
    # Length guardrail: if the two diverge by more than 40% in length the diff
    # becomes mostly insert/delete blocks and isn't useful.
    la, lb = len(source), len(draft)
    ratio = min(la, lb) / max(la, lb)
    if ratio < 0.6:
        return False
    # Similarity guardrail: if the sequences share less than ~50% of content
    # the diff view is noisier than a stacked view.
    sm = difflib.SequenceMatcher(a=_token_diff_keys(_tokenize(source)),
                                 b=_token_diff_keys(_tokenize(draft)),
                                 autojunk=False)
    if sm.ratio() < 0.5:
        return False
    return True


def source_diff_html(paragraphs: list[str], draft: str) -> list[str]:
    """Annotate original source paragraphs, retaining their text and boundaries.

    Insertions appear beside their source location. Whitespace and quote-style
    changes alone are ignored; unchanged words keep the source's typography.
    This low-level renderer always emits a full diff; the sentence comparison
    layer decides whether that diff would be readable.
    """
    tokens, owners = [], []
    for index, paragraph in enumerate(paragraphs):
        if index:
            tokens.append('\n\n')
            owners.append(None)
        words = _tokenize(paragraph)
        tokens.extend(words)
        owners.extend([index] * len(words))
    if not paragraphs:
        return []
    revised = _tokenize(draft)
    # Align words rather than spaces, retaining token offsets for rendering.
    # This keeps real phrases together without letting repeated whitespace
    # anchor unrelated wording (or fragment a retained phrase).
    source_words = [i for i, token in enumerate(tokens) if token.strip()]
    draft_words = [i for i, token in enumerate(revised) if token.strip()]
    if not source_words:
        rendered = [html.escape(paragraph) for paragraph in paragraphs]
        if draft.strip():
            rendered[0] += f'<ins>{html.escape(draft)}</ins>'
        return rendered
    source_edges = [0, *source_words[1:], len(tokens)]
    draft_edges = [0, *draft_words[1:], len(revised)]
    matcher = difflib.SequenceMatcher(a=[_token_diff_key(tokens[i]) for i in source_words],
                                     b=[_token_diff_key(revised[i]) for i in draft_words], autojunk=False)
    rendered = [[] for _ in paragraphs]

    def source_span(start, end, deleted=False):
        # Split markers at paragraph boundaries; never put a paragraph ID or
        # a neighboring paragraph inside an open deletion tag.
        while start < end:
            owner = owners[start]
            stop = start + 1
            while stop < end and owners[stop] == owner:
                stop += 1
            if owner is not None:
                text = ''.join(tokens[start:stop])
                escaped = html.escape(text)
                rendered[owner].append(f'<del>{escaped}</del>' if deleted and text.strip() else escaped)
            start = stop

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        i1, i2 = source_edges[i1], source_edges[i2]
        j1, j2 = draft_edges[j1], draft_edges[j2]
        original, replacement = ''.join(tokens[i1:i2]), ''.join(revised[j1:j2])
        equivalent = _visual_diff_key(original) == _visual_diff_key(replacement)
        source_span(i1, i2, deleted=tag in {'delete', 'replace'} and not equivalent)
        if tag in {'insert', 'replace'} and replacement.strip() and not equivalent:
            if i1 and tokens[i1 - 1].strip() and j1 and not revised[j1 - 1].strip():
                replacement = revised[j1 - 1] + replacement
            # Replacements follow the removed wording; insertions precede the
            # next source token (or follow the last one at the end).
            candidates = (list(reversed(owners[i1:i2])) if tag == 'replace' else [])
            candidates += owners[i2:] + list(reversed(owners[:i1]))
            owner = next((index for index in candidates if index is not None), 0)
            rendered[owner].append(f'<ins>{html.escape(replacement)}</ins>')
    return [''.join(parts) for parts in rendered]


_SENTENCE_END = re.compile(r'''[.!?]+[”’"')\]]*\s+''')
_ABBREVIATIONS = {'mr', 'mrs', 'ms', 'dr', 'prof', 'rev', 'st', 'sr', 'jr', 'capt', 'col', 'gen', 'etc', 'vs'}
_WORDS = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def _sentence_parts(text: str) -> list[str]:
    """Conservative sentence boundaries, retaining every original character."""
    parts, start = [], 0
    for match in _SENTENCE_END.finditer(text):
        before = text[:match.start()]
        word = re.search(r'(\w+)$', before)
        if text[match.start()] == '.' and word:
            if word[1].lower() in _ABBREVIATIONS or (len(word[1]) == 1 and word[1].isupper()):
                continue
        # Keep dialogue attribution with its quotation: “Why?” she asked.
        following = text[match.end():].lstrip('“‘"\'')
        if following and following[0].islower():
            continue
        parts.append(text[start:match.end()])
        start = match.end()
    if start < len(text) or not parts:
        parts.append(text[start:])
    return parts


def _word_overlap(source: str, draft: str) -> tuple[float, bool]:
    """Readability heuristic, not a judgment of semantic equivalence.

    Preserve useful compression diffs when most of the shorter text survives.
    Otherwise require a majority of shared wording, including at least three
    words (or all but one word in a short sentence).
    """
    a = _WORDS.findall(source.translate(_QUOTE_NORMALIZE).casefold())
    b = _WORDS.findall(draft.translate(_QUOTE_NORMALIZE).casefold())
    if not a or not b:
        return 0.0, _visual_diff_key(source) == _visual_diff_key(draft)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    retained = sum(match.size for match in matcher.get_matching_blocks())
    shorter = min(len(a), len(b))
    readable = retained >= min(3, max(1, shorter - 1)) and (retained / shorter >= 0.75 or matcher.ratio() >= 0.55)
    return matcher.ratio(), readable


def _sentence_comparison(paragraphs: list[str], draft: str) -> list[dict]:
    """Anchor sentences before diffing words; leave uncertain rewrites plain."""
    units = [(owner, part) for owner, paragraph in enumerate(paragraphs)
             for part in _sentence_parts(paragraph)]
    draft_paragraphs = draft.split('\n\n')
    revised = [part for i, paragraph in enumerate(draft_paragraphs)
               for part in _sentence_parts(paragraph + ('\n\n' if i + 1 < len(draft_paragraphs) else ''))
               if part.strip()]
    source_keys = [_visual_diff_key(part) for _, part in units]
    draft_keys = [_visual_diff_key(part) for part in revised]
    matcher = difflib.SequenceMatcher(a=source_keys, b=draft_keys, autojunk=False)
    paired = {i + offset: j + offset for i, j, size in matcher.get_matching_blocks()
              for offset in range(size)}
    # Match remaining identical sentences by occurrence, even when reordered.
    # Repeated sentences are consumed only once, so genuine cuts stay visible.
    remaining = defaultdict(deque)
    used_drafts = set(paired.values())
    for j, key in enumerate(draft_keys):
        if j not in used_drafts and key:
            remaining[key].append(j)
    moved = set()
    for i, key in enumerate(source_keys):
        if i not in paired and remaining[key]:
            paired[i] = remaining[key].popleft()
            moved.add(i)
    used_drafts = set(paired.values())
    rendered = [html.escape(part) for _, part in units]
    before, after = defaultdict(list), defaultdict(list)
    suppressed = set()

    def render_region(source_ids, draft_ids, next_source):
        if not source_ids:
            added = ''.join(revised[j] for j in draft_ids)
            if added.strip():
                if draft_ids[0] > 0 and not added[0].isspace():
                    added = ' ' + added
                markup = f'<ins>{html.escape(added)}</ins>'
                if next_source < len(units):
                    before[next_source].append(markup)
                elif units:
                    after[len(units) - 1].append(markup)
            return
        if not draft_ids:
            for i in source_ids:
                part = units[i][1]
                rendered[i] = f'<del>{html.escape(part)}</del>' if part.strip() else html.escape(part)
            return
        # Similar sentences provide additional anchors inside changed runs.
        # One-to-many runs remain together so split/merged sentences can retain
        # their wording without creating false deletions.
        if len(source_ids) > 1 and len(draft_ids) > 1:
            candidates = []
            for si, i in enumerate(source_ids):
                for dj, j in enumerate(draft_ids):
                    score, readable = _word_overlap(units[i][1], revised[j])
                    if readable and score >= 0.6:
                        candidates.append((score, -abs(si - dj), -si, -dj))
            if candidates:
                _, _, si, dj = max(candidates)
                si, dj = -si, -dj
                render_region(source_ids[:si], draft_ids[:dj], source_ids[si])
                render_region([source_ids[si]], [draft_ids[dj]], source_ids[si] + 1)
                render_region(source_ids[si + 1:], draft_ids[dj + 1:], next_source)
                return
        original = [units[i][1] for i in source_ids]
        replacement = ''.join(revised[j] for j in draft_ids)
        _, readable = _word_overlap(' '.join(original), replacement)
        if readable or not ''.join(original).strip():
            for i, markup in zip(source_ids, source_diff_html(original, replacement)):
                rendered[i] = markup
        else:
            suppressed.update(source_ids)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            render_region([i for i in range(i1, i2) if i not in paired],
                          [j for j in range(j1, j2) if j not in used_drafts], i2)
    result = []
    for owner in range(len(paragraphs)):
        indices = [i for i, (paragraph, _) in enumerate(units) if paragraph == owner]
        notes = []
        if any(i in suppressed for i in indices):
            notes.append('Contains substantial rewriting shown without highlights.')
        if any(i in moved for i in indices):
            notes.append('Sentence order changed.')
        result.append({'diff_html': ''.join(''.join(before[i]) + rendered[i] + ''.join(after[i]) for i in indices),
                       'comparison_note': ' '.join(notes) or None})
    return result


def source_comparisons(alignment: dict) -> dict[int, dict]:
    """Compare connected source/draft groups once, including split paragraphs.

    A source paragraph reused by two draft paragraphs must be compared with
    both; comparing each in isolation falsely labels the other half as cut.
    """
    sources = alignment.get('source_paragraphs', [])
    drafts = alignment.get('draft_paragraphs', [])
    draft_sources = {}
    source_drafts = defaultdict(set)
    for item in alignment.get('mapping', []):
        index = item.get('draft_para')
        if type(index) is not int or not 0 <= index < len(drafts):
            continue
        indices = sorted({i for i in item.get('source_paras', []) or []
                          if type(i) is int and 0 <= i < len(sources)})
        draft_sources[index] = indices
        for source in indices:
            source_drafts[source].add(index)
    comparisons = {}
    for index, indices in draft_sources.items():
        if index in comparisons:
            continue
        if not indices:
            comparisons[index] = {'sources': [], 'draft_paras': [index],
                                  'addition_html': f'<ins>{html.escape(drafts[index])}</ins>'}
            continue
        pending, group_drafts, group_sources = [index], set(), set()
        while pending:
            current = pending.pop()
            if current in group_drafts:
                continue
            group_drafts.add(current)
            for source in draft_sources[current]:
                if source not in group_sources:
                    group_sources.add(source)
                    pending.extend(source_drafts[source] - group_drafts)
        ordered_sources, ordered_drafts = sorted(group_sources), sorted(group_drafts)
        annotated = _sentence_comparison([sources[i] for i in ordered_sources],
                                         '\n\n'.join(drafts[i] for i in ordered_drafts))
        by_source = dict(zip(ordered_sources, annotated))
        for current in ordered_drafts:
            comparisons[current] = {
                'sources': [{'index': i, 'text': sources[i], **by_source[i]}
                            for i in draft_sources[current]],
                'draft_paras': ordered_drafts, 'addition_html': None,
            }
    return comparisons


def _render_chapter(alignment: dict) -> str:
    sid = alignment["segment_id"]
    src_paras = alignment["source_paragraphs"]
    draft_paras = alignment["draft_paragraphs"]
    mapping = alignment["mapping"]
    comparisons = source_comparisons(alignment)

    # Bucket stats
    notes = [str(m.get("note", "")).split("—")[0].strip().lower() for m in mapping]
    counts = {k: notes.count(k) for k in ("verbatim", "paraphrased", "compressed", "unsupported")}
    used_src_ids = {source['index'] for comparison in comparisons.values()
                    for source in comparison['sources']}

    parts = [f'<h2>Chapter {sid} <span class="meta">— {len(draft_paras)} draft paras '
             f'from {len(src_paras)} source paras</span></h2>']
    stats = "  ·  ".join(f"{k}: {v}" for k, v in counts.items() if v > 0)
    parts.append(f'<div class="chapter-summary">{stats}</div>')

    for m in mapping:
        idx = m.get("draft_para")
        if type(idx) is not int or idx < 0 or idx >= len(draft_paras):
            continue
        note_raw = str(m.get("note", "")).strip()
        note_key = note_raw.split("—")[0].strip().lower()
        if note_key not in ("verbatim", "paraphrased", "compressed", "unsupported"):
            note_key = "unsupported"

        draft_text = draft_paras[idx]

        parts.append(f'<div class="block {note_key}">')
        parts.append(f'  <div class="note">{html.escape(note_raw or note_key)} · draft [{idx}]</div>')

        parts.append(f'  <div class="draft">{html.escape(draft_text)}</div>')
        comparison = comparisons[idx]
        parts.append('  <div class="source"><div class="diff-label">Source comparison</div>')
        if len(comparison['draft_paras']) > 1:
            parts.append(f'<div class="diff-label">Covers {len(comparison["draft_paras"])} abridged paragraphs</div>')
        for source in comparison['sources']:
            if source['comparison_note']:
                parts.append(f'<div class="diff-label">{html.escape(source["comparison_note"])}</div>')
            parts.append(f'<div class="source-text"><span class="para-id">src [{source["index"]}]</span>'
                         f'{source["diff_html"]}</div>')
        if comparison['addition_html']:
            parts.append('<div class="diff-label">No matched source passage</div>')
            parts.append(f'<div class="source-text">{comparison["addition_html"]}</div>')
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
                         f'<del>{html.escape(src_paras[si])}</del></div>')
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
        '<p class="legend">Source comparison: <del>removed from source</del> · '
        '<ins>added in abridgment</ins>. Substantial rewrites may be shown without highlights. '
        'Abridged text is shown without change marks.</p>',
    ]

    for p in alignment_files:
        alignment = json.loads(p.read_text())
        parts.append(_render_chapter(alignment))

    parts.append("</body></html>")
    out_path = book.work_dir / "proofread.html"
    out_path.write_text("\n".join(parts))
    return out_path
