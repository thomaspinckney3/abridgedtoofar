"""Crash-boundary proof for accepted prose plus durable review decisions."""
import json
from contextlib import contextmanager

import pytest

from forage import production, publication, review_apply, review_recovery, review_sync
from forage.production_state import atomic_json
from tests.test_production_runner import pipeline, run_ok
from tests.test_review_sync import FeedTransport, comment, feed, fake_apply_provider


def prepared(pipeline, monkeypatch):
    book, calls = pipeline
    first = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]))
    review_sync.pull_feedback(book, transport)
    prior = {"ledger_version": 1, "entries": [{"feedback_key": "earlier-decision", "reason": "Preserve history"}]}
    atomic_json(review_apply.default_ledger_path(book), prior)
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    return book, calls, first, transport, seen, prior


@contextmanager
def interruption(monkeypatch, book, boundary, *, after=False):
    with monkeypatch.context() as patch:
        if boundary == "intent":
            real = review_recovery.atomic_json
            def fail(path, value):
                if after:
                    real(path, value)
                raise OSError("interrupted intent")
            patch.setattr(review_recovery, "atomic_json", fail)
        elif boundary == "finalization":
            patch.setattr(review_recovery, "_finalize_intent", lambda path: (_ for _ in ()).throw(OSError("interrupted finalization")))
        else:
            real = review_recovery.atomic_write_bytes
            paths = {"draft": book.work_dir / "segments/001.md",
                     "checks": book.work_dir / "segments/001.checks.json",
                     "ledger": review_apply.default_ledger_path(book)}
            def fail(path, data):
                match = ".before.md" in path.name if boundary == "snapshot" else path == paths[boundary]
                if match and not after:
                    raise OSError("interrupted " + boundary)
                real(path, data)
                if match:
                    raise OSError("interrupted " + boundary)
            patch.setattr(review_recovery, "atomic_write_bytes", fail)
        yield


@pytest.mark.parametrize("boundary,after", [("intent", True), ("snapshot", False),
    ("snapshot", True), ("draft", False), ("draft", True), ("checks", False),
    ("checks", True), ("ledger", False), ("ledger", True), ("finalization", False)])
def test_durable_intent_recovers_every_boundary_without_model_repetition(pipeline, monkeypatch, boundary, after):
    book, calls, first, transport, seen, prior = prepared(pipeline, monkeypatch)
    original = (book.work_dir / "segments/001.md").read_bytes()
    with interruption(monkeypatch, book, boundary, after=after), pytest.raises(OSError):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert review_recovery.pending_path(book).is_file()
    assert len(seen) == 1 and not transport.published
    intent = json.loads(review_recovery.pending_path(book).read_text())
    assert intent["changes"][-1]["role"] == "ledger"
    retry = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert retry["success"] and len(seen) == 1
    assert not review_recovery.pending_path(book).exists()
    assert (book.work_dir / "segments/001.md").read_bytes() != original
    assert "review_apply" in json.loads((book.work_dir / "segments/001.checks.json").read_text())
    ledger = json.loads(review_apply.default_ledger_path(book).read_text())
    assert ledger["entries"][0] == prior["entries"][0]
    assert len(ledger["entries"]) == 2 and ledger["entries"][1]["comment_id"] == "note-1"
    snapshots = list((book.work_dir / "segments").glob("001.review_apply.*.before.md"))
    assert len(snapshots) == 1 and snapshots[0].read_bytes() == original
    assert transport.published[-1][0] != first["review_revision"]
    before = calls.copy()
    assert review_sync.sync_feedback(book, transport, apply=True)["production"] == {"status": "unchanged"}
    assert calls == before and len(seen) == 1


def test_failure_before_durable_intent_changes_no_accepted_state(pipeline, monkeypatch):
    book, _, _, transport, seen, _ = prepared(pipeline, monkeypatch)
    paths = [book.work_dir / "segments/001.md", book.work_dir / "segments/001.checks.json",
             review_apply.default_ledger_path(book)]
    before = [path.read_bytes() for path in paths]
    with interruption(monkeypatch, book, "intent"), pytest.raises(OSError):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert before == [path.read_bytes() for path in paths]
    assert not review_recovery.pending_path(book).exists()
    assert not transport.published and len(seen) == 1
    assert not list((book.work_dir / "segments").glob("*.review_apply.*.before.md"))


@pytest.mark.parametrize("changed_path", ["segments/001.md", "segments/001.checks.json", "editorial/review_apply_ledger.json"])
def test_intervening_human_edit_blocks_recovery_and_publication(pipeline, monkeypatch, changed_path):
    book, _, first, transport, seen, _ = prepared(pipeline, monkeypatch)
    with interruption(monkeypatch, book, "ledger"), pytest.raises(OSError):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    path = book.work_dir / changed_path
    edited = path.read_bytes() + b"\nHuman changed this file.\n"
    path.write_bytes(edited)
    with pytest.raises(RuntimeError, match="conflict"):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    with pytest.raises(RuntimeError, match="conflict"):
        production.run_production(book)
    with pytest.raises(RuntimeError, match="unresolved"):
        production.plan_production(book)
    with pytest.raises(RuntimeError, match="unresolved"):
        publication.snapshot_revision(book, text_revision=first["text_revision"], outputs=[], media_index={}, stage_summary={})
    assert path.read_bytes() == edited and review_recovery.pending_path(book).exists()
    assert len(seen) == 1 and not transport.published


@pytest.mark.parametrize("entry", ["standalone", "run", "pull"])
def test_alternate_entry_points_recover_before_planning_freshness(pipeline, monkeypatch, entry):
    book, calls, first, transport, seen, _ = prepared(pipeline, monkeypatch)
    with interruption(monkeypatch, book, "ledger"), pytest.raises(OSError):
        review_sync.sync_feedback(book, transport, apply=True)
    if entry == "standalone":
        result = review_apply.apply_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
        assert result["pending_feedback"] == 0
    elif entry == "run":
        result = production.run_production(book)
        assert result["success"] and result["review_revision"] != first["review_revision"]
    else:
        result = review_sync.pull_feedback(book, transport)
        assert result["counts"] == {"stale": 1}
    assert not review_recovery.pending_path(book).exists() and len(seen) == 1
    assert len(json.loads(review_apply.default_ledger_path(book).read_text())["entries"]) == 2


def test_review_plan_and_dry_run_refuse_pending_without_mutation(pipeline, monkeypatch):
    book, _, _, transport, seen, _ = prepared(pipeline, monkeypatch)
    with interruption(monkeypatch, book, "draft"), pytest.raises(OSError):
        review_sync.sync_feedback(book, transport, apply=True)
    original = (book.work_dir / "segments/001.md").read_bytes()
    for options in [{"plan_only": True}, {"dry_run": True}]:
        with pytest.raises(RuntimeError, match="unresolved"):
            review_apply.apply_review_feedback(book, edits_path=review_sync.imported_edits_path(book), **options)
    assert (book.work_dir / "segments/001.md").read_bytes() == original and len(seen) == 1


def test_human_edit_during_model_request_is_not_overwritten(pipeline, monkeypatch):
    book, _, _, transport, seen, _ = prepared(pipeline, monkeypatch)
    complete = review_apply.complete
    draft = book.work_dir / "segments/001.md"
    changed = draft.read_bytes() + b"\nA new human paragraph.\n"
    def edit(**kwargs):
        result = complete(**kwargs)
        draft.write_bytes(changed)
        return result
    monkeypatch.setattr(review_apply, "complete", edit)
    with pytest.raises(RuntimeError, match="changed while"):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert draft.read_bytes() == changed
    assert not review_recovery.pending_path(book).exists() and not transport.published


def test_ledger_edit_during_model_request_is_preserved(pipeline, monkeypatch):
    book, _, _, transport, _, prior = prepared(pipeline, monkeypatch)
    complete = review_apply.complete
    ledger = review_apply.default_ledger_path(book)
    original = (book.work_dir / "segments/001.md").read_bytes()
    edited = {**prior, "entries": [*prior["entries"], {"feedback_key": "another-decision"}]}
    def edit(**kwargs):
        result = complete(**kwargs)
        atomic_json(ledger, edited)
        return result
    monkeypatch.setattr(review_apply, "complete", edit)
    with pytest.raises(RuntimeError, match="ledger changed while"):
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert json.loads(ledger.read_text()) == edited
    assert (book.work_dir / "segments/001.md").read_bytes() == original
    assert not review_recovery.pending_path(book).exists() and not transport.published
