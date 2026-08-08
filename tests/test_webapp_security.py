"""Route-level security behaviour: what the app exposes, what it refuses, and
what it refuses to take the caller's word for.

Each test here corresponds to a defect that was live in production, so a
failure means a real regression rather than a changed opinion about style.
"""

from __future__ import annotations

import pytest

from .conftest import ADMIN_TOKEN, ALLOWED_HOST, BOOK_ID, REVIEW_TOKEN, sign_in


# -- schema exposure -------------------------------------------------------


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_schema_and_doc_viewers_are_not_served(client, path):
    """docs_url/redoc_url alone leave openapi_url serving the full route
    table, admin endpoints included, to anonymous callers."""
    assert client.get(path).status_code == 404


def test_healthz_stays_public(client):
    # The platform's liveness probe is unauthenticated by necessity.
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True


# -- cross-origin writes ---------------------------------------------------


def _write(client, origin: str | None):
    headers = {"Origin": origin} if origin is not None else {}
    return client.post(f"/api/books/{BOOK_ID}/comments", json={}, headers=headers)


def test_null_origin_write_is_refused(make_client):
    """"null" is an opaque origin — a sandboxed iframe or a data:/file:
    document. It must fail the check, not skip it. A 401 here means the guard
    let it through to the auth layer."""
    client = make_client(allowed_hosts=ALLOWED_HOST)
    response = _write(client, "null")
    assert response.status_code == 403
    assert "Cross-origin" in response.json()["detail"]


def test_foreign_origin_write_is_refused(make_client):
    client = make_client(allowed_hosts=ALLOWED_HOST)
    assert _write(client, "https://evil.example.com").status_code == 403


def test_allowed_origin_reaches_the_auth_layer(make_client):
    """403 would mean the allowlist rejected its own hostname; 401 is the
    correct outcome for an unauthenticated caller from a good origin."""
    client = make_client(allowed_hosts=ALLOWED_HOST)
    assert _write(client, f"https://{ALLOWED_HOST}").status_code == 401


def test_absent_origin_reaches_the_auth_layer(client):
    # Non-browser clients send no Origin; they are gated by the token instead.
    assert _write(client, None).status_code == 401


def test_origin_is_checked_against_the_allowlist_not_the_host_header(make_client):
    """With an allowlist configured, a caller cannot authorise its own write by
    setting Origin and Host to the same attacker-chosen value."""
    client = make_client(allowed_hosts=ALLOWED_HOST)
    response = client.post(
        f"/api/books/{BOOK_ID}/comments", json={},
        headers={"Origin": "https://evil.example.com", "Host": "evil.example.com"})
    assert response.status_code == 403


def test_unconfigured_deployment_falls_back_to_host_comparison(make_client):
    """Without an allowlist the check is weaker but not absent: the origin
    still has to match the host the request arrived on."""
    client = make_client()  # no FORAGE_ALLOWED_HOSTS
    assert _write(client, "https://evil.example.com").status_code == 403
    assert _write(client, "http://testserver").status_code == 401


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_every_unsafe_method_is_guarded(make_client, method):
    client = make_client(allowed_hosts=ALLOWED_HOST)
    response = getattr(client, method)("/api/comments/whatever",
                                       headers={"Origin": "null"})
    assert response.status_code == 403


def test_reads_are_not_origin_guarded(make_client):
    # The guard covers writes only; a cross-origin GET is not a state change.
    client = make_client(allowed_hosts=ALLOWED_HOST)
    response = client.get("/api/books", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200


# -- comment attribution ---------------------------------------------------


def _comment(client, **payload):
    body = {"scope": "book", "body": "attribution test"}
    body.update(payload)
    return client.post(f"/api/books/{BOOK_ID}/comments", json=body)


def test_author_comes_from_the_session_not_the_body(client):
    """A client-supplied author lets any reviewer sign a comment with someone
    else's name — they all share one token, so nothing else distinguishes
    them."""
    sign_in(client, label="alice")
    response = _comment(client, author="bob-the-impostor")
    assert response.status_code == 201
    assert response.json()["author"] == "alice"


def test_author_cannot_be_rewritten_by_patch(client):
    sign_in(client, label="alice")
    comment_id = _comment(client).json()["id"]

    response = client.patch(f"/api/comments/{comment_id}",
                            json={"body": "edited", "author": "bob-the-impostor"})
    assert response.status_code == 200
    assert response.json()["author"] == "alice"
    assert response.json()["body"] == "edited"


def test_unlabelled_session_yields_no_author_rather_than_a_claimed_one(client):
    sign_in(client, label="")
    assert _comment(client, author="bob-the-impostor").json()["author"] == ""


# -- role separation -------------------------------------------------------


def test_publishing_requires_the_admin_token(client):
    sign_in(client, token=REVIEW_TOKEN)
    assert client.post(f"/api/books/{BOOK_ID}/publish").status_code == 403


def test_admin_may_publish(client, tmp_path, monkeypatch):
    monkeypatch.setenv("FORAGE_EDITS_DIR", str(tmp_path / "edits"))
    sign_in(client, token=ADMIN_TOKEN)
    response = client.post(f"/api/books/{BOOK_ID}/publish")
    assert response.status_code == 200
    assert (tmp_path / "edits" / BOOK_ID / "edits.json").is_file()


def test_anonymous_callers_cannot_write(client):
    assert _comment(client).status_code == 401
