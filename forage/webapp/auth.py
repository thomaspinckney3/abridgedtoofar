"""Account roles, session configuration, request provenance and rate limits.

Passwords and revocable sessions live in accounts.py. Legacy shared login
secrets and signed role cookies are deliberately no longer accepted.
"""
from __future__ import annotations

import math
import os
import time
import threading
from dataclasses import dataclass

COOKIE_NAME = "forage_review"
PUBLIC = "public"
REVIEWER = "reviewer"
ADMIN = "admin"
ROLES = (PUBLIC, REVIEWER, ADMIN)


class AuthConfigError(RuntimeError):
    """Invalid account/bootstrap configuration."""


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Session:
    role: str = PUBLIC
    label: str = ""
    user_id: str = ""
    username: str = ""

    @property
    def can_write(self) -> bool:
        return self.role in (REVIEWER, ADMIN)

    @property
    def can_admin(self) -> bool:
        return self.role == ADMIN


@dataclass(frozen=True)
class AuthConfig:
    session_seconds: int = 30 * 24 * 3600
    epoch: str = "0"
    trust_proxy: bool = False
    production: bool = False

    @classmethod
    def from_env(cls) -> "AuthConfig":
        production = (os.environ.get("FORAGE_ENV", "").strip().lower() == "production"
                      or bool(os.environ.get("FLY_APP_NAME")))
        try:
            hours = float(os.environ.get("FORAGE_SESSION_HOURS", "720"))
            if not math.isfinite(hours) or hours <= 0:
                raise ValueError()
        except ValueError:
            raise AuthConfigError("FORAGE_SESSION_HOURS must be a positive finite number") from None
        return cls(session_seconds=max(60, int(hours * 3600)),
                   epoch=os.environ.get("FORAGE_SESSION_EPOCH", "0").strip() or "0",
                   trust_proxy=env_flag("FORAGE_TRUST_PROXY", production),
                   production=production)


# --------------------------------------------------------------------------
# Request provenance
# --------------------------------------------------------------------------


def client_ip(request, trust_proxy: bool) -> str:
    """The address rate limits are counted against.

    Behind Fly's proxy every request arrives from an internal address, so
    without this the whole internet shares one bucket. Forwarded headers are
    only read when the deployment says a proxy is in front — otherwise a
    client could spoof its way around the limiter.
    """
    if trust_proxy:
        fly = request.headers.get("fly-client-ip")
        if fly:
            return fly.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Right-most entry, not left-most: proxies append, so the last hop
            # is the value our own proxy wrote. Everything to its left was
            # supplied by the caller, who would otherwise get a fresh
            # rate-limit bucket per forged address.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def is_secure(request, trust_proxy: bool) -> bool:
    """Whether the browser reached us over HTTPS — TLS terminates at the proxy,
    so the ASGI scheme says http even when the connection was encrypted."""
    if trust_proxy:
        proto = request.headers.get("x-forwarded-proto")
        if proto:
            # Right-most for the same reason as the address: it's the hop our
            # own proxy recorded, not one the caller prepended.
            return proto.split(",")[-1].strip() == "https"
    return request.url.scheme == "https"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window per-key cap. Used for writes by authenticated accounts."""

    def __init__(self, limit: int = 60, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """Return 0 when allowed, else seconds until the next attempt fits."""
        with self._lock:
            return self._check(key)

    def _check(self, key: str) -> float:
        now = time.time()
        bucket = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(bucket) >= self.limit:
            self._hits[key] = bucket
            return max(1.0, self.window - (now - bucket[0]))
        bucket.append(now)
        self._hits[key] = bucket
        self._evict(now)
        return 0.0

    def allow(self, key: str) -> bool:
        return self.check(key) == 0.0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def _evict(self, now: float) -> None:
        if len(self._hits) <= 4096:  # bound memory on a public host
            return
        cutoff = now - self.window
        self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}


class LoginLimiter(RateLimiter):
    """Stricter window for password guessing.

    Successful sign-ins clear the counter, so a reviewer who fat-fingers their
    password twice and then gets it right is not locked out.
    """

    def __init__(self, limit: int = 8, window: float = 900.0) -> None:
        super().__init__(limit=limit, window=window)
