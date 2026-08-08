"""FastAPI application for editorial review of abridgments.

Public read, token-gated write, admin-gated publish. Reads pipeline artifacts
off disk (see store.ArtifactStore) and owns exactly one piece of mutable state:
the comment queue in SQLite.

Routes
  GET  /                              review console shell
  GET  /b/{book_id}                   ditto (client-side routing)
  GET  /healthz                       liveness probe for the platform
  GET  /api/session                   role + vocabulary for the client
  POST /api/session                   { token, label } -> sets cookie
  DELETE /api/session                 sign out
  GET  /api/books                     book list with alignment + comment counts
  GET  /api/books/{book}/chapters     chapter index
  GET  /api/books/{book}/chapters/{s} rendered alignment blocks + comments
  GET  /api/books/{book}/comments     whole-book queue
  POST /api/books/{book}/comments     add a comment                  (reviewer)
  PATCH  /api/comments/{id}           edit / restatus                (reviewer)
  DELETE /api/comments/{id}           remove                         (reviewer)
  GET  /api/books/{book}/edits.json   overlay document (download)
  POST /api/books/{book}/publish      write the overlay to disk      (admin)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from fastapi import (Body, Cookie, Depends, FastAPI, HTTPException, Request,
                     Response)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import (COOKIE_NAME, AuthConfig, LoginLimiter, RateLimiter, Session,
                   client_ip, env_flag, is_secure)
from .store import (BOOK_COMMENT_SEGMENT, KINDS, SEVERITIES, STATUSES,
                    ArtifactStore, ReviewStore, build_edits, publish_edits,
                    valid_segment_id)

STATIC_DIR = Path(__file__).parent / "static"

# No inline scripts anywhere in the client, so script-src can stay strict.
# Style attributes are set from JS, which is why style-src is not.
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

_UNSAFE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def create_app(artifacts: ArtifactStore | None = None,
               reviews: ReviewStore | None = None,
               auth: AuthConfig | None = None) -> FastAPI:
    artifacts = artifacts or ArtifactStore()
    reviews = reviews or ReviewStore()
    auth = auth or AuthConfig.from_env()
    writes = RateLimiter()
    logins = LoginLimiter()

    # openapi_url too, not just the doc viewers: leaving it on publishes the
    # full route table, admin endpoints included, to anonymous callers.
    app = FastAPI(title="Forage editorial review",
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.artifacts = artifacts
    app.state.reviews = reviews
    app.state.auth = auth

    # -- middleware --------------------------------------------------------

    allowed_hosts = [h.strip() for h in
                     os.environ.get("FORAGE_ALLOWED_HOSTS", "").split(",") if h.strip()]

    # Rejecting unknown Host headers outright is opt-in and deliberately not
    # implied by setting the allowlist: the platform's health check reaches the
    # machine directly, with its own address in Host rather than the public
    # hostname. Switching this on without accounting for that fails /healthz,
    # which restarts the machine on a loop. The allowlist is useful either way
    # — origin_allowed() below consults it whether or not this is enabled.
    if allowed_hosts and env_flag("FORAGE_STRICT_HOST", False):
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        app.add_middleware(TrustedHostMiddleware,
                           allowed_hosts=allowed_hosts + ["*.internal"])

    def origin_allowed(origin: str, host: str) -> bool:
        """Whether a write may carry this Origin.

        Prefer the configured hostnames. Falling back to the request's own Host
        header means comparing one caller-supplied value against another, which
        is why the allowlist exists — but an unconfigured deployment is still
        better served by the weak check than by none.
        """
        netloc = urlsplit(origin).netloc
        if not netloc:
            return False
        return netloc in allowed_hosts if allowed_hosts else netloc == host

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # Cookies are SameSite=Lax, so a cross-site POST never carries one.
        # This rejects the request outright rather than processing it
        # unauthenticated, and covers same-site-but-wrong-origin cases.
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin:
                # "null" is an opaque origin — a sandboxed iframe, or a
                # data:/file: document. It can never legitimately match, so it
                # has to fail the check rather than skip it.
                host = request.headers.get("host", "")
                if origin == "null" or not origin_allowed(origin, host):
                    return JSONResponse({"detail": "Cross-origin write refused."},
                                        status_code=403)

        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if is_secure(request, auth.trust_proxy):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    # -- dependencies ------------------------------------------------------

    def session(forage_review: Optional[str] = Cookie(default=None)) -> Session:
        return auth.verify(forage_review)

    def require_write(request: Request,
                      sess: Session = Depends(session)) -> Session:
        if not sess.can_write:
            raise HTTPException(status_code=401,
                                detail="Sign in with the review token to comment.")
        retry = writes.check(client_ip(request, auth.trust_proxy))
        if retry:
            raise HTTPException(status_code=429,
                                detail="Too many edits at once. Wait a minute.",
                                headers={"Retry-After": str(int(retry))})
        return sess

    def require_admin(sess: Session = Depends(require_write)) -> Session:
        if not sess.can_admin:
            raise HTTPException(status_code=403,
                                detail="Publishing needs the admin token.")
        return sess

    def require_book(book_id: str) -> str:
        if not artifacts.has_book(book_id):
            raise HTTPException(status_code=404, detail=f"No alignments for {book_id!r}.")
        return book_id

    def shell() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html",
                            headers={"Cache-Control": "no-cache"})

    # -- pages -------------------------------------------------------------

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return shell()

    @app.get("/b/{book_id}", include_in_schema=False)
    def book_page(book_id: str) -> FileResponse:
        return shell()

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"ok": True, "books": len(artifacts.book_ids())}

    # -- session -----------------------------------------------------------

    @app.get("/api/session")
    def get_session(sess: Session = Depends(session)) -> dict:
        return {"role": sess.role, "label": sess.label,
                "can_write": sess.can_write, "can_admin": sess.can_admin,
                "admin_enabled": auth.admin_enabled,
                "generated_token": "FORAGE_REVIEW_TOKEN" in auth.generated,
                "severities": list(SEVERITIES), "kinds": list(KINDS),
                "statuses": list(STATUSES)}

    @app.post("/api/session")
    def sign_in(request: Request, response: Response,
                payload: dict = Body(...)) -> dict:
        ip = client_ip(request, auth.trust_proxy)
        retry = logins.check(ip)
        if retry:
            raise HTTPException(
                status_code=429,
                detail=f"Too many sign-in attempts. Try again in {int(retry / 60) + 1} min.",
                headers={"Retry-After": str(int(retry))})

        role = auth.authenticate(str(payload.get("token", "")))
        if role is None:
            raise HTTPException(status_code=403, detail="That token isn't right.")

        logins.reset(ip)  # a correct token clears the guess counter
        label = str(payload.get("label", "")).strip()[:64]
        response.set_cookie(
            COOKIE_NAME, auth.issue(role, label),
            max_age=auth.session_seconds, httponly=True, samesite="lax",
            secure=is_secure(request, auth.trust_proxy),
        )
        return {"role": role, "label": label, "can_write": True,
                "can_admin": role == "admin"}

    @app.delete("/api/session")
    def sign_out(response: Response) -> dict:
        response.delete_cookie(COOKIE_NAME)
        return {"role": "public", "label": "", "can_write": False, "can_admin": False}

    # -- reading -----------------------------------------------------------

    @app.get("/api/books")
    def list_books() -> dict:
        comment_counts = reviews.counts_by_book()
        books = []
        for book_id in artifacts.book_ids():
            summary = artifacts.book_summary(book_id)
            if not summary:
                continue
            books.append({
                "book_id": summary.book_id,
                "title": summary.title,
                "author": summary.author,
                "chapters": summary.chapters,
                "counts": summary.counts,
                "diagnostics": summary.diagnostics,
                "comments": comment_counts.get(book_id, {"total": 0}),
            })
        return {"books": books}

    @app.get("/api/books/{book_id}/chapters")
    def chapter_index(book_id: str = Depends(require_book)) -> dict:
        summary = artifacts.book_summary(book_id)
        comment_counts = reviews.counts_by_chapter(book_id)
        chapters = artifacts.chapter_index(book_id)
        for ch in chapters:
            ch["comments"] = comment_counts.get(ch["segment_id"], {"total": 0})
        return {
            "book_id": book_id,
            "title": summary.title if summary else book_id,
            "author": summary.author if summary else "",
            "counts": summary.counts if summary else {},
            "diagnostics": summary.diagnostics if summary else {"total": 0},
            "chapters": chapters,
        }

    @app.get("/api/books/{book_id}/chapters/{segment_id}")
    def chapter(segment_id: str, book_id: str = Depends(require_book)) -> dict:
        if not valid_segment_id(segment_id):
            raise HTTPException(status_code=400, detail="Bad chapter id.")
        view = artifacts.chapter_view(book_id, segment_id)
        if view is None:
            raise HTTPException(status_code=404, detail=f"No chapter {segment_id!r}.")
        responses = artifacts.review_apply_responses(book_id, segment_id)
        view["comments"] = _decorate(
            reviews.list_comments(book_id, segment_id), view, responses)
        view["book_comments"] = _decorate(
            reviews.list_comments(book_id, BOOK_COMMENT_SEGMENT), None, responses)
        return view

    @app.get("/api/books/{book_id}/comments")
    def book_comments(book_id: str = Depends(require_book)) -> dict:
        comments = []
        responses = artifacts.review_apply_responses(book_id)
        for row in reviews.list_comments(book_id):
            view = None
            if row["segment_id"] != BOOK_COMMENT_SEGMENT:
                view = artifacts.chapter_view(book_id, row["segment_id"])
            comments.extend(_decorate([row], view, responses))
        return {"book_id": book_id, "comments": comments}

    # -- writing -----------------------------------------------------------

    @app.post("/api/books/{book_id}/comments", status_code=201)
    def add_comment(payload: dict = Body(...),
                    book_id: str = Depends(require_book),
                    sess: Session = Depends(require_write)) -> dict:
        scope = str(payload.get("scope") or "paragraph").strip().lower()
        if scope not in {"book", "chapter", "paragraph"}:
            raise HTTPException(status_code=400, detail="Bad comment scope.")

        segment_id = str(payload.get("segment_id", "")).strip()
        view = None
        if scope == "book":
            segment_id = BOOK_COMMENT_SEGMENT
        else:
            if not valid_segment_id(segment_id):
                raise HTTPException(status_code=400, detail="Bad chapter id.")
            view = artifacts.chapter_view(book_id, segment_id)
            if view is None:
                raise HTTPException(status_code=404, detail=f"No chapter {segment_id!r}.")

        body = str(payload.get("body", "")).strip()
        if not body:
            raise HTTPException(status_code=400, detail="A comment needs a body.")

        raw_para = payload.get("draft_para")
        draft_para: int | None = None
        anchor = ""
        if scope == "paragraph" and raw_para is not None and str(raw_para) != "":
            try:
                draft_para = int(raw_para)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Bad paragraph index.")
            block = next((b for b in view["blocks"] if b["draft_para"] == draft_para), None)
            if block is None:
                raise HTTPException(status_code=400,
                                    detail=f"Paragraph {draft_para} isn't in {segment_id}.")
            anchor = block["anchor"]
        elif scope == "paragraph":
            raise HTTPException(status_code=400,
                                detail="Paragraph comments need a paragraph index.")

        row = reviews.add(
            book_id=book_id, segment_id=segment_id, draft_para=draft_para,
            anchor=anchor, quote=str(payload.get("quote", "")),
            severity=str(payload.get("severity", "minor")),
            kind=str(payload.get("kind", "other")),
            body=body,
            # From the signed cookie, never the body: a client-supplied author
            # lets any reviewer sign a comment with someone else's name.
            author=sess.label,
        )
        return _decorate([row], view)[0]

    @app.patch("/api/comments/{comment_id}")
    def edit_comment(comment_id: str, payload: dict = Body(...),
                     sess: Session = Depends(require_write)) -> dict:
        existing = reviews.get(comment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="No such comment.")
        row = reviews.update(comment_id, **{
            k: payload.get(k) for k in ("body", "severity", "kind", "status")
        })
        view = artifacts.chapter_view(existing["book_id"], existing["segment_id"])
        responses = artifacts.review_apply_responses(existing["book_id"])
        return _decorate([row], view, responses)[0] if row else {}

    @app.delete("/api/comments/{comment_id}")
    def remove_comment(comment_id: str,
                       sess: Session = Depends(require_write)) -> dict:
        if not reviews.delete(comment_id):
            raise HTTPException(status_code=404, detail="No such comment.")
        return {"deleted": comment_id}

    # -- publish -----------------------------------------------------------

    @app.get("/api/books/{book_id}/edits.json")
    def download_edits(book_id: str = Depends(require_book)) -> JSONResponse:
        doc = build_edits(artifacts, reviews, book_id)
        return JSONResponse(doc, headers={
            "Content-Disposition": f'attachment; filename="{book_id}-edits.json"'})

    @app.post("/api/books/{book_id}/publish")
    def publish(book_id: str = Depends(require_book),
                sess: Session = Depends(require_admin)) -> dict:
        try:
            path, doc = publish_edits(artifacts, reviews, book_id)
        except OSError as e:
            raise HTTPException(status_code=503,
                                detail=f"Artifact volume isn't writable: {e}")
        return {"path": str(path), "comment_count": doc["comment_count"],
                "stale_count": doc["stale_count"]}

    return app


def _decorate(
    rows: list[dict],
    view: dict | None,
    responses: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Attach staleness to comments: the paragraph a comment was written
    against may have been redrafted since."""
    blocks = {b["draft_para"]: b for b in (view or {}).get("blocks", [])}
    out = []
    for row in rows:
        item = dict(row)
        block = blocks.get(row.get("draft_para"))
        if row.get("segment_id") == BOOK_COMMENT_SEGMENT:
            item["scope"] = "book"
        elif row.get("draft_para") is None:
            item["scope"] = "chapter"
        else:
            item["scope"] = "paragraph"
        item["stale"] = bool(row.get("anchor")) and block is not None \
            and block["anchor"] != row["anchor"]
        item["orphaned"] = row.get("draft_para") is not None and block is None
        llm_responses = (responses or {}).get(row["id"], [])
        if llm_responses:
            item["llm_responses"] = llm_responses
            item["llm_response_count"] = len(llm_responses)
        out.append(item)
    return out


def get_app() -> FastAPI:
    """ASGI entrypoint: `uvicorn forage.webapp.app:get_app --factory`."""
    return create_app()
