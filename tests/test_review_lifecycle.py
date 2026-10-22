"""One complete hosted lifecycle, real storage/HTTP stages and fake provider I/O."""
import json
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forage import production
from forage.artifacts import Book
from forage.llm import LLMResponse
from forage.production_state import atomic_json, load_state, book_lock
from forage.hosted_publication import HostedPublications
from forage.review_transport import ReviewTransport
from forage.review_sync import sync_feedback, import_path, imported_edits_path
from forage.webapp.app import create_app
from forage.webapp.auth import AuthConfig
from forage.webapp.store import ArtifactStore, ReviewStore
from .test_production_runner import pipeline, run_ok, _media_mocks
from .conftest import ADMIN_PASSWORD, REVIEW_PASSWORD, seed_accounts, sign_in


def _site(tmp_path):
    host = HostedPublications(tmp_path / 'separate-website')
    reviews = ReviewStore(tmp_path / 'site-comments.sqlite')
    artifacts = ArtifactStore(work_dir=tmp_path / 'empty-artifacts', books_dir=tmp_path / 'empty-metadata', hosted_dir=host.root)
    auth = AuthConfig(session_seconds=3600)
    app = create_app(artifacts=artifacts, reviews=reviews, auth=auth, hosted=host)
    seed_accounts(app)
    machine, reviewer = TestClient(app), TestClient(app)
    transport = ReviewTransport(base_url='http://testserver', username="admin", password=ADMIN_PASSWORD, http_client=machine)
    sign_in(reviewer)
    return host, reviews, transport, reviewer


def _comment(client, revision, scope='paragraph', segment='001', **extra):
    payload = {'publication_revision': revision, 'scope': scope, 'segment_id': segment,
               'draft_para': 0, 'body': 'Use the more precise source wording.', **extra}
    response = client.post('/api/books/sample/comments', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_http_review_apply_republish_release_and_further_feedback(pipeline, monkeypatch, tmp_path):
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    from forage.audiobook import ElevenLabsClient
    from forage import graphic as graphic_module
    synthesize = ElevenLabsClient.text_to_speech
    draw = graphic_module.generate_image
    narrated_voices, art_prompts = [], []
    def narration(self, **kwargs):
        narrated_voices.append(kwargs['voice_id'])
        return synthesize(self, **kwargs)
    def artwork(**kwargs):
        art_prompts.append(kwargs['prompt'])
        return draw(**kwargs)
    monkeypatch.setattr(ElevenLabsClient, 'text_to_speech', narration)
    monkeypatch.setattr(graphic_module, 'generate_image', artwork)
    opts = {'outputs': ['text', 'audio', 'graphic'], 'audio_voice_id': 'chosen-voice',
            'audio_combine': False, 'graphic_style': 'Woodblock engraving.',
            'graphic_words_per_frame': 100, 'graphic_font_size': 24}
    a = run_ok(book, **opts)['review_revision']
    state = load_state(book)
    assert state['production_options']['audio_voice_id'] == 'chosen-voice'
    assert state['production_options']['graphic_style'] == 'Woodblock engraving.'
    assert 'continue_revision' not in state['production_options']
    host, reviews, transport, client = _site(tmp_path)
    transport.publish(book, a)
    assert host.status('sample')['release'] is None
    prose = _comment(client, a, author='spoofed')
    assert prose['author'] == 'alice'
    media = client.get('/api/books/sample/media').json()
    assert media['publication_revision'] == a
    audio = next(t for t in media['targets'] if t['kind'] == 'audio')
    graphic = next(t for t in media['targets'] if t['kind'] == 'graphic')
    audio_note = _comment(client, a, 'audio', target_id=audio['id'], target_revision=audio['revision'], timestamp_seconds=1.25)
    panel_note = _comment(client, a, 'graphic', target_id=graphic['id'], target_revision=graphic['revision'])
    media_response = client.get(audio['url'], headers={'Range': 'bytes=0-5'})
    assert media_response.status_code == 206 and len(media_response.content) == 6
    before_calls = calls.copy()
    first = sync_feedback(book, transport)
    imported = import_path(book).read_bytes()
    second = sync_feedback(book, transport)
    assert first['pull']['counts'] == {'eligible': 1, 'media': 2}
    assert second['pull']['changed_comments'] == 0
    assert import_path(book).read_bytes() == imported and calls == before_calls

    def apply_mock(**kwargs):
        from forage.review_apply import pending_review_feedback
        sid = kwargs['stage'].rsplit(':', 1)[1]
        plan = pending_review_feedback(book, edits_path=imported_edits_path(book))
        pending = next(s['pending'] for s in plan['segments'] if s['segment_id'] == sid)
        calls['apply'] += 1
        draft = (book.work_dir / 'segments' / f'{sid}.md').read_text().strip()
        replacement = draft.replace('traveler', 'wanderer')
        return LLMResponse(json.dumps({'segment_id': sid, 'revised_draft': replacement,
            'decisions': [{'feedback_key': p['feedback_key'], 'comment_id': p['comment_id'],
                           'action': 'applied', 'reason': 'Clarifies the requested wording.',
                           'changed_paragraphs': [0], 'target_paragraphs': [0]} for p in pending]}), 'mock', 1, 1, 0, 'stop')
    monkeypatch.setattr('forage.review_apply.complete', apply_mock)
    book.metadata['audiobook'] = {'voice_id': 'a-later-metadata-default'}
    applied = sync_feedback(book, transport, apply=True, republish=True)
    assert applied['success'], applied
    b = applied['publication']['revision']
    assert b != a and calls['apply'] == 1 and calls['draft'] == before_calls['draft']
    saved = load_state(book)['production_options']
    assert saved['audio_voice_id'] == 'chosen-voice' and saved['graphic_style'] == 'Woodblock engraving.'
    assert len(narrated_voices) >= 2 and set(narrated_voices) == {'chosen-voice'}
    assert art_prompts and all('Woodblock engraving.' in prompt for prompt in art_prompts)
    assert set(saved['outputs']) == {'text', 'audio', 'graphic'}
    comments = {c['id']: c for c in client.get('/api/books/sample/feedback').json()['comments']}
    assert comments[prose['id']]['publication_revision'] == a and comments[prose['id']]['stale']
    assert comments[audio_note['id']]['stale'] and comments[panel_note['id']]['stale']
    assert host.resolve('sample', a)[0].is_dir() and reviews.get(prose['id'])
    assert host.status('sample')['release'] is None
    ledger = (book.work_dir / 'editorial/review_apply_ledger.json').read_bytes()
    repeat_calls = calls.copy()
    assert sync_feedback(book, transport, apply=True, republish=True)['success']
    assert calls == repeat_calls
    assert (book.work_dir / 'editorial/review_apply_ledger.json').read_bytes() == ledger
    transport.publish(book, b, channel='release')
    release = client.get('/api/books/sample/chapters?channel=release').json()
    assert release['publication_revision'] == b and release['downloads']
    text = next(d for d in release['downloads'] if d['path'] == 'abridgment.txt')
    assert b'wanderer' in client.get(text['url']).content
    assert client.get('/release/sample').status_code == 200

    # Release readers can add feedback for that exact immutable version.
    second_prose = _comment(client, b, segment='002')
    updated = sync_feedback(book, transport, apply=True, republish=True,
                            production_options={'outputs': ['text']})
    assert updated['success'], updated
    c = updated['publication']['revision']
    assert c not in {a, b} and calls['apply'] == 2
    assert host.status('sample')['release']['revision'] == b
    assert client.get('/api/books/sample/media').json()['targets'] == []
    comments = {r['id']: r for r in client.get('/api/books/sample/feedback').json()['comments']}
    assert comments[audio_note['id']]['orphaned'] and comments[panel_note['id']]['orphaned']
    transport.publish(book, c, channel='release')
    status = host.status('sample')
    assert [r['revision'] for r in status['release']['history']] == [b, c]
    assert [r['revision'] for r in status['review']['history']] == [a, b, c]
    assert host.resolve('sample', b)[0].is_dir()
    assert reviews.get(second_prose['id'])['publication_revision'] == b
    assert calls['draft'] == before_calls['draft']


def test_cli_local_lifecycle_failure_and_free_pull(pipeline, tmp_path):
    from forage.cli import app
    book, calls = pipeline
    revision = run_ok(book)['review_revision']
    host = tmp_path / 'cli-host'
    args = ['sample', revision, '--workspace', str(tmp_path), '--local-root', str(host)]
    runner = CliRunner()
    for command in ['publish-review', 'publish-release']:
        result = runner.invoke(app, [command, *args])
        assert result.exit_code == 0, result.output
    atomic_json(host / 'sample/feedback.json', {'version':1, 'source_id':'cli-source',
                'book_id':'sample', 'complete':True, 'comments':[]})
    before = calls.copy()
    for command in ['review-pull', 'review-sync']:
        result = runner.invoke(app, [command, 'sample', '--workspace', str(tmp_path), '--local-root', str(host)])
        assert result.exit_code == 0, result.output
    assert calls == before
    bad = runner.invoke(app, ['publish-review', 'sample', 'f'*64, '--workspace', str(tmp_path), '--local-root', str(host)])
    assert bad.exit_code != 0 and 'confirmed' not in bad.output
    invalid = runner.invoke(app, ['review-sync', 'sample', '--republish'])
    assert invalid.exit_code != 0 and '--republish requires --apply' in invalid.output
    assert HostedPublications(host).status('sample')['review']['revision'] == revision
