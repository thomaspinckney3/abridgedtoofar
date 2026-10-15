"""Fixtures for the review app's tests.

Every test gets its own artifact tree and SQLite file under tmp_path, so
nothing here touches `work/` or a developer's real review queue.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forage.webapp.app import create_app
from forage.webapp.auth import AuthConfig
from forage.webapp.store import ArtifactStore, ReviewStore

REVIEW_TOKEN = "review-token-for-tests"
ADMIN_TOKEN = "admin-token-for-tests"
ALLOWED_HOST = "review.example.com"
BOOK_ID = "testbook"
SEGMENT_ID = "001"

# ArtifactStore and ReviewStore consult the environment *before* their
# constructor arguments, so an exported FORAGE_WORK_DIR in the developer's own
# shell would otherwise silently redirect these tests at real data.
_ENV_KEYS = (
    "FORAGE_WORK_DIR", "FORAGE_BOOKS_DIR", "FORAGE_ARTIFACT_OVERLAY_DIR",
    "FORAGE_BOOKS_OVERLAY_DIR", "FORAGE_REVIEW_DB", "FORAGE_EDITS_DIR",
    "FORAGE_ALLOWED_HOSTS", "FORAGE_STRICT_HOST", "FORAGE_TRUST_PROXY",
    "FORAGE_ENV", "FLY_APP_NAME", "FORAGE_SECRET_KEY", "FORAGE_REVIEW_TOKEN",
    "FORAGE_ADMIN_TOKEN", "FORAGE_SESSION_HOURS", "FORAGE_SESSION_EPOCH",
    "FORAGE_HOSTED_ROOT", "FORAGE_PUBLICATION_DIR", "FORAGE_REVIEW_URL",
    "FORAGE_REVIEW_LOCAL_ROOT", "FORAGE_MAX_UPLOAD_BYTES",
    "FORAGE_MAX_EXPANDED_BYTES", "FORAGE_MAX_UPLOAD_FILES",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def artifact_tree(tmp_path: Path) -> Path:
    """A one-chapter book, in the shape ArtifactStore expects on disk."""
    work = tmp_path / "work"
    books = tmp_path / "books"
    aligns = work / BOOK_ID / "alignments"
    aligns.mkdir(parents=True)
    (books / BOOK_ID).mkdir(parents=True)

    (aligns / f"{SEGMENT_ID}.json").write_text(json.dumps({
        "source_paragraphs": ["The first source paragraph.",
                              "The second source paragraph, longer than the draft."],
        "draft_paragraphs": ["The first source paragraph.",
                             "The second, compressed."],
        "mapping": [
            {"draft_para": 0, "source_paras": [0], "note": "verbatim"},
            {"draft_para": 1, "source_paras": [1], "note": "compressed"},
        ],
    }))
    (work / BOOK_ID / "plan.json").write_text(json.dumps({
        "title": "Test Book", "author": "A. Tester",
        "segments": [{"id": SEGMENT_ID, "title": "Chapter One"}],
    }))
    (books / BOOK_ID / "metadata.json").write_text(json.dumps({
        "title": "Test Book", "author": "A. Tester",
    }))
    return tmp_path


@pytest.fixture
def make_client(artifact_tree: Path, tmp_path: Path, monkeypatch):
    """Build a TestClient. `allowed_hosts` mirrors FORAGE_ALLOWED_HOSTS, which
    create_app reads at construction time."""

    def _make(allowed_hosts: str | None = None, admin_token: str = ADMIN_TOKEN,
              strict_host: bool = False, **auth_overrides) -> TestClient:
        if allowed_hosts is not None:
            monkeypatch.setenv("FORAGE_ALLOWED_HOSTS", allowed_hosts)
        if strict_host:
            monkeypatch.setenv("FORAGE_STRICT_HOST", "1")

        artifacts = ArtifactStore(work_dir=artifact_tree / "work",
                                  books_dir=artifact_tree / "books")
        reviews = ReviewStore(db_path=tmp_path / "review.db")
        auth_kwargs = dict(
            review_token=REVIEW_TOKEN,
            admin_token=admin_token,
            secret_key=b"secret-key-for-tests",
            session_seconds=3600,
            epoch="0",
            trust_proxy=False,
            production=False,
            generated=(),
        )
        auth_kwargs.update(auth_overrides)
        app = create_app(artifacts=artifacts, reviews=reviews,
                         auth=AuthConfig(**auth_kwargs))
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def sign_in(client: TestClient, token: str = REVIEW_TOKEN,
            label: str = "alice") -> dict:
    """Sign in and leave the session cookie in the client's jar."""
    response = client.post("/api/session", json={"token": token, "label": label})
    assert response.status_code == 200, response.text
    return response.json()


def docker_available() -> bool:
    return (os.environ.get("FORAGE_DOCKER_TESTS") == "1"
            and os.system("docker info >/dev/null 2>&1") == 0)
