"""Clean reading editions derived from completed assembled text, without providers."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .assemble import _plain_text_export, _segment_heading
from .production_state import confined_path


LICENSE = {
    "name": "Creative Commons Attribution 4.0 International",
    "short_name": "CC BY 4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "owner": "Abridged Too Far",
    "copyright": "Original editorial contributions by Abridged Too Far: Copyright © Abridged Too Far, to the extent copyright applies. Reviewer contributions remain copyright their respective authors.",
    "permissions": "You may share and adapt these contributions, including commercially, with appropriate credit, a link to the license, and an indication of changes.",
    "scope": "This license covers original editorial contributions to the abridged edition by Abridged Too Far and reviewer contributions submitted under its CC BY 4.0 contribution terms. The original source text and other third-party material retain their existing rights. No additional restrictions are imposed on material in the public domain.",
}


def completed_text(root: Path, manifest: dict | None = None) -> str:
    """Read an authoritative complete assembly, never synthesize one from drafts."""
    if manifest is None:
        report_path = confined_path(root, 'assembly_report.json')
        if not report_path.is_file():
            raise FileNotFoundError('A completed reading edition is not available yet.')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if not isinstance(report, dict):
            raise ValueError('Invalid assembly report.')
        if (report.get('partial') is not False or type(report.get('segments_missing')) is not int
                or report['segments_missing'] != 0 or type(report.get('segments_drafted')) is not int
                or report['segments_drafted'] <= 0):
            raise FileNotFoundError('A completed reading edition is not available yet.')
        allowed = {'abridgment.txt', 'abridgment.md'}
    else:
        # ArtifactStore has verified the immutable inventory and completion
        # record before calling here. Only consume its inventoried outputs.
        allowed = {item['path'] for item in manifest['outputs']}
    for name in ('abridgment.txt', 'abridgment.md'):
        if name not in allowed:
            continue
        path = confined_path(root, name)
        if path.is_file():
            content = path.read_text(encoding='utf-8')
            if name.endswith('.md'):
                content = _plain_text_export(content)
            if content.strip():
                return content
    raise FileNotFoundError('A completed reading edition is not available yet.')


def _normalized(text: str) -> str:
    return ' '.join(text.split())


def _chapter_boundaries(text: str, root: Path, plan: dict, manifest: dict | None) -> list[tuple[int, str]]:
    """Use alignment only to locate chapters within the assembled book.

    If an old alignment differs from the assembly, fall back to the full text.
    A stale alignment can never replace, omit, or reorder the reading prose.
    """
    words = list(re.finditer(r'\S+', text))
    normalized = ' '.join(word[0] for word in words)
    offsets, position = {}, 0
    for word in words:
        offsets[position] = word.start()
        position += len(word[0]) + 1
    allowed = {item['path'] for item in manifest['outputs']} if manifest else None
    boundaries, cursor = [], 0
    for segment in plan.get('segments', []):
        sid = str(segment.get('id', ''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', sid):
            continue
        relative = f'alignments/{sid}.json'
        if allowed is not None and relative not in allowed:
            continue
        path = confined_path(root, relative)
        if not path.is_file():
            continue
        alignment = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(alignment, dict):
            return []
        paragraphs = alignment.get('draft_paragraphs', [])
        if not isinstance(paragraphs, list) or any(not isinstance(p, str) for p in paragraphs):
            return []
        body = _normalized(_plain_text_export('\n\n'.join(paragraphs)))
        if not body:
            continue
        title = _segment_heading(segment) or f'Chapter {len(boundaries) + 1}'
        found = normalized.find(body, cursor)
        if found < 0 or found not in offsets:
            return []
        gap = normalized[cursor:found].strip()
        headings = {_normalized(str(segment.get(key) or '')) for key in ('title', 'raw_heading')}
        headings.add(_normalized(title))
        if gap and gap not in headings:
            return []
        # Include an existing chapter heading in the canonical slice.
        start = offsets.get(cursor, offsets[found]) if gap else offsets[found]
        boundaries.append((start, title))
        cursor = found + len(body)
        if cursor < len(normalized) and normalized[cursor] == ' ':
            cursor += 1
    if normalized[cursor:].strip():
        return []
    return boundaries


def _heading_boundaries(text: str, plan: dict) -> list[tuple[int, str]]:
    """Locate existing, whole-paragraph chapter headings in older assemblies."""
    headings = {}
    for index, segment in enumerate(plan.get('segments', [])):
        for heading in (_segment_heading(segment), segment.get('raw_heading'), segment.get('title')):
            if heading:
                headings.setdefault(_normalized(str(heading)), index)
    boundaries, cursor, previous = [], 0, -1
    for separator in [*re.finditer(r'\n[ \t]*\n+', text), None]:
        end = separator.start() if separator else len(text)
        paragraph = text[cursor:end].strip()
        index = headings.get(_normalized(paragraph))
        if index is not None and index > previous:
            boundaries.append((cursor, paragraph))
            previous = index
        cursor = separator.end() if separator else len(text)
    if boundaries and text[:boundaries[0][0]].strip():
        boundaries.insert(0, (0, 'Opening'))
    return boundaries


def reading_document(root: Path, book_id: str, metadata: dict, plan: dict,
                     manifest: dict | None = None) -> dict:
    if (not isinstance(plan, dict) or not isinstance(plan.get('segments', []), list)
            or any(not isinstance(segment, dict) for segment in plan.get('segments', []))):
        raise ValueError('Invalid reading plan.')
    content = completed_text(root, manifest)
    title = str(metadata.get('title') or plan.get('title') or book_id)
    author = str(metadata.get('author') or plan.get('author') or '')
    boundaries = _chapter_boundaries(content, root, plan, manifest)
    if not boundaries:
        boundaries = _heading_boundaries(content, plan)
    if not boundaries:
        # Older assemblies may have no matching chapter inventory. Preserve
        # the entire completed book instead of presenting partial chapters.
        boundaries = [(0, 'The complete book')]
    chapters = []
    for index, (start, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(content)
        paragraphs = [part.strip() for part in re.split(r'\n\s*\n', content[start:end]) if part.strip()]
        if paragraphs and _normalized(paragraphs[0]) == _normalized(heading):
            paragraphs.pop(0)
        chapters.append({'id': str(index + 1), 'title': heading, 'paragraphs': paragraphs})
    notice = dict(LICENSE)
    notice['attribution'] = f'{title}' + (f' by {author}' if author else '') + '; abridged edition by Abridged Too Far. Editorial review credit: Abridged Too Far contributors. Original editorial contributions licensed under CC BY 4.0.'
    identity = json.dumps({'title': title, 'author': author, 'text': content, 'license': notice}, sort_keys=True)
    return {'book_id': book_id, 'title': title, 'author': author, 'chapters': chapters,
            'word_count': len(content.split()), 'text': content, 'license': notice,
            'edition_id': hashlib.sha256(identity.encode('utf-8')).hexdigest(),
            'publication_revision': manifest['revision'] if manifest else None}


def plain_text_download(book: dict) -> str:
    """Add attribution and scoped license without changing the assembled prose."""
    credit = book['license']
    heading = book['title'] + (f"\nby {book['author']}" if book['author'] else '')
    notice = '\n\n'.join((credit['copyright'], f"{credit['name']} ({credit['short_name']})\n{credit['url']}",
                          credit['permissions'], credit['scope'], 'Attribution: ' + credit['attribution']))
    return f"{heading}\nAbridged edition by {credit['owner']}\n\n{book['text'].rstrip()}\n\n---\nCopyright and license\n\n{notice}\n"
