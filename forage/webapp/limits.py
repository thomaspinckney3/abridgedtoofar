"""Request admission before JSON buffering, parsing or expensive public reads."""
from __future__ import annotations

import asyncio
import math
import re
import threading

from starlette.requests import Request
from starlette.responses import JSONResponse

from .auth import RateLimiter, client_ip

MAX_JSON_BYTES = 64 * 1024
_UPLOAD = re.compile(r'/api/books/[A-Za-z0-9][A-Za-z0-9_-]{0,63}/revisions\Z')


class RequestLimitsMiddleware:
    def __init__(self, app, *, trust_proxy=False, upload_limit=128 * 1024 * 1024,
                 json_limit=MAX_JSON_BYTES, body_timeout=15.0, max_reads=8,
                 max_writes=16, read_limit=180, global_read_limit=600):
        self.app = app
        self.trust_proxy = trust_proxy
        self.upload_limit, self.json_limit = upload_limit, json_limit
        self.body_timeout = body_timeout
        self.reads = RateLimiter(read_limit, 60)
        self.all_reads = RateLimiter(global_read_limit, 60, max_keys=1)
        self.read_slots = threading.BoundedSemaphore(max_reads)
        self.write_slots = threading.BoundedSemaphore(max_writes)
        self.upload_slots = threading.BoundedSemaphore(1)

    async def reject(self, scope, receive, send, status, detail, retry=None):
        headers = {'Cache-Control': 'no-store'}
        if retry:
            headers['Retry-After'] = str(math.ceil(retry))
        await JSONResponse({'detail': detail}, status_code=status, headers=headers)(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path, method = scope['path'], scope['method']
        upload = method == 'POST' and bool(_UPLOAD.fullmatch(path))
        writing = method in {'POST', 'PUT', 'PATCH', 'DELETE'}
        reading = method in {'GET', 'HEAD'} and (path == '/api/books' or path.startswith('/api/books/'))
        if reading:
            retry = self.reads.check(client_ip(Request(scope), self.trust_proxy))
            if not retry:
                retry = self.all_reads.check('all')
            if retry:
                return await self.reject(scope, receive, send, 429, 'Too many reads. Try again shortly.', retry)
        gate = self.upload_slots if upload else self.write_slots if writing else self.read_slots if reading else None
        if gate is not None and not gate.acquire(blocking=False):
            return await self.reject(scope, receive, send, 503, 'Server is busy. Try again shortly.', 1)
        try:
            if writing:
                limit = self.upload_limit if upload else self.json_limit
                lengths = [value for key, value in scope['headers'] if key.lower() == b'content-length']
                if lengths:
                    if len(lengths) != 1 or not lengths[0].isdigit():
                        return await self.reject(scope, receive, send, 400, 'Bad content length.')
                    # Compare decimal lengths without converting an unbounded integer.
                    length = lengths[0].lstrip(b'0') or b'0'
                    maximum = str(limit).encode()
                    if len(length) > len(maximum) or (len(length) == len(maximum) and length > maximum):
                        return await self.reject(scope, receive, send, 413, 'Request body is too large.')
                if not upload:
                    body = bytearray()
                    try:
                        async with asyncio.timeout(self.body_timeout):
                            while True:
                                message = await receive()
                                if message['type'] == 'http.disconnect':
                                    return
                                chunk = message.get('body', b'')
                                if len(body) + len(chunk) > limit:
                                    return await self.reject(scope, receive, send, 413, 'Request body is too large.')
                                body.extend(chunk)
                                if not message.get('more_body', False):
                                    break
                    except TimeoutError:
                        return await self.reject(scope, receive, send, 408, 'Request body timed out.')
                    delivered = False
                    original_receive = receive
                    async def buffered_receive():
                        nonlocal delivered
                        if not delivered:
                            delivered = True
                            return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                        return await original_receive()
                    receive = buffered_receive
            # Upload bodies stay streamed behind require_admin and the route's
            # byte counter. They never enter the general JSON buffer.
            await self.app(scope, receive, send)
        finally:
            if gate is not None:
                gate.release()
