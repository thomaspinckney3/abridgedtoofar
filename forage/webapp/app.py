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
import hashlib
import math
import logging
from contextlib import contextmanager
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
                    ArtifactStore, ReviewStore, build_edits, build_feedback,
                    decorate_comments, publish_edits, valid_book_id,
                    valid_segment_id, mutable_path)

STATIC_DIR = Path(__file__).parent / "static"

# No inline scripts anywhere in the client, so script-src can stay strict.
# Style attributes are set from JS, which is why style-src is not.
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

_UNSAFE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def create_app(artifacts: ArtifactStore | None = None,
               reviews: ReviewStore | None = None,
               auth: AuthConfig | None = None, hosted=None) -> FastAPI:
    artifacts = artifacts or ArtifactStore()
    if hosted is not None:
        artifacts.hosted = hosted
    reviews = reviews or ReviewStore()
    mutable_path(reviews.db_path)
    if os.environ.get("FORAGE_EDITS_DIR"):
        mutable_path(Path(os.environ["FORAGE_EDITS_DIR"]))
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

    def selected_book(book_id: str, revision: str | None = None,
                      channel: str | None = None) -> ArtifactStore:
        if not valid_book_id(book_id):
            raise HTTPException(status_code=404, detail="No such book.")
        try:
            selected = artifacts.selected(book_id, revision, channel)
            if not selected.has_book(book_id):
                raise FileNotFoundError("No alignments for this book.")
            return selected
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    def receiver():
        if artifacts.hosted is None:
            raise HTTPException(status_code=503, detail="Set FORAGE_HOSTED_ROOT to enable hosted publication.")
        return artifacts.hosted

    @contextmanager
    def review_mutation(book_id: str):
        """Serialize DB changes and their local-transport projection.

        SQLite/HTTP are authoritative. A durable pending marker makes a failed
        projection unusable to local readers instead of exposing stale edits.
        """
        warning = {}
        if artifacts.hosted is None:
            yield warning
            return
        from ..production_state import atomic_json, book_lock
        book = artifacts.hosted._book(book_id)
        try:
            with book_lock(book):
                pending = book.work_dir / "feedback_pending"
                atomic_json(pending, {"version": 1, "book_id": book_id})
                yield warning
                try:
                    selected = artifacts.selected(book_id)
                    atomic_json(book.work_dir / "feedback.json", build_feedback(selected, reviews, book_id))
                    pending.unlink()
                except (OSError, ValueError):
                    warning["feedback_projection_warning"] = "Saved successfully. Local feedback cache refresh failed; use HTTP feedback or repeat publication to refresh it."
                    logging.getLogger(__name__).warning("Feedback projection refresh failed for %s; local pulls are blocked", book_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

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

    @app.get("/release/{book_id}", include_in_schema=False)
    def release_page(book_id: str) -> FileResponse:
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
            try:
                selected = artifacts.selected(book_id)
            except FileNotFoundError:
                selected = artifacts.selected(book_id, channel="release")
            summary = selected.book_summary(book_id)
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

    @app.post("/api/books/{book_id}/revisions", status_code=201)
    async def upload_revision(book_id: str, request: Request,
                              sess: Session = Depends(require_admin)) -> dict:
        from ..hosted_publication import valid_book_id as valid_hosted_id
        if not valid_hosted_id(book_id):
            raise HTTPException(status_code=400, detail="Bad book id.")
        store = receiver()
        limit = store.max_archive_bytes
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) < 0 or int(declared) > limit:
                    raise HTTPException(status_code=413, detail="Publication archive is too large.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Bad content length.")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > limit:
                raise HTTPException(status_code=413, detail="Publication archive is too large.")
            data.extend(chunk)
        try:
            manifest = store.upload(book_id, bytes(data))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"book_id": book_id, "revision": manifest["revision"]}

    @app.post("/api/books/{book_id}/publication")
    def promote_publication(book_id: str, payload: dict = Body(...),
                            sess: Session = Depends(require_admin)) -> dict:
        if (not isinstance(payload.get("revision"), str)
                or payload.get("channel", "review") not in ("review", "release")):
            raise HTTPException(status_code=400, detail="Publication needs a revision and review/release channel.")
        try:
            store = receiver()
            with review_mutation(book_id) as warning:
                pointer = store.promote(book_id, payload.get("revision"), payload.get("channel", "review"), lock_held=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {**pointer, **warning}

    @app.get("/api/books/{book_id}/publication")
    def publication_status(book_id: str) -> dict:
        try:
            if not valid_book_id(book_id):
                raise ValueError("Bad book id.")
            if artifacts.hosted:
                return artifacts.hosted.status(book_id)
            from ..hosted_publication import HostedPublications
            for root in (artifacts.overlay_work_dir, artifacts.work_dir):
                if root and (root / book_id).is_dir():
                    return HostedPublications(root).status(book_id)
            return {"review": None, "release": None}
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/books/{book_id}/chapters")
    def chapter_index(book_id: str, selected: ArtifactStore = Depends(selected_book)) -> dict:
        summary = selected.book_summary(book_id)
        comment_counts = reviews.counts_by_chapter(book_id)
        chapters = selected.chapter_index(book_id)
        for ch in chapters:
            ch["comments"] = comment_counts.get(ch["segment_id"], {"total": 0})
        manifest = selected._revisions.get(book_id, {})
        downloads = []
        for item in manifest.get("outputs", []):
            path = item["path"]
            if path.endswith((".txt", ".md", ".pdf", ".mp3", ".epub")) and not path.startswith("segments/"):
                downloads.append({"path": path, "url": f"/api/books/{book_id}/revisions/{manifest['revision']}/assets/{path}"})
        return {"book_id": book_id, "title": summary.title if summary else book_id,
                "author": summary.author if summary else "", "counts": summary.counts if summary else {},
                "diagnostics": summary.diagnostics if summary else {"total": 0},
                "chapters": chapters, "downloads": downloads,
                "publication_channel": selected._channels.get(book_id),
                **selected.revision_info(book_id)}

    @app.get("/api/books/{book_id}/chapters/{segment_id}")
    def chapter(book_id: str, segment_id: str,
                selected: ArtifactStore = Depends(selected_book)) -> dict:
        if not valid_segment_id(segment_id):
            raise HTTPException(status_code=400, detail="Bad chapter id.")
        view = selected.chapter_view(book_id, segment_id)
        if view is None:
            raise HTTPException(status_code=404, detail=f"No chapter {segment_id!r}.")
        responses = selected.review_apply_responses(book_id, segment_id, source_id=reviews.source_id)
        view["comments"] = decorate_comments(selected, book_id,
            [c for c in reviews.list_comments(book_id, segment_id) if c.get("target_kind") == "text"], responses)
        view["book_comments"] = decorate_comments(selected, book_id,
            reviews.list_comments(book_id, BOOK_COMMENT_SEGMENT), responses)
        view.update(selected.revision_info(book_id))
        return view

    @app.get("/api/books/{book_id}/comments")
    def book_comments(book_id: str, selected: ArtifactStore = Depends(selected_book)) -> dict:
        return {"book_id": book_id, "comments": decorate_comments(selected, book_id,
                reviews.list_comments(book_id), selected.review_apply_responses(book_id, source_id=reviews.source_id))}

    @app.get("/api/books/{book_id}/feedback")
    def feedback(book_id: str, selected: ArtifactStore = Depends(selected_book)) -> dict:
        return build_feedback(selected, reviews, book_id)

    @app.get("/api/books/{book_id}/media")
    def media_index(book_id: str, selected: ArtifactStore = Depends(selected_book)) -> dict:
        try:
            index = selected.media(book_id)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        revision = selected.revision_info(book_id)["publication_revision"]
        targets = []
        for target in index["targets"]:
            item = dict(target)
            item["url"] = (f"/api/books/{book_id}/revisions/{revision}/assets/{item['path']}"
                           if revision else f"/api/books/{book_id}/media/{item['id']}/asset")
            targets.append(item)
        rows = [c for c in reviews.list_comments(book_id) if c.get("target_kind") in {"audio", "graphic"}]
        return {**index, "targets": targets, **selected.revision_info(book_id),
                "comments": decorate_comments(selected, book_id, rows)}

    @app.get("/api/books/{book_id}/media/{target_id}/asset")
    def media_asset(book_id: str, target_id: str,
                    selected: ArtifactStore = Depends(selected_book)) -> FileResponse:
        from ..production_state import confined_path
        try:
            target = next((t for t in selected.media(book_id)["targets"] if t["id"] == target_id), None)
            if target is None:
                raise FileNotFoundError("No such media target.")
            path = confined_path(selected._book_work_dir(book_id), target["path"])
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return FileResponse(path, media_type=target["mime_type"])

    @app.get("/api/books/{book_id}/revisions/{revision_id}/assets/{asset_path:path}")
    def revision_asset(book_id: str, revision_id: str, asset_path: str) -> FileResponse:
        from ..production_state import confined_path
        try:
            selected = artifacts.selected(book_id, revision_id)
            manifest = selected._revisions[book_id]
            entry = next((item for item in manifest["outputs"] if item["path"] == asset_path), None)
            if entry is None:
                raise FileNotFoundError("Asset is absent from this revision.")
            path = confined_path(selected._book_work_dir(book_id), asset_path)
            mime = {".txt": "text/plain", ".md": "text/plain", ".json": "application/json",
                    ".pdf": "application/pdf", ".epub": "application/epub+zip", ".mp3": "audio/mpeg",
                    ".wav": "audio/wav", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".webp": "image/webp"}.get(path.suffix.lower(), "application/octet-stream")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return FileResponse(path, media_type=mime, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.post("/api/books/{book_id}/comments", status_code=201)
    def add_comment(book_id: str, payload: dict = Body(...),
                    sess: Session = Depends(require_write)) -> dict:
        # Historical comments are supported explicitly. The submitted viewed
        # revision chooses the anchor; a concurrent pointer change cannot do so.
        revision = payload.get("publication_revision")
        selected = selected_book(book_id, revision=revision)
        current = selected_book(book_id)
        if current.revision_info(book_id)["publication_revision"] and not revision:
            raise HTTPException(status_code=409, detail="Submit the publication_revision you viewed.")
        scope = str(payload.get("scope") or "paragraph").strip().lower()
        if scope not in {"book", "chapter", "paragraph", "audio", "graphic"}:
            raise HTTPException(status_code=400, detail="Bad comment scope.")
        body = payload.get("body")
        if not isinstance(body, str) or not body.strip():
            raise HTTPException(status_code=400, detail="A comment needs a body.")
        segment_id = str(payload.get("segment_id", "")).strip()
        draft_para, anchor, original_text = None, "", ""
        target_id, target_revision, timestamp = None, None, None
        if scope in {"audio", "graphic"}:
            target_id = payload.get("target_id")
            target = next((t for t in selected.media(book_id)["targets"] if t["id"] == target_id), None)
            if target is None or target["kind"] != scope:
                raise HTTPException(status_code=404, detail="No such media target in the viewed revision.")
            target_revision = target["revision"]
            if payload.get("target_revision") != target_revision:
                raise HTTPException(status_code=409, detail="Media changed; submit the target_revision you viewed.")
            segment_id = target.get("segment_id") or "__media__"
            if scope == "audio":
                raw_timestamp = payload.get("timestamp_seconds")
                try:
                    timestamp = float(raw_timestamp) if (not isinstance(raw_timestamp, bool)
                        and isinstance(raw_timestamp, (int, float))) else math.nan
                except (OverflowError, ValueError):
                    timestamp = math.nan
                if (not math.isfinite(timestamp) or timestamp < 0
                        or (target.get("duration_seconds") is not None and timestamp > target["duration_seconds"])):
                    raise HTTPException(status_code=400, detail="Audio time must be finite, nonnegative and within the chunk duration when known.")
        elif scope == "book":
            segment_id = BOOK_COMMENT_SEGMENT
        else:
            if not valid_segment_id(segment_id):
                raise HTTPException(status_code=400, detail="Bad chapter id.")
            alignment = selected.alignment(book_id, segment_id)
            if alignment is None:
                raise HTTPException(status_code=404, detail=f"No chapter {segment_id!r}.")
            paras = alignment.get("draft_paragraphs", [])
            if scope == "paragraph":
                raw = payload.get("draft_para")
                if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw < len(paras):
                    raise HTTPException(status_code=400, detail="Bad paragraph index.")
                draft_para, original_text = raw, paras[raw]
            else:
                original_text = "\n\n".join(paras)
            from .store import anchor_hash
            anchor = anchor_hash(original_text)
            target_revision = hashlib.sha256(original_text.encode()).hexdigest()
        with review_mutation(book_id) as warning:
            row = reviews.add(book_id=book_id, segment_id=segment_id, draft_para=draft_para,
                anchor=anchor, original_text=original_text, quote=str(payload.get("quote", "")),
                severity=str(payload.get("severity", "minor")), kind=str(payload.get("kind", "other")),
                body=body.strip(), author=sess.label, scope=scope,
                target_kind=scope if scope in {"audio", "graphic"} else "text", target_id=target_id,
                target_revision=target_revision, timestamp_seconds=timestamp, **selected.revision_info(book_id))
        return {**decorate_comments(current, book_id, [row])[0], **warning}

    @app.patch("/api/comments/{comment_id}")
    def edit_comment(comment_id: str, payload: dict = Body(...),
                     sess: Session = Depends(require_write)) -> dict:
        existing = reviews.get(comment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="No such comment.")
        if "body" in payload and (not isinstance(payload["body"], str) or not payload["body"].strip()):
            raise HTTPException(status_code=400, detail="A comment needs a body.")
        book_id = existing["book_id"]
        with review_mutation(book_id) as warning:
            row = reviews.update(comment_id, **{k: payload.get(k) for k in ("body", "severity", "kind", "status")})
        selected = selected_book(book_id)
        return {**decorate_comments(selected, book_id, [row], selected.review_apply_responses(book_id, source_id=reviews.source_id))[0], **warning}

    @app.delete("/api/comments/{comment_id}")
    def remove_comment(comment_id: str, sess: Session = Depends(require_write)) -> dict:
        existing = reviews.get(comment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="No such comment.")
        with review_mutation(existing["book_id"]) as warning:
            if not reviews.delete(comment_id):
                raise HTTPException(status_code=404, detail="No such comment.")
        return {"deleted": comment_id, **warning}

    @app.get("/api/books/{book_id}/edits.json")
    def download_edits(book_id: str, selected: ArtifactStore = Depends(selected_book)) -> JSONResponse:
        return JSONResponse(build_edits(selected, reviews, book_id), headers={
            "Content-Disposition": f'attachment; filename="{book_id}-edits.json"'})

    @app.post("/api/books/{book_id}/publish")
    def publish(book_id: str, selected: ArtifactStore = Depends(selected_book),
                sess: Session = Depends(require_admin)) -> dict:
        try:
            path, doc = publish_edits(selected, reviews, book_id)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Artifact volume is not writable: {exc}")
        return {"path": str(path), "comment_count": doc["comment_count"], "stale_count": doc["stale_count"]}

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
