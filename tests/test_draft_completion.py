"""Offline completion regressions for both providers and merged drafts."""
import json
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from forage import drafter, llm
from forage.artifacts import Book, write_json
from forage.assemble import assemble_book


@pytest.fixture
def book_plan(tmp_path, monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith('FORAGE_'):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('FORAGE_DRAFT_THINKING', 'medium')
    source = tmp_path / 'books' / 'sample' / 'source.txt'
    source.parent.mkdir(parents=True)
    source.write_text('Original source.')
    work = tmp_path / 'work' / 'sample'
    (work / 'chapters').mkdir(parents=True)
    (work / 'segments').mkdir()
    segments = []
    for sid in ('001', '002'):
        (work / 'chapters' / f'{sid}.md').write_text('Original source.\n' * 100)
        segments.append(dict(id=sid, title=f'Chapter {sid}', source_word_count=200,
                             target_word_count=100, diegetic_status='diegetic'))
    plan = dict(title='Sample', segments=segments, _meta={'builder': 'lean_plan'})
    write_json(work / 'plan.json', plan)
    # No accidental paid fallback if a test forgets to supply a response.
    monkeypatch.setattr(drafter, 'complete', Mock(side_effect=AssertionError('unexpected provider call')))
    return Book('sample', source, {}, work), plan


def response(text, reason='end_turn'):
    return llm.LLMResponse(text, 'anthropic:fixture', 10, 10, 0, reason)


def grouped(plan):
    for segment in plan['segments']:
        segment['group_id'] = 'g001'
    plan['merged_groups'] = {'g001': dict(member_ids=['001', '002'],
        combined_source_word_count=400, combined_target_word_count=200)}


@pytest.mark.parametrize('reason', ['max_tokens', 'length'])
@pytest.mark.parametrize('group', [False, True])
def test_truncation_never_assembles(book_plan, monkeypatch, reason, group):
    book, plan = book_plan
    if group:
        grouped(plan)
    fake = Mock(return_value=response('## Chapter 1\nA complete beginning.\n\n## Chapter 2\nThen he', reason))
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', fake)
    result = drafter.draft_segment(book, plan, '001')
    assert result.status == 'truncated'
    if group:
        assert drafter.draft_segment(book, plan, '002').status == 'truncated'
        assert fake.call_count == 1
        assert all(json.loads((book.work_dir / 'segments' / f'{s}.checks.json').read_text())['status'] == 'truncated'
                   for s in ('001', '002'))
    assembled = assemble_book(book, plan)
    assert assembled.segments_missing == 2
    assert assembled.abridgment_path is None
    assert not (book.source_path.parent / 'abridgment.txt').exists()


@pytest.mark.parametrize('reason', ['end_turn', 'stop', 'max_tokens', 'length', 'content_filter'])
@pytest.mark.parametrize('group', [False, True])
def test_empty_response_is_missing(book_plan, monkeypatch, reason, group):
    book, plan = book_plan
    if group:
        grouped(plan)
    fake = Mock(return_value=response('', reason))
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', fake)
    result = drafter.draft_segment(book, plan, '001')
    assert result.status in {'error', 'truncated'}
    if group:
        assert drafter.draft_segment(book, plan, '002').status in {'error', 'truncated'}
        assert fake.call_count == 1
    assert assemble_book(book, plan).segments_missing == 2


def test_group_success_generates_once_and_reuses(book_plan, monkeypatch):
    book, plan = book_plan
    grouped(plan)
    fake = Mock(return_value=response('## Chapter 1\nA whole beginning.\n\n## Chapter 2\nA whole ending.'))
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', fake)
    assert [r.status for r in drafter.draft_all(book, plan)] == ['drafted', 'drafted']
    assert [r.status for r in drafter.draft_all(book, plan)] == ['drafted', 'drafted']
    assert fake.call_count == 1
    assert assemble_book(book, plan).segments_missing == 0


def test_failed_group_retries_once_on_next_pass(book_plan, monkeypatch):
    book, plan = book_plan
    grouped(plan)
    fake = Mock(side_effect=[response('## Chapter 1\nPartial\n## Chapter 2\nPartial', 'length'),
                            response('## Chapter 1\nDone.\n## Chapter 2\nDone.')])
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', fake)
    assert [r.status for r in drafter.draft_all(book, plan)] == ['truncated', 'truncated']
    assert [r.status for r in drafter.draft_all(book, plan)] == ['drafted', 'drafted']
    assert fake.call_count == 2


@pytest.mark.parametrize('checks', [None, '{', '[]', '{}', '{"status":[]}', '{"status":"error"}', '{"status":"truncated"}'])
def test_disk_cannot_infer_success_from_nonempty_text(book_plan, checks):
    book, plan = book_plan
    seg_dir = book.work_dir / 'segments'
    (seg_dir / '001.md').write_text('Partial old draft.')
    if checks is not None:
        (seg_dir / '001.checks.json').write_text(checks)
    result = drafter._disk_draft_result(seg_dir, plan['segments'][0])
    assert result.status == ('truncated' if checks and 'truncated' in checks else 'error')


@pytest.mark.parametrize('group', [False, True])
@pytest.mark.parametrize('fallback', ['exception', 'content_filter'])
def test_fallback_truncation_is_rejected(book_plan, monkeypatch, group, fallback):
    book, plan = book_plan
    if group:
        grouped(plan)
    monkeypatch.setenv('FORAGE_DRAFT_MODEL', 'openai:fixture')
    first = RuntimeError('provider failed') if fallback == 'exception' else response('blocked', 'content_filter')
    fake = Mock(side_effect=[first, response('## Chapter 1\nPartial\n## Chapter 2\nPartial', 'length')])
    monkeypatch.setattr(drafter, 'complete', fake)
    assert drafter.draft_segment(book, plan, '001').status == 'truncated'
    assert fake.call_count == 2


@pytest.mark.parametrize('reason', ['max_tokens', 'length'])
@pytest.mark.parametrize('group', [False, True])
def test_old_replay_completion_reasons(book_plan, monkeypatch, reason, group):
    book, plan = book_plan
    if group:
        grouped(plan)
    monkeypatch.setenv('FORAGE_REPLAY', '1')
    monkeypatch.setattr(llm, '_replay_load', lambda key: {'response': asdict(response('## Chapter 1\nPartial\n## Chapter 2\nPartial', reason))})
    monkeypatch.setattr(llm, '_anthropic', Mock(side_effect=AssertionError('live call')))
    monkeypatch.setattr(llm, '_openai', Mock(side_effect=AssertionError('live call')))
    monkeypatch.setattr(drafter, 'complete', llm.complete)
    assert drafter.draft_segment(book, plan, '001').status == 'truncated'


@pytest.mark.parametrize('mode', ['extradiegetic', 'zero_target', 'response_cut', 'success'])
def test_success_and_cut_semantics(book_plan, monkeypatch, mode):
    book, plan = book_plan
    segment = plan['segments'][0]
    if mode == 'extradiegetic':
        segment['diegetic_status'] = 'extradiegetic'
    if mode == 'zero_target':
        segment['target_word_count'] = 0
    fake = Mock(return_value=response('A complete chapter.' if mode == 'success' else 'CUT'))
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', fake)
    assert drafter.draft_segment(book, plan, '001').status == ('drafted' if mode == 'success' else 'cut')
    assert fake.call_count == (mode in {'response_cut', 'success'})


def test_reduced_thinking_retry_obeys_final_completion(book_plan, monkeypatch):
    book, plan = book_plan
    monkeypatch.setenv('FORAGE_DRAFT_THINKING', 'max')
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', Mock(return_value=response('', 'max_tokens')))
    fake = Mock(return_value=response('Then he', 'length'))
    monkeypatch.setattr(drafter, 'complete', fake)
    assert drafter.draft_segment(book, plan, '001').status == 'truncated'
    assert fake.call_args.kwargs['thinking'] == 'medium'


@pytest.mark.parametrize('checks', [None, '{', '[]', '{}'])
def test_assembly_cannot_accept_unverified_group_splits(book_plan, checks):
    book, plan = book_plan
    grouped(plan)
    for sid in ('001', '002'):
        (book.work_dir / 'segments' / f'{sid}.md').write_text('An unverified split.')
        if checks is not None:
            (book.work_dir / 'segments' / f'{sid}.checks.json').write_text(checks)
    assert assemble_book(book, plan).segments_missing == 2


@pytest.mark.parametrize('group', [False, True])
def test_reduced_thinking_retry_preserves_final_cut_or_failure(book_plan, monkeypatch, group):
    book, plan = book_plan
    if group:
        grouped(plan)
    monkeypatch.setenv('FORAGE_DRAFT_THINKING', 'max')
    monkeypatch.setattr(drafter, '_complete_draft_with_exception_fallback', Mock(return_value=response('', 'length')))
    monkeypatch.setattr(drafter, 'complete', Mock(return_value=response('CUT' if not group else '', 'end_turn')))
    assert drafter.draft_segment(book, plan, '001').status == ('cut' if not group else 'error')
