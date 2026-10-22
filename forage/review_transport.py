"""Confirmed publication and full-feedback transport, independent of providers."""
from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from .hosted_publication import HostedPublications, archive_snapshot, valid_book_id
from .production_state import book_lock

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class TransportError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never replay a login body or session cookie to a redirected origin.
        return None


class ReviewTransport:
    def __init__(self, *, base_url: str | None = None, local_root=None,
                 username: str | None = None, password: str | None = None,
                 http_client=None, feedback_path=None,
                 timeout: float = 30, max_response_bytes: int = MAX_RESPONSE_BYTES):
        if base_url is None and local_root is None:
            base_url = os.environ.get("FORAGE_REVIEW_URL")
            local_root = os.environ.get("FORAGE_REVIEW_LOCAL_ROOT")
        if bool(base_url) == bool(local_root):
            raise ValueError("configure exactly one review site URL or local hosting root")
        self.local = HostedPublications(local_root) if local_root else None
        self.base_url = base_url.rstrip("/") if base_url else None
        if self.base_url:
            parsed = urllib.parse.urlsplit(self.base_url)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment):
                raise ValueError("review site must be an HTTP(S) URL without credentials/query/fragment")
        self.username = username
        self.password = password
        self.http_client = http_client
        self.feedback_path = Path(feedback_path) if feedback_path else None
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._authenticated = False
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def _request(self, method: str, path: str, *, payload: bytes | None = None,
                 content_type: str = "application/json") -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json", "Content-Type": content_type}
        try:
            if self.http_client is not None:
                response = self.http_client.request(method, url, content=payload,
                                                    headers=headers, follow_redirects=False,
                                                    timeout=self.timeout)
                status = response.status_code
                raw = response.content
            else:
                request = urllib.request.Request(url, data=payload, headers=headers, method=method)
                with self._opener.open(request, timeout=self.timeout) as response:
                    status = response.status
                    raw = response.read(self.max_response_bytes + 1)
            if not 200 <= status < 300:
                raise TransportError(f"review site rejected {method} {path}: HTTP {status}")
            if len(raw) > self.max_response_bytes:
                raise TransportError("review site response exceeds limit")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise TransportError("review site response must be an object")
            return result
        except urllib.error.HTTPError as exc:
            raise TransportError(f"review site rejected {method} {path}: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransportError(f"review site transport failed: {type(exc).__name__}") from None
        except (ValueError, UnicodeError) as exc:
            raise TransportError("invalid review site JSON response") from exc

    def _login(self):
        if self._authenticated or self.local:
            return
        if self.username and self.password:
            result = self._request("POST", "/api/session", payload=json.dumps(
                {"username": self.username, "password": self.password}).encode())
            if result.get("role") != "admin":
                raise TransportError("publication transport requires an administrator session")
        self._authenticated = True

    def publish(self, book, revision: str, channel: str = "review") -> dict:
        if channel not in {"review", "release"}:
            raise ValueError("publication channel must be review or release")
        payload = archive_snapshot(book, revision)
        if self.local:
            uploaded = self.local.upload(book.book_id, payload)
            pointer = self.local.promote(book.book_id, revision, channel)
        else:
            if not self.username or not self.password:
                raise TransportError("an admin username and password are required to publish to the review site")
            self._login()
            uploaded = self._request("POST", f"/api/books/{book.book_id}/revisions",
                                     payload=payload, content_type="application/gzip")
            if uploaded.get("revision") != revision:
                raise TransportError("review site acknowledged a different uploaded revision")
            pointer = self._request("POST", f"/api/books/{book.book_id}/publication",
                                    payload=json.dumps({"channel": channel, "revision": revision}).encode())
        if (uploaded.get("revision") != revision or pointer.get("revision") != revision
                or pointer.get("channel") != channel or pointer.get("book_id") != book.book_id):
            raise TransportError("review site did not confirm the requested publication")
        return {"success": True, "book_id": book.book_id, "revision": revision,
                "channel": channel, "publication": pointer}

    def fetch_feedback(self, book_id: str) -> dict:
        if not valid_book_id(book_id):
            raise ValueError("invalid book ID")
        if self.local:
            book = self.local._book(book_id)
            if not book.work_dir.is_dir():
                raise FileNotFoundError(f"no hosted book {book_id}")
            with book_lock(book):
                marker = book.work_dir / "feedback_pending"
                if marker.exists() or marker.is_symlink():
                    raise TransportError("hosted feedback projection is pending; fetch via HTTP or repair the projection")
                path = self.feedback_path or book.work_dir / "feedback.json"
                if path.is_symlink():
                    raise ValueError("feedback projection cannot be a symlink")
                with path.open("rb") as stream:
                    raw = stream.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise TransportError("feedback projection exceeds limit")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("feedback projection must be an object")
            return result
        self._login()
        return self._request("GET", f"/api/books/{book_id}/feedback")
