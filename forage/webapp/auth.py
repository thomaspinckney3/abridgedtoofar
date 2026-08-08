"""Access control for the review app: anyone may read, writing needs a token.

Two roles, because the app is meant to grow into running the pipeline itself:

  reviewer  FORAGE_REVIEW_TOKEN  leave, edit, and restatus comments
  admin     FORAGE_ADMIN_TOKEN   everything a reviewer can do, plus publishing
                                 edits.json — and, later, running paid stages

Sessions are stateless HMAC-signed cookies: no session table, no shared state
between machines. The signed payload carries the role, so a reviewer cookie
cannot be edited into an admin one without the key.

Environment
  FORAGE_REVIEW_TOKEN   password for commenting
  FORAGE_ADMIN_TOKEN    password for admin actions (defaults to disabled)
  FORAGE_SECRET_KEY     cookie signing key
  FORAGE_SESSION_HOURS  session lifetime, default 720 (30 days)
  FORAGE_SESSION_EPOCH  bump this integer to invalidate every live session
  FORAGE_ENV            "production" enables strict startup checks
  FORAGE_TRUST_PROXY    1/0 — honour X-Forwarded-*; defaults on under Fly

In production (FORAGE_ENV=production, or any FLY_APP_NAME in the environment)
the app refuses to start without an explicit secret key and review token:
generated-at-startup values silently break sessions across restarts and give
two machines two different passwords.
"""

from __future__ import annotations

import base64
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional

COOKIE_NAME = "forage_review"
COOKIE_VERSION = "v1"

# Shortest token/key a production deployment will accept. `token_urlsafe(9)`
# yields exactly this many characters, so the generated values clear it.
MIN_SECRET_LEN = 12

PUBLIC = "public"
REVIEWER = "reviewer"
ADMIN = "admin"
ROLES = (PUBLIC, REVIEWER, ADMIN)


class AuthConfigError(RuntimeError):
    """Raised at startup when a production deployment is misconfigured."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Session:
    role: str = PUBLIC
    label: str = ""

    @property
    def can_write(self) -> bool:
        return self.role in (REVIEWER, ADMIN)

    @property
    def can_admin(self) -> bool:
        return self.role == ADMIN


@dataclass
class AuthConfig:
    review_token: str
    admin_token: str
    secret_key: bytes
    session_seconds: int
    epoch: str
    trust_proxy: bool
    production: bool
    generated: tuple[str, ...]      # env vars that got a generated value

    @classmethod
    def from_env(cls) -> "AuthConfig":
        production = (os.environ.get("FORAGE_ENV", "").strip().lower() == "production"
                      or bool(os.environ.get("FLY_APP_NAME")))

        review_token = os.environ.get("FORAGE_REVIEW_TOKEN", "").strip()
        admin_token = os.environ.get("FORAGE_ADMIN_TOKEN", "").strip()
        key = os.environ.get("FORAGE_SECRET_KEY", "").strip()

        generated: list[str] = []
        if production:
            missing = [name for name, value in
                       (("FORAGE_SECRET_KEY", key), ("FORAGE_REVIEW_TOKEN", review_token))
                       if not value]
            if missing:
                raise AuthConfigError(
                    "production start refused — set " + ", ".join(missing) +
                    " (fly secrets set FORAGE_SECRET_KEY=... FORAGE_REVIEW_TOKEN=...). "
                    "Generated values break sessions on restart and differ per machine.")
            # A short shared secret on the public internet is guessable even
            # through the lockout, given enough addresses.
            weak = [name for name, value in
                    (("FORAGE_REVIEW_TOKEN", review_token),
                     ("FORAGE_ADMIN_TOKEN", admin_token),
                     ("FORAGE_SECRET_KEY", key))
                    if value and len(value) < MIN_SECRET_LEN]
            if weak:
                raise AuthConfigError(
                    "production start refused — " + ", ".join(weak) +
                    f" must be at least {MIN_SECRET_LEN} characters. "
                    "Generate one with: python -c 'import secrets;print(secrets.token_urlsafe(12))'")
        else:
            if not review_token:
                review_token = secrets.token_urlsafe(9)
                generated.append("FORAGE_REVIEW_TOKEN")
            if not key:
                key = secrets.token_urlsafe(32)
                generated.append("FORAGE_SECRET_KEY")

        if admin_token and hmac.compare_digest(admin_token, review_token):
            raise AuthConfigError(
                "FORAGE_ADMIN_TOKEN and FORAGE_REVIEW_TOKEN must differ — "
                "otherwise every reviewer is an admin.")

        try:
            hours = float(os.environ.get("FORAGE_SESSION_HOURS", "720"))
        except ValueError:
            hours = 720.0

        return cls(
            review_token=review_token,
            admin_token=admin_token,
            secret_key=key.encode(),
            session_seconds=max(60, int(hours * 3600)),
            epoch=os.environ.get("FORAGE_SESSION_EPOCH", "0").strip() or "0",
            trust_proxy=env_flag("FORAGE_TRUST_PROXY", production),
            production=production,
            generated=tuple(generated),
        )

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_token)

    # -- tokens ------------------------------------------------------------

    def authenticate(self, candidate: str) -> Optional[str]:
        """Return the role a token grants, or None. Both comparisons always
        run so a wrong token takes the same time whichever one it missed."""
        raw = (candidate or "").encode()
        is_admin = bool(self.admin_token) and hmac.compare_digest(self.admin_token.encode(), raw)
        is_reviewer = bool(self.review_token) and hmac.compare_digest(self.review_token.encode(), raw)
        if is_admin:
            return ADMIN
        if is_reviewer:
            return REVIEWER
        return None

    # -- session cookies ---------------------------------------------------

    def issue(self, role: str, label: str = "") -> str:
        """Mint a signed cookie. `label` is the reviewer's self-chosen name,
        carried along for display only — it grants nothing."""
        if role not in (REVIEWER, ADMIN):
            raise ValueError(f"cannot issue a session for role {role!r}")
        expiry = int(time.time() + self.session_seconds)
        payload = f"{COOKIE_VERSION}.{role}.{expiry}.{self.epoch}.{_b64(label.encode()[:64])}"
        return f"{payload}.{_b64(self._sign(payload))}"

    def verify(self, cookie: str | None) -> Session:
        if not cookie:
            return Session()
        parts = cookie.split(".")
        if len(parts) != 6:
            return Session()
        version, role, expiry_raw, epoch, label_raw, sig_raw = parts
        payload = ".".join(parts[:5])
        try:
            if not hmac.compare_digest(self._sign(payload), _unb64(sig_raw)):
                return Session()
            if version != COOKIE_VERSION or epoch != self.epoch:
                return Session()
            if role not in (REVIEWER, ADMIN):
                return Session()
            if float(expiry_raw) < time.time():
                return Session()
            label = _unb64(label_raw).decode("utf-8", "replace")
        except (ValueError, TypeError):
            return Session()
        # An admin cookie is worthless once the admin token is withdrawn.
        if role == ADMIN and not self.admin_enabled:
            return Session(role=REVIEWER, label=label)
        return Session(role=role, label=label)

    def _sign(self, payload: str) -> bytes:
        return hmac.new(self.secret_key, payload.encode(), sha256).digest()


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
    """Sliding-window per-key cap. Used for writes, where the token already
    gates access and this only stops a shared password flooding the queue."""

    def __init__(self, limit: int = 60, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> float:
        """Return 0 when allowed, else seconds until the next attempt fits."""
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
        self._hits.pop(key, None)

    def _evict(self, now: float) -> None:
        if len(self._hits) <= 4096:  # bound memory on a public host
            return
        cutoff = now - self.window
        self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}


class LoginLimiter(RateLimiter):
    """Much stricter window for token guessing: the shared secret is the only
    thing between the public and the write path, so wrong guesses are cheap to
    make and must not be cheap to repeat.

    Successful sign-ins clear the counter, so a reviewer who fat-fingers their
    token twice and then gets it right is not locked out.
    """

    def __init__(self, limit: int = 8, window: float = 900.0) -> None:
        super().__init__(limit=limit, window=window)
