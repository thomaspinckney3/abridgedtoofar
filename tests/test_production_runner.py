from collections import Counter
from dataclasses import asdict
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from typer.testing import CliRunner

from forage import production as p
from forage.artifacts import Book
from forage.production_state import atomic_json, load_state, sha256_file, digest
from forage.llm import LLMResponse


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    source = tmp_path / 'books' / 'sample' / 'source.txt'
    source.parent.mkdir(parents=True)
    source.write_text('The beginning of this story. ' * 100 + '\n\nThe final adventure. ' * 100)
    book = Book('sample', source, {'title': 'A Story', 'author': 'Tester'}, tmp_path / 'work' / 'sample')
    calls = Counter()
    def split(book):
        calls['split'] += 1
        chapters = []
        for i in [1, 2]:
            sid = f'{i:03d}'
            chapters.append({'id': sid, 'kind': 'chapter', 'number': str(i), 'title': f'Chapter {i}', 'word_count': 500})
            path = book.work_dir / 'chapters' / f'{sid}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(book.source_text)
        atomic_json(book.work_dir / 'chapters.json', {'chapters': chapters})
    def classify(book):
        calls['classify'] += 1
        result = {s['id']: {'status': 'diegetic'} for s in json.loads((book.work_dir / 'chapters.json').read_text())['chapters']}
        atomic_json(book.work_dir / 'chapter_classifications.json', result)
        return result
    def summarize(book):
        calls['summarize'] += 1
        text = 'A person takes an adventure.'
        (book.work_dir / 'book_synopsis.md').write_text(text)
        return text
    def cuts(book):
        calls['cuts'] += 1
        result = {'skippable_chapters': []}
        atomic_json(book.work_dir / 'cuts.json', result)
        return result
    def plan(book):
        calls['plan'] += 1
        result = {'book_id': book.book_id, 'title': 'A Story', 'author': 'Tester',
                  'structural_classification': 'lean', 'motifs': [], 'merged_groups': {},
                  '_meta': {'builder': 'lean_plan', 'computed': {'source_word_count': 1000, 'target_word_count': 100}},
                  'segments': [{'id': f'{i:03d}', 'title': f'Chapter {i}', 'role': 'narrative', 'group_id': None,
                                'source_word_count': 500, 'target_word_count': 50, 'diegetic_status': 'diegetic'} for i in [1, 2]]}
        atomic_json(book.work_dir / 'plan.json', result)
        return result
    def draft(book, plan, sid):
        calls['draft'] += 1
        path = book.work_dir / 'segments' / f'{sid}.md'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'Chapter {sid} begins. The traveler walks past the old house and across the bridge, remembering the story that brought him there. At last, he comes safely home.\n')
        atomic_json(path.with_suffix('.checks.json'), {'status': 'drafted'})
        return SimpleNamespace(status='drafted')
    def coherence(book):
        calls['coherence'] += 1
        report = {'pairs_checked': 1, 'per_pair': [{'pair': '001-002', 'count': 0}], 'findings': []}
        atomic_json(book.work_dir / 'coherence_report.json', report)
        return report
    def repair(book, **kwargs):
        calls['repair'] += 1
        report = {'pairs_failed': 0, 'pairs_rejected': 0}
        atomic_json(book.work_dir / 'coherence_fix_report.json', report)
        return report
    def critic(book):
        calls['critic'] += 1
        result = {'verdict': 'hold', 'is_partial': False, 'synopsis_sentence_count': 1, 'findings': [{'sentence': 1, 'status': 'missing'}]}
        atomic_json(book.work_dir / 'book_critic.json', result)
        return result
    def align_complete(**kwargs):
        calls['align'] += 1
        return LLMResponse('[{"draft_para":0,"source_paras":[0],"note":"compressed"}]', 'mock', 0, 0, 0, 'stop')
    for name, func in [('split_to_disk', split), ('classify_chapters', classify), ('summarize_book', summarize), ('generate_cuts', cuts), ('build_lean_plan', plan), ('draft_segment', draft), ('run_coherence', coherence), ('run_coherence_fixes', repair), ('run_book_critic', critic)]:
        monkeypatch.setattr(p, name, func)
    monkeypatch.setattr('forage.align.complete', align_complete)
    def live_forbidden(**kwargs):
        raise AssertionError('unexpected live LLM boundary')
    monkeypatch.setattr('forage.llm._anthropic', live_forbidden)
    monkeypatch.setattr('forage.llm._openai', live_forbidden)
    return book, calls


def run_ok(book, **options):
    result = p.run_production(book, options)
    assert result['success'], result
    return result


def test_preview_is_free_and_does_not_create_state(pipeline):
    book, calls = pipeline
    result = p.plan_production(book)
    assert not result['execute'] and not calls
    assert not book.work_dir.exists()
    assert set(result['stages']) >= {'drafting', 'assembly', 'alignment', 'snapshot'}


def test_full_text_resume_and_quality_hold(pipeline):
    book, calls = pipeline
    first = run_ok(book)
    assert first['stages']['book_critic']['metadata']['verdict'] == 'hold'
    before = calls.copy()
    state_bytes = (book.work_dir / 'production_state.json').read_bytes()
    plan = p.plan_production(book)
    assert plan['success'] and calls == before
    assert (book.work_dir / 'production_state.json').read_bytes() == state_bytes
    second = run_ok(book)
    assert calls == before and first['review_revision'] == second['review_revision']
    assert all(v['status'] == 'reused' for v in second['stages'].values())


def test_manual_revision_preserves_draft_and_does_not_repair(pipeline):
    book, calls = pipeline
    first = run_ok(book)
    path = book.work_dir / 'segments/001.md'
    text = path.read_text().replace('traveler', 'wanderer')
    path.write_text(text)
    before = calls.copy()
    second = run_ok(book)
    assert path.read_text() == text
    assert calls['draft'] == before['draft'] and calls['repair'] == before['repair']
    assert calls['align'] == before['align'] + 1
    assert calls['critic'] == before['critic'] + 1
    assert first['text_revision'] != second['text_revision']
    assert (book.work_dir / 'publications' / first['review_revision'] / 'segments/001.md').read_text() != text
    assert run_ok(book)['review_revision'] == second['review_revision']


@pytest.mark.parametrize('change', ['source', 'split_config', 'model', 'prompt'])
def test_generation_changes_archive_and_regenerate(pipeline, monkeypatch, change):
    book, calls = pipeline
    run_ok(book)
    old = (book.work_dir / 'segments/001.md').read_bytes()
    before = calls.copy()
    options = {}
    if change == 'source':
        book.source_path.write_text(book.source_path.read_text().replace('story', 'fable'))
    elif change == 'split_config':
        (book.source_path.parent / 'split_config.json').write_text('{"toc_algorithm":"block_run"}')
    elif change == 'model':
        options['models'] = {'draft': 'openai:gpt-6-astra'}
    else:
        original = p.source_fingerprint_for_stage
        monkeypatch.setattr(p, 'source_fingerprint_for_stage', lambda s: {'hash': 'new-prompt'} if s == 'draft' else original(s))
    run_ok(book, **options)
    assert calls['draft'] > before['draft']
    archived = list((book.work_dir / '.production/draft_history').glob('*/segments/001.md'))
    assert archived and any(f.read_bytes() == old for f in archived)


def test_removed_cuts_restore_pristine_source(pipeline):
    book, calls = pipeline
    run_ok(book)
    root = book.work_dir
    pristine = (root / 'chapters/002.md').read_text()
    atomic_json(root / 'cuts.json', {'skippable_chapters': [{'chapter_id': '001', 'relocate_to': '002', 'position': 'start', 'kernel': 'Relocated unique kernel.'}]})
    run_ok(book)
    assert 'Relocated unique kernel.' in (root / 'chapters/002.md').read_text()
    atomic_json(root / 'cuts.json', {'skippable_chapters': []})
    run_ok(book)
    assert (root / 'chapters/002.md').read_text() == pristine
    assert not json.loads((root / 'plan.json').read_text())['segments'][0].get('skipped')


def test_new_source_ignores_old_orig_backup(pipeline):
    book, calls = pipeline
    run_ok(book)
    (book.work_dir / 'chapters/002.md.orig').write_text('stale old source')
    book.source_path.write_text('Entirely new source text. ' * 100)
    run_ok(book)
    assert 'stale old source' not in (book.work_dir / 'chapters/002.md').read_text()


@pytest.mark.parametrize('stage', ['draft', 'alignment', 'repair', 'book_critic', 'plan', 'coherence'])
def test_returned_failures_block_snapshot(pipeline, monkeypatch, stage):
    book, calls = pipeline
    if stage == 'draft':
        monkeypatch.setattr(p, 'draft_segment', lambda *a, **k: SimpleNamespace(status='truncated'))
    elif stage == 'alignment':
        monkeypatch.setattr(p, 'align_chapter', lambda *a, **k: {'error': 'provider failure'})
    elif stage == 'repair':
        monkeypatch.setattr(p, 'run_coherence_fixes', lambda *a, **k: {'pairs_failed': 1})
    elif stage == 'book_critic':
        monkeypatch.setattr(p, 'run_book_critic', lambda *a, **k: {'verdict': 'ship', 'is_partial': True})
    elif stage == 'plan':
        monkeypatch.setattr(p, 'build_lean_plan', lambda *a, **k: {'refused': 'too short'})
    else:
        monkeypatch.setattr(p, 'run_coherence', lambda *a, **k: {'per_pair': [{'skipped': 'parse error'}]})
    result = p.run_production(book)
    assert not result['success'] and result['failed_stage']
    assert not (book.work_dir / 'review_current.json').exists()
    if stage in {'draft', 'repair', 'plan', 'coherence'}:
        assert not (book.work_dir / 'abridgment.txt').exists()


def test_interrupted_and_missing_outputs_retry(pipeline):
    book, calls = pipeline
    run_ok(book)
    state = load_state(book)
    state['stages']['summarize']['status'] = 'running'
    atomic_json(book.work_dir / 'production_state.json', state)
    before = calls.copy()
    run_ok(book)
    assert calls['summarize'] == before['summarize'] + 1
    (book.work_dir / 'abridgment.txt').unlink()
    run_ok(book)
    assert (book.work_dir / 'abridgment.txt').exists()


def test_missing_draft_regenerates_unit(pipeline):
    book, calls = pipeline
    run_ok(book)
    (book.work_dir / 'segments/001.md').unlink()
    before = calls['draft']
    run_ok(book)
    assert calls['draft'] == before + 1


def test_legacy_adoption_explicit_and_no_false_provider_provenance(pipeline):
    book, calls = pipeline
    run_ok(book)
    (book.work_dir / 'production_state.json').unlink()
    before = calls.copy()
    with pytest.raises(ValueError, match='adopt-existing'):
        p.run_production(book)
    assert calls == before
    run_ok(book, adopt_existing=True)
    state = load_state(book)
    assert all(r['origin'] == 'user-adopted' and r['generated'] is None for r in state['draft_units'].values())
    assert calls['draft'] == before['draft']


def _media_mocks(monkeypatch, calls):
    import forage.graphic as graphic
    def storyboard(**kwargs):
        calls['storyboard'] += 1
        # Extract the JSON payload following the narrative instructions.
        body = kwargs['prompt']
        payload = json.loads(body[body.index('{'):])
        frames = [{'id': u['id'], 'image_prompt': 'A traveler at a bridge.', 'caption': 'He crosses the bridge.'} for u in payload['units']]
        return LLMResponse(json.dumps({'frames': frames}), 'mock', 0, 0, 0, 'stop')
    def image(**kwargs):
        calls['image'] += 1
        out = io.BytesIO(); Image.new('RGB', tuple(map(int, kwargs['size'].split('x'))), 'navy').save(out, format='PNG')
        return out.getvalue()
    def tts(self, **kwargs):
        calls['tts'] += 1
        return b'fixture-audio-' + kwargs['text'].encode(), {}
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'offline-test')
    monkeypatch.setattr(graphic, 'complete', storyboard)
    monkeypatch.setattr(graphic, 'generate_image', image)
    monkeypatch.setattr('forage.audiobook.ElevenLabsClient.text_to_speech', tts)


def test_both_real_media_branches_resume_after_edit(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    options = {'outputs': ['audio', 'graphic'], 'audio_voice_id': 'fixture', 'audio_combine': False}
    first = run_ok(book, **options)
    index = json.loads((book.work_dir / 'media_manifest.json').read_text())
    assert {t['kind'] for t in index['targets']} == {'audio', 'graphic'}
    before = calls.copy()
    run_ok(book, **options)
    assert calls == before
    path = book.work_dir / 'segments/001.md'
    path.write_text(path.read_text().replace('traveler', 'wanderer'))
    second = run_ok(book, **options)
    assert first['text_revision'] != second['text_revision']
    assert calls['draft'] == before['draft'] and calls['repair'] == before['repair']
    assert calls['tts'] > before['tts'] and calls['storyboard'] > before['storyboard']


def test_failed_media_branch_preserves_other_then_resumes(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    original = p.generate_audiobook
    monkeypatch.setattr(p, 'generate_audiobook', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('audio offline')))
    opts = {'outputs': ['audio', 'graphic'], 'audio_voice_id': 'fixture', 'audio_combine': False}
    first = p.run_production(book, opts)
    assert not first['success'] and first['stages']['graphic']['status'] == 'complete'
    images = calls['image']
    monkeypatch.setattr(p, 'generate_audiobook', original)
    run_ok(book, **opts)
    assert calls['image'] == images


def test_requested_combined_audio_failure_fails_run(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    monkeypatch.setattr('forage.audiobook.combine_audio_chunks', lambda *a, **kw: (None, 'ffmpeg unavailable'))
    result = p.run_production(book, {'outputs': ['audio'], 'audio_voice_id': 'fixture'})
    assert not result['success'] and result['failed_stage'] == 'audio'
    assert 'ffmpeg' in result['stages']['audio']['reason']


def test_release_preserves_review_loop(pipeline):
    from forage.publication import promote_release
    book, calls = pipeline
    first = run_ok(book)
    promote_release(book, first['review_revision'])
    path = book.work_dir / 'segments/001.md'; path.write_text(path.read_text().replace('traveler', 'wanderer'))
    second = run_ok(book)
    assert first['review_revision'] != second['review_revision']
    assert json.loads((book.work_dir / 'release_current.json').read_text())['revision'] == first['review_revision']
    assert json.loads((book.work_dir / 'review_current.json').read_text())['revision'] == second['review_revision']


def test_cli_preview_and_execution_failure(pipeline, monkeypatch):
    from forage.cli import app
    book, calls = pipeline
    workspace = book.source_path.parents[2]
    result = CliRunner().invoke(app, ['run', 'sample', '--workspace', str(workspace)])
    assert result.exit_code == 0, result.output
    assert not calls
    monkeypatch.setattr(p, 'draft_segment', lambda *a, **k: SimpleNamespace(status='truncated'))
    result = CliRunner().invoke(app, ['run', 'sample', '--workspace', str(workspace), '--execute'])
    assert result.exit_code == 1 and 'drafting' in result.output


def test_group_generation_bypasses_old_group_cache_after_model_change(pipeline, monkeypatch):
    from forage.drafter import draft_segment
    book, calls = pipeline
    original = p.build_lean_plan
    def grouped(book):
        plan = original(book)
        for s in plan['segments']:
            s['group_id'] = 'g001'
        plan['merged_groups'] = {'g001': {'member_ids': ['001', '002'], 'combined_target_word_count': 100, 'combined_source_word_count': 1000}}
        atomic_json(book.work_dir / 'plan.json', plan)
        return plan
    def provider(**kwargs):
        calls['group_provider'] += 1
        return LLMResponse('## Chapter 1\nThe first traveler crosses a bridge.\n## Chapter 2\nThe other traveler arrives safely at home.', 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(p, 'build_lean_plan', grouped)
    monkeypatch.setattr(p, 'draft_segment', draft_segment)
    monkeypatch.setattr('forage.drafter._complete_draft_with_exception_fallback', provider)
    run_ok(book)
    assert calls['group_provider'] == 1
    run_ok(book)
    assert calls['group_provider'] == 1
    run_ok(book, models={'draft': 'openai:gpt-6-astra'})
    assert calls['group_provider'] == 2
    state = load_state(book)
    assert state['draft_units']['g001']['request_sha256']


def test_graphic_lettering_only_edit_preserves_art_in_runner(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    opts = {'outputs': ['graphic']}
    run_ok(book, **opts)
    before = calls.copy()
    path = book.work_dir / 'graphic/storyboard.json'
    data = json.loads(path.read_text())
    data['frames'][0]['caption'] = 'An edited human caption.'
    atomic_json(path, data)
    run_ok(book, **opts)
    assert calls['image'] == before['image']
    assert calls['storyboard'] == before['storyboard']


def test_short_required_chapters_do_not_fail_coherence(pipeline, monkeypatch):
    book, calls = pipeline
    original = p.build_lean_plan
    def short(book):
        plan = original(book)
        for s in plan['segments']:
            s['source_word_count'] = 150
        atomic_json(book.work_dir / 'plan.json', plan)
        return plan
    monkeypatch.setattr(p, 'build_lean_plan', short)
    run_ok(book)
    assert calls['coherence'] == 0


@pytest.mark.parametrize('options', [
    {'bogus': True}, {'outputs': ['unknown']}, {'models': {'what': 'openai:test'}},
    {'coherence_fix': False, 'coherence_fix_pairs': ['001-002']},
    {'outputs': ['audio'], 'audio_voice_id': 'v', 'audio_format': 'garbage'},
    {'outputs': ['audio'], 'audio_voice_id': 'v', 'audio_format': 'pcm_44100'},
    {'outputs': ['audio']}, {'outputs': ['graphic'], 'graphic_provider': 'unknown'},
])
def test_bad_configuration_fails_before_any_paid_stage(pipeline, options):
    book, calls = pipeline
    with pytest.raises(ValueError):
        p.run_production(book, options)
    assert not calls


def test_effective_book_critic_model_is_used(pipeline, monkeypatch):
    from forage import llm
    book, calls = pipeline
    seen = []
    original = p.run_book_critic
    def critic(book):
        seen.append(llm.resolve_model_for_stage('anthropic:default', 'critic:book:sample')[0])
        return original(book)
    monkeypatch.setattr(p, 'run_book_critic', critic)
    monkeypatch.delenv('FORAGE_CRITIC_MODEL', raising=False)
    monkeypatch.delenv('FORAGE_MODEL', raising=False)
    run_ok(book, models={'critic:book': 'openai:gpt-6-astra', 'critic': 'anthropic:claude-sonnet-5-5'})
    assert seen == ['openai:gpt-6-astra']


@pytest.mark.parametrize('module,call,text', [
    ('coherence', lambda m, b: m.run_coherence(b), '[]'),
    ('critics', lambda m, b: m.run_critic(b, '001', 'signature'), '{"verdict":"pass","findings":[]}'),
    ('book_critic', lambda m, b: m.run_book_critic(b), '[{"status":"present"}]'),
    ('chapter_classifier', lambda m, b: m.classify_chapters(b), '[]'),
    ('summarizer', lambda m, b: m.summarize_book(b), 'A partial story.'),
    ('cuts', lambda m, b: m.generate_cuts(b), '{}'),
])
def test_parseable_truncated_preparation_and_critics_rejected(pipeline, monkeypatch, module, call, text):
    import importlib
    book, calls = pipeline
    run_ok(book)
    mod = importlib.import_module('forage.' + module)
    monkeypatch.setattr(mod, 'complete', lambda **kwargs: LLMResponse(text, 'mock', 1, 1, 0, 'length'))
    with pytest.raises(ValueError, match='incomplete'):
        call(mod, book)


def test_snapshot_corruption_is_not_skipped(pipeline):
    book, calls = pipeline
    result = run_ok(book)
    (book.work_dir / 'publications' / result['review_revision'] / 'abridgment.txt').write_text('corrupted')
    result = p.run_production(book)
    assert not result['success'] and result['failed_stage'] == 'snapshot'


def test_compatibility_wrapper_maps_options_and_rejects_unsupported(pipeline, monkeypatch, capsys):
    from scripts import full_pipeline
    book, calls = pipeline
    workspace = str(book.source_path.parents[2])
    assert full_pipeline.main(['sample', '--workspace', workspace, '--resume-drafts']) == 0
    assert not calls
    with pytest.raises(SystemExit):
        full_pipeline.main(['sample', '--workspace', workspace, '--unknown'])
    with pytest.raises(SystemExit):
        full_pipeline.main(['sample', '--workspace', workspace, '--skip-coherence-fix', '--coherence-fix-pair', '001-002'])
    assert not calls
    assert full_pipeline.main(['sample', '--workspace', workspace, '--execute', '--skip-coherence-fix']) == 0
    assert calls['repair'] == 0


def test_plan_edit_after_skips_does_not_retain_removed_skip(pipeline):
    book, calls = pipeline
    run_ok(book)
    atomic_json(book.work_dir / 'cuts.json', {'skippable_chapters': [{'chapter_id': '001'}]})
    run_ok(book)
    plan = json.loads((book.work_dir / 'plan.json').read_text())
    plan['title'] = 'Human edited title'
    atomic_json(book.work_dir / 'plan.json', plan)
    run_ok(book)
    atomic_json(book.work_dir / 'cuts.json', {'skippable_chapters': []})
    run_ok(book)
    plan = json.loads((book.work_dir / 'plan.json').read_text())
    assert plan['title'] == 'Human edited title'
    assert plan['segments'][0]['target_word_count'] > 0 and not plan['segments'][0].get('skipped')


def test_regenerating_identical_assembly_preserves_content_revision(pipeline, monkeypatch):
    book, calls = pipeline
    first = run_ok(book)
    (book.work_dir / 'abridgment.txt').unlink()
    monkeypatch.setattr('forage.assemble.time.strftime', lambda *a: 'a later timestamp')
    second = run_ok(book)
    assert first['review_revision'] == second['review_revision']


def test_missing_review_pointer_is_recovered(pipeline):
    book, calls = pipeline
    first = run_ok(book)
    (book.work_dir / 'review_current.json').unlink()
    second = run_ok(book)
    assert first['review_revision'] == second['review_revision']
    assert json.loads((book.work_dir / 'review_current.json').read_text())['revision'] == first['review_revision']


def test_align_model_change_regenerates_mapping_without_redrafting(pipeline, monkeypatch):
    book, calls = pipeline
    monkeypatch.delenv('FORAGE_ALIGN_MODEL', raising=False)
    monkeypatch.delenv('FORAGE_MODEL', raising=False)
    run_ok(book)
    before = calls.copy()
    run_ok(book, models={'align': 'openai:gpt-6-astra'})
    assert calls['align'] == before['align'] + 2
    assert calls['draft'] == before['draft']


def test_short_chapter_remains_in_revision_alignment_and_graphics(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    original = p.build_lean_plan
    def short(book):
        plan = original(book)
        plan['segments'][0]['source_word_count'] = 50
        atomic_json(book.work_dir / 'plan.json', plan)
        return plan
    monkeypatch.setattr(p, 'build_lean_plan', short)
    first = run_ok(book, outputs=['graphic'])
    assert (book.work_dir / 'alignments/001.json').exists()
    targets = json.loads((book.work_dir / 'media_manifest.json').read_text())['targets']
    assert {t['segment_id'] for t in targets} == {'001', '002'}
    path = book.work_dir / 'segments/001.md'
    path.write_text(path.read_text().replace('traveler', 'wanderer'))
    assert run_ok(book, outputs=['graphic'])['text_revision'] != first['text_revision']


@pytest.mark.parametrize('findings', [[{'sentence': 1, 'status': 'invalid'}], [{'sentence': 2, 'status': 'present'}]])
def test_book_critic_invalid_claims_cannot_certify_complete(pipeline, monkeypatch, findings):
    from forage import book_critic
    book, calls = pipeline
    run_ok(book)
    monkeypatch.setattr(book_critic, 'complete', lambda **kwargs: LLMResponse(json.dumps(findings), 'mock', 1, 1, 0, 'stop'))
    with pytest.raises(ValueError, match='every synopsis sentence'):
        book_critic.run_book_critic(book)


def test_optional_checkpoint_is_bound_to_accepted_text_revision(pipeline, monkeypatch):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    options = {'outputs': ['audio'], 'audio_voice_id': 'fixture', 'audio_combine': False, 'checkpoint_before_media': True}
    first = p.run_production(book, options)
    assert not first['success'] and first['stages']['checkpoint']['status'] == 'pending'
    assert calls['tts'] == 0
    approved = first['text_revision']
    run_ok(book, **options, continue_revision=approved)
    count = calls['tts']
    run_ok(book, **options)
    assert calls['tts'] == count
    path = book.work_dir / 'segments/001.md'; path.write_text(path.read_text().replace('traveler', 'wanderer'))
    third = p.run_production(book, {**options, 'continue_revision': approved})
    assert not third['success'] and third['text_revision'] != approved
    assert calls['tts'] == count


def test_iteration_and_selected_repairs_are_real_options(pipeline, monkeypatch):
    from forage.iterate import IterateResult
    book, calls = pipeline
    repair_args = []
    def iterate(book, plan, sid, **kwargs):
        calls['iteration'] += 1
        assert kwargs['max_retries'] == 2
        return IterateResult(sid, 'pass', 1, False, [])
    original = p.run_coherence_fixes
    def repair(book, **kwargs):
        repair_args.append(kwargs)
        return original(book, **kwargs)
    monkeypatch.setattr(p, 'iterate_segment', iterate)
    monkeypatch.setattr(p, 'run_coherence_fixes', repair)
    opts = {'iterate': True, 'max_retries': 2, 'coherence_fix_pairs': ['001-002']}
    run_ok(book, **opts)
    assert calls['iteration'] == 2
    assert repair_args == [{'all_findings': False, 'pairs': ['001-002'], 'max_retries': 2}]
    run_ok(book, **opts)
    assert calls['iteration'] == 2


def test_regeneration_and_retry_models_match_resolved_configuration(pipeline, monkeypatch):
    from forage.drafter import _draft_runtime_options
    from forage.prompts import load_prompt
    from forage import llm
    book, calls = pipeline
    for name in ['FORAGE_MODEL', 'FORAGE_DRAFT_MODEL', 'FORAGE_REGEN_MODEL']:
        monkeypatch.delenv(name, raising=False)
    options = p.resolve_options(book, {'models': {'draft': 'anthropic:claude-opus-5-5', 'regen': 'openai:gpt-6-astra'}})
    with llm.production_context(options['resolved_models'], book.work_dir.parent / '.replay_cache'):
        active, thinking, budget = _draft_runtime_options(load_prompt('draft_lean'), 'anthropic:default', 'regen:sample:001')
        assert active == 'openai:gpt-6-astra' and thinking is None
        assert llm.resolve_model_for_stage('anthropic:default', 'regen_thinkretry:sample:001')[0] == active


def test_review_apply_check_updates_preserve_accepted_prose(pipeline):
    from forage.review_apply import _update_checks
    book, calls = pipeline
    run_ok(book)
    before = calls.copy()
    path = book.work_dir / 'segments/001.md'
    reviewed = path.read_text().replace('traveler', 'wanderer')
    path.write_text(reviewed)
    _update_checks(book=book, segment_id='001', source_words=500, draft_words=len(reviewed.split()), run_id='review-import-1')
    run_ok(book)
    assert calls['draft'] == before['draft'] and calls['repair'] == before['repair']
    assert path.read_text() == reviewed
    assert json.loads((book.work_dir / 'segments/001.checks.json').read_text())['review_apply']['run_id'] == 'review-import-1'


def test_corrupt_edited_plan_is_recorded_as_failed_preparation(pipeline):
    book, calls = pipeline
    run_ok(book)
    (book.work_dir / 'plan.json').write_text('{invalid')
    before = calls.copy()
    result = p.run_production(book)
    assert not result['success'] and result['failed_stage'] == 'preparation'
    assert load_state(book)['stages']['preparation']['status'] == 'failed'
    assert p.run_production(book)['failed_stage'] == 'preparation'
    assert calls == before


def _set_group(book, group_id):
    path = book.work_dir / 'plan.json'
    plan = json.loads(path.read_text())
    for segment in plan['segments']:
        segment['group_id'] = group_id
    plan['merged_groups'] = ({group_id: {'member_ids': ['001', '002'], 'combined_target_word_count': 100, 'combined_source_word_count': 1000}} if group_id else {})
    atomic_json(path, plan)


@pytest.mark.parametrize('transition', ['merge', 'split', 'rename'])
def test_generation_unit_members_retain_provenance_across_group_changes(pipeline, monkeypatch, transition):
    from forage.drafter import draft_segment
    book, calls = pipeline
    original_plan = p.build_lean_plan
    if transition != 'merge':
        def grouped(book):
            plan = original_plan(book)
            _set_group(book, 'g001')
            return json.loads((book.work_dir / 'plan.json').read_text())
        monkeypatch.setattr(p, 'build_lean_plan', grouped)
    def provider(**kwargs):
        calls['provider'] += 1
        unit = kwargs['stage'].split(':')[-1]
        prose = ('## Chapter 1\nThe traveler crosses the bridge.\n## Chapter 2\nThe traveler returns safely home.'
                 if unit.startswith('g') else 'The traveler crosses the bridge and returns safely home.')
        return LLMResponse(prose, 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr(p, 'draft_segment', draft_segment)
    monkeypatch.setattr('forage.drafter._complete_draft_with_exception_fallback', provider)
    run_ok(book)
    before = calls['provider']
    accepted = (book.work_dir / 'segments/001.md').read_bytes()
    group_id = 'g001' if transition == 'merge' else None if transition == 'split' else 'g009'
    _set_group(book, group_id)
    run_ok(book)
    assert calls['provider'] == before + (2 if transition == 'split' else 1)
    archived = list((book.work_dir / '.production/draft_history').glob('*/segments/001.md'))
    assert any(path.read_bytes() == accepted for path in archived)
    record = load_state(book)['draft_units'][group_id or '001']
    assert record['origin'] == 'provider-generated'
    assert record['previous_units']
    count = calls.copy()
    run_ok(book)
    assert calls == count


def test_regrouping_does_not_silently_adopt_unknown_existing_member(pipeline):
    book, calls = pipeline
    run_ok(book)
    state = load_state(book)
    state['draft_units'].pop('002')
    atomic_json(book.work_dir / 'production_state.json', state)
    _set_group(book, 'g001')
    result = p.run_production(book)
    assert not result['success'] and result['failed_stage'] == 'drafting'
    assert 'adopt-existing' in result['stages']['drafting']['reason']


def _extend_recorded_group_with_unowned_chapter(book):
    run_ok(book)
    _set_group(book, 'g001')
    run_ok(book)
    path = book.work_dir / 'plan.json'
    plan = json.loads(path.read_text())
    plan['segments'].append({**plan['segments'][0], 'id': '003', 'title': 'Chapter 3'})
    group = plan['merged_groups']['g001']
    group['member_ids'].append('003')
    group['combined_target_word_count'] += 50
    group['combined_source_word_count'] += 500
    (book.work_dir / 'chapters/003.md').write_text('The new chapter has its source. ' * 50)
    (book.work_dir / 'segments/003.md').write_text('Unowned human-authored chapter.\n')
    atomic_json(book.work_dir / 'segments/003.checks.json', {'status': 'drafted'})
    atomic_json(path, plan)


def _draft_files(book):
    return {str(path.relative_to(book.work_dir)): path.read_bytes()
            for directory in ['segments', '.production/draft_history']
            for path in (book.work_dir / directory).rglob('*') if path.is_file()}


def test_existing_group_extension_requires_explicit_adoption_before_any_archive(pipeline):
    book, calls = pipeline
    _extend_recorded_group_with_unowned_chapter(book)
    before = calls.copy()
    files = _draft_files(book)
    record = load_state(book)['draft_units']['g001']
    pointer = (book.work_dir / 'review_current.json').read_bytes()
    for _ in range(2):
        result = p.run_production(book)
        assert not result['success'] and result['failed_stage'] == 'drafting'
        assert 'adopt-existing' in result['stages']['drafting']['reason']
        assert calls == before
        assert _draft_files(book) == files
        assert load_state(book)['draft_units']['g001'] == record
        assert (book.work_dir / 'review_current.json').read_bytes() == pointer
    run_ok(book, adopt_existing=True)
    assert calls['draft'] == before['draft']
    assert _draft_files(book) == files
    adopted = load_state(book)['draft_units']['g001']
    assert adopted['origin'] == 'user-adopted' and adopted['generated'] is None
    assert adopted['members'] == ['001', '002', '003']
    assert {item['path'] for item in adopted['accepted']} == {f'segments/{sid}.md' for sid in adopted['members']}
    after = calls.copy()
    run_ok(book)
    assert calls == after and _draft_files(book) == files


@pytest.mark.parametrize('invalid', ['missing_checks', 'truncated', 'empty_prose'])
def test_existing_group_extension_rejects_incomplete_adoption_without_archiving(pipeline, invalid):
    book, calls = pipeline
    _extend_recorded_group_with_unowned_chapter(book)
    if invalid == 'missing_checks':
        (book.work_dir / 'segments/003.checks.json').unlink()
    elif invalid == 'truncated':
        atomic_json(book.work_dir / 'segments/003.checks.json', {'status': 'truncated'})
    else:
        (book.work_dir / 'segments/003.md').write_text('')
    before = calls.copy()
    files = _draft_files(book)
    record = load_state(book)['draft_units']['g001']
    result = p.run_production(book, {'adopt_existing': True})
    assert not result['success'] and result['failed_stage'] == 'drafting'
    assert 'cannot adopt g001' in result['stages']['drafting']['reason']
    assert calls == before and _draft_files(book) == files
    assert load_state(book)['draft_units']['g001'] == record


@pytest.mark.parametrize('setting,value', [('voice_id', 'voice-two'), ('model_id', 'model-two'), ('max_chars', 1100)])
def test_audio_metadata_changes_only_audio_and_publication(pipeline, monkeypatch, setting, value):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    book.metadata['audiobook'] = {'voice_id': 'voice-one'}
    options = {'outputs': ['audio', 'graphic'], 'audio_combine': False}
    run_ok(book, **options)
    prose = book.work_dir / 'segments/001.md'
    accepted = prose.read_text().replace('traveler', 'wanderer')
    prose.write_text(accepted)
    previous = run_ok(book, **options)
    before = calls.copy()
    book.metadata['audiobook'][setting] = value
    result = run_ok(book, **options)
    assert result['text_revision'] == previous['text_revision']
    if setting in {'voice_id', 'model_id'}:
        assert result['review_revision'] != previous['review_revision']
    else:
        # This tiny narration still fits one chunk; changing the limit does not
        # change its synthesis request or the immutable publication content.
        assert result['review_revision'] == previous['review_revision']
        assert calls['tts'] == before['tts']
    assert prose.read_text() == accepted
    for stage in ['split', 'classify', 'summarize', 'cuts', 'plan', 'drafting', 'quality', 'assembly', 'book_critic', 'validation', 'alignment', 'graphic']:
        assert result['stages'][stage]['status'] == 'reused', (stage, result)
    for key in ['split', 'classify', 'summarize', 'cuts', 'plan', 'draft', 'repair', 'critic', 'align', 'image', 'storyboard']:
        assert calls[key] == before[key]
    assert result['stages']['audio']['status'] == 'complete'


@pytest.mark.parametrize("metadata_key,value", [("publication", {"publisher": "A different publisher"}), ("audiobook", {"voice_id": "unselected-new-voice"})])
def test_publication_metadata_does_not_invalidate_generation(pipeline, metadata_key, value):
    book, calls = pipeline
    first = run_ok(book)
    before = calls.copy()
    book.metadata[metadata_key] = value
    second = run_ok(book)
    assert calls == before and second['text_revision'] == first['text_revision']


@pytest.mark.parametrize('key,value,first_changed', [
    ('genre', 'biography', 'classify'),
    ('force_keep_chapters', [{'chapter_id': '001', 'reason': 'Keep the opening'}], 'cuts'),
    ('modernization_level', 'L2', 'plan'),
])
def test_text_metadata_still_invalidates_its_consumers(pipeline, key, value, first_changed):
    book, calls = pipeline
    run_ok(book)
    before = calls.copy()
    book.metadata[key] = value
    result = run_ok(book)
    assert result['stages']['split']['status'] == 'reused'
    assert result['stages'][first_changed]['status'] == 'complete'
    assert calls['draft'] > before['draft']
    if first_changed != 'classify':
        assert calls['classify'] == before['classify']


def _signature_verdict():
    return {'segment_id': '001', 'critic': 'signature', 'verdict': 'pass', 'summary': 'No losses found.', 'findings': []}


@pytest.mark.parametrize('mutation', [
    {'error': 'cannot evaluate this chapter'}, {'refusal': 'cannot evaluate this chapter'},
    {'verdict': None}, {'findings': None}, {'findings': {}}, {'findings': [{}]},
    {'findings': [{'severity': 'unknown'}]}, {'verdict': 'unknown'}, {'summary': None},
    {'segment_id': '002'}, {'critic': 'other'},
])
def test_malformed_signature_critic_cannot_complete_iteration(pipeline, monkeypatch, mutation):
    from forage.iterate import iterate_segment
    book, calls = pipeline
    monkeypatch.setattr(p, 'iterate_segment', iterate_segment)
    payload = ({'error': mutation['error']} if 'error' in mutation else {**_signature_verdict(), **mutation})
    monkeypatch.setattr('forage.critics.complete', lambda **kwargs: LLMResponse(json.dumps(payload), 'mock', 1, 1, 0, 'stop'))
    result = p.run_production(book, {'iterate': True})
    assert not result['success'] and result['failed_stage'] == 'quality'
    assert 'signature critic' in result['stages']['quality']['reason']
    assert not (book.work_dir / 'review_current.json').exists()
    assert not (book.work_dir / 'segments/001.critic_signature.json').exists()


@pytest.mark.parametrize('stop_reason', ['length', 'max_tokens', 'content_filter', None])
def test_complete_shaped_signature_response_requires_provider_completion(pipeline, monkeypatch, stop_reason):
    from forage.iterate import iterate_segment
    book, calls = pipeline
    monkeypatch.setattr(p, 'iterate_segment', iterate_segment)
    monkeypatch.setattr('forage.critics.complete', lambda **kwargs: LLMResponse(json.dumps(_signature_verdict()), 'mock', 1, 1, 0, stop_reason))
    result = p.run_production(book, {'iterate': True})
    assert result['failed_stage'] == 'quality' and not result['success']


def test_valid_signature_critic_empty_findings_is_a_real_pass(pipeline, monkeypatch):
    from forage.iterate import iterate_segment
    book, calls = pipeline
    monkeypatch.setattr(p, 'iterate_segment', iterate_segment)
    def response(**kwargs):
        payload = _signature_verdict()
        payload['segment_id'] = kwargs['stage'].split(':')[-1]
        return LLMResponse(json.dumps(payload), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr('forage.critics.complete', response)
    result = run_ok(book, iterate=True)
    assert result['stages']['quality']['status'] == 'complete'


def test_valid_signature_finding_is_quality_hold_not_technical_failure(pipeline, monkeypatch):
    from forage.iterate import iterate_segment
    book, calls = pipeline
    monkeypatch.setattr(p, 'iterate_segment', iterate_segment)
    def response(**kwargs):
        payload = _signature_verdict()
        payload.update(segment_id=kwargs['stage'].split(':')[-1], verdict='regenerate')
        payload['findings'] = [{'severity': 'high', 'class': 'signature_loss', 'source_passage': 'A source phrase.', 'source_locator': 'Paragraph 1', 'draft_treatment': 'absent', 'why_it_matters': 'It preserves the narrator.', 'suggested_fix': 'Restore the source phrase.'}]
        return LLMResponse(json.dumps(payload), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr('forage.critics.complete', response)
    result = run_ok(book, iterate=True, max_retries=0)
    assert result['stages']['quality']['metadata']['iteration_hold'] is True
