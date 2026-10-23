"""Change marks belong to the source comparison, including substantial cuts."""
from html.parser import HTMLParser
import json

import pytest

from forage.proofread import source_comparisons, source_diff_html, _render_chapter, _sentence_comparison, _sentence_parts
from .conftest import BOOK_ID, SEGMENT_ID


class Text(HTMLParser):
    def __init__(self, exclude=None):
        super().__init__()
        self.exclude = exclude
        self.depth = 0
        self.text = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == self.exclude:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == self.exclude:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.text.append(data)


def text(markup, exclude=None):
    parser = Text(exclude)
    parser.feed(markup)
    return ''.join(parser.text)


@pytest.mark.parametrize('source,draft', [
    (['Keep. Cut this long digression entirely, including every remaining word.'], 'Keep.'),
    (['The door was closed.'], 'The window is open.'),
    (['Alice opened the door.', 'Bob watched the silent garden.'], 'Alice opened the door. Bob watched the garden.'),
    (['At dawn she left.'], 'Suddenly, at dawn she quietly left. Later she returned.'),
    (['<script>alert("source")</script> & words'], '<img src=x onerror=alert(1)> & other'),
    (['First.', 'Second.'], 'A completely different sentence.'),
    ([''], 'Added.'),
    (['Gone completely.'], ''),
])
def test_source_text_and_paragraph_boundaries_survive_markup(source, draft):
    rendered = source_diff_html(source, draft)
    assert len(rendered) == len(source)
    assert [text(part, 'ins') for part in rendered] == source
    assert ' '.join(' '.join(text(part, 'del') for part in rendered).split()) == ' '.join(draft.split())
    parser = Text()
    parser.feed(''.join(rendered))
    assert set(parser.tags) <= {'ins', 'del'}
    assert parser.tags


def test_typographic_only_changes_keep_source_spelling_without_highlights():
    source = '“Don’t\nleave,” she said.\u00a0Wait.'
    draft = '"Don\'t leave," she said. Wait.'
    rendered = source_diff_html([source], draft)[0]
    assert '<ins>' not in rendered and '<del>' not in rendered
    assert text(rendered) == source


def test_rewritten_phrases_are_not_fragmented_by_matching_spaces():
    source = 'The old house stood among tall trees.'
    draft = 'A cottage overlooked the river.'
    assert source_diff_html([source], draft) == [f'<del>{source}</del><ins>{draft}</ins>']


def test_retained_phrase_in_later_source_is_not_mistaken_for_new_wording():
    source = ['Alice opened the door. She paused to consider the long journey and the many roads she might take.',
              'Bob watched the silent garden.']
    draft = 'Alice opened the door. She hurried outside. Bob watched the garden.'
    rendered = source_diff_html(source, draft)
    assert rendered[1] == 'Bob watched the <del>silent </del>garden.'
    assert '<ins>hurried outside. </ins>' in rendered[0]


@pytest.mark.parametrize('label', ['verbatim', 'paraphrased', 'compressed', 'unsupported', 'unknown'])
def test_alignment_labels_never_suppress_readable_source_highlights(label):
    alignment = {'source_paragraphs': ['She opened the old door.'],
                 'draft_paragraphs': ['She opened the new door.'],
                 'mapping': [{'draft_para': 0, 'source_paras': [0], 'note': label}]}
    rendered = source_comparisons(alignment)[0]['sources'][0]['diff_html']
    assert '<del>' in rendered and '<ins>' in rendered


def test_split_and_merged_mappings_compare_all_retained_draft_text_once():
    alignment = {'source_paragraphs': ['Alice woke. Bob slept.', 'Clara left.'],
                 'draft_paragraphs': ['Alice woke.', 'Bob slept. Clara left.'],
                 'mapping': [{'draft_para': 1, 'source_paras': [1, 0, 0]},
                             {'draft_para': 0, 'source_paras': [0]}]}
    comparisons = source_comparisons(alignment)
    for index, comparison in comparisons.items():
        assert comparison['draft_paras'] == [0, 1]
        for source in comparison['sources']:
            assert '<del>' not in source['diff_html'] and '<ins>' not in source['diff_html']
            assert text(source['diff_html']) == source['text']
    assert [s['index'] for s in comparisons[1]['sources']] == [0, 1]


def test_unmatched_draft_is_explicitly_added_and_escaped():
    comparisons = source_comparisons({'source_paragraphs': [], 'draft_paragraphs': ['New <b>text</b>.'],
        'mapping': [{'draft_para': 0, 'source_paras': []}]})
    assert comparisons[0]['sources'] == []
    assert comparisons[0]['addition_html'] == '<ins>New &lt;b&gt;text&lt;/b&gt;.</ins>'


def test_api_and_static_proofread_keep_draft_clean_and_annotate_all_sources(client, artifact_tree):
    alignment = {'segment_id': SEGMENT_ID,
        'source_paragraphs': ['Keep this opening. Change the old middle.', 'Keep the ending.', 'Wholly cut paragraph.'],
        'draft_paragraphs': ['Keep this opening. Change the new middle. Keep the ending.', 'An unmatched addition.'],
        'mapping': [{'draft_para': 0, 'source_paras': [0, 1], 'note': 'compressed'},
                    {'draft_para': 1, 'source_paras': [], 'note': 'unsupported'}]}
    (artifact_tree/'work'/BOOK_ID/'alignments'/f'{SEGMENT_ID}.json').write_text(json.dumps(alignment))
    response = client.get(f'/api/books/{BOOK_ID}/chapters/{SEGMENT_ID}')
    assert response.status_code == 200
    chapter = response.json()
    first, second = chapter['blocks']
    assert first['draft'] == alignment['draft_paragraphs'][0]
    assert 'diff_html' not in first
    assert '<del>' in first['sources'][0]['diff_html']
    assert '<ins>' in first['sources'][0]['diff_html']
    assert second['source_addition_html'] == '<ins>An unmatched addition.</ins>'
    assert chapter['unused'] == [{'index': 2, 'text': 'Wholly cut paragraph.'}]
    markup = _render_chapter(alignment)
    for draft in alignment['draft_paragraphs']:
        assert f'<div class="draft">{draft}</div>' in markup
    assert '<del>Wholly cut paragraph.</del>' in markup
    assert first['sources'][0]['diff_html'] in markup


@pytest.mark.parametrize('source,draft', [
    ('She was very tired, so she went home.', 'Exhausted, she returned home.'),
    ('The old house stood among tall trees.', 'A cottage overlooked the river.'),
    ('<script>alert("source")</script>', '<img src=x onerror=alert(1)>'),
])
def test_substantial_rewrites_keep_escaped_source_plain_with_explanation(source, draft):
    rendered = _sentence_comparison([source], draft)[0]
    assert text(rendered['diff_html']) == source
    assert '<del>' not in rendered['diff_html'] and '<ins>' not in rendered['diff_html']
    assert '<script>' not in rendered['diff_html']
    assert 'without highlights' in rendered['comparison_note']


def test_rewrite_does_not_hide_neighboring_small_change_or_clear_cut():
    source = ['She opened the old door. The old house stood among tall trees. She left.',
              'This paragraph was removed entirely.']
    draft = 'She opened the new door. A cottage overlooked the river. She left.'
    rendered = _sentence_comparison(source, draft)
    assert '<del>old </del><ins>new </ins>' in rendered[0]['diff_html']
    assert 'The old house stood among tall trees.' in rendered[0]['diff_html']
    assert 'without highlights' in rendered[0]['comparison_note']
    assert rendered[1]['diff_html'] == '<del>This paragraph was removed entirely.</del>'
    assert rendered[1]['comparison_note'] is None
    assert [text(r['diff_html'], 'ins') for r in rendered] == source


def test_moved_sentences_are_plain_and_explained_without_hiding_duplicate_cut():
    source = ['Alice opened the door. Bob lit the lamp. Alice opened the door.']
    rendered = _sentence_comparison(source, 'Bob lit the lamp. Alice opened the door.')[0]
    assert rendered['diff_html'].count('<del>') == 1
    assert '<ins>' not in rendered['diff_html']
    assert text(rendered['diff_html'], 'ins') == source[0]
    moved = _sentence_comparison(['Alice opened the door. Bob lit the lamp.'],
                                 'Bob lit the lamp. Alice opened the door.')[0]
    assert '<del>' not in moved['diff_html'] and '<ins>' not in moved['diff_html']
    assert moved['comparison_note'] == 'Sentence order changed.'


@pytest.mark.parametrize('source,draft', [
    (['Alice opened the door and quietly entered the house.'], 'Alice opened the door. She quietly entered the house.'),
    (['Alice opened the door. She quietly entered the house.'], 'Alice opened the door and quietly entered the house.'),
    (['She opened the heavy old wooden door.'], 'She opened the door.'),
    (['She went home.'], 'She returned home.'),
    (['Gone completely.'], ''),
    ([''], 'Added.'),
    (['First.'], 'First. Added afterward.'),
    (['Last.'], 'Added before. Last.'),
])
def test_sentence_comparisons_preserve_readable_edits_and_pure_additions_or_cuts(source, draft):
    rendered = _sentence_comparison(source, draft)
    assert all(r['comparison_note'] is None for r in rendered)
    assert [text(r['diff_html'], 'ins') for r in rendered] == source
    assert ' '.join(' '.join(text(r['diff_html'], 'del') for r in rendered).split()) == ' '.join(draft.split())
    assert any('<del>' in r['diff_html'] or '<ins>' in r['diff_html'] for r in rendered)


def test_sentence_boundaries_preserve_titles_initials_decimals_and_dialogue():
    source = 'Mr. J. Brown paid 3.50. “Why?” she asked. He left.\nNext came Dr. Smith.'
    parts = _sentence_parts(source)
    assert parts == ['Mr. J. Brown paid 3.50. ', '“Why?” she asked. ', 'He left.\n', 'Next came Dr. Smith.']
    assert ''.join(parts) == source


def test_api_and_static_report_explain_unhighlighted_rewrites(client, artifact_tree):
    alignment = {'segment_id': SEGMENT_ID,
        'source_paragraphs': ['The old house stood among tall trees.'],
        'draft_paragraphs': ['A cottage overlooked the river.'],
        'mapping': [{'draft_para': 0, 'source_paras': [0], 'note': 'paraphrased'}]}
    (artifact_tree/'work'/BOOK_ID/'alignments'/f'{SEGMENT_ID}.json').write_text(json.dumps(alignment))
    response = client.get(f'/api/books/{BOOK_ID}/chapters/{SEGMENT_ID}')
    assert response.status_code == 200
    source = response.json()['blocks'][0]['sources'][0]
    assert source['diff_html'] == alignment['source_paragraphs'][0]
    assert source['comparison_note'] in _render_chapter(alignment)
    assert 'without highlights' in source['comparison_note']
