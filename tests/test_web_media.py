"""Hosted publication and original-anchor review; no generation or network calls."""
from __future__ import annotations

import builtins
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forage.artifacts import Book
from forage.hosted_publication import HostedPublications, archive_snapshot
from forage.media import target_revision
from forage.production_state import atomic_json, digest, inventory, sha256_file
from forage.publication import snapshot_revision
from forage.webapp.app import create_app
from forage.webapp.auth import AuthConfig
from forage.webapp.store import ArtifactStore, ReviewStore, _SCHEMA
from .conftest import ADMIN_PASSWORD, REVIEW_PASSWORD, sign_in


@pytest.fixture
def hosted(tmp_path):
    root = tmp_path / 'local' / 'work' / 'sample'
    root.mkdir(parents=True)
    book = Book('sample', tmp_path / 'source.txt', {}, root)
    text = 'The first paragraph.\n\nThe second paragraph.'
    (root / 'abridgment.txt').write_text(text)
    atomic_json(root / 'plan.json', {'title': 'Sample', 'segments': [{'id': '001', 'title': 'One'}]})
    atomic_json(root / 'alignments/001.json', {
        'source_paragraphs': text.split('\n\n'), 'draft_paragraphs': text.split('\n\n'),
        'mapping': [{'draft_para': 0, 'source_paras': [0], 'note': 'verbatim'},
                    {'draft_para': 1, 'source_paras': [1], 'note': 'verbatim'}]})
    targets = []
    for kind, extension in [('audio', 'mp3'), ('graphic', 'png')]:
        path = root / kind / f'001.{extension}'
        path.parent.mkdir()
        path.write_bytes(b'0123456789abcdef')
        target = {'id': f'{kind}-001', 'kind': kind, 'title': f'Chapter one {kind}',
                  'segment_id': '001', 'path': path.relative_to(root).as_posix(),
                  'sha256': sha256_file(path), 'mime_type': 'audio/mpeg' if kind == 'audio' else 'image/png',
                  'duration_seconds': 10.0 if kind == 'audio' else None}
        target['revision'] = target_revision(target)
        targets.append(target)
    kwargs = {'text_revision': digest(text),
              'outputs': inventory(root, ['abridgment.txt', 'plan.json', 'alignments/001.json', 'audio/001.mp3', 'graphic/001.png']),
              'media_index': {'version': 1, 'book_id': 'sample', 'text_revision': digest(text), 'targets': targets},
              'stage_summary': {'status': 'complete', 'selected_outputs': ['text', 'audio', 'graphic'],
                                'stages': {s: {'status': 'complete'} for s in ['assembly', 'alignment', 'audio', 'graphic']}}}
    revision = snapshot_revision(book, **kwargs)['revision']
    storage = HostedPublications(tmp_path / 'hosted')
    artifacts = ArtifactStore(work_dir=tmp_path / 'empty', books_dir=tmp_path / 'books')
    reviews = ReviewStore(tmp_path / 'reviews.sqlite')
    auth = AuthConfig(session_seconds=3600)
    client = TestClient(create_app(artifacts=artifacts, reviews=reviews, auth=auth, hosted=storage))
    return client, storage, book, kwargs, revision, reviews


def publish(hosted, channel='review', revision=None):
    client, storage, book, kwargs, first, reviews = hosted
    revision = revision or first
    sign_in(client, ADMIN_PASSWORD)
    response = client.post('/api/books/sample/revisions', content=archive_snapshot(book, revision),
                           headers={'Content-Type': 'application/gzip'})
    assert response.status_code == 201, response.text
    response = client.post('/api/books/sample/publication', json={'revision': revision, 'channel': channel})
    assert response.status_code == 200, response.text
    return revision


def media_note(hosted, kind='audio', **extra):
    client, _, _, kwargs, revision, _ = hosted
    target = next(t for t in kwargs['media_index']['targets'] if t['kind'] == kind)
    body = {'scope': kind, 'target_id': target['id'], 'target_revision': target['revision'],
            'publication_revision': revision, 'body': 'Please review this.', 'timestamp_seconds': 1.25,
            'author': 'impostor'}
    body.update(extra)
    return client.post('/api/books/sample/comments', json=body)


def test_first_book_upload_auth_independent_pointers_and_download(hosted):
    client, storage, book, _, revision, _ = hosted
    archive = archive_snapshot(book, revision)
    assert client.post('/api/books/sample/revisions', content=archive).status_code == 401
    sign_in(client)
    assert client.post('/api/books/sample/revisions', content=archive).status_code == 403
    publish(hosted)
    assert client.get('/api/books').json()['books'][0]['book_id'] == 'sample'
    status = client.get('/api/books/sample/publication').json()
    assert status['review']['revision'] == revision and status['release'] is None
    assert client.get('/api/books/sample/chapters?channel=release').status_code == 404
    publish(hosted, 'release')
    info = client.get('/api/books/sample/chapters?channel=release').json()
    assert info['publication_revision'] == revision
    assert client.get(info['downloads'][0]['url']).status_code == 200
    text = client.get(f'/api/books/sample/revisions/{revision}/assets/abridgment.txt')
    assert text.text.startswith('The first paragraph.')
    assert text.headers['content-type'].startswith('text/plain')
    assert client.get('/release/sample').status_code == 200
    assert client.get(f'/api/books/sample/revisions/{revision}/assets/../source.txt').status_code == 404
    assert client.get(f'/api/books/sample/revisions/{revision}/assets/revision.json').status_code == 404
    assert (storage.root / 'sample/feedback.json').is_file()


@pytest.mark.parametrize('scope', ['book', 'chapter', 'paragraph', 'audio', 'graphic'])
def test_release_only_book_supports_comment_lifecycle_and_feedback_parity(hosted, scope):
    from forage.review_transport import ReviewTransport
    client, storage, _, kwargs, revision, reviews = hosted
    publish(hosted, 'release')
    assert storage.status('sample')['review'] is None
    current = client.get('/api/books/sample/chapters').json()
    assert current['publication_revision'] == revision
    assert current['publication_channel'] == 'release'
    assert client.get('/api/books/sample/chapters?channel=review').status_code == 404
    assert client.get('/api/books/sample/chapters?channel=release').status_code == 200
    assert client.get('/api/books/sample/media').status_code == 200
    sign_in(client, label='Release reviewer')
    payload = {'scope': scope, 'body': 'A release note', 'publication_revision': revision,
               'segment_id': '001', 'draft_para': 0}
    if scope in {'audio', 'graphic'}:
        target = next(t for t in kwargs['media_index']['targets'] if t['kind'] == scope)
        payload.update(target_id=target['id'], target_revision=target['revision'], timestamp_seconds=2.5)
    response = client.post('/api/books/sample/comments', json=payload)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['publication_revision'] == revision
    assert row['text_revision'] == kwargs['text_revision']
    assert row['author'] == 'Release reviewer'
    assert not row['stale'] and not row['orphaned']
    if scope == 'paragraph':
        assert row['original_text'] == 'The first paragraph.' and row['anchor']
    if scope == 'chapter':
        assert row['original_text'] == 'The first paragraph.\n\nThe second paragraph.'
    if scope in {'audio', 'graphic'}:
        assert row['target_revision'] == payload['target_revision']
    exported = client.get('/api/books/sample/edits.json').json()
    assert exported['comment_count'] == 1
    assert len(exported['media_comments']) == (1 if scope in {'audio', 'graphic'} else 0)
    http = ReviewTransport(base_url='http://testserver', http_client=client)
    local = ReviewTransport(local_root=storage.root)
    feed = http.fetch_feedback('sample')
    assert feed == local.fetch_feedback('sample')
    assert feed['source_id'] == reviews.source_id and feed['comments'][0]['id'] == row['id']
    edited = client.patch(f"/api/comments/{row['id']}", json={'body': 'Edited release note'}).json()
    assert edited['publication_revision'] == revision and edited['anchor'] == row['anchor']
    resolved = client.patch(f"/api/comments/{row['id']}", json={'status': 'resolved'})
    assert resolved.status_code == 200 and resolved.json()['status'] == 'resolved'
    assert http.fetch_feedback('sample') == local.fetch_feedback('sample')
    assert client.get('/api/books/sample/edits.json').json()['comment_count'] == 0
    assert client.delete(f"/api/comments/{row['id']}").status_code == 200
    feed = http.fetch_feedback('sample')
    assert feed == local.fetch_feedback('sample') and feed['comments'] == []
    assert storage.status('sample')['review'] is None
    assert storage.status('sample')['release']['revision'] == revision
    assert len(storage.status('sample')['release']['history']) == 1


def test_historical_release_feedback_keeps_viewed_anchors_after_new_release(hosted):
    from forage.review_transport import ReviewTransport
    client, storage, book, kwargs, first, _ = hosted
    publish(hosted, 'release')
    original_targets = json.loads(json.dumps(kwargs['media_index']['targets']))
    alignment_path = book.work_dir / 'alignments/001.json'
    alignment = json.loads(alignment_path.read_text())
    alignment['draft_paragraphs'][0] = 'A newly released opening.'
    atomic_json(alignment_path, alignment)
    text = '\n\n'.join(alignment['draft_paragraphs'])
    (book.work_dir / 'abridgment.txt').write_text(text)
    for target in kwargs['media_index']['targets']:
        path = book.work_dir / target['path']
        path.write_bytes(b'new release media')
        target['sha256'] = sha256_file(path)
        target['revision'] = target_revision(target)
    kwargs['text_revision'] = kwargs['media_index']['text_revision'] = digest(text)
    kwargs['outputs'] = inventory(book.work_dir, [entry['path'] for entry in kwargs['outputs']])
    second = snapshot_revision(book, **kwargs)['revision']
    publish(hosted, 'release', second)
    assert storage.status('sample')['review'] is None
    assert client.get('/api/books/sample/chapters').json()['publication_revision'] == second
    assert client.get('/api/books/sample/chapters', params={'revision': first}).json()['publication_revision'] == first
    payloads = [{'scope': 'paragraph', 'segment_id': '001', 'draft_para': 0}, *[
        {'scope': t['kind'], 'target_id': t['id'], 'target_revision': t['revision'], 'timestamp_seconds': 1.0}
        for t in original_targets]]
    for payload in payloads:
        response = client.post('/api/books/sample/comments', json={
            **payload, 'publication_revision': first, 'body': 'Note from the older release'})
        assert response.status_code == 201, response.text
        row = response.json()
        assert row['publication_revision'] == first and row['stale']
        if row['scope'] == 'paragraph':
            assert row['original_text'] == 'The first paragraph.'
        else:
            assert row['target_revision'] == payload['target_revision']
    http = ReviewTransport(base_url='http://testserver', http_client=client)
    assert http.fetch_feedback('sample') == ReviewTransport(local_root=storage.root).fetch_feedback('sample')
    status = storage.status('sample')
    assert status['review'] is None
    assert [item['revision'] for item in status['release']['history']] == [first, second]
    # A deliberately created review channel becomes the default without
    # changing the public release or historical comment anchors.
    publish(hosted, 'review', first)
    assert client.get('/api/books/sample/chapters').json()['publication_revision'] == first
    assert client.get('/api/books/sample/chapters?channel=release').json()['publication_revision'] == second


def test_media_comments_original_anchors_edit_resolve_delete_full_feed(hosted):
    client, storage, _, _, revision, reviews = hosted
    publish(hosted)
    sign_in(client, label='Alice')
    audio = media_note(hosted).json()
    graphic = media_note(hosted, 'graphic').json()
    assert audio['author'] == 'Alice' and audio['publication_revision'] == revision
    assert audio['scope'] == 'audio' and audio['timestamp_seconds'] == 1.25
    assert graphic['target_kind'] == 'graphic' and graphic['timestamp_seconds'] is None
    notes = client.get('/api/books/sample/edits.json').json()
    assert len(notes['media_comments']) == 2 and notes['segments'] == [] and notes['book_comments'] == []
    edited = client.patch(f"/api/comments/{audio['id']}", json={'body': 'New note', 'publication_revision': 'fake', 'author': 'Bob'}).json()
    assert edited['publication_revision'] == revision and edited['author'] == 'Alice'
    assert client.patch(f"/api/comments/{audio['id']}", json={'status': 'resolved'}).status_code == 200
    feed = client.get('/api/books/sample/feedback').json()
    assert feed['complete'] is True and feed['source_id'] == reviews.source_id
    assert len(feed['comments']) == 2 and next(c for c in feed['comments'] if c['id'] == audio['id'])['status'] == 'resolved'
    assert client.delete(f"/api/comments/{graphic['id']}").status_code == 200
    projected = json.loads((storage.root / 'sample/feedback.json').read_text())
    assert [c['id'] for c in projected['comments']] == [audio['id']]
    assert projected == client.get('/api/books/sample/feedback').json()


@pytest.mark.parametrize('time', [True, False, -0.1, 10.001, '1.0', None, 10 ** 400])
def test_audio_rejects_invalid_timestamp(hosted, time):
    publish(hosted)
    assert media_note(hosted, timestamp_seconds=time).status_code == 400


@pytest.mark.parametrize('time', ['NaN', 'Infinity', '-Infinity'])
def test_audio_rejects_nonfinite_json_number(hosted, time):
    publish(hosted)
    client, _, _, kwargs, revision, _ = hosted
    target = kwargs['media_index']['targets'][0]
    payload = json.dumps({'scope': 'audio', 'target_id': target['id'], 'target_revision': target['revision'],
                          'publication_revision': revision, 'body': 'Bad time', 'timestamp_seconds': 'REPLACE'})
    payload = payload.replace('"REPLACE"', time)
    assert client.post('/api/books/sample/comments', content=payload, headers={'Content-Type': 'application/json'}).status_code == 400


def test_comment_requires_viewed_revision_and_target(hosted):
    publish(hosted)
    assert media_note(hosted, publication_revision=None).status_code == 409
    assert media_note(hosted, target_revision='wrong').status_code == 409
    assert media_note(hosted, target_id='missing').status_code == 404
    assert media_note(hosted, publication_revision='f' * 64).status_code == 404


def test_audio_ranges_and_media_mime(hosted):
    publish(hosted)
    client = hosted[0]
    media = client.get('/api/books/sample/media').json()
    audio, graphic = media['targets']
    response = client.get(audio['url'], headers={'Range': 'bytes=2-5'})
    assert response.status_code == 206 and response.content == b'2345'
    assert response.headers['content-range'] == 'bytes 2-5/16'
    assert response.headers['content-type'] == 'audio/mpeg'
    assert client.get(graphic['url']).headers['content-type'] == 'image/png'


def test_republication_preserves_context_marks_stale_and_orphans(hosted):
    client, storage, book, kwargs, first, reviews = hosted
    publish(hosted)
    audio = media_note(hosted).json()
    graphic = media_note(hosted, 'graphic').json()
    paragraph = client.post('/api/books/sample/comments', json={
        'publication_revision': first, 'scope': 'paragraph', 'segment_id': '001', 'draft_para': 0, 'body': 'Fix paragraph'}).json()
    chapter = client.post('/api/books/sample/comments', json={
        'publication_revision': first, 'scope': 'chapter', 'segment_id': '001', 'body': 'Fix chapter'}).json()
    publish(hosted, 'release')
    old_release = (storage.root / 'sample/release_current.json').read_bytes()
    alignment = json.loads((book.work_dir / 'alignments/001.json').read_text())
    alignment['draft_paragraphs'][0] = 'An improved first paragraph.'
    atomic_json(book.work_dir / 'alignments/001.json', alignment)
    (book.work_dir / 'abridgment.txt').write_text('\n\n'.join(alignment['draft_paragraphs']))
    (book.work_dir / 'audio/001.mp3').write_bytes(b'new audio')
    target = kwargs['media_index']['targets'][0]
    target['sha256'] = sha256_file(book.work_dir / target['path'])
    target['revision'] = target_revision(target)
    kwargs['media_index']['targets'] = [target]
    kwargs['stage_summary']['selected_outputs'] = ['text', 'audio']
    kwargs['text_revision'] = kwargs['media_index']['text_revision'] = digest('changed')
    kwargs['outputs'] = inventory(book.work_dir, ['abridgment.txt', 'plan.json', 'alignments/001.json', 'audio/001.mp3'])
    second = snapshot_revision(book, **kwargs)['revision']
    publish(hosted, revision=second)
    assert (storage.root / 'sample/release_current.json').read_bytes() == old_release
    feed = {c['id']: c for c in client.get('/api/books/sample/feedback').json()['comments']}
    assert feed[audio['id']]['stale'] and feed[graphic['id']]['orphaned']
    assert feed[paragraph['id']]['stale'] and feed[chapter['id']]['stale']
    assert feed[paragraph['id']]['original_text'] == 'The first paragraph.'
    assert feed[chapter['id']]['original_text'] == 'The first paragraph.\n\nThe second paragraph.'
    # A form opened on the old revision may explicitly create a historical note.
    historical = client.post('/api/books/sample/comments', json={
        'publication_revision': first, 'scope': 'paragraph', 'segment_id': '001', 'draft_para': 0, 'body': 'Late old note'}).json()
    assert historical['publication_revision'] == first and historical['stale']
    assert storage.resolve('sample', first)[0].is_dir()
    assert client.get('/api/books/sample/chapters?channel=release').json()['publication_revision'] == first


def test_old_database_migrates_idempotently_preserving_legacy_rows(tmp_path):
    db = tmp_path / 'old.db'
    with sqlite3.connect(db) as conn:
        conn.executescript(_SCHEMA)
        conn.execute("INSERT INTO comments VALUES ('legacy','sample','001',0,'anchor','','minor','other','open','note','Alice',1,2)")
    first = ReviewStore(db)
    assert first.get('legacy')['anchor'] == 'anchor'
    assert first.get('legacy')['original_text'] is None
    second = ReviewStore(db)
    assert first.source_id == second.source_id
    assert second.get('legacy')['updated_at'] == 2


@pytest.mark.parametrize('path', ['/revisions', '/publication'])
@pytest.mark.parametrize('origin', ['null', 'https://evil.example'])
def test_new_unsafe_endpoints_keep_origin_guard(hosted, path, origin):
    client = hosted[0]
    sign_in(client, ADMIN_PASSWORD)
    assert client.post('/api/books/sample' + path, content=b'x', headers={'Origin': origin}).status_code == 403


def test_bounded_upload_and_failed_upload_preserve_current(hosted):
    client, storage, _, _, revision, _ = hosted
    publish(hosted)
    pointer = (storage.root / 'sample/review_current.json').read_bytes()
    storage.max_archive_bytes = 3
    assert client.post('/api/books/sample/revisions', content=b'1234').status_code == 413
    assert client.post('/api/books/sample/revisions', content=b'x').status_code == 400
    assert (storage.root / 'sample/review_current.json').read_bytes() == pointer


def test_baked_revision_and_whole_book_overlay_do_not_fallback(hosted, tmp_path):
    client, _, book, kwargs, revision, _ = hosted
    artifacts = ArtifactStore(work_dir=book.work_dir.parent, books_dir=tmp_path / 'none')
    selected = artifacts.selected('sample')
    assert selected.revision_info('sample')['publication_revision'] == revision
    assert len(selected.media('sample')['targets']) == 2
    overlay = tmp_path / 'overlay'
    atomic_json(overlay / 'sample/alignments/001.json', {'draft_paragraphs': ['Overlay']})
    artifacts = ArtifactStore(work_dir=book.work_dir.parent, books_dir=tmp_path / 'none', overlay_work_dir=overlay)
    selected = artifacts.selected('sample')
    assert selected.media('sample')['targets'] == []
    assert selected.revision_info('sample')['publication_revision'] is None


def test_hosted_limit_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('FORAGE_HOSTED_ROOT', str(tmp_path / 'hosted'))
    monkeypatch.setenv('FORAGE_MAX_UPLOAD_BYTES', '123')
    monkeypatch.setenv('FORAGE_MAX_EXPANDED_BYTES', '456')
    monkeypatch.setenv('FORAGE_MAX_UPLOAD_FILES', '7')
    store = ArtifactStore()
    assert (store.hosted.max_archive_bytes, store.hosted.max_expanded_bytes, store.hosted.max_files) == (123, 456, 7)
    monkeypatch.setenv('FORAGE_MAX_UPLOAD_BYTES', '0')
    with pytest.raises(ValueError, match='positive'):
        ArtifactStore()


def test_mutable_review_configuration_cannot_modify_snapshot(hosted, monkeypatch):
    client, _, book, _, revision, reviews = hosted
    root = book.work_dir / 'publications' / revision
    with pytest.raises(ValueError, match='outside immutable'):
        ReviewStore(root / 'review.db')
    assert not (root / 'review.db').exists()
    monkeypatch.setenv('FORAGE_EDITS_DIR', str(root))
    with pytest.raises(ValueError, match='outside immutable'):
        create_app(artifacts=client.app.state.artifacts, reviews=reviews,
                   auth=client.app.state.auth)
    assert not (root / 'sample').exists()


def test_unknown_audio_duration_does_not_invent_limit(hosted):
    client, _, book, kwargs, _, _ = hosted
    kwargs['media_index']['targets'][0]['duration_seconds'] = None
    target = kwargs['media_index']['targets'][0]
    target['revision'] = target_revision(target)
    revision = snapshot_revision(book, **kwargs)['revision']
    publish(hosted, revision=revision)
    response = media_note(hosted, publication_revision=revision, timestamp_seconds=1000000)
    assert response.status_code == 201 and response.json()['timestamp_seconds'] == 1000000
    assert client.get('/api/books/sample/media').json()['targets'][0]['duration_seconds'] is None


def test_failed_projection_keeps_committed_mutation_and_blocks_stale_local_feed(hosted, monkeypatch):
    from forage import production_state
    client, storage, _, _, revision, _ = hosted
    publish(hosted)
    old_feed = (storage.root / 'sample/feedback.json').read_bytes()
    real_write = production_state.atomic_json

    def fail_projection(path, value):
        if path.name == 'feedback.json':
            raise OSError('disk failure')
        return real_write(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(production_state, 'atomic_json', fail_projection)
        response = media_note(hosted)
        assert response.status_code == 201
        assert 'feedback_projection_warning' in response.json()
        assert (storage.root / 'sample/feedback_pending').is_file()
        assert (storage.root / 'sample/feedback.json').read_bytes() == old_feed
        feed = client.get('/api/books/sample/feedback').json()
        assert feed['comments'][0]['id'] == response.json()['id']
        promoted = client.post('/api/books/sample/publication', json={'revision': revision, 'channel': 'release'})
        assert promoted.status_code == 200 and 'feedback_projection_warning' in promoted.json()
        assert storage.status('sample')['release']['revision'] == revision
    # Repeating publication repairs the projection without duplicate history.
    publish(hosted)
    assert not (storage.root / 'sample/feedback_pending').exists()
    assert json.loads((storage.root / 'sample/feedback.json').read_text()) == feed


def test_displayed_feedback_responses_are_scoped_to_original_site(hosted):
    client, storage, _, _, revision, reviews = hosted
    publish(hosted)
    row = client.post('/api/books/sample/comments', json={
        'publication_revision': revision, 'scope': 'paragraph', 'segment_id': '001',
        'draft_para': 0, 'body': 'A note'}).json()
    atomic_json(storage.root / 'sample/editorial/review_apply_ledger.json', {'entries': [
        {'source_id': 'different-site', 'comment_id': row['id'], 'segment_id': '001',
         'action': 'skipped', 'reason': 'Wrong response'},
        {'source_id': reviews.source_id, 'comment_id': row['id'], 'segment_id': '001',
         'action': 'applied', 'reason': 'Correct response'},
    ]})
    chapter = client.get('/api/books/sample/chapters/001').json()
    assert [r['body'] for r in chapter['comments'][0]['llm_responses']] == ['Correct response']


def test_web_only_import_start_upload_media_without_pipeline_dependencies(hosted, tmp_path):
    _, _, book, _, revision, _ = hosted
    archive = tmp_path / 'snapshot.tar.gz'
    archive.write_bytes(archive_snapshot(book, revision))
    script = r'''
import builtins, sys
original = builtins.__import__
blocked = {'anthropic', 'openai', 'PIL', 'typer', 'rich', 'rapidfuzz', 'json_repair', 'ebooklib', 'bs4', 'lxml', 'jinja2'}
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in blocked:
        raise AssertionError('pipeline dependency imported: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from pathlib import Path
from fastapi.testclient import TestClient
from forage.webapp.app import create_app
from forage.webapp.store import ArtifactStore, ReviewStore
from forage.webapp.auth import AuthConfig
from forage.hosted_publication import HostedPublications
root = Path(sys.argv[1])
app = create_app(ArtifactStore(work_dir=root/'empty', books_dir=root/'books'),
                 ReviewStore(root/'web.db'), AuthConfig(session_seconds=3600),
                 HostedPublications(root/'publications'))
app.state.accounts.create_user('admin', 'web-only-admin-password', role='admin')
with TestClient(app) as client:
    assert client.get('/healthz').status_code == 200
    assert client.post('/api/session',json={'username':'admin','password':'web-only-admin-password'}).status_code == 200
    response = client.post('/api/books/sample/revisions',content=Path(sys.argv[2]).read_bytes())
    assert response.status_code == 201, response.text
    revision = response.json()['revision']
    assert client.post('/api/books/sample/publication',json={'revision':revision,'channel':'review'}).status_code == 200
    response = client.get('/api/books/sample/media')
    assert response.status_code == 200 and len(response.json()['targets']) == 2
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path / 'web-only'), str(archive)],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
