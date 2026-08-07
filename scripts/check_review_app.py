#!/usr/bin/env python3
"""End-to-end smoke check for the editorial review app (forage serve).

Three layers, all against a throwaway database on a free port:

  units    session cookies — signing, tampering, expiry, epoch, role downgrade,
           and the production startup refusal
  api      access control over HTTP — anonymous reads, reviewer vs admin,
           sign-in lockout, cross-origin refusal, proxy headers, security headers
  browser  the review loop in real Chrome over the DevTools protocol — routing,
           filters, keyboard nav, select-to-quote, add/resolve/delete a note,
           publish visibility per role, deep links, mobile layout

    python scripts/check_review_app.py [--book gatsby] [--shots DIR]

Requires the web extra (fastapi + uvicorn); the browser layer is skipped when
no Chrome is installed. Zero LLM cost. Exits non-zero if anything fails.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]

REVIEW_TOKEN = "smoke-review-token"
ADMIN_TOKEN = "smoke-admin-token"
SECRET = "smoke-secret"


def find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def __call__(self, name: str, ok: bool, detail: str = "") -> None:
        print(("  ok    " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail and not ok else ""))
        if not ok:
            self.failures.append(name)


class CDP:
    """Minimal DevTools client: enough to evaluate JS and grab screenshots."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.n = 0

    async def send(self, method: str, **params):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expr: str):
        result = await self.send("Runtime.evaluate",
                                 expression=f"(async () => {{ {expr} }})()",
                                 awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(json.dumps(result["exceptionDetails"])[:400])
        return result.get("result", {}).get("value")

    async def shot(self, path: Path) -> None:
        data = await self.send("Page.captureScreenshot")
        path.write_bytes(base64.b64decode(data["data"]))

    @staticmethod
    def key(name: str) -> str:
        return (f"document.body.dispatchEvent(new KeyboardEvent('keydown',"
                f" {{key: '{name}', bubbles: true}}));")


class Client:
    """Cookie-carrying HTTP client with a spoofable forwarded address, so each
    scenario gets its own rate-limit bucket."""

    def __init__(self, base: str, ip: str = "203.0.113.1") -> None:
        self.base = base
        self.ip = ip
        self.cookie = ""

    def request(self, method: str, path: str, body: dict | None = None,
                headers: dict | None = None) -> tuple[int, dict, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Forwarded-For", self.ip)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req) as res:
                payload, status, raw_head = res.read(), res.status, res.headers
        except urllib.error.HTTPError as e:
            payload, status, raw_head = e.read(), e.code, e.headers
        # Header names arrive lowercased from Starlette; normalise so lookups
        # here don't depend on casing, and keep every Set-Cookie line intact
        # (expiry dates contain commas, so joining them would be ambiguous).
        head = {k.lower(): v for k, v in raw_head.items()}
        cookies = raw_head.get_all("set-cookie") or []
        head["set-cookie"] = "\n".join(cookies)
        for raw in cookies:
            if raw.strip().startswith("forage_review="):
                self.cookie = raw.split(";")[0].strip()
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            parsed = {"raw": payload[:200].decode("utf-8", "replace")}
        return status, parsed, head

    def sign_in(self, token: str, label: str = "smoke") -> tuple[int, dict]:
        status, payload, _ = self.request("POST", "/api/session",
                                          {"token": token, "label": label})
        return status, payload


def check_units(check: Checks) -> None:
    """Cookie mechanics and startup policy — no server, no browser."""
    from forage.drafter import _extract_chapter_notes
    from forage.proofread import should_word_diff, word_diff_html
    from forage.artifacts import Book
    from forage.review_apply import (
        _validate_apply_response,
        _validate_revision_consistency,
        feedback_fingerprint,
        pending_review_feedback,
    )
    from forage.webapp import auth as A
    from forage.webapp.store import ArtifactStore

    env = {"FORAGE_SECRET_KEY": SECRET, "FORAGE_REVIEW_TOKEN": REVIEW_TOKEN,
           "FORAGE_ADMIN_TOKEN": ADMIN_TOKEN}
    with patched_env(env):
        cfg = A.AuthConfig.from_env()

    check("review token maps to the reviewer role",
          cfg.authenticate(REVIEW_TOKEN) == A.REVIEWER)
    check("admin token maps to the admin role",
          cfg.authenticate(ADMIN_TOKEN) == A.ADMIN)
    check("an unknown token maps to no role", cfg.authenticate("nope") is None)

    admin_cookie = cfg.issue(A.ADMIN, "Tom")
    check("an issued cookie verifies", cfg.verify(admin_cookie).can_admin)
    check("the label survives the round trip", cfg.verify(admin_cookie).label == "Tom")

    reviewer_cookie = cfg.issue(A.REVIEWER, "Tom")
    forged = reviewer_cookie.replace(f".{A.REVIEWER}.", f".{A.ADMIN}.", 1)
    check("editing the role in a cookie invalidates it",
          cfg.verify(forged).role == A.PUBLIC, cfg.verify(forged).role)
    check("editing the signature invalidates it",
          cfg.verify(reviewer_cookie[:-4] + "AAAA").role == A.PUBLIC)
    check("a cookie from another key is rejected", A.AuthConfig(
        review_token=REVIEW_TOKEN, admin_token=ADMIN_TOKEN, secret_key=b"other-key",
        session_seconds=3600, epoch="0", trust_proxy=False, production=False,
        generated=()).verify(reviewer_cookie).role == A.PUBLIC)

    with patched_env({**env, "FORAGE_SESSION_EPOCH": "7"}):
        rotated = A.AuthConfig.from_env()
    check("bumping the session epoch signs everyone out",
          rotated.verify(reviewer_cookie).role == A.PUBLIC)

    with patched_env({**env, "FORAGE_SESSION_HOURS": "0"}):
        brief = A.AuthConfig.from_env()
    expired = brief.issue(A.REVIEWER, "Tom")
    expired = ".".join(["v1", A.REVIEWER, "1", "0"] + expired.split(".")[4:5])
    check("an expired cookie is rejected", brief.verify(expired).role == A.PUBLIC)

    with patched_env({**env, "FORAGE_ADMIN_TOKEN": ""}):
        no_admin = A.AuthConfig.from_env()
    check("withdrawing the admin token downgrades live admin cookies",
          no_admin.verify(admin_cookie).role == A.REVIEWER)

    quote_source = "“Do you live down on Long Island, too?” she inquired."
    quote_draft = "\"Do you live down on Long Island, too?\""
    quote_diff = word_diff_html(quote_source, quote_draft)
    check("word diff ignores quote style around unchanged text",
          quote_diff.startswith("&quot;Do you live down on Long Island, too?&quot;"))
    check("word diff still marks the real deletion",
          "<del> she inquired.</del>" in quote_diff)
    check("quote and wrapping-only changes do not produce word diffs",
          not should_word_diff("verbatim", "“Do you see?”\n", "\"Do you see?\""))

    draft, notes = _extract_chapter_notes("""Draft text.
<!-- FORAGE_CHAPTER_NOTES
{
  "summary": "Compressed repeated scene-setting.",
  "acceptable_changes": ["Merged two low-load beats."],
  "risks": ["A later name reference may need checking."],
  "review_focus": ["Confirm the name still has a local gloss."]
}
-->""")
    check("chapter note sidecar is stripped from draft prose",
          draft == "Draft text.", draft)
    check("chapter note sidecar is parsed for reviewers",
          notes.get("summary") == "Compressed repeated scene-setting."
          and notes.get("risks") == ["A later name reference may need checking."],
          str(notes))

    dummy_book = Book(
        book_id="dummy",
        source_path=ROOT / "books" / "dummy" / "source.txt",
        metadata={},
        work_dir=ROOT / "work" / "dummy",
    )
    overlay = {
        "book_id": "dummy",
        "generated_at": 123.0,
        "book_comments": [{
            "id": "book1",
            "scope": "book",
            "severity": "major",
            "kind": "continuity",
            "status": "open",
            "note": "Dialogue is often unattributed.",
            "quote": "",
            "author": "reviewer",
            "created_at": 1.0,
            "updated_at": 1.0,
        }],
        "segments": [{
            "segment_id": "002",
            "comments": [{
                "id": "chap1",
                "scope": "chapter",
                "draft_para": None,
                "severity": "major",
                "kind": "continuity",
                "status": "open",
                "note": "Add source-backed dialogue attribution here.",
                "quote": "",
                "author": "reviewer",
                "paragraph": None,
                "stale": False,
                "created_at": 2.0,
                "updated_at": 2.0,
            }],
        }],
    }
    review_plan = pending_review_feedback(
        dummy_book, overlay=overlay, ledger={"entries": []}, segment_ids=["2"])
    planned = review_plan["segments"][0]
    check("review-apply plan includes book and chapter feedback",
          planned["segment_id"] == "002"
          and planned["pending_count"] == 2
          and {item["scope"] for item in planned["pending"]} == {"book", "chapter"},
          str(planned))
    used_key = planned["pending"][0]["feedback_key"]
    reused_plan = pending_review_feedback(
        dummy_book,
        overlay=overlay,
        ledger={"entries": [{"feedback_key": used_key}]},
        segment_ids=["002"],
    )
    check("review-apply ledger suppresses used feedback",
          reused_plan["segments"][0]["pending_count"] == 1
          and reused_plan["segments"][0]["used_count"] == 1,
          str(reused_plan["segments"][0]))
    comment_basis = dict(planned["pending"][1])
    same_after_stale = feedback_fingerprint(
        book_id="dummy",
        segment_id="002",
        comment={**comment_basis, "paragraph": "changed draft", "stale": True},
    )
    edited_note = feedback_fingerprint(
        book_id="dummy",
        segment_id="002",
        comment={**comment_basis, "note": "Different reviewer note",
                 "updated_at": 3.0},
    )
    check("review-apply feedback keys ignore draft staleness but track edits",
          same_after_stale == comment_basis["feedback_key"]
          and edited_note != comment_basis["feedback_key"])
    valid_response = {
        "segment_id": "002",
        "decisions": [{
            "feedback_key": comment_basis["feedback_key"],
            "comment_id": "chap1",
            "action": "skipped",
            "reason": "Already resolved in the draft.",
            "changed_paragraphs": [],
        }],
    }
    try:
        _validate_apply_response(
            valid_response,
            segment_id="002",
            expected_keys={comment_basis["feedback_key"]},
        )
        _validate_revision_consistency(
            decisions=valid_response["decisions"],
            original="same draft",
            revised="different draft",
        )
        rejected_bad_skip = False
    except ValueError:
        rejected_bad_skip = True
    check("review-apply rejects skipped feedback that edits the draft",
          rejected_bad_skip)
    try:
        _validate_revision_consistency(
            decisions=[{
                "feedback_key": "dialogue-key",
                "comment_id": "dialogue-comment",
                "action": "applied",
                "reason": "Restored source dialogue.",
                "changed_paragraphs": [1],
            }],
            original='"Clear enough," said Tuppence.\n\nTommy nodded.',
            revised=(
                '"Rich relations?"\n\n'
                '"I have an uncle."\n\n'
                '"Why not?"\n\n'
                '"He hated her."'
            ),
        )
        rejected_new_unattributed_dialogue = False
    except ValueError:
        rejected_new_unattributed_dialogue = True
    check("review-apply rejects new unattributed dialogue runs",
          rejected_new_unattributed_dialogue)
    try:
        _validate_revision_consistency(
            decisions=[{
                "feedback_key": "dialogue-key",
                "comment_id": "dialogue-comment",
                "action": "applied",
                "reason": "Added source-backed speaker tags.",
                "changed_paragraphs": [1],
            }],
            original='"Clear enough," said Tuppence.\n\nTommy nodded.',
            revised=(
                '"Rich relations?" asked Tuppence.\n\n'
                '"I have an uncle."\n\n'
                '"Why not?" she pressed.\n\n'
                '"He hated her."'
            ),
        )
        accepted_tagged_dialogue = True
    except ValueError:
        accepted_tagged_dialogue = False
    check("review-apply accepts compact attributed dialogue turns",
          accepted_tagged_dialogue)
    try:
        _validate_revision_consistency(
            decisions=[{
                "feedback_key": "hidden-change-key",
                "comment_id": "hidden-change-comment",
                "action": "applied",
                "reason": "Changed the target paragraph.",
                "changed_paragraphs": [1],
            }],
            original="unchanged\n\ntarget before\n\nother before",
            revised="unchanged\n\ntarget after\n\nother after",
        )
        rejected_undeclared_change = False
    except ValueError:
        rejected_undeclared_change = True
    check("review-apply rejects undeclared paragraph changes",
          rejected_undeclared_change)

    def write_review_book(artifact_root: Path, books_root: Path, book_id: str,
                          title: str, draft: str) -> None:
        align_dir = artifact_root / book_id / "alignments"
        align_dir.mkdir(parents=True, exist_ok=True)
        (align_dir / "001.json").write_text(json.dumps({
            "source_paragraphs": ["Source paragraph."],
            "draft_paragraphs": [draft],
            "mapping": [{
                "draft_para": 0,
                "source_paras": [0],
                "note": "compressed",
            }],
        }, indent=2) + "\n")
        (artifact_root / book_id / "plan.json").write_text(json.dumps({
            "book_id": book_id,
            "title": title,
            "author": "Fixture",
            "segments": [{"id": "001", "title": "Opening"}],
        }, indent=2) + "\n")
        meta_dir = books_root / book_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "metadata.json").write_text(json.dumps({
            "title": title,
            "author": "Fixture",
        }, indent=2) + "\n")

    overlay_tmp = Path(tempfile.mkdtemp(prefix="forage-overlay-unit-"))
    try:
        base_artifacts = overlay_tmp / "base_artifacts"
        base_books = overlay_tmp / "base_books"
        mounted_artifacts = overlay_tmp / "mounted_artifacts"
        mounted_books = overlay_tmp / "mounted_books"
        write_review_book(base_artifacts, base_books, "overlayed",
                          "Baked Title", "baked draft")
        write_review_book(mounted_artifacts, mounted_books, "overlayed",
                          "Mounted Title", "mounted draft")
        write_review_book(mounted_artifacts, mounted_books, "mounted_only",
                          "Mounted Only", "mounted-only draft")
        with patched_env({
            "FORAGE_WORK_DIR": "",
            "FORAGE_BOOKS_DIR": "",
            "FORAGE_ARTIFACT_OVERLAY_DIR": str(mounted_artifacts),
            "FORAGE_BOOKS_OVERLAY_DIR": str(mounted_books),
        }):
            overlay_store = ArtifactStore(work_dir=base_artifacts, books_dir=base_books)
            overlay_summary = overlay_store.book_summary("overlayed")
            overlay_chapter = overlay_store.chapter_view("overlayed", "001") or {}
            mounted_chapter = overlay_store.chapter_view("mounted_only", "001") or {}
        check("artifact overlay replaces a baked book",
              overlay_summary is not None
              and overlay_summary.title == "Mounted Title"
              and overlay_chapter.get("blocks", [{}])[0].get("draft") == "mounted draft",
              str(overlay_chapter))
        check("artifact overlay can add a book without rebaking",
              "mounted_only" in overlay_store.book_ids()
              and mounted_chapter.get("blocks", [{}])[0].get("draft") == "mounted-only draft",
              str(overlay_store.book_ids()))
    finally:
        shutil.rmtree(overlay_tmp, ignore_errors=True)

    with patched_env({"FORAGE_ENV": "production", "FORAGE_SECRET_KEY": "",
                      "FORAGE_REVIEW_TOKEN": "", "FORAGE_ADMIN_TOKEN": "",
                      "FLY_APP_NAME": ""}):
        try:
            A.AuthConfig.from_env()
            refused = False
        except A.AuthConfigError:
            refused = True
    check("production refuses to start without a secret key and token", refused)

    with patched_env({"FORAGE_ENV": "production", "FORAGE_SECRET_KEY": SECRET,
                      "FORAGE_REVIEW_TOKEN": "short", "FORAGE_ADMIN_TOKEN": "",
                      "FLY_APP_NAME": ""}):
        try:
            A.AuthConfig.from_env()
            refused_weak = False
        except A.AuthConfigError:
            refused_weak = True
    check("production refuses a token shorter than the floor", refused_weak)

    with patched_env({**env, "FORAGE_ADMIN_TOKEN": REVIEW_TOKEN}):
        try:
            A.AuthConfig.from_env()
            rejected = False
        except A.AuthConfigError:
            rejected = True
    check("identical review and admin tokens are rejected", rejected)


def check_api(
    check: Checks,
    app_url: str,
    book: str,
    segment: str,
    edits_dir: Path,
    ledger_fixture: "ReviewApplyLedgerFixture",
) -> None:
    """Access control over HTTP."""
    anon = Client(app_url, ip="203.0.113.10")
    status, payload, headers = anon.request("GET", "/api/books")
    check("anyone can read the book list", status == 200 and payload["books"])
    check("book list includes diagnostic counts",
          isinstance(payload["books"][0].get("diagnostics"), dict))
    check("security headers are set",
          headers.get("x-content-type-options") == "nosniff"
          and "default-src 'self'" in headers.get("content-security-policy", "")
          and headers.get("x-frame-options") == "DENY",
          str({k: v for k, v in headers.items() if k.startswith(("x-", "content-s"))}))

    status, chapter_payload, _ = anon.request("GET", f"/api/books/{book}/chapters/{segment}")
    check("chapter API includes current review flags",
          status == 200
          and isinstance(chapter_payload.get("diagnostic_counts"), dict)
          and isinstance(chapter_payload.get("diagnostics"), list)
          and isinstance(chapter_payload.get("diagnostics_unmatched"), list),
          str(chapter_payload.keys() if isinstance(chapter_payload, dict) else chapter_payload))
    check("chapter API includes draft-sidecar notes",
          status == 200
          and isinstance(chapter_payload.get("chapter_notes"), dict)
          and "draft_words" in chapter_payload.get("chapter_notes", {}),
          str(chapter_payload.get("chapter_notes") if isinstance(chapter_payload, dict)
              else chapter_payload))

    note = {"segment_id": segment, "draft_para": 0, "body": "anonymous note"}
    status, _, _ = anon.request("POST", f"/api/books/{book}/comments", note)
    check("anonymous writes are refused", status == 401, str(status))

    reviewer = Client(app_url, ip="203.0.113.11")
    status, payload = reviewer.sign_in(REVIEW_TOKEN)
    check("the review token signs in as reviewer",
          status == 200 and payload["role"] == "reviewer", str(payload))
    status, created, _ = reviewer.request("POST", f"/api/books/{book}/comments",
                                          {**note, "body": "reviewer note"})
    check("a reviewer can comment", status == 201, str(status))
    status, chapter_created, _ = reviewer.request(
        "POST", f"/api/books/{book}/comments",
        {"scope": "chapter", "segment_id": segment, "body": "chapter-level note",
         "kind": "continuity"})
    check("a reviewer can leave a chapter-level note",
          status == 201 and chapter_created.get("scope") == "chapter"
          and chapter_created.get("draft_para") is None,
          str(chapter_created))
    status, book_created, _ = reviewer.request(
        "POST", f"/api/books/{book}/comments",
        {"scope": "book", "body": "book-level note", "kind": "continuity"})
    check("a reviewer can leave a book-level note",
          status == 201 and book_created.get("scope") == "book",
          str(book_created))
    status, processed_created, _ = reviewer.request(
        "POST", f"/api/books/{book}/comments",
        {**note, "body": "processed response smoke note", "kind": "continuity"})
    check("a reviewer can create a note with a later LLM response",
          status == 201 and processed_created.get("id"),
          str(processed_created))
    ledger_fixture.write(book, {
        "ledger_version": 1,
        "entries": [{
            "run_id": "smoke-review-apply",
            "used_at": 1.0,
            "book_id": book,
            "segment_id": segment,
            "feedback_key": "smoke-feedback-key-old",
            "comment_id": processed_created["id"],
            "scope": "paragraph",
            "source_segment_id": segment,
            "draft_para": 0,
            "comment_updated_at": processed_created.get("updated_at"),
            "action": "applied",
            "reason": "Older response.",
            "changed_paragraphs": [0],
            "comment_response": {
                "source": "review_apply",
                "processed_at": 1.0,
                "run_id": "smoke-review-apply",
                "segment_id": segment,
                "action": "applied",
                "body": "Older response.",
                "draft_changed": True,
                "changed_paragraphs": [0],
                "model": "smoke:model",
            },
            "draft_before_hash": "before",
            "draft_after_hash": "after",
            "draft_changed": True,
            "overlay_generated_at": 123.0,
            "prompt": "review_apply_segment",
            "model": "smoke:model",
            "input_tokens": 1,
            "output_tokens": 1,
        }, {
            "run_id": "smoke-review-apply",
            "used_at": 2.0,
            "book_id": book,
            "segment_id": segment,
            "feedback_key": "smoke-feedback-key-new",
            "comment_id": processed_created["id"],
            "scope": "paragraph",
            "source_segment_id": segment,
            "draft_para": 0,
            "comment_updated_at": processed_created.get("updated_at"),
            "action": "applied",
            "reason": "Applied a source-backed speaker tag.",
            "changed_paragraphs": [0],
            "comment_response": {
                "source": "review_apply",
                "processed_at": 2.0,
                "run_id": "smoke-review-apply",
                "segment_id": segment,
                "action": "applied",
                "body": "Applied a source-backed speaker tag.",
                "draft_changed": True,
                "changed_paragraphs": [0],
                "model": "smoke:model",
            },
            "draft_before_hash": "before",
            "draft_after_hash": "after",
            "draft_changed": True,
            "overlay_generated_at": 123.0,
            "prompt": "review_apply_segment",
            "model": "smoke:model",
            "input_tokens": 1,
            "output_tokens": 1,
        }],
    })
    status, processed_chapter, _ = anon.request(
        "GET", f"/api/books/{book}/chapters/{segment}")
    processed_comment = next(
        (c for c in processed_chapter.get("comments", [])
         if c.get("id") == processed_created["id"]),
        {},
    )
    check("chapter API attaches LLM responses to processed comments",
          status == 200
          and processed_comment.get("llm_response_count") == 1
          and processed_comment.get("llm_responses", [{}])[0].get("body")
          == "Applied a source-backed speaker tag.",
          str(processed_comment))
    status, _, _ = reviewer.request("POST", f"/api/books/{book}/publish")
    check("a reviewer cannot publish", status == 403, str(status))

    admin = Client(app_url, ip="203.0.113.12")
    status, payload = admin.sign_in(ADMIN_TOKEN)
    check("the admin token signs in as admin",
          status == 200 and payload["role"] == "admin", str(payload))
    status, published, _ = admin.request("POST", f"/api/books/{book}/publish")
    check("an admin can publish", status == 200, str(published))
    check("publish honours FORAGE_EDITS_DIR",
          status == 200 and str(edits_dir) in published.get("path", ""),
          published.get("path", ""))
    check("the published overlay is on disk",
          (edits_dir / book / "edits.json").exists())
    published_doc = json.loads((edits_dir / book / "edits.json").read_text())
    check("published overlay carries book-level notes separately",
          any(c.get("note") == "book-level note" and c.get("scope") == "book"
              for c in published_doc.get("book_comments", [])),
          str(published_doc.get("book_comments")))
    all_published_comments = list(published_doc.get("book_comments", []))
    all_published_comments.extend(
        c for seg in published_doc.get("segments", [])
        for c in seg.get("comments", [])
    )
    check("published overlay carries comment update timestamps",
          all("updated_at" in c for c in all_published_comments),
          str(all_published_comments))
    chapter_comments = [
        c for seg in published_doc.get("segments", [])
        if seg.get("segment_id") == segment
        for c in seg.get("comments", [])
    ]
    check("published overlay carries chapter-level notes",
          any(c.get("note") == "chapter-level note" and c.get("scope") == "chapter"
              and c.get("draft_para") is None for c in chapter_comments),
          str(chapter_comments))

    status, _, _ = reviewer.request("DELETE", f"/api/comments/{created.get('id', 'missing')}")
    check("a reviewer can clean up their note", status == 200, str(status))
    reviewer.request("DELETE", f"/api/comments/{chapter_created.get('id', 'missing')}")
    reviewer.request("DELETE", f"/api/comments/{book_created.get('id', 'missing')}")

    # Cross-origin writes: SameSite already blocks the cookie, this rejects outright.
    status, _, _ = admin.request("POST", f"/api/books/{book}/comments", note,
                                 headers={"Origin": "https://evil.example"})
    check("cross-origin writes are refused", status == 403, str(status))

    # Secure cookie only when the proxy says the hop was HTTPS.
    plain = Client(app_url, ip="203.0.113.13")
    _, _, headers = plain.request("POST", "/api/session", {"token": REVIEW_TOKEN})
    check("no Secure flag on a plain-http sign-in",
          "Secure" not in headers.get("set-cookie", ""), headers.get("set-cookie", ""))
    tls = Client(app_url, ip="203.0.113.14")
    _, _, headers = tls.request("POST", "/api/session", {"token": REVIEW_TOKEN},
                                headers={"X-Forwarded-Proto": "https"})
    check("Secure flag is set behind an HTTPS proxy",
          "Secure" in headers.get("set-cookie", ""), headers.get("set-cookie", ""))
    check("HSTS is set behind an HTTPS proxy",
          "max-age" in headers.get("strict-transport-security", ""))

    # Guessing lockout, on its own address so the other scenarios stay usable.
    guesser = Client(app_url, ip="203.0.113.99")
    codes = [guesser.sign_in("wrong-" + str(i))[0] for i in range(9)]
    check("wrong tokens are refused", codes[0] == 403, str(codes[0]))
    check("repeated guessing locks the address out", codes[-1] == 429, str(codes))
    status, _ = guesser.sign_in(REVIEW_TOKEN)
    check("the lockout also blocks the correct token", status == 429, str(status))
    check("the lockout is per address, not global",
          Client(app_url, ip="203.0.113.15").sign_in(REVIEW_TOKEN)[0] == 200)
    # A caller who prepends their own forwarded entry must not escape the
    # lockout: the proxy's appended value is the one that counts.
    spoofer = Client(app_url, ip="198.51.100.7, 203.0.113.99")
    check("forged forwarded entries don't buy a fresh bucket",
          spoofer.sign_in(REVIEW_TOKEN)[0] == 429, str(spoofer.sign_in(REVIEW_TOKEN)[0]))


class patched_env:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.saved: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self.values.items():
            self.saved[key] = os.environ.get(key)
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, old in self.saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        return False


class ReviewApplyLedgerFixture:
    def __init__(self) -> None:
        self.saved: dict[Path, str | None] = {}

    def write(self, book_id: str, ledger: dict) -> None:
        path = ROOT / "work" / book_id / "editorial" / "review_apply_ledger.json"
        if path not in self.saved:
            self.saved[path] = path.read_text() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n")

    def restore(self) -> None:
        for path, old in self.saved.items():
            if old is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(old)


async def run(book: str, shots_dir: Path) -> int:
    import websockets  # ships with uvicorn[standard]

    from forage.webapp.auth import ADMIN, REVIEWER, AuthConfig
    from forage.webapp.store import ArtifactStore

    artifacts = ArtifactStore()
    if not artifacts.has_book(book):
        print(f"no alignments for {book!r} — run: forage proofread {book}")
        return 2
    chapter_ids = artifacts.segment_ids(book)
    # Pick a chapter that exercises the interesting paths.
    flagged = next((sid for sid in chapter_ids
                    if artifacts.chapter_counts(book, sid)["unsupported"]), None)
    if flagged is None:
        print(f"{book} has no unsupported paragraphs — the u-key check needs one")
        return 2
    diagnostic_segment = next(
        (sid for sid in chapter_ids
         if artifacts.diagnostic_counts(book, sid).get("total")),
        None,
    )

    check = Checks()
    print("\nunits")
    check_units(check)

    tmp = Path(tempfile.mkdtemp(prefix="forage-review-check-"))
    edits_dir = tmp / "edits"
    port = free_port()
    env = {**os.environ,
           "FORAGE_REVIEW_TOKEN": REVIEW_TOKEN,
           "FORAGE_ADMIN_TOKEN": ADMIN_TOKEN,
           "FORAGE_SECRET_KEY": SECRET,
           "FORAGE_REVIEW_DB": str(tmp / "review.db"),
           "FORAGE_EDITS_DIR": str(edits_dir),
           # so the checks can present distinct client addresses
           "FORAGE_TRUST_PROXY": "1"}
    env.pop("FLY_APP_NAME", None)
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "forage.webapp.app:get_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    app_url = f"http://127.0.0.1:{port}"

    chrome = find_chrome()
    browser = None
    debug_port = free_port()
    ledger_fixture = ReviewApplyLedgerFixture()
    if chrome:
        browser = subprocess.Popen(
            [chrome, "--headless=new", f"--remote-debugging-port={debug_port}",
             f"--user-data-dir={tmp / 'chrome'}", "--no-first-run", "--disable-gpu",
             "--window-size=1440,1000", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"{app_url}/healthz", timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("the app never started")
            return 1

        print("\napi")
        check_api(check, app_url, book, flagged, edits_dir, ledger_fixture)

        if not browser:
            print("\nbrowser: skipped — no Chrome or Chromium found")
            return _report(check, shots_dir)

        for _ in range(80):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("Chrome never exposed a debugging target")
            return 1

        with patched_env({"FORAGE_SECRET_KEY": SECRET, "FORAGE_REVIEW_TOKEN": REVIEW_TOKEN,
                          "FORAGE_ADMIN_TOKEN": ADMIN_TOKEN, "FLY_APP_NAME": ""}):
            cookie = AuthConfig.from_env().issue(ADMIN, "smoke")

        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=40_000_000) as ws:
            c = CDP(ws)
            await c.send("Page.enable")
            await c.send("Runtime.enable")
            await c.send("Network.enable")
            await c.send("Network.setCookie", name="forage_review", value=cookie,
                         domain="127.0.0.1", path="/")
            await c.send("Page.addScriptToEvaluateOnNewDocument", source="""
              window.__errors = [];
              addEventListener('error', e => window.__errors.push(String(e.message)));
              addEventListener('unhandledrejection', e => window.__errors.push(String(e.reason)));
            """)

            print("\nindex")
            await c.send("Page.navigate", url=app_url + "/")
            await asyncio.sleep(1.5)
            cards = await c.js("return document.querySelectorAll('.book-card').length")
            check("book cards render", cards > 0, f"got {cards}")
            check("an admin cookie is recognised",
                  "Admin" in (await c.js("return document.getElementById('session-btn').textContent") or ""))

            await c.js(f"""
              const card = [...document.querySelectorAll('.book-card')]
                .find(a => a.getAttribute('href').endsWith('/{book}'));
              card.click();""")
            await asyncio.sleep(1.5)
            check("clicking a card opens the book", f"/b/{book}" in await c.js("return location.pathname"))
            check("the chapter rail is populated",
                  await c.js("return document.querySelectorAll('.chapter-link').length") == len(chapter_ids))

            print("\nchapter")
            await c.send("Page.navigate", url=f"{app_url}/b/{book}?c={flagged}")
            await asyncio.sleep(1.6)
            total = await c.js("return document.querySelectorAll('.block').length")
            check("blocks render", total > 0, f"got {total}")
            check("chapter draft notes render",
                  await c.js("return !!document.querySelector('.chapter-notes')"))
            check("book and chapter note controls render", await c.js("""
              return [...document.querySelectorAll('button')]
                .some(b => b.textContent === 'Book note') &&
                [...document.querySelectorAll('button')]
                .some(b => b.textContent === 'Chapter note');"""))
            check("source paragraphs render without toggles",
                  await c.js("return document.querySelectorAll('.toggle-source').length === 0"))
            check("LLM responses render on processed comments",
                  await c.js("""
                  const response = document.querySelector('.llm-response');
                  return !!response &&
                    response.textContent.includes('Applied a source-backed speaker tag.');"""))
            check("the flags filter renders",
                  await c.js("""
                  return [...document.querySelectorAll('.filter-chip')]
                    .some(b => b.textContent === 'Flags');"""))
            if diagnostic_segment:
                await c.send("Page.navigate", url=f"{app_url}/b/{book}?c={diagnostic_segment}")
                await asyncio.sleep(1.1)
                await c.js("""
                  [...document.querySelectorAll('.filter-chip')]
                    .find(b => b.textContent === 'Flags').click();""")
                await asyncio.sleep(0.4)
                check("flags filter shows current review flags",
                      await c.js("return document.querySelectorAll('.diagnostic').length") > 0)
                check("flag source context is visible",
                      await c.js("""
                      const source = document.querySelector('.diagnostic-source');
                      return !!source && source.offsetHeight > 0 &&
                        source.textContent.includes('Source context');"""))
                await c.js("""
                  [...document.querySelectorAll('.filter-chip')]
                    .find(b => b.textContent === 'Flags').click();""")
                await asyncio.sleep(0.2)
                await c.send("Page.navigate", url=f"{app_url}/b/{book}?c={flagged}")
                await asyncio.sleep(1.1)

            await c.js("""
              [...document.querySelectorAll('.filter-chip')]
                .find(b => b.textContent === 'Unsupported').click();""")
            await asyncio.sleep(0.4)
            kinds = await c.js("""
              return [...new Set([...document.querySelectorAll('.block')]
                .map(b => b.className.split(' ')[1]))];""")
            check("the unsupported filter narrows the view", kinds == ["unsupported"], str(kinds))
            await c.js("""
              [...document.querySelectorAll('.filter-chip')]
                .find(b => b.textContent === 'Unsupported').click();""")
            await asyncio.sleep(0.4)

            first_word = await c.js("""
              return document.querySelector('.block .draft').textContent.split(/\\s+/)[3];""")
            await c.js(f"""
              const box = document.getElementById('chapter-search');
              box.value = {json.dumps(first_word)};
              box.dispatchEvent(new Event('input', {{bubbles: true}}));""")
            await asyncio.sleep(0.4)
            found = await c.js("return document.querySelectorAll('.block').length")
            check("search filters blocks", 0 < found <= total, f"got {found} of {total}")
            await c.js("""
              const box = document.getElementById('chapter-search');
              box.value = ''; box.dispatchEvent(new Event('input', {bubbles: true}));""")
            await asyncio.sleep(0.4)

            print("\nkeyboard")
            await c.js(CDP.key("j"))
            await asyncio.sleep(0.25)
            check("j selects the first paragraph",
                  await c.js("return document.querySelector('.block.is-current')?.dataset.para") == "0")
            await c.js(CDP.key("j") + CDP.key("j"))
            await asyncio.sleep(0.25)
            check("j advances",
                  await c.js("return document.querySelector('.block.is-current')?.dataset.para") == "2")
            await c.js(CDP.key("k"))
            await asyncio.sleep(0.25)
            check("k goes back",
                  await c.js("return document.querySelector('.block.is-current')?.dataset.para") == "1")
            check("the url tracks the current paragraph",
                  "p=1" in await c.js("return location.search"))
            await c.js(CDP.key("u"))
            await asyncio.sleep(0.3)
            check("u jumps to an unsupported paragraph",
                  "unsupported" in (await c.js("return document.querySelector('.block.is-current')?.className") or ""))

            print("\nnotes")
            await c.js("""
              [...document.querySelectorAll('button')]
                .find(b => b.textContent === 'Chapter note').click();""")
            await asyncio.sleep(0.4)
            await c.js("""
              document.querySelector('.scope-composer textarea').value = 'chapter-level smoke note';
              [...document.querySelectorAll('.scope-composer .btn')]
                .find(b => b.textContent === 'Add note').click();""")
            await asyncio.sleep(0.7)
            check("adding a chapter-level note renders above the paragraphs",
                  await c.js("""
                  return [...document.querySelectorAll('.scope-notes .note-body')]
                    .some(n => n.textContent.includes('chapter-level smoke note'));"""))

            await c.js("""
              const p = document.querySelector('.block[data-para="0"] .draft');
              const node = [...p.childNodes].find(n => n.nodeType === 3);
              const range = document.createRange();
              range.setStart(node, 0); range.setEnd(node, Math.min(24, node.length));
              const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
              document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));""")
            await asyncio.sleep(0.4)
            check("selecting text offers a comment",
                  await c.js("return !document.getElementById('selection-tip').hidden"))
            await c.js("return document.getElementById('selection-comment').click()")
            await asyncio.sleep(0.5)
            check("the composer carries the quote",
                  bool(await c.js("return document.querySelector('.composer-quote')?.textContent")))

            before = await c.js(f"""
              const r = await fetch('/api/books/{book}/comments');
              return (await r.json()).comments.length;""")
            await c.js("""
              document.querySelector('.composer textarea').value = 'smoke check note';
              document.querySelector('#composer-severity').value = 'blocker';
              [...document.querySelectorAll('.composer .btn')]
                .find(b => b.textContent === 'Add note').click();""")
            await asyncio.sleep(0.9)
            after = await c.js(f"""
              const r = await fetch('/api/books/{book}/comments');
              return (await r.json()).comments.length;""")
            check("adding a note persists it", after == before + 1, f"{before} -> {after}")
            check("the note renders in the margin", await c.js("""
              return [...document.querySelectorAll('.note-body')]
                .some(n => n.textContent.includes('smoke check note'));"""))
            check("severity carries through", "blocker" in (await c.js("""
              return [...document.querySelectorAll('.note')]
                .find(n => n.textContent.includes('smoke check note')).className;""")))
            await c.shot(shots_dir / "review-note.png")

            await c.js("""
              const note = [...document.querySelectorAll('.note')]
                .find(n => n.textContent.includes('smoke check note'));
              [...note.querySelectorAll('button')].find(b => b.textContent === 'Resolve').click();""")
            await asyncio.sleep(0.7)
            check("resolve updates the note", "resolved" in (await c.js("""
              return [...document.querySelectorAll('.note')]
                .find(n => n.textContent.includes('smoke check note')).className;""")))
            await c.js("""
              const note = [...document.querySelectorAll('.note')]
                .find(n => n.textContent.includes('smoke check note'));
              [...note.querySelectorAll('button')].find(b => b.textContent === 'Delete').click();""")
            await asyncio.sleep(0.7)
            check("delete removes the note", await c.js(f"""
              const r = await fetch('/api/books/{book}/comments');
              return !(await r.json()).comments.some(c => c.body.includes('smoke check note'));"""))

            print("\naccess")
            check("an admin sees the publish button", 1 == await c.js("""
              return [...document.querySelectorAll('.rail-tools .btn')]
                .filter(b => b.textContent.includes('Publish')).length;"""))
            check("the session button names the role",
                  "Admin" in (await c.js("return document.getElementById('session-btn').textContent") or ""))

            await c.js("return document.getElementById('session-btn').click()")
            await asyncio.sleep(0.9)
            check("signing out returns to read-only",
                  "Sign in" in (await c.js("return document.getElementById('session-btn').textContent") or ""))
            check("read-only hides note actions",
                  await c.js("return document.querySelectorAll('.note-foot').length") == 0)
            check("read-only hides the publish button", 0 == await c.js("""
              return [...document.querySelectorAll('.rail-tools .btn')]
                .filter(b => b.textContent.includes('Publish')).length;"""))

            await c.js("return document.getElementById('session-btn').click()")
            await asyncio.sleep(0.4)
            await c.js("""
              document.getElementById('signin-token').value = 'wrong';
              document.getElementById('signin-form')
                .dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true}));""")
            await asyncio.sleep(0.7)
            check("a wrong token is rejected",
                  await c.js("return !document.getElementById('signin-error').hidden"))
            await c.js(f"""
              document.getElementById('signin-token').value = {json.dumps(REVIEW_TOKEN)};
              document.getElementById('signin-label').value = 'smoke';
              document.getElementById('signin-form')
                .dispatchEvent(new SubmitEvent('submit', {{bubbles: true, cancelable: true}}));""")
            await asyncio.sleep(1.2)
            check("the review token signs in as a reviewer",
                  "Reviewer" in (await c.js("return document.getElementById('session-btn').textContent") or ""))
            check("a reviewer does not see the publish button", 0 == await c.js("""
              return [...document.querySelectorAll('.rail-tools .btn')]
                .filter(b => b.textContent.includes('Publish')).length;"""))

            await c.js(f"""
              document.getElementById('session-btn').click();
              await new Promise(r => setTimeout(r, 400));
              document.getElementById('session-btn').click();
              await new Promise(r => setTimeout(r, 200));
              document.getElementById('signin-token').value = {json.dumps(ADMIN_TOKEN)};
              document.getElementById('signin-form')
                .dispatchEvent(new SubmitEvent('submit', {{bubbles: true, cancelable: true}}));""")
            await asyncio.sleep(1.4)
            check("the admin token signs in as an admin",
                  "Admin" in (await c.js("return document.getElementById('session-btn').textContent") or ""))
            await c.js("""
              [...document.querySelectorAll('.rail-tools .btn')]
                .find(b => b.textContent.includes('Publish')).click();""")
            await asyncio.sleep(1.0)
            check("publishing from the browser reports where it landed", await c.js("""
              return [...document.querySelectorAll('.toast')]
                .some(t => t.textContent.includes('edits.json'));"""))

            print("\nlayout")
            await c.send("Page.navigate", url=f"{app_url}/b/{book}?c={flagged}&p=5")
            await asyncio.sleep(1.6)
            check("a deep link focuses the paragraph",
                  await c.js("return document.querySelector('.block.is-current')?.dataset.para") == "5")
            await c.send("Emulation.setDeviceMetricsOverride", width=430, height=930,
                         deviceScaleFactor=2, mobile=True)
            await asyncio.sleep(0.8)
            overflow = await c.js("""
              return document.documentElement.scrollWidth - document.documentElement.clientWidth;""")
            check("no horizontal overflow at 430px", overflow <= 1, f"{overflow}px")
            check("topbar items do not overlap on mobile", 0 == await c.js("""
              const kids = [...document.querySelectorAll('.topbar > *')]
                .map(n => n.getBoundingClientRect());
              let bad = 0;
              for (let i = 0; i < kids.length; i++)
                for (let j = i + 1; j < kids.length; j++)
                  if (kids[i].right > kids[j].left + 1 && kids[i].left < kids[j].right - 1 &&
                      kids[i].bottom > kids[j].top + 1 && kids[i].top < kids[j].bottom - 1) bad++;
              return bad;"""))
            await c.shot(shots_dir / "review-mobile.png")
            await c.send("Emulation.clearDeviceMetricsOverride")

            check("no uncaught page errors",
                  not await c.js("return (window.__errors || []).length"),
                  str(await c.js("return (window.__errors || []).join('; ')")))
    finally:
        if browser:
            browser.terminate()
        server.terminate()
        ledger_fixture.restore()
        shutil.rmtree(tmp, ignore_errors=True)

    return _report(check, shots_dir)


def _report(check: Checks, shots_dir: Path) -> int:
    print()
    if check.failures:
        print(f"FAILED: {len(check.failures)} — " + ", ".join(check.failures))
        return 1
    print(f"all checks passed · screenshots in {shots_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", default="gatsby", help="book id to drive the checks against")
    parser.add_argument("--shots", default=None, help="directory for screenshots")
    args = parser.parse_args()
    shots = Path(args.shots) if args.shots else Path(tempfile.gettempdir()) / "forage-review-shots"
    shots.mkdir(parents=True, exist_ok=True)
    return asyncio.run(run(args.book, shots))


if __name__ == "__main__":
    sys.exit(main())
