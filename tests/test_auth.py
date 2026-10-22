"""Session configuration and trusted proxy behavior."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from forage.webapp.auth import AuthConfig, AuthConfigError, client_ip, is_secure


def test_fly_implies_production(monkeypatch):
    monkeypatch.setenv('FLY_APP_NAME', 'review')
    assert AuthConfig.from_env().production
    assert AuthConfig.from_env().trust_proxy


@pytest.mark.parametrize('hours', ['0', '-1', 'inf', 'nan', 'wrong'])
def test_invalid_session_duration_fails(monkeypatch, hours):
    monkeypatch.setenv('FORAGE_SESSION_HOURS', hours)
    with pytest.raises(AuthConfigError):
        AuthConfig.from_env()


def test_old_shared_credentials_have_no_effect(monkeypatch):
    monkeypatch.setenv('FORAGE_ADMIN_TOKEN', 'old-admin')
    monkeypatch.setenv('FORAGE_REVIEW_TOKEN', 'old-reviewer')
    assert AuthConfig.from_env() == AuthConfig()


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
