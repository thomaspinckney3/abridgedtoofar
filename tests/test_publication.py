"""Local immutable publication proof, using temporary files and no providers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forage.artifacts import Book
from forage.media import target_revision
from forage.production_state import atomic_json, book_lock, digest, inventory, sha256_file
from forage import publication


@pytest.fixture
def publication_input(tmp_path):
    source = tmp_path / "books" / "sample" / "source.txt"
    source.parent.mkdir(parents=True)
    source.write_text("The full source book.")
    root = tmp_path / "work" / "sample"
    root.mkdir(parents=True)
    book = Book("sample", source, {"title": "Sample"}, root)
    (root / "abridgment.txt").write_text("An abridged book.")
    atomic_json(root / "plan.json", {"segments": [{"id": "001"}]})
    atomic_json(root / "alignments" / "001.json", {"draft_paragraphs": ["An abridged book."]})
    revision = digest("accepted text")
    kwargs = {
        "text_revision": revision,
        "outputs": inventory(root, ["abridgment.txt", "plan.json", "alignments/001.json"]),
        "media_index": {"version": 1, "book_id": book.book_id, "text_revision": revision, "targets": []},
        "stage_summary": {
            "status": "complete", "selected_outputs": ["text"],
            "stages": {"assembly": {"status": "complete"}, "alignment": {"status": "complete"}},
            "quality": {"verdict": "hold", "reason": "Operator review needed"},
        },
    }
    return book, kwargs


def _refresh(book, kwargs):
    kwargs["outputs"] = inventory(book.work_dir, [item["path"] for item in kwargs["outputs"]])


def _add_media(book, kwargs, kind):
    path = f"{kind}/001." + ("mp3" if kind == "audio" else "png")
    asset = book.work_dir / path
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"test media bytes")
    target = {
        "id": f"{kind}-001", "kind": kind, "title": "Chapter One",
        "segment_id": "001", "path": path, "sha256": sha256_file(asset),
        "mime_type": "audio/mpeg" if kind == "audio" else "image/png",
        "text_revision": kwargs["text_revision"],
    }
    if kind == "audio":
        target.update(text_path="abridgment.txt", text_sha256=sha256_file(book.work_dir / "abridgment.txt"), duration_seconds=None)
    else:
        target.update(frame_id="001", page=1)
    target["revision"] = target_revision(target)
    kwargs["media_index"]["targets"].append(target)
    kwargs["outputs"] += inventory(book.work_dir, [path])
    kwargs["stage_summary"]["selected_outputs"].append(kind)
    kwargs["stage_summary"]["stages"][kind] = {"status": "complete"}
    return target


def test_snapshot_is_portable_copy_with_verified_identity(publication_input):
    book, kwargs = publication_input
    audio = _add_media(book, kwargs, "audio")
    graphic = _add_media(book, kwargs, "graphic")
    result = publication.snapshot_revision(book, **kwargs)
    root = Path(result["path"])
    assert root == book.work_dir / "publications" / result["revision"]
    assert publication.verify_revision(book, result["revision"])["revision"] == result["revision"]
    assert result["release_current"] is None
    stored = json.loads((root / "media_manifest.json").read_text())
    assert stored == kwargs["media_index"]
    assert stored["targets"][0]["duration_seconds"] is None
    for target in (audio, graphic):
        assert sha256_file(root / target["path"]) == target["sha256"]
    (book.work_dir / "abridgment.txt").write_text("A human edit.")
    assert (root / "abridgment.txt").read_text() == "An abridged book."
    publication.verify_revision(book, result["revision"])


def test_repeat_content_reuses_revision_and_does_not_append_history(publication_input):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    pointer = (book.work_dir / "review_current.json").read_bytes()
    kwargs["stage_summary"]["stages"]["assembly"].update(status="reused", completed_at="tomorrow", duration_seconds=8)
    kwargs["stage_summary"]["created_at"] = "later"
    kwargs["outputs"].reverse()
    second = publication.snapshot_revision(book, **kwargs)
    assert first["revision"] == second["revision"]
    assert first["created_at"] == second["created_at"]
    assert (book.work_dir / "review_current.json").read_bytes() == pointer
    assert len(second["review_current"]["history"]) == 1


def test_release_is_explicit_and_independent_of_later_review(publication_input):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    assert not (book.work_dir / "release_current.json").exists()
    release = publication.promote_release(book, first["revision"])
    assert release["stage_summary"]["quality"]["verdict"] == "hold"
    old_release = (book.work_dir / "release_current.json").read_bytes()
    (book.work_dir / "abridgment.txt").write_text("The revised book.")
    _refresh(book, kwargs)
    kwargs["text_revision"] = kwargs["media_index"]["text_revision"] = digest("new accepted text")
    second = publication.snapshot_revision(book, **kwargs)
    assert second["revision"] != first["revision"]
    assert second["release_current"]["revision"] == first["revision"]
    assert (book.work_dir / "release_current.json").read_bytes() == old_release
    assert len(second["review_current"]["history"]) == 2
    review_pointer = (book.work_dir / "review_current.json").read_bytes()
    released = publication.promote_release(book, second["revision"])
    assert [item["revision"] for item in released["release_current"]["history"]] == [first["revision"], second["revision"]]
    assert (book.work_dir / "review_current.json").read_bytes() == review_pointer
    publication.promote_release(book, second["revision"])
    assert len(json.loads((book.work_dir / "release_current.json").read_text())["history"]) == 2


def test_adding_media_retains_text_revision_but_changes_publication(publication_input):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    _add_media(book, kwargs, "audio")
    second = publication.snapshot_revision(book, **kwargs)
    assert second["text_revision"] == first["text_revision"]
    assert second["revision"] != first["revision"]
    assert second["selected_outputs"] == ["audio", "text"]


@pytest.mark.parametrize("status", ["pending", "running", "failed", "waiting-review", "skipped", None])
def test_incomplete_stages_do_not_create_snapshot(publication_input, status):
    book, kwargs = publication_input
    kwargs["stage_summary"]["stages"]["alignment"]["status"] = status
    with pytest.raises(ValueError, match="not complete"):
        publication.snapshot_revision(book, **kwargs)
    assert not (book.work_dir / "review_current.json").exists()
    assert not (book.work_dir / "publications").exists()


@pytest.mark.parametrize("change", ["overall", "missing-stage", "no-stages", "missing-text", "unknown-output", "duplicate-output"])
def test_invalid_completion_summary_is_rejected(publication_input, change):
    book, kwargs = publication_input
    summary = kwargs["stage_summary"]
    if change == "overall":
        summary["status"] = "failed"
    elif change == "missing-stage":
        del summary["stages"]["alignment"]
    elif change == "no-stages":
        del summary["stages"]
    elif change == "missing-text":
        summary["selected_outputs"] = ["audio"]
    elif change == "unknown-output":
        summary["selected_outputs"].append("video")
    else:
        summary["selected_outputs"].append("text")
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)


@pytest.mark.parametrize("path", ["../outside", "/absolute", "a/../b", "a//b", "./a", "C:/outside", "a\\b", "publications/old/file", ".env", "editorial/reviews.json", "queue.sqlite", "queue.db-wal", ".replay_cache/entry", "credentials.json"])
def test_unsafe_and_private_paths_rejected(publication_input, path):
    book, kwargs = publication_input
    kwargs["outputs"].append({"path": path, "sha256": "a" * 64})
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)
    assert not (book.work_dir / "review_current.json").exists()


def test_resolved_symlink_escape_rejected(publication_input):
    book, kwargs = publication_input
    (book.work_dir / "secret.txt").symlink_to(book.source_path)
    kwargs["outputs"].append({"path": "secret.txt", "sha256": sha256_file(book.source_path)})
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)


def test_internal_symlink_to_private_file_is_rejected(publication_input):
    book, kwargs = publication_input
    (book.work_dir / ".env").write_text("secret")
    (book.work_dir / "innocent.txt").symlink_to(book.work_dir / ".env")
    kwargs["outputs"] += inventory(book.work_dir, ["innocent.txt"])
    with pytest.raises(ValueError, match="private/runtime"):
        publication.snapshot_revision(book, **kwargs)


def test_source_book_within_work_directory_is_rejected(publication_input):
    book, kwargs = publication_input
    source = book.work_dir / "original.txt"
    source.write_text("Original book")
    book.source_path = source
    kwargs["outputs"] += inventory(book.work_dir, ["original.txt"])
    with pytest.raises(ValueError, match="original source"):
        publication.snapshot_revision(book, **kwargs)


def test_hard_link_to_original_book_is_rejected(publication_input):
    book, kwargs = publication_input
    (book.work_dir / "original.txt").hardlink_to(book.source_path)
    kwargs["outputs"] += inventory(book.work_dir, ["original.txt"])
    with pytest.raises(ValueError, match="original source"):
        publication.snapshot_revision(book, **kwargs)


@pytest.mark.parametrize("missing", ["plan.json", "alignments/001.json"])
def test_review_inventory_requires_plan_and_alignments(publication_input, missing):
    book, kwargs = publication_input
    kwargs["outputs"] = [item for item in kwargs["outputs"] if item["path"] != missing]
    with pytest.raises(ValueError, match="plan and paragraph alignments"):
        publication.snapshot_revision(book, **kwargs)


def test_empty_assembled_text_is_not_a_complete_snapshot(publication_input):
    book, kwargs = publication_input
    (book.work_dir / "abridgment.txt").write_text("  \n")
    _refresh(book, kwargs)
    with pytest.raises(ValueError, match="cannot be empty"):
        publication.snapshot_revision(book, **kwargs)


@pytest.mark.parametrize("change", ["missing", "changed", "duplicate", "no-text"])
def test_missing_changed_or_invalid_inventory_is_rejected(publication_input, change):
    book, kwargs = publication_input
    if change == "missing":
        (book.work_dir / "abridgment.txt").unlink()
    elif change == "changed":
        (book.work_dir / "abridgment.txt").write_text("Changed content")
    elif change == "duplicate":
        kwargs["outputs"].append(dict(kwargs["outputs"][0]))
    else:
        kwargs["outputs"] = [item for item in kwargs["outputs"] if item["path"] != "abridgment.txt"]
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)


@pytest.mark.parametrize("change", ["book", "revision", "target-missing", "text-missing", "not-selected", "selected-empty", "target-corrupt"])
def test_media_index_must_match_complete_selected_inventory(publication_input, change):
    book, kwargs = publication_input
    target = _add_media(book, kwargs, "audio")
    if change == "book":
        kwargs["media_index"]["book_id"] = "wrong"
    elif change == "revision":
        kwargs["media_index"]["text_revision"] = digest("wrong")
    elif change == "target-missing":
        kwargs["outputs"] = [item for item in kwargs["outputs"] if item["path"] != target["path"]]
    elif change == "text-missing":
        (book.work_dir / "narration.txt").write_text("Narration")
        target.update(text_path="narration.txt", text_sha256=sha256_file(book.work_dir / "narration.txt"))
        target["revision"] = target_revision(target)
    elif change == "not-selected":
        kwargs["stage_summary"]["selected_outputs"].remove("audio")
    elif change == "selected-empty":
        kwargs["media_index"]["targets"] = []
    else:
        target["sha256"] = "b" * 64
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)


def test_existing_media_manifest_must_match_supplied_index(publication_input):
    book, kwargs = publication_input
    atomic_json(book.work_dir / "media_manifest.json", {**kwargs["media_index"], "extra": "stale"})
    kwargs["outputs"] += inventory(book.work_dir, ["media_manifest.json"])
    with pytest.raises(ValueError, match="differs"):
        publication.snapshot_revision(book, **kwargs)
    atomic_json(book.work_dir / "media_manifest.json", kwargs["media_index"])
    _refresh(book, kwargs)
    result = publication.snapshot_revision(book, **kwargs)
    assert [item["path"] for item in result["outputs"]].count("media_manifest.json") == 1


@pytest.mark.parametrize("change", ["file", "missing", "extra", "symlink", "identity", "book", "summary", "selected", "revision-manifest"])
def test_tampered_snapshot_cannot_replace_release(publication_input, change):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    publication.promote_release(book, first["revision"])
    previous = (book.work_dir / "release_current.json").read_bytes()
    _add_media(book, kwargs, "graphic")
    second = publication.snapshot_revision(book, **kwargs)
    root = Path(second["path"])
    if change == "file":
        (root / "abridgment.txt").write_text("Tampered")
    elif change == "missing":
        (root / "abridgment.txt").unlink()
    elif change == "extra":
        (root / "not-in-inventory.txt").write_text("Extra")
    elif change == "symlink":
        (root / "abridgment.txt").unlink()
        (root / "abridgment.txt").symlink_to(book.work_dir / "abridgment.txt")
    elif change == "revision-manifest":
        (root / "revision.json").write_text("null")
    else:
        record = json.loads((root / "revision.json").read_text())
        if change == "identity":
            record["text_revision"] = "0" * 64
        elif change == "book":
            record["book_id"] = "wrong"
        elif change == "summary":
            record["stage_summary"]["quality"]["verdict"] = "ship"
        else:
            record["selected_outputs"] = ["text"]
        atomic_json(root / "revision.json", record)
    with pytest.raises(ValueError):
        publication.promote_release(book, second["revision"])
    assert (book.work_dir / "release_current.json").read_bytes() == previous


def test_reuse_detects_tampered_revision_without_overwriting_it(publication_input):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    path = Path(first["path"]) / "abridgment.txt"
    path.write_text("Damaged snapshot")
    previous = (book.work_dir / "review_current.json").read_bytes()
    with pytest.raises(ValueError):
        publication.snapshot_revision(book, **kwargs)
    assert path.read_text() == "Damaged snapshot"
    assert (book.work_dir / "review_current.json").read_bytes() == previous


@pytest.mark.parametrize("revision", ["../unsafe", "x" * 64, "0" * 64, "", None])
def test_missing_or_unsafe_release_does_not_create_pointer(publication_input, revision):
    book, _ = publication_input
    with pytest.raises(ValueError):
        publication.promote_release(book, revision)
    assert not (book.work_dir / "release_current.json").exists()


def test_copy_failure_preserves_old_review_and_cleans_staging(publication_input, monkeypatch):
    book, kwargs = publication_input
    publication.snapshot_revision(book, **kwargs)
    previous = (book.work_dir / "review_current.json").read_bytes()
    (book.work_dir / "abridgment.txt").write_text("Changed book")
    _refresh(book, kwargs)
    def fail_copy(*args, **kwargs):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(publication.shutil, "copyfile", fail_copy)
    with pytest.raises(OSError, match="disk failure"):
        publication.snapshot_revision(book, **kwargs)
    assert (book.work_dir / "review_current.json").read_bytes() == previous
    assert not list((book.work_dir / "publications").glob(".staging-*"))


def test_changed_source_during_copy_is_not_exposed(publication_input, monkeypatch):
    book, kwargs = publication_input
    original_copy = publication.shutil.copyfile
    def change_copy(source, target):
        result = original_copy(source, target)
        if target.name == "abridgment.txt":
            target.write_text("Content changed during copy")
        return result
    monkeypatch.setattr(publication.shutil, "copyfile", change_copy)
    with pytest.raises(ValueError, match="changed while copying"):
        publication.snapshot_revision(book, **kwargs)
    assert list((book.work_dir / "publications").iterdir()) == []


@pytest.mark.parametrize("channel", ["review", "release"])
def test_pointer_write_failure_preserves_pointer_and_history(publication_input, monkeypatch, channel):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    publication.promote_release(book, first["revision"])
    pointer = book.work_dir / f"{channel}_current.json"
    previous = pointer.read_bytes()
    (book.work_dir / "abridgment.txt").write_text("A later book")
    _refresh(book, kwargs)
    if channel == "release":
        second = publication.snapshot_revision(book, **kwargs)
    original_write = publication.atomic_json
    def fail_pointer(path, value):
        if path == pointer:
            raise OSError("pointer write failed")
        original_write(path, value)
    monkeypatch.setattr(publication, "atomic_json", fail_pointer)
    with pytest.raises(OSError, match="pointer write failed"):
        if channel == "review":
            publication.snapshot_revision(book, **kwargs)
        else:
            publication.promote_release(book, second["revision"])
    assert pointer.read_bytes() == previous


def test_per_book_lock_and_runner_held_lock(publication_input):
    book, kwargs = publication_input
    with book_lock(book):
        with pytest.raises(RuntimeError, match="already running"):
            publication.snapshot_revision(book, **kwargs)
        snapshot = publication.snapshot_revision(book, lock_held=True, **kwargs)
        with pytest.raises(RuntimeError, match="already running"):
            publication.promote_release(book, snapshot["revision"])
    publication.promote_release(book, snapshot["revision"])


def test_failed_branch_leaves_existing_valid_review_untouched(publication_input):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    _add_media(book, kwargs, "audio")
    _add_media(book, kwargs, "graphic")
    kwargs["stage_summary"]["stages"]["graphic"] = {"status": "failed", "error": "provider timeout"}
    with pytest.raises(ValueError, match="graphic.*not complete"):
        publication.snapshot_revision(book, **kwargs)
    current = json.loads((book.work_dir / "review_current.json").read_text())
    assert current["revision"] == first["revision"]
    assert (book.work_dir / "audio/001.mp3").read_bytes() == b"test media bytes"


@pytest.mark.parametrize("change", ["path", "history", "text_revision", "selected_outputs", "null"])
def test_corrupt_pointer_is_not_silently_replaced(publication_input, change):
    book, kwargs = publication_input
    first = publication.snapshot_revision(book, **kwargs)
    publication.promote_release(book, first["revision"])
    path = book.work_dir / "release_current.json"
    pointer = json.loads(path.read_text())
    if change == "path":
        pointer["path"] = "elsewhere"
    elif change == "history":
        pointer["history"] = []
    elif change == "text_revision":
        pointer["text_revision"] = "a" * 64
    elif change == "selected_outputs":
        pointer["selected_outputs"] = ["unknown"]
    else:
        pointer = None
    atomic_json(path, pointer)
    corrupt = path.read_bytes()
    with pytest.raises(ValueError):
        publication.promote_release(book, first["revision"])
    assert path.read_bytes() == corrupt


@pytest.mark.parametrize("location", ["publications", "review_current.json", "release_current.json"])
def test_publication_storage_and_pointers_cannot_be_symlinks(publication_input, location):
    book, kwargs = publication_input
    if location == "publications":
        target = book.work_dir / "elsewhere"
        target.mkdir()
    else:
        target = book.work_dir / "plan.json"
    (book.work_dir / location).symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        publication.snapshot_revision(book, **kwargs)
