"""Packaging failures must never damage source or previously published books."""

from __future__ import annotations

import json
import os
import tarfile
from pathlib import Path

import pytest

from scripts import package_review_artifacts as packaging
from scripts.publish_review_book import _archive_book

from .conftest import BOOK_ID


def _snapshot(root: Path) -> dict:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[relative] = ("link", str(path.readlink()))
        elif path.is_dir():
            snapshot[relative] = ("directory",)
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def package_tree(artifact_tree, monkeypatch):
    root = artifact_tree
    monkeypatch.setattr(packaging, "WORK_DIR", root / "work")
    monkeypatch.setattr(packaging, "BOOKS_DIR", root / "books")
    (root / "books" / BOOK_ID / "source.txt").write_text("Original source.\n")
    book = root / "work" / BOOK_ID
    _write_json(book / "segments" / "001.checks.json", {"status": "drafted"})
    _write_json(book / "segments" / "002.checks.json", {"status": "drafted"})
    (book / "segments" / "001.md").write_text("Private working draft.")
    _write_json(book / "name_lint_report.json", {"findings": []})
    _write_json(book / "editorial" / "review_apply_ledger.json", {"comments": {}})
    # Existing output deliberately differs from the selected package.
    _write_json(root / "deploy" / "artifacts" / "old" / "plan.json", {"old": True})
    _write_json(root / "deploy" / "books" / "old" / "metadata.json", {"old": True})
    return root


def test_package_preserves_input_and_replaces_both_slim_outputs(package_tree):
    root = package_tree
    before_work = _snapshot(root / "work")
    before_books = _snapshot(root / "books")
    out = root / "deploy" / "artifacts"
    assert packaging.package([BOOK_ID, BOOK_ID], out) == 0
    assert _snapshot(root / "work") == before_work
    assert _snapshot(root / "books") == before_books
    assert not (out / "old").exists()
    assert not (root / "deploy" / "books" / "old").exists()
    assert (out / BOOK_ID / "alignments" / "001.json").is_file()
    assert (out / BOOK_ID / "segments" / "001.checks.json").is_file()
    assert not (out / BOOK_ID / "segments" / "002.checks.json").exists()
    assert not (out / BOOK_ID / "segments" / "001.md").exists()
    assert (out / BOOK_ID / "name_lint_report.json").is_file()
    assert (out / BOOK_ID / "editorial" / "review_apply_ledger.json").is_file()
    assert json.loads((out / BOOK_ID / "plan.json").read_text()) == {
        "book_id": BOOK_ID, "title": "Test Book", "author": "A. Tester",
        "segments": [{"id": "001", "title": "Chapter One"}],
    }
    metadata = root / "deploy" / "books" / BOOK_ID / "metadata.json"
    assert json.loads(metadata.read_text()) == {"title": "Test Book", "author": "A. Tester"}
    assert not list((root / "deploy").glob(".forage-package-*"))


@pytest.mark.parametrize("output", [
    "work", "books", ".", "work/bundle/artifacts", "books/bundle/artifacts",
    "artifacts",  # Its sibling is the original books directory.
])
def test_resolved_input_output_overlap_is_rejected(package_tree, output):
    root = package_tree
    before = _snapshot(root)
    with pytest.raises(ValueError, match="overlaps input"):
        packaging.package([BOOK_ID], root / output)
    assert _snapshot(root) == before


@pytest.mark.parametrize("root_name", ["WORK_DIR", "BOOKS_DIR"])
def test_sibling_books_cannot_be_ancestor_of_input(package_tree, monkeypatch, root_name):
    root = package_tree
    nested_input = root / "deploy" / "books" / "library"
    nested_input.mkdir()
    (nested_input / "source.txt").write_text("Preserve this input.")
    monkeypatch.setattr(packaging, root_name, nested_input)
    before = _snapshot(root)
    with pytest.raises(ValueError, match="overlaps input"):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


@pytest.mark.parametrize("alias", ["output", "parent", "sibling", "input"])
def test_symlink_input_output_alias_is_rejected(package_tree, monkeypatch, alias):
    root = package_tree
    out = root / "alias" / "artifacts"
    if alias == "output":
        out.parent.mkdir()
        out.symlink_to(root / "work", target_is_directory=True)
    elif alias == "parent":
        out.parent.symlink_to(root / "work", target_is_directory=True)
    elif alias == "sibling":
        out.parent.mkdir()
        (out.parent / "books").symlink_to(root / "books", target_is_directory=True)
    else:
        (root / "work-alias").symlink_to(root / "work", target_is_directory=True)
        monkeypatch.setattr(packaging, "WORK_DIR", root / "work-alias")
        out = root / "work"
    before = _snapshot(root)
    with pytest.raises(ValueError, match="overlaps input"):
        packaging.package([BOOK_ID], out)
    assert _snapshot(root) == before


def test_output_directories_cannot_be_the_same(package_tree):
    root = package_tree
    before = _snapshot(root)
    with pytest.raises(ValueError, match="must be separate"):
        packaging.package([BOOK_ID], root / "deploy" / "books")
    assert _snapshot(root) == before


@pytest.mark.parametrize("book_id", [".", "..", "", "../testbook", "/tmp/testbook",
                                    "testbook/nested", "a\\b", "a" * 65])
def test_invalid_book_selection_preserves_inputs_and_outputs(package_tree, book_id):
    root = package_tree
    before = _snapshot(root)
    with pytest.raises(ValueError, match="invalid artifact id"):
        packaging.package([BOOK_ID, book_id], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


def test_missing_explicit_book_preserves_prior_package(package_tree):
    root = package_tree
    before = _snapshot(root)
    with pytest.raises(FileNotFoundError, match="no alignments"):
        packaging.package([BOOK_ID, "missing"], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


@pytest.mark.parametrize("invalid", ["bad id", "..", "a" * 65])
def test_invalid_alignment_id_preserves_prior_package(package_tree, invalid):
    root = package_tree
    alignments = root / "work" / BOOK_ID / "alignments"
    (alignments / "001.json").rename(alignments / f"{invalid}.json")
    before = _snapshot(root)
    with pytest.raises(ValueError, match="invalid artifact id"):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


@pytest.mark.parametrize("segments", [{}, [None], [{"id": "../outside"}]])
def test_invalid_plan_shape_preserves_prior_package(package_tree, segments):
    root = package_tree
    _write_json(root / "work" / BOOK_ID / "plan.json", {"segments": segments})
    before = _snapshot(root)
    with pytest.raises(ValueError):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


def test_empty_discovery_preserves_prior_package(package_tree):
    root = package_tree
    (root / "work" / BOOK_ID / "alignments" / "001.json").unlink()
    before = _snapshot(root)
    assert packaging.package([], root / "deploy" / "artifacts") == 1
    assert _snapshot(root) == before


@pytest.mark.parametrize("relative", [
    f"work/{BOOK_ID}/alignments/001.json",
    f"work/{BOOK_ID}/segments/001.checks.json",
    f"work/{BOOK_ID}/plan.json",
    f"work/{BOOK_ID}/name_lint_report.json",
    f"work/{BOOK_ID}/editorial/review_apply_ledger.json",
    f"books/{BOOK_ID}/metadata.json",
])
@pytest.mark.parametrize("content", ["{bad json", "[]"])
def test_malformed_selected_json_preserves_prior_package(package_tree, relative, content):
    root = package_tree
    (root / relative).write_text(content)
    before = _snapshot(root)
    with pytest.raises(ValueError):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


@pytest.mark.parametrize("relative", [
    f"work/{BOOK_ID}",
    f"work/{BOOK_ID}/alignments",
    f"work/{BOOK_ID}/alignments/001.json",
    f"work/{BOOK_ID}/segments/001.checks.json",
    f"work/{BOOK_ID}/plan.json",
    f"work/{BOOK_ID}/editorial/review_apply_ledger.json",
    f"books/{BOOK_ID}",
    f"books/{BOOK_ID}/metadata.json",
])
def test_selected_input_symlink_cannot_escape_its_root(package_tree, relative):
    root = package_tree
    selected = root / relative
    external = root / "external"
    selected.rename(external)
    selected.symlink_to(external, target_is_directory=external.is_dir())
    before = _snapshot(root)
    with pytest.raises(ValueError, match="input escapes"):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert _snapshot(root) == before


def test_copy_failure_preserves_inputs_and_outputs(package_tree, monkeypatch):
    root = package_tree
    before = _snapshot(root)
    original = packaging.shutil.copy2
    copied = 0

    def fail_second_copy(source, destination):
        nonlocal copied
        copied += 1
        if copied == 2:
            raise OSError("injected copy failure")
        return original(source, destination)

    monkeypatch.setattr(packaging.shutil, "copy2", fail_second_copy)
    with pytest.raises(OSError, match="injected copy failure"):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert copied == 2
    assert _snapshot(root) == before


@pytest.mark.parametrize("failure_at", [1, 2, 3, 4])
def test_publication_failure_rolls_back_both_outputs(package_tree, monkeypatch, failure_at):
    root = package_tree
    before = _snapshot(root)
    original = os.replace
    replacements = 0

    def fail_once(source, destination):
        nonlocal replacements
        replacements += 1
        if replacements == failure_at:
            # The fourth rename is the second replacement, after the first
            # replacement is already live and both old outputs are backed up.
            if failure_at == 4:
                assert (root / "deploy" / "artifacts" / BOOK_ID).is_dir()
                assert not (root / "deploy" / "books").exists()
            raise OSError("injected publication failure")
        return original(source, destination)

    monkeypatch.setattr(packaging.os, "replace", fail_once)
    with pytest.raises(OSError, match="injected publication failure"):
        packaging.package([BOOK_ID], root / "deploy" / "artifacts")
    assert replacements >= failure_at
    assert _snapshot(root) == before


def test_second_publication_failure_restores_absent_output(package_tree, monkeypatch):
    root = package_tree
    out = root / "fresh" / "artifacts"
    out.parent.mkdir()
    before = _snapshot(root)
    original = os.replace

    def fail_second(source, destination):
        if Path(source).name == "books" and Path(destination) == out.parent / "books":
            assert (out / BOOK_ID).is_dir()
            raise OSError("injected second publication failure")
        return original(source, destination)

    monkeypatch.setattr(packaging.os, "replace", fail_second)
    with pytest.raises(OSError, match="injected second publication failure"):
        packaging.package([BOOK_ID], out)
    assert _snapshot(root) == before


def test_failed_rollback_keeps_original_backups_for_recovery(package_tree, monkeypatch):
    root = package_tree
    out = root / "deploy" / "artifacts"
    before_artifacts = _snapshot(out)
    before_metadata = _snapshot(out.parent / "books")
    before_work = _snapshot(root / "work")
    before_books = _snapshot(root / "books")
    original = os.replace

    def fail_publish_and_restore(source, destination):
        source = Path(source)
        destination = Path(destination)
        if (source.name == "books" and destination == out.parent / "books"
                or source.name.startswith("previous-")):
            raise OSError("injected rename failure")
        return original(source, destination)

    monkeypatch.setattr(packaging.os, "replace", fail_publish_and_restore)
    with pytest.raises(RuntimeError, match="recover previous output"):
        packaging.package([BOOK_ID], out)
    stages = list(out.parent.glob(".forage-package-*"))
    assert len(stages) == 1
    assert _snapshot(stages[0] / "previous-artifacts") == before_artifacts
    assert _snapshot(stages[0] / "previous-books") == before_metadata
    assert _snapshot(root / "work") == before_work
    assert _snapshot(root / "books") == before_books


def test_package_without_metadata_still_creates_docker_books_directory(package_tree):
    root = package_tree
    (root / "books" / BOOK_ID / "metadata.json").unlink()
    assert packaging.package([BOOK_ID], root / "deploy" / "artifacts") == 0
    assert (root / "deploy" / "books").is_dir()
    assert not list((root / "deploy" / "books").iterdir())


def test_default_selection_excludes_internal_variants(package_tree):
    root = package_tree
    internal = root / "work" / "testbook_nontrial_draft" / "alignments"
    _write_json(internal / "001.json", {"mapping": []})
    assert packaging.package([], root / "deploy" / "artifacts") == 0
    assert {p.name for p in (root / "deploy" / "artifacts").iterdir()} == {BOOK_ID}


def test_one_book_archive_keeps_existing_layout(package_tree):
    root = package_tree
    before_work = _snapshot(root / "work")
    before_books = _snapshot(root / "books")
    archive = root / "book.tgz"
    result = _archive_book(BOOK_ID, archive)
    assert result["chapters"] == 1
    assert result["metadata_files"] == 1
    with tarfile.open(archive) as bundle:
        names = set(bundle.getnames())
    assert f"artifacts/{BOOK_ID}/alignments/001.json" in names
    assert f"books/{BOOK_ID}/metadata.json" in names
    assert f"books/{BOOK_ID}/source.txt" not in names
    assert _snapshot(root / "work") == before_work
    assert _snapshot(root / "books") == before_books


@pytest.mark.parametrize("archive", [False, True])
def test_private_pipeline_files_publish_readable_copies(package_tree, archive):
    root = package_tree
    alignment = root / "work" / BOOK_ID / "alignments" / "001.json"
    ledger = root / "work" / BOOK_ID / "editorial" / "review_apply_ledger.json"
    for path in (alignment, ledger):
        path.chmod(0o600)
        path.parent.chmod(0o700)
    if archive:
        bundle_path = root / "book.tgz"
        _archive_book(BOOK_ID, bundle_path)
        with tarfile.open(bundle_path) as bundle:
            for member in bundle.getmembers():
                assert member.mode == (0o755 if member.isdir() else 0o644)
    else:
        output = root / "deploy" / "artifacts"
        assert packaging.package([BOOK_ID], output) == 0
        for public_root in (output, output.parent / "books"):
            for path in [public_root, *public_root.rglob("*")]:
                assert path.stat().st_mode & 0o777 == (0o755 if path.is_dir() else 0o644)
    for path in (alignment, ledger):
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
