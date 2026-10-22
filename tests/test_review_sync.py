import copy
import hashlib
import json

import pytest

from forage import review_apply, review_sync
from forage.llm import LLMResponse
from forage.production_state import atomic_json, book_lock, load_state
from forage.review_transport import ReviewTransport
from tests.test_production_runner import pipeline, run_ok


class FeedTransport:
    def __init__(self, feed, root=None):
        self.feed = feed
        self.published = []
        self.transport = ReviewTransport(local_root=root) if root else None
    def fetch_feedback(self, book_id):
        return copy.deepcopy(self.feed)
    def publish(self, book, revision, channel="review"):
        self.published.append((revision, channel))
        if self.transport:
            return self.transport.publish(book, revision, channel)
        return {"success": True, "revision": revision, "channel": channel}


def comment(book, revision, *, identifier="note-1", scope="paragraph", **updates):
    text = (book.work_dir / "segments/001.md").read_text().strip()
    item = {"id": identifier, "book_id": book.book_id, "scope": scope, "segment_id": "001",
            "target_kind": "text", "target_id": None, "draft_para": 0 if scope == "paragraph" else None,
            "publication_revision": revision, "text_revision": review_sync.current_text_revision(book),
            "target_revision": None, "anchor": hashlib.sha1(" ".join(text.split()).encode()).hexdigest()[:16],
            "original_text": text, "body": "Use wanderer consistently.", "quote": "traveler",
            "kind": "other", "severity": "minor", "author": "Reviewer",
            "created_at": 100.0, "updated_at": 100.0, "status": "open"}
    item.update(updates)
    return item


def feed(book, comments, source="site-1"):
    return {"version": 1, "source_id": source, "book_id": book.book_id,
            "complete": True, "comments": comments}


def test_pull_idempotent_status_edits_deletion_and_sources(pipeline):
    book, _ = pipeline
    result = run_ok(book)
    c = comment(book, result["review_revision"])
    transport = FeedTransport(feed(book, [c]))
    first = review_sync.pull_feedback(book, transport)
    assert first["counts"] == {"eligible": 1}
    original = review_sync.import_path(book).read_bytes()
    assert review_sync.pull_feedback(book, transport)["changed_comments"] == 0
    assert review_sync.import_path(book).read_bytes() == original
    transport.feed["comments"][0].update(body="Updated note", updated_at=101)
    assert review_sync.pull_feedback(book, transport)["changed_comments"] == 1
    transport.feed["comments"][0]["status"] = "resolved"
    assert review_sync.pull_feedback(book, transport)["counts"] == {"inactive": 1}
    transport.feed["comments"] = []
    assert review_sync.pull_feedback(book, transport)["changed_comments"] == 1
    state = json.loads(review_sync.import_path(book).read_text())
    assert state["sources"]["site-1"]["comments"][c["id"]]["removed"]
    assert len(state["sources"]["site-1"]["comments"][c["id"]]["history"]) == 3
    transport.feed = feed(book, [{**c, "status": "open"}], source="site-2")
    assert review_sync.pull_feedback(book, transport)["counts"] == {"inactive": 1, "eligible": 1}
    assert len(json.loads(review_sync.import_path(book).read_text())["sources"]) == 2


def test_sources_preserve_remote_ids_with_distinct_ledger_keys(pipeline):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    for source in ["site-one", "site-two"]:
        review_sync.pull_feedback(book, FeedTransport(feed(book, [comment(book, revision)], source)))
    pending = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))["segments"][0]["pending"]
    assert {p["comment_id"] for p in pending} == {"note-1"}
    assert {p["source_id"] for p in pending} == {"site-one", "site-two"}
    assert len({p["feedback_key"] for p in pending}) == 2


@pytest.mark.parametrize("change", [
    {"complete": False}, {"version": 2}, {"version": True}, {"book_id": "other"},
    {"source_id": ""}, {"comments": {}}, {"comments": [{"id": "broken"}]},
])
def test_invalid_feed_leaves_previous_complete_state(pipeline, change):
    book, _ = pipeline
    result = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, result["review_revision"])]))
    review_sync.pull_feedback(book, transport)
    paths = [review_sync.import_path(book), review_sync.imported_edits_path(book)]
    before = [p.read_bytes() for p in paths]
    transport.feed.update(change)
    with pytest.raises(ValueError):
        review_sync.pull_feedback(book, transport)
    assert before == [p.read_bytes() for p in paths]


def test_interrupted_import_and_duplicate_ids_preserve_complete_state(pipeline, monkeypatch):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    transport = FeedTransport(feed(book, [comment(book, revision)]))
    review_sync.pull_feedback(book, transport)
    before = review_sync.import_path(book).read_bytes()
    projection = review_sync.imported_edits_path(book).read_bytes()
    transport.feed["comments"].append(copy.deepcopy(transport.feed["comments"][0]))
    with pytest.raises(ValueError, match="unique"):
        review_sync.pull_feedback(book, transport)
    transport.feed["comments"].pop()
    transport.feed["comments"][0]["body"] = "New revision of this note."
    def interrupted(*args):
        raise OSError("interrupted before atomic replace")
    monkeypatch.setattr(review_sync, "atomic_json", interrupted)
    with pytest.raises(OSError):
        review_sync.pull_feedback(book, transport)
    assert review_sync.import_path(book).read_bytes() == before
    assert review_sync.imported_edits_path(book).read_bytes() == projection


def test_failed_derived_cache_write_cannot_reactivate_resolved_feedback(pipeline, monkeypatch):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    transport = FeedTransport(feed(book, [comment(book, revision)]))
    review_sync.pull_feedback(book, transport)
    transport.feed["comments"][0]["status"] = "resolved"
    real = review_sync.atomic_json
    def cache_failure(path, value):
        if path == review_sync.imported_edits_path(book):
            raise OSError("cache write interrupted")
        real(path, value)
    monkeypatch.setattr(review_sync, "atomic_json", cache_failure)
    with pytest.raises(OSError):
        review_sync.pull_feedback(book, transport)
    assert review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))["pending_count"] == 0


@pytest.mark.parametrize("change", [
    {"timestamp_seconds": True}, {"timestamp_seconds": float("nan")},
    {"timestamp_seconds": float("inf")}, {"timestamp_seconds": -1},
    {"timestamp_seconds": 10**400}, {"status": {}},
    {"segment_id": "../bad"}, {"draft_para": True}, {"status": "unknown"},
    {"publication_revision": "unknown"}, {"target_kind": "new-kind"},
    {"author": None}, {"body": None}, {"created_at": None},
])
def test_invalid_comment_rejected_without_writes(pipeline, change):
    book, _ = pipeline
    result = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, result["review_revision"], **change)]))
    with pytest.raises(ValueError):
        review_sync.pull_feedback(book, transport)
    assert not review_sync.import_path(book).exists()


def test_import_excludes_media_inactive_stale_orphan_unanchored(pipeline):
    book, _ = pipeline
    result = run_ok(book)
    comments = [comment(book, result["review_revision"], identifier=str(i), **change) for i, change in enumerate([
        {}, {"scope": "audio", "target_kind": "audio", "timestamp_seconds": 2},
        {"scope": "graphic", "target_kind": "graphic"}, {"status": "resolved"},
        {"original_text": "Old prose."}, {"segment_id": "999"}, {"anchor": ""},
        {"publication_revision": None},
    ])]
    report = review_sync.pull_feedback(book, FeedTransport(feed(book, comments)))
    assert report["counts"] == {"eligible": 1, "media": 2, "inactive": 1, "stale": 1, "orphaned": 1, "unanchored": 2}
    overlay = json.loads(review_sync.imported_edits_path(book).read_text())
    assert len(overlay["segments"][0]["comments"]) == 1
    assert len(overlay["media_comments"]) == 2


def test_local_live_bytes_override_cached_alignment_and_remote_flag(pipeline):
    book, _ = pipeline
    result = run_ok(book)
    c = comment(book, result["review_revision"], stale=False)
    transport = FeedTransport(feed(book, [c]))
    review_sync.pull_feedback(book, transport)
    assert review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))["pending_count"] == 1
    path = book.work_dir / "segments/001.md"
    path.write_text(path.read_text().replace("traveler", "wanderer"))
    assert review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))["pending_count"] == 0
    assert review_sync.pull_feedback(book, transport)["counts"] == {"stale": 1}


def test_chapter_and_book_freshness(pipeline):
    book, _ = pipeline
    result = run_ok(book)
    chapter = comment(book, result["review_revision"], scope="chapter")
    whole = comment(book, result["review_revision"], scope="book", segment_id="__book__", original_text="", anchor="")
    assert review_sync.imported_eligibility(book, chapter) == "eligible"
    assert review_sync.imported_eligibility(book, whole) == "eligible"
    path = book.work_dir / "segments/002.md"
    path.write_text(path.read_text().replace("traveler", "wanderer"))
    assert review_sync.imported_eligibility(book, chapter) == "eligible"
    assert review_sync.imported_eligibility(book, whole) == "stale"


def test_removed_chapter_is_orphaned_even_if_old_draft_remains(pipeline):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    c = comment(book, revision)
    plan_path = book.work_dir / "plan.json"
    plan = json.loads(plan_path.read_text())
    plan["segments"][0]["target_word_count"] = 0
    atomic_json(plan_path, plan)
    assert (book.work_dir / "segments/001.md").is_file()
    assert review_sync.imported_eligibility(book, c) == "orphaned"


def test_legacy_index_only_overlay_requires_original_context(pipeline):
    book, _ = pipeline
    run_ok(book)
    overlay = {"segments": [{"segment_id": "001", "comments": [{"id": "local", "note": "Review this", "draft_para": 0}]}]}
    assert review_apply.pending_review_feedback(book, overlay=overlay)["pending_count"] == 0
    assert review_apply.pending_review_feedback(book, overlay=overlay)["blocked_count"] == 1


def fake_apply_provider(book, monkeypatch, seen):
    def complete(**kwargs):
        seen.append(kwargs)
        with pytest.raises(RuntimeError):
            with book_lock(book):
                pass
        plan = review_apply.pending_review_feedback(book, edits_path=review_sync.imported_edits_path(book))
        pending = plan["segments"][0]["pending"]
        old = (book.work_dir / "segments/001.md").read_text()
        response = {"segment_id": "001", "revised_draft": old.replace("traveler", "wanderer"),
                    "decisions": [{"feedback_key": item["feedback_key"], "action": "applied",
                                   "reason": "Consistent naming.", "changed_paragraphs": [0], "target_paragraphs": [0]} for item in pending]}
        return LLMResponse(json.dumps(response), "mock", 0, 0, 0, "stop")
    monkeypatch.setattr(review_apply, "complete", complete)


def test_sync_apply_regenerate_and_repeat_no_reapplication(pipeline, monkeypatch, tmp_path):
    book, calls = pipeline
    first = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]), root=tmp_path / "hosted")
    transport.publish(book, first["review_revision"])
    calls_before = calls.copy()
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    report = review_sync.sync_feedback(book, transport)
    assert report["success"] and len(seen) == 0 and calls == calls_before
    report = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert report["success"], report
    assert report["apply"]["segments_applied"] == 1
    assert calls["draft"] == calls_before["draft"]
    assert calls["repair"] == calls_before["repair"]
    assert len(seen) == 1
    second_revision = report["production"]["review_revision"]
    assert second_revision != first["review_revision"]
    assert transport.published[-1] == (second_revision, "review")
    assert transport.transport.local.status(book.book_id)["release"] is None
    ledger_path = review_apply.default_ledger_path(book)
    ledger = ledger_path.read_bytes()
    before = calls.copy()
    report = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert report["success"] and report["production"]["status"] == "unchanged"
    assert len(seen) == 1 and calls == before
    assert ledger_path.read_bytes() == ledger
    assert len(transport.transport.local.status(book.book_id)["review"]["history"]) == 2


def test_sync_no_republish_after_failed_apply(pipeline, monkeypatch):
    book, _ = pipeline
    first = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]))
    monkeypatch.setattr(review_apply, "apply_review_feedback", lambda *a, **k: {"segments_failed": 1})
    report = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert not report["success"] and report["failed_stage"] == "apply" and not transport.published


@pytest.mark.parametrize("stop_reason", ["length", "max_tokens", "content_filter", "refusal", "error"])
def test_incomplete_apply_response_never_changes_or_publishes(pipeline, monkeypatch, stop_reason):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    transport = FeedTransport(feed(book, [comment(book, revision)]))
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    completed = review_apply.complete
    def truncated(**kwargs):
        good = completed(**kwargs)
        return LLMResponse(good.text, good.model, 0, 0, 0, stop_reason)
    monkeypatch.setattr(review_apply, "complete", truncated)
    original = (book.work_dir / "segments/001.md").read_bytes()
    report = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert not report["success"] and report["failed_stage"] == "apply"
    assert (book.work_dir / "segments/001.md").read_bytes() == original
    assert not review_apply.default_ledger_path(book).exists()
    assert not transport.published


def test_saved_production_settings_and_lock_compose(pipeline, monkeypatch):
    book, _ = pipeline
    first = run_ok(book, audio_voice_id="configured-voice", graphic_style="woodcut")
    state = load_state(book)
    assert state["production_options"]["audio_voice_id"] == "configured-voice"
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]))
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    real = __import__("forage.production", fromlist=["run_production"]).run_production
    def capture(book, options, *, lock_held=False):
        assert lock_held
        assert options["audio_voice_id"] == "configured-voice"
        assert options["graphic_style"] == "woodcut"
        with pytest.raises(RuntimeError):
            with book_lock(book):
                pass
        return real(book, options, lock_held=lock_held)
    monkeypatch.setattr("forage.production.run_production", capture)
    assert review_sync.sync_feedback(book, transport, apply=True)["success"]


def test_retry_failed_descendants_without_reapplying_feedback(pipeline, monkeypatch):
    book, calls = pipeline
    first = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]))
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    from forage import production
    real = production.run_production
    monkeypatch.setattr(production, "run_production", lambda *a, **k: {"success": False})
    result = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert not result["success"] and not transport.published and len(seen) == 1
    monkeypatch.setattr(production, "run_production", real)
    result = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert result["success"] and len(seen) == 1 and len(transport.published) == 1


def test_sync_retries_failed_acknowledged_media_checkpoint(pipeline, monkeypatch, tmp_path):
    from forage import production
    from tests.test_production_runner import _media_mocks
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    options = {"outputs": ["audio"], "audio_voice_id": "fixture", "audio_combine": False,
               "checkpoint_before_media": True}
    waiting = production.run_production(book, options)
    first = run_ok(book, **options, continue_revision=waiting["text_revision"])
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]), tmp_path / "hosted")
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    waiting = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert not waiting["success"] and not transport.published
    current = review_sync.current_text_revision(book)
    real = production.generate_audiobook
    monkeypatch.setattr(production, "generate_audiobook", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline failure")))
    failed = production.run_production(book, {**options, "continue_revision": current})
    assert failed["failed_stage"] == "audio"
    assert load_state(book)["text_revision"] == current
    monkeypatch.setattr(production, "generate_audiobook", real)
    before = calls.copy()
    retry = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert retry["success"] and retry["production"]["stages"]["audio"]["status"] == "complete"
    assert retry["publication"]["revision"] != first["review_revision"]
    assert calls["tts"] > before["tts"] and len(seen) == 1
    assert load_state(book)["text_revision"] == current


@pytest.mark.parametrize("start_audio,requested", [(False, {"outputs": ["text", "audio"]}),
    (True, {"outputs": ["text"]}), (True, {"audio_voice_id": "new-voice"})])
def test_sync_honors_options_without_new_prose(pipeline, monkeypatch, start_audio, requested):
    from tests.test_production_runner import _media_mocks
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    initial = {"outputs": ["audio"] if start_audio else ["text"],
               "audio_voice_id": "fixture", "audio_combine": False}
    first = run_ok(book, **initial)
    before = calls.copy()
    transport = FeedTransport(feed(book, []))
    result = review_sync.sync_feedback(book, transport, apply=True, republish=True, production_options=requested)
    assert result["success"] and result["production"].get("execute")
    assert calls["draft"] == before["draft"]
    saved = load_state(book)["production_options"]
    if "outputs" in requested:
        assert set(saved["outputs"]) == set(requested["outputs"])
    else:
        assert saved["audio_voice_id"] == "new-voice" and calls["tts"] > before["tts"]
    before = calls.copy()
    assert review_sync.sync_feedback(book, transport, apply=True)["production"] == {"status": "unchanged"}
    assert calls == before


def test_sync_invalid_options_fail_before_paid_apply(pipeline, monkeypatch):
    book, _ = pipeline
    revision = run_ok(book)["review_revision"]
    transport = FeedTransport(feed(book, [comment(book, revision)]))
    seen = []
    fake_apply_provider(book, monkeypatch, seen)
    with pytest.raises(ValueError, match="unsupported production options"):
        review_sync.sync_feedback(book, transport, apply=True, production_options={"unsupported": True})
    assert not seen


def test_sync_retries_new_failed_configuration_without_reverting_outputs(pipeline, monkeypatch):
    from forage import production
    from tests.test_production_runner import _media_mocks
    book, calls = pipeline
    _media_mocks(monkeypatch, calls)
    first = run_ok(book)
    transport = FeedTransport(feed(book, []))
    real = production.generate_audiobook
    monkeypatch.setattr(production, "generate_audiobook", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline failure")))
    failed = review_sync.sync_feedback(book, transport, apply=True, republish=True,
        production_options={"outputs": ["audio"], "audio_voice_id": "new-voice", "audio_combine": False})
    assert not failed["success"] and not transport.published
    assert load_state(book)["production_options"]["outputs"] == ["text"]
    assert set(load_state(book)["requested_production_options"]["outputs"]) == {"text", "audio"}
    monkeypatch.setattr(production, "generate_audiobook", real)
    retry = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert retry["success"] and retry["production"]["outputs"] == ["audio", "text"]
    assert retry["publication"]["revision"] != first["review_revision"]
