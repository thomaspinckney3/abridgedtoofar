import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from forage import publication
from forage.hosted_publication import HostedPublications
from forage.review_transport import ReviewTransport, TransportError, _NoRedirect
from forage.webapp.app import create_app
from forage.webapp.auth import AuthConfig
from forage.webapp.store import ArtifactStore, ReviewStore
from tests.test_publication import publication_input
from tests.conftest import ADMIN_PASSWORD, REVIEW_PASSWORD, seed_accounts


def test_local_publish_and_feedback(publication_input, tmp_path):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    client = ReviewTransport(local_root=tmp_path / "hosted")
    assert client.publish(book, revision)["channel"] == "review"
    assert client.publish(book, revision, "release")["channel"] == "release"
    feed = {"version": 1, "book_id": book.book_id, "source_id": "test", "complete": True, "comments": []}
    (tmp_path / "hosted" / book.book_id / "feedback.json").write_text(json.dumps(feed))
    assert client.fetch_feedback(book.book_id) == feed


def test_actual_http_publish_first_book_and_fetch(publication_input, tmp_path):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    artifacts = ArtifactStore(work_dir=tmp_path / "baked", books_dir=tmp_path / "books", hosted_dir=tmp_path / "hosted")
    reviews = ReviewStore(db_path=tmp_path / "review.db")
    auth = AuthConfig(session_seconds=3600)
    with TestClient(create_app(artifacts=artifacts, reviews=reviews, auth=auth)) as http:
        seed_accounts(http.app)
        transport = ReviewTransport(base_url="http://testserver", username="admin", password=ADMIN_PASSWORD, http_client=http)
        result = transport.publish(book, revision)
        assert result["revision"] == revision
        assert transport.fetch_feedback(book.book_id)["complete"] is True
        assert transport.publish(book, revision, "release")["channel"] == "release"
    assert HostedPublications(tmp_path / "hosted").resolve(book.book_id, channel="release")[1]["revision"] == revision


@pytest.mark.parametrize("kwargs", [{}, {"base_url": "ftp://example.com"},
    {"base_url": "http://user:secret@example.com"}, {"base_url": "https://example.com/?x=1"},
    {"base_url": "https://example.com/#anchor"}, {"base_url": "https://example.com", "local_root": "/tmp/x"}])
def test_configuration_validation(kwargs, monkeypatch):
    monkeypatch.delenv("FORAGE_REVIEW_URL", raising=False)
    monkeypatch.delenv("FORAGE_REVIEW_LOCAL_ROOT", raising=False)
    with pytest.raises(ValueError):
        ReviewTransport(**kwargs)


class Stub:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        return SimpleNamespace(status_code=response[0], content=response[1])


@pytest.mark.parametrize("status,data", [(302, b"{}"), (403, b'{"detail":"denied"}'),
    (200, b"not-json"), (200, b"[]"), (200, b"x" * 101)])
def test_bad_responses_fail_bounded_and_do_not_follow_redirects(status, data):
    stub = Stub([(status, data)])
    transport = ReviewTransport(base_url="https://example.com", http_client=stub, max_response_bytes=100)
    with pytest.raises(TransportError):
        transport.fetch_feedback("sample")
    assert len(stub.calls) == 1
    assert stub.calls[0][2]["follow_redirects"] is False
    assert stub.calls[0][2]["timeout"] == 30
    assert _NoRedirect().redirect_request(None, None, 307, "", {}, "https://evil.example") is None


def test_wrong_confirmation_is_failure(publication_input):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    stub = Stub([(200, b'{"role":"admin"}'), (200, b'{"revision":"wrong"}')])
    transport = ReviewTransport(base_url="https://example.com", username="admin", password="secret", http_client=stub)
    with pytest.raises(TransportError, match="different"):
        transport.publish(book, revision)
    assert len(stub.calls) == 2


def test_reviewer_credentials_cannot_publish(publication_input):
    book, kwargs = publication_input
    revision = publication.snapshot_revision(book, **kwargs)["revision"]
    stub = Stub([(200, b'{"role":"reviewer"}')])
    transport = ReviewTransport(base_url="https://example.com", username="admin", password="secret", http_client=stub)
    with pytest.raises(TransportError, match="administrator"):
        transport.publish(book, revision)
    assert len(stub.calls) == 1


def test_local_feedback_refuses_symlink_book(tmp_path):
    root = tmp_path / "host"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "feedback.json").write_text("{}")
    (root / "sample").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        ReviewTransport(local_root=root).fetch_feedback("sample")


def test_local_feedback_pending_projection_fails_closed(tmp_path):
    root = tmp_path / "host"
    book_root = root / "sample"
    book_root.mkdir(parents=True)
    (book_root / "feedback.json").write_text("{}")
    (book_root / "feedback_pending").write_text("pending")
    with pytest.raises(TransportError, match="pending"):
        ReviewTransport(local_root=root).fetch_feedback("sample")
