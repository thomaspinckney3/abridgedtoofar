"""Session cookies and request provenance.

The cookie is the whole write boundary: it is unsigned data from the client
until the HMAC says otherwise, so the rejection cases matter more than the
happy path.
"""

from __future__ import annotations

import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from forage.webapp.auth import (ADMIN, PUBLIC, REVIEWER, AuthConfig,
                                AuthConfigError, client_ip, is_secure)

from .conftest import ADMIN_TOKEN, REVIEW_TOKEN


@pytest.fixture
def auth() -> AuthConfig:
    return AuthConfig(
        review_token=REVIEW_TOKEN, admin_token=ADMIN_TOKEN,
        secret_key=b"secret-key-for-tests", session_seconds=3600, epoch="0",
        trust_proxy=False, production=False, generated=(),
    )


# -- tokens ----------------------------------------------------------------


@pytest.mark.parametrize("token, expected", [
    (REVIEW_TOKEN, REVIEWER),
    (ADMIN_TOKEN, ADMIN),
    ("wrong", None),
    ("", None),
    (REVIEW_TOKEN + "x", None),
    (REVIEW_TOKEN.upper(), None),
])
def test_authenticate_maps_tokens_to_roles(auth, token, expected):
    assert auth.authenticate(token) == expected


def test_empty_admin_token_does_not_authenticate(auth):
    """An unset admin token is falsy — it must not match an empty candidate."""
    disabled = replace(auth, admin_token="")
    assert disabled.authenticate("") is None
    assert disabled.admin_enabled is False


# -- cookie round trip -----------------------------------------------------


@pytest.mark.parametrize("role", [REVIEWER, ADMIN])
def test_issued_cookie_verifies(auth, role):
    session = auth.verify(auth.issue(role, "alice"))
    assert session.role == role
    assert session.label == "alice"
    assert session.can_write is True


def test_public_role_cannot_be_issued(auth):
    with pytest.raises(ValueError):
        auth.issue(PUBLIC)


def test_label_is_display_only_and_grants_nothing(auth):
    session = auth.verify(auth.issue(REVIEWER, "admin"))
    assert session.role == REVIEWER
    assert session.can_admin is False


# -- cookie rejection ------------------------------------------------------


def test_role_cannot_be_escalated_by_editing_the_payload(auth):
    """The signature covers the role, so rewriting reviewer->admin invalidates
    it. This is the attack the signing key exists to stop."""
    cookie = auth.issue(REVIEWER, "alice")
    tampered = cookie.replace(f".{REVIEWER}.", f".{ADMIN}.", 1)
    assert tampered != cookie
    assert auth.verify(tampered).role == PUBLIC


def test_a_different_key_does_not_verify(auth):
    cookie = auth.issue(ADMIN, "alice")
    assert replace(auth, secret_key=b"another-key-entirely").verify(cookie).role == PUBLIC


def test_expired_cookie_is_rejected(auth):
    expired = replace(auth, session_seconds=-1)
    assert expired.verify(expired.issue(ADMIN, "alice")).role == PUBLIC


def test_epoch_bump_invalidates_live_sessions(auth):
    """The documented way to sign everyone out after rotating a token."""
    cookie = auth.issue(ADMIN, "alice")
    assert replace(auth, epoch="1").verify(cookie).role == PUBLIC


def test_admin_cookie_downgrades_when_the_admin_token_is_withdrawn(auth):
    cookie = auth.issue(ADMIN, "alice")
    session = replace(auth, admin_token="").verify(cookie)
    assert session.role == REVIEWER
    assert session.can_admin is False
    assert session.label == "alice"


@pytest.mark.parametrize("cookie", [
    None, "", "garbage", "a.b.c.d.e.f", "v1.admin.9999999999.0.YWxpY2U",
    "v1.admin.9999999999.0.YWxpY2U.!!!not-base64!!!",
    "v2.admin.9999999999.0.YWxpY2U.c2ln",
])
def test_malformed_cookies_yield_the_public_session(auth, cookie):
    assert auth.verify(cookie).role == PUBLIC


def test_unknown_role_in_a_validly_signed_cookie_is_rejected(auth):
    """Belt and braces: even something we signed ourselves is re-checked
    against the known roles."""
    expiry = int(time.time() + 3600)
    payload = f"v1.superuser.{expiry}.0."
    from forage.webapp.auth import _b64  # noqa: PLC0415 - test reaches inside
    forged = f"{payload}.{_b64(auth._sign(payload))}"
    assert auth.verify(forged).role == PUBLIC


# -- startup configuration -------------------------------------------------


def test_production_refuses_to_start_without_secrets(monkeypatch):
    monkeypatch.setenv("FORAGE_ENV", "production")
    for key in ("FORAGE_SECRET_KEY", "FORAGE_REVIEW_TOKEN", "FORAGE_ADMIN_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(AuthConfigError, match="FORAGE_SECRET_KEY"):
        AuthConfig.from_env()


def test_production_refuses_short_secrets(monkeypatch):
    monkeypatch.setenv("FORAGE_ENV", "production")
    monkeypatch.setenv("FORAGE_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("FORAGE_REVIEW_TOKEN", "short")
    with pytest.raises(AuthConfigError, match="at least"):
        AuthConfig.from_env()


def test_admin_token_may_not_equal_the_review_token(monkeypatch):
    """Otherwise every reviewer is silently an admin."""
    monkeypatch.setenv("FORAGE_ENV", "production")
    monkeypatch.setenv("FORAGE_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("FORAGE_REVIEW_TOKEN", "y" * 32)
    monkeypatch.setenv("FORAGE_ADMIN_TOKEN", "y" * 32)
    with pytest.raises(AuthConfigError, match="must differ"):
        AuthConfig.from_env()


def test_presence_of_a_fly_app_name_implies_production(monkeypatch):
    monkeypatch.delenv("FORAGE_ENV", raising=False)
    monkeypatch.setenv("FLY_APP_NAME", "forage-review")
    monkeypatch.delenv("FORAGE_SECRET_KEY", raising=False)
    monkeypatch.delenv("FORAGE_REVIEW_TOKEN", raising=False)
    with pytest.raises(AuthConfigError):
        AuthConfig.from_env()


def test_development_generates_what_is_missing(monkeypatch):
    monkeypatch.delenv("FORAGE_ENV", raising=False)
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    config = AuthConfig.from_env()
    assert "FORAGE_REVIEW_TOKEN" in config.generated
    assert config.review_token and config.secret_key


# -- request provenance ----------------------------------------------------


def _request(headers: dict, host: str = "10.0.0.1", scheme: str = "http"):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host),
                           url=SimpleNamespace(scheme=scheme))


def test_client_ip_prefers_the_platform_header():
    request = _request({"fly-client-ip": "203.0.113.9",
                        "x-forwarded-for": "1.2.3.4"})
    assert client_ip(request, trust_proxy=True) == "203.0.113.9"


def test_client_ip_takes_the_rightmost_forwarded_entry():
    """Proxies append. Everything left of the last hop was supplied by the
    caller, who would otherwise mint a fresh rate-limit bucket per forged
    address."""
    request = _request({"x-forwarded-for": "9.9.9.9, 8.8.8.8, 203.0.113.9"})
    assert client_ip(request, trust_proxy=True) == "203.0.113.9"


def test_client_ip_ignores_forwarded_headers_when_no_proxy_is_declared():
    request = _request({"x-forwarded-for": "203.0.113.9"}, host="10.0.0.1")
    assert client_ip(request, trust_proxy=False) == "10.0.0.1"


@pytest.mark.parametrize("header, expected", [
    ("https", True),
    ("http", False),
    ("https, http", False),
    ("http, https", True),
])
def test_is_secure_reads_the_rightmost_forwarded_proto(header, expected):
    assert is_secure(_request({"x-forwarded-proto": header}), trust_proxy=True) is expected


def test_is_secure_ignores_the_header_when_no_proxy_is_declared():
    request = _request({"x-forwarded-proto": "https"}, scheme="http")
    assert is_secure(request, trust_proxy=False) is False
