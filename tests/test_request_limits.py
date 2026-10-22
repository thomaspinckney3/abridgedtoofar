"""Admission is enforced before JSON parsing, including streamed bodies."""
import asyncio
import threading
import time

import httpx
import pytest
from starlette.responses import Response

from forage.webapp.auth import RateLimiter
from forage.webapp.limits import RequestLimitsMiddleware, MAX_JSON_BYTES
from .conftest import ADMIN_PASSWORD, REVIEW_PASSWORD, sign_in
from .test_web_media import hosted


def scope(path='/api/users', method='POST', headers=()):
    return {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
            'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
            'query_string': b'', 'root_path': '', 'headers': list(headers),
            'client': ('127.0.0.1', 1), 'server': ('testserver', 80)}


async def invoke(app, request_scope=None, chunks=(b'',)):
    messages, reads = [], []
    remaining = list(chunks)
    async def receive():
        reads.append(True)
        if not remaining:
            return {'type': 'http.disconnect'}
        chunk = remaining.pop(0)
        return {'type': 'http.request', 'body': chunk, 'more_body': bool(remaining)}
    await app(request_scope or scope(), receive, _sender(messages))
    return messages, reads


def _sender(messages):
    async def send(message):
        messages.append(message)
    return send


def status(messages):
    return next(m['status'] for m in messages if m['type'] == 'http.response.start')


async def ok(request_scope, receive, send):
    await Response('ok')(request_scope, receive, send)


@pytest.mark.parametrize('length,expected', [(b'65', 413), (b'9' * 5000, 413),
                                             (b'-1', 400), (b'abc', 400)])
def test_declared_oversize_and_invalid_lengths_never_read_body(length, expected):
    app = RequestLimitsMiddleware(ok, json_limit=64)
    messages, reads = asyncio.run(invoke(app, scope(headers=[(b'content-length', length)])))
    assert status(messages) == expected and not reads


@pytest.mark.parametrize('headers', [[], [(b'content-length', b'1')]])
def test_chunked_and_understated_body_lengths_are_counted(headers):
    app = RequestLimitsMiddleware(ok, json_limit=64)
    messages, reads = asyncio.run(invoke(app, scope(headers=headers), (b'x' * 32, b'x' * 33)))
    assert status(messages) == 413 and len(reads) == 2


def test_duplicate_length_is_rejected():
    app = RequestLimitsMiddleware(ok)
    messages, reads = asyncio.run(invoke(app, scope(headers=[(b'content-length', b'1')] * 2)))
    assert status(messages) == 400 and not reads


def test_admitted_body_is_replayed_exactly_once():
    seen = []
    async def collect(request_scope, receive, send):
        seen.append(await receive())
        await ok(request_scope, receive, send)
    messages, _ = asyncio.run(invoke(RequestLimitsMiddleware(collect), chunks=(b'{', b'"x":1}')))
    assert status(messages) == 200
    assert seen == [{'type': 'http.request', 'body': b'{"x":1}', 'more_body': False}]


def test_body_timeout_and_disconnect_release_admission_slots():
    async def exercise():
        app = RequestLimitsMiddleware(ok, max_writes=1, body_timeout=0.01)
        messages = []
        async def stalled():
            await asyncio.Event().wait()
        await app(scope(), stalled, _sender(messages))
        assert status(messages) == 408
        assert status((await invoke(app))[0]) == 200
        assert (await invoke(app, chunks=()))[0] == []
        assert status((await invoke(app))[0]) == 200
    asyncio.run(exercise())


def test_read_and_write_concurrency_is_bounded_and_health_stays_available():
    async def exercise(path, method, option):
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(request_scope, receive, send):
            if request_scope['path'] != '/healthz':
                started.set()
                await release.wait()
            await ok(request_scope, receive, send)
        app = RequestLimitsMiddleware(slow, **{option: 1})
        first = asyncio.create_task(invoke(app, scope(path, method)))
        await started.wait()
        assert status((await invoke(app, scope(path, method)))[0]) == 503
        assert status((await invoke(app, scope('/healthz', 'GET')))[0]) == 200
        release.set()
        assert status((await first)[0]) == 200
        assert status((await invoke(app, scope(path, method)))[0]) == 200
    asyncio.run(exercise('/api/books/sample', 'GET', 'max_reads'))
    asyncio.run(exercise('/api/users', 'POST', 'max_writes'))


def test_upload_is_separate_streamed_admission():
    app = RequestLimitsMiddleware(ok, json_limit=8, upload_limit=64)
    upload = scope('/api/books/sample/revisions', headers=[(b'content-length', b'32')])
    messages, reads = asyncio.run(invoke(app, upload, (b'x' * 32,)))
    assert status(messages) == 200 and not reads
    upload['headers'] = [(b'content-length', b'65')]
    assert status(asyncio.run(invoke(app, upload))[0]) == 413


def test_public_read_budgets_apply_per_ip_and_globally():
    async def exercise():
        app = RequestLimitsMiddleware(ok, read_limit=1, global_read_limit=2)
        first = scope('/api/books', 'GET')
        assert status((await invoke(app, first))[0]) == 200
        assert status((await invoke(app, first))[0]) == 429
        for ip, expected in [('127.0.0.2', 200), ('127.0.0.3', 429)]:
            request = {**first, 'client': (ip, 1)}
            assert status((await invoke(app, request))[0]) == expected
    asyncio.run(exercise())


def test_large_json_is_rejected_before_parser_even_on_locked_login(client, monkeypatch):
    from starlette.requests import Request
    for _ in range(8):
        assert client.post('/api/session', json={'username': 'admin', 'password': 'wrong'}).status_code == 403
    async def forbidden(self):
        raise AssertionError('oversized JSON reached parser')
    monkeypatch.setattr(Request, 'json', forbidden)
    for path in ('/api/users', '/api/session'):
        response = client.post(path, content=b'{"x":"' + b'x' * MAX_JSON_BYTES,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 413
        assert response.headers['cache-control'] == 'no-store'


def test_valid_login_cannot_reset_another_accounts_guess_budget(client):
    for i in range(10):
        username = 'ADMIN' if i % 2 else 'admin'
        result = client.post('/api/session', json={'username': username, 'password': 'wrong'})
        assert result.status_code == (403 if i < 8 else 429)
        assert client.post('/api/session', json={'username': 'alice', 'password': REVIEW_PASSWORD}).status_code == 200


def test_successful_logins_cannot_reset_ip_budget(client):
    for _ in range(30):
        assert client.post('/api/session', json={'username': 'alice', 'password': REVIEW_PASSWORD}).status_code == 200
    assert client.post('/api/session', json={'username': 'unused', 'password': 'wrong'}).status_code == 429


def test_rate_limiter_is_bounded_and_recovers_at_expiry():
    now = [0.0]
    limiter = RateLimiter(2, 10, max_keys=2, clock=lambda: now[0])
    assert limiter.check('a') == limiter.check('b') == 0
    for i in range(5000):
        assert limiter.check(str(i)) > 0
    assert len(limiter._hits) == 2
    now[0] = 3
    assert limiter.check('a') == 0 and limiter.check('a') > 0
    now[0] = 10
    assert limiter.check('c') == 0  # b expired; a retains its later hit.
    assert limiter.check('a') == 0 and limiter.check('a') > 0
    now[0] = 20
    assert limiter.check('d') == 0 and len(limiter._hits) == 1


def test_unauthenticated_upload_does_not_read_stream(hosted):
    client, *_ = hosted
    async def exercise():
        async def body():
            raise AssertionError('unauthenticated upload body was consumed')
            yield b''
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                                     base_url='http://testserver') as http:
            assert (await http.post('/api/books/sample/revisions', content=body())).status_code == 401
    asyncio.run(exercise())


def test_upload_read_deadline(hosted, monkeypatch):
    client, *_ = hosted
    sign_in(client, ADMIN_PASSWORD)
    timeout = asyncio.timeout
    monkeypatch.setattr(asyncio, 'timeout', lambda seconds: timeout(0.01 if seconds == 120 else seconds))
    async def exercise():
        async def body():
            yield b'first chunk'
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                base_url='http://testserver', cookies=dict(client.cookies)) as http:
            assert (await http.post('/api/books/sample/revisions', content=body())).status_code == 408
            assert (await http.get('/healthz')).status_code == 200
    asyncio.run(exercise())


def test_upload_verification_does_not_block_health_on_same_event_loop(hosted, monkeypatch):
    client, store, *_ = hosted
    sign_in(client, ADMIN_PASSWORD)
    entered, release = threading.Event(), threading.Event()
    def verify(*args):
        entered.set()
        assert release.wait(3), 'upload blocked the event loop'
        return {'revision': 'a' * 64}
    monkeypatch.setattr(store, 'upload', verify)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                base_url='http://testserver', cookies=dict(client.cookies)) as http:
            started = time.monotonic()
            upload = asyncio.create_task(http.post('/api/books/sample/revisions', content=b'archive'))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert (await http.get('/healthz')).status_code == 200
                assert time.monotonic() - started < 2
                assert not upload.done()
            finally:
                release.set()
                response = await upload
            assert response.status_code == 201
    asyncio.run(exercise())
