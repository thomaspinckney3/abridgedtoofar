"""Offline narration provenance, resume, and replacement safety checks."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from forage import audiobook
from forage.artifacts import Book


@pytest.fixture
def narration(tmp_path, monkeypatch):
    source_dir = tmp_path / "books" / "fixture"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "source.txt"
    source_path.write_text("Original book.")
    source = source_dir / "abridgment.txt"
    source.write_text("First narrated passage.")
    book = Book("fixture", source_path, {}, tmp_path / "work" / "fixture")
    state = SimpleNamespace(book=book, source=source, calls=[], fail=False,
                            empty=False, combines=[])

    def fake_tts(_self, **request):
        state.calls.append(request)
        if state.fail:
            raise audiobook.AudiobookError("fixture synthesis failure")
        return (b"" if state.empty else f"audio-{len(state.calls)}".encode(),
                {"request_id": f"request-{len(state.calls)}", "character_cost": "9"})

    def no_network(*args, **kwargs):
        raise AssertionError("live network calls are forbidden in this test")

    def fake_combine(paths, output_path, **kwargs):
        state.combines.append(list(paths))
        output_path.write_bytes(b"|".join(p.read_bytes() for p in paths))
        return output_path, None

    monkeypatch.setenv("ELEVENLABS_API_KEY", "offline-fixture")
    monkeypatch.setattr(audiobook.ElevenLabsClient, "text_to_speech", fake_tts)
    monkeypatch.setattr(audiobook.urllib.request, "urlopen", no_network)
    state.fake_combine = fake_combine

    def run(**kwargs):
        settings = {"voice_id": "fixture-voice", "combine": False, **kwargs}
        return audiobook.generate_audiobook(book, **settings)

    state.run = run
    return state


def manifest(result):
    return json.loads(result.manifest_path.read_text())


def three_chunks(narration, *, last="C", middle="B", first="A"):
    narration.source.write_text("\n\n".join(letter * 700 for letter in (first, middle, last)))


def test_success_and_unchanged_stitched_reuse(narration):
    three_chunks(narration)
    first = narration.run(max_chars=1000)
    assert first.generated_count == 3
    entries = manifest(first)["chunks"]
    for entry in entries:
        audio = Path(entry["audio_path"]).read_bytes()
        assert entry["audio_sha256"] == hashlib.sha256(audio).hexdigest()
        assert entry["audio_size"] == len(audio)
        assert entry["request_sha256"]
    assert narration.calls[1]["previous_request_ids"] == ["request-1"]
    assert narration.calls[1]["previous_text"] is None
    second = narration.run(max_chars=1000)
    assert (second.generated_count, second.skipped_count, second.error_count) == (0, 3, 0)
    assert len(narration.calls) == 3
    assert [e["request_sha256"] for e in manifest(second)["chunks"]] == [
        e["request_sha256"] for e in entries
    ]


@pytest.mark.parametrize("settings", [
    {"voice_id": "different-voice"},
    {"model_id": "different-model"},
    {"output_format": "mp3_22050_32"},
    {"output_format": "pcm_44100"},
    {"voice_settings": {"speed": 1.2, "stability": 0.4}},
    {"seed": 42},
    {"language_code": "fr"},
    {"apply_text_normalization": "off"},
    {"enable_logging": False},
    {"stitch": False},
    {"context_chars": 200},
])
def test_changed_synthesis_settings_regenerate(narration, settings):
    first = narration.run()
    old = manifest(first)["chunks"][0]
    second = narration.run(**settings)
    entry = manifest(second)["chunks"][0]
    assert (second.generated_count, second.skipped_count) == (1, 0)
    assert entry["request_sha256"] != old["request_sha256"]
    assert entry["audio_sha256"] != old["audio_sha256"]
    third = narration.run(**settings)
    assert (third.generated_count, third.skipped_count) == (0, 1)


@pytest.mark.parametrize("logging", [True, False])
def test_neighbor_change_invalidates_affected_stitched_chunks(narration, logging):
    three_chunks(narration)
    narration.run(max_chars=1000, enable_logging=logging)
    three_chunks(narration, last="D")
    result = narration.run(max_chars=1000, enable_logging=logging)
    assert (result.generated_count, result.skipped_count) == (2, 1)
    if logging:
        assert narration.calls[-1]["previous_request_ids"] == ["request-1", "request-4"]
    else:
        assert narration.calls[-1]["previous_request_ids"] is None
        assert narration.calls[-1]["previous_text"] == "B" * 700


def test_unstitched_neighbor_change_does_not_invalidate_other_chunks(narration):
    three_chunks(narration)
    narration.run(max_chars=1000, stitch=False)
    three_chunks(narration, middle="D")
    result = narration.run(max_chars=1000, stitch=False)
    assert (result.generated_count, result.skipped_count) == (1, 2)


@pytest.mark.parametrize("damage", ["missing", "empty", "tampered", "missing-sidecar", "bad-sidecar"])
def test_invalid_output_never_reused(narration, damage):
    first = narration.run()
    entry = manifest(first)["chunks"][0]
    audio = Path(entry["audio_path"])
    sidecar = Path(entry["text_path"])
    if damage == "missing":
        audio.unlink()
    elif damage == "empty":
        audio.write_bytes(b"")
    elif damage == "tampered":
        audio.write_bytes(b"bad-001")  # Same length still requires the byte hash.
    elif damage == "missing-sidecar":
        sidecar.unlink()
    else:
        sidecar.write_text("Unrelated text.")
    second = narration.run()
    assert (second.generated_count, second.skipped_count) == (1, 0)


@pytest.mark.parametrize("damage", [
    "missing", "invalid-json", "list-root", "bad-chunks", "bad-entry",
    "legacy", "missing-hash", "error", "planned", "dry-run", "recorded-error",
])
def test_invalid_provenance_never_reused(narration, damage):
    first = narration.run()
    data = manifest(first)
    if damage == "missing":
        first.manifest_path.unlink()
    elif damage == "invalid-json":
        first.manifest_path.write_text("{")
    else:
        if damage == "list-root":
            data = []
        elif damage == "bad-chunks":
            data["chunks"] = None
        elif damage == "bad-entry":
            data["chunks"] = [None]
        elif damage == "legacy":
            del data["version"]
        elif damage == "missing-hash":
            del data["chunks"][0]["request_sha256"]
        elif damage == "dry-run":
            data["dry_run"] = True
        elif damage == "recorded-error":
            data["chunks"][0]["error"] = "prior generation failed"
        else:
            data["chunks"][0]["status"] = damage
        first.manifest_path.write_text(json.dumps(data))
    second = narration.run()
    assert (second.generated_count, second.skipped_count) == (1, 0)


def test_dry_run_preserves_successful_manifest_sidecars_and_audio(narration, monkeypatch):
    monkeypatch.setattr(audiobook, "combine_audio_chunks", narration.fake_combine)
    first = narration.run(combine=True)
    original = {p: p.read_bytes() for p in first.output_dir.rglob("*") if p.is_file()}
    published = first.published_audio_path.read_bytes()
    narration.source.write_text("Completely revised text.")
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    preview = narration.run(dry_run=True, voice_id=None, seed=7, combine=True)
    assert preview.manifest_path == first.output_dir / "preview" / "audiobook_manifest.json"
    assert (preview.generated_count, preview.planned_count) == (0, 1)
    assert len(narration.calls) == 1
    assert len(narration.combines) == 1
    assert first.published_audio_path.read_bytes() == published
    for path, content in original.items():
        assert path.read_bytes() == content
    entry = manifest(preview)["chunks"][0]
    assert Path(entry["text_path"]).read_text() == "Completely revised text.\n"
    assert entry["audio_path"] is None
    assert entry["audio_sha256"] is None


def test_fresh_dry_run_cannot_produce_success_provenance(narration, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    result = narration.run(dry_run=True, voice_id=None)
    assert not (result.output_dir / "audiobook_manifest.json").exists()
    assert not (result.output_dir / "audio").exists()
    assert not narration.calls
    assert manifest(result)["chunks"][0]["status"] == "planned"


@pytest.mark.parametrize("failure", ["exception", "empty"])
def test_failed_replacement_preserves_old_bytes_without_claiming_success(narration, monkeypatch, failure):
    monkeypatch.setattr(audiobook, "combine_audio_chunks", narration.fake_combine)
    first = narration.run(combine=True)
    old = manifest(first)["chunks"][0]
    paths = [Path(old["audio_path"]), Path(old["text_path"]),
             first.combined_audio_path, first.published_audio_path]
    original = {p: p.read_bytes() for p in paths}
    narration.source.write_text("Revised text requiring new narration.")
    narration.fail = failure == "exception"
    narration.empty = failure == "empty"
    second = narration.run(combine=True)
    assert (second.generated_count, second.error_count) == (0, 1)
    entry = manifest(second)["chunks"][0]
    assert entry["status"] == "error"
    assert entry["audio_path"] is None
    assert entry["text_path"] is None
    assert entry["audio_sha256"] is None
    assert entry["request_id"] is None
    assert len(narration.combines) == 1
    for path, content in original.items():
        assert path.read_bytes() == content
    narration.fail = narration.empty = False
    third = narration.run()
    assert (third.generated_count, third.skipped_count) == (1, 0)


def test_replacement_rolls_back_audio_if_sidecar_replace_fails(narration, monkeypatch):
    first = narration.run()
    old = manifest(first)["chunks"][0]
    audio_path = Path(old["audio_path"])
    text_path = Path(old["text_path"])
    audio, text = audio_path.read_bytes(), text_path.read_bytes()
    replace = Path.replace

    def fail_sidecar(self, target):
        if self.name == "1.new" and target == text_path:
            raise OSError("fixture sidecar replacement failure")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_sidecar)
    narration.source.write_text("Changed narration.")
    second = narration.run()
    assert second.error_count == 1
    assert audio_path.read_bytes() == audio
    assert text_path.read_bytes() == text
    assert manifest(second)["chunks"][0]["audio_sha256"] is None


def test_overwrite_failure_cannot_reuse_the_old_success(narration):
    first = narration.run()
    entry = manifest(first)["chunks"][0]
    audio_path = Path(entry["audio_path"])
    audio = audio_path.read_bytes()
    narration.fail = True
    failed = narration.run(overwrite=True)
    assert failed.error_count == 1
    assert audio_path.read_bytes() == audio
    narration.fail = False
    retried = narration.run()
    assert (retried.generated_count, retried.skipped_count) == (1, 0)


def test_failure_does_not_stitch_later_chunk_to_old_request_ids(narration, monkeypatch):
    three_chunks(narration)
    narration.run(max_chars=1000)
    method = audiobook.ElevenLabsClient.text_to_speech

    def fail_middle(self, **request):
        if request["text"] == "B" * 700:
            raise audiobook.AudiobookError("middle chunk failed")
        return method(self, **request)

    monkeypatch.setattr(audiobook.ElevenLabsClient, "text_to_speech", fail_middle)
    result = narration.run(max_chars=1000, overwrite=True)
    assert (result.generated_count, result.error_count) == (2, 1)
    assert narration.calls[-1]["previous_request_ids"] is None
    assert narration.calls[-1]["previous_text"] == "B" * 700


def test_limit_cannot_combine_old_unselected_audio(narration, monkeypatch):
    monkeypatch.setattr(audiobook, "combine_audio_chunks", narration.fake_combine)
    three_chunks(narration)
    first = narration.run(max_chars=1000, combine=True)
    previous = manifest(first)
    old_combined = first.combined_audio_path.read_bytes()
    old_published = first.published_audio_path.read_bytes()
    three_chunks(narration, first="D", middle="E", last="F")
    second = narration.run(max_chars=1000, limit=1, combine=True)
    assert (second.generated_count, second.planned_count) == (1, 2)
    assert second.combined_audio_path is None
    assert second.published_audio_path is None
    assert len(narration.combines) == 1
    assert first.combined_audio_path.read_bytes() == old_combined
    assert first.published_audio_path.read_bytes() == old_published
    for index in (1, 2):
        current = manifest(second)["chunks"][index]
        assert current["status"] == "planned"
        assert current["audio_path"] is None
        assert current["audio_sha256"] is None
        assert Path(previous["chunks"][index]["text_path"]).read_text() == ("B", "C")[index - 1] * 700 + "\n"
    third = narration.run(max_chars=1000, combine=True)
    assert (third.generated_count, third.skipped_count) == (2, 1)
    assert third.combined_audio_path is not None
    assert len(narration.combines) == 2


def test_limit_allows_only_verified_existing_audio(narration, monkeypatch):
    monkeypatch.setattr(audiobook, "combine_audio_chunks", narration.fake_combine)
    three_chunks(narration)
    narration.run(max_chars=1000)
    result = narration.run(max_chars=1000, limit=0, combine=True)
    assert (result.generated_count, result.skipped_count, result.planned_count) == (0, 3, 0)
    assert result.combined_audio_path is not None


def test_failed_ffmpeg_keeps_previous_combined_audio(tmp_path, monkeypatch):
    output = tmp_path / "audiobook.mp3"
    output.write_bytes(b"previous complete audio")
    chunk = tmp_path / "chunk.mp3"
    chunk.write_bytes(b"chunk")
    monkeypatch.setattr(audiobook.shutil, "which", lambda executable: "/fixture/ffmpeg")

    def fail_combine(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial corrupt replacement")
        raise subprocess.CalledProcessError(1, command, stderr="fixture combine failure")

    monkeypatch.setattr(audiobook.subprocess, "run", fail_combine)
    path, error = audiobook.combine_audio_chunks([chunk], output, output_format="mp3_44100_128")
    assert path is None
    assert "fixture combine failure" in error
    assert output.read_bytes() == b"previous complete audio"


@pytest.mark.parametrize("data", [b"combined current audio", b""])
def test_ffmpeg_replaces_combined_audio_only_after_nonempty_success(tmp_path, monkeypatch, data):
    output = tmp_path / "audiobook.mp3"
    output.write_bytes(b"previous complete audio")
    chunk = tmp_path / "chunk.mp3"
    chunk.write_bytes(b"chunk")
    monkeypatch.setattr(audiobook.shutil, "which", lambda executable: "/fixture/ffmpeg")

    def combine(command, **kwargs):
        assert Path(command[-1]) != output
        Path(command[-1]).write_bytes(data)

    monkeypatch.setattr(audiobook.subprocess, "run", combine)
    path, error = audiobook.combine_audio_chunks([chunk], output, output_format="mp3_44100_128")
    if data:
        assert (path, error) == (output, None)
        assert output.read_bytes() == data
    else:
        assert path is None
        assert error == "ffmpeg returned no audio"
        assert output.read_bytes() == b"previous complete audio"


def test_failed_publication_keeps_previous_public_audio(narration, monkeypatch):
    monkeypatch.setattr(audiobook, "combine_audio_chunks", narration.fake_combine)
    first = narration.run(combine=True)
    published = first.published_audio_path.read_bytes()
    replace = Path.replace

    def fail_publish(self, target):
        if target == first.published_audio_path:
            raise OSError("fixture publication failure")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_publish)
    narration.source.write_text("New narration.")
    result = narration.run(combine=True)
    assert result.published_audio_path is None
    assert "fixture publication failure" in result.combine_error
    assert "fixture publication failure" in manifest(result)["combine_error"]
    assert first.published_audio_path.read_bytes() == published


def test_failed_rollback_retains_recoverable_original_audio(narration, monkeypatch):
    first = narration.run()
    old = manifest(first)['chunks'][0]
    audio_path, text_path = Path(old['audio_path']), Path(old['text_path'])
    audio, text = audio_path.read_bytes(), text_path.read_bytes()
    replace = Path.replace

    def fail_sidecar_and_restore(self, target):
        if self.name == '1.new' and target == text_path:
            raise OSError('fixture sidecar replacement failure')
        if self.name == '0.old' and target == audio_path:
            raise OSError('fixture backup restoration failure')
        return replace(self, target)

    monkeypatch.setattr(Path, 'replace', fail_sidecar_and_restore)
    narration.source.write_text('Changed narration.')
    result = narration.run()
    assert result.error_count == 1
    recovery_dirs = list(audio_path.parent.glob('.chunk-*'))
    assert len(recovery_dirs) == 1
    backup = recovery_dirs[0] / '0.old'
    assert backup.read_bytes() == audio
    assert text_path.read_bytes() == text
    entry = manifest(result)['chunks'][0]
    assert entry['status'] == 'error' and entry['audio_path'] is None
    assert 'rollback failed' in entry['error']
    assert str(backup) in entry['error']
    # The actionable path is sufficient to recover the original bytes.
    replace(backup, audio_path)
    assert audio_path.read_bytes() == audio


@pytest.mark.parametrize('failure', ['publish', 'combine_return', 'combine_raise', 'limit'])
def test_cli_reports_failed_combined_output(narration, monkeypatch, failure):
    from typer.testing import CliRunner
    from forage import cli

    monkeypatch.setattr(cli, 'load_book', lambda book_id: narration.book)
    monkeypatch.setattr(audiobook, 'combine_audio_chunks', narration.fake_combine)
    first = narration.run(combine=True)
    old_publication = first.published_audio_path.read_bytes()
    narration.source.write_text('Changed narration.')
    expected = 'fixture publication failure'
    if failure == 'publish':
        replace = Path.replace

        def fail_publish(self, target):
            if target == first.published_audio_path:
                raise OSError(expected)
            return replace(self, target)

        monkeypatch.setattr(Path, 'replace', fail_publish)
    elif failure == 'combine_return':
        expected = 'fixture ffmpeg failure'
        monkeypatch.setattr(audiobook, 'combine_audio_chunks', lambda *a, **kw: (None, expected))
    elif failure == 'combine_raise':
        expected = 'fixture concat write failure'

        def fail_combine(*args, **kwargs):
            raise OSError(expected)

        monkeypatch.setattr(audiobook, 'combine_audio_chunks', fail_combine)
    else:
        expected = 'cannot combine incomplete narration'
    args = ['audiobook', narration.book.book_id, '--voice-id', 'fixture-voice']
    if failure == 'limit':
        args += ['--limit', '0']
    result = CliRunner().invoke(cli.app, args, terminal_width=200)
    assert result.exit_code == 1, result.output
    assert expected in result.output
    assert first.published_audio_path.read_bytes() == old_publication
    data = json.loads(first.manifest_path.read_text())
    assert expected in data['combine_error']
    assert data['published_audio_path'] is None


def test_cli_explicit_separate_chunks_succeeds(narration, monkeypatch):
    from typer.testing import CliRunner
    from forage import cli

    monkeypatch.setattr(cli, 'load_book', lambda book_id: narration.book)

    def unexpected_combine(*args, **kwargs):
        raise AssertionError('combine disabled')

    monkeypatch.setattr(audiobook, 'combine_audio_chunks', unexpected_combine)
    result = CliRunner().invoke(cli.app, [
        'audiobook', narration.book.book_id, '--voice-id', 'fixture-voice', '--no-combine',
    ])
    assert result.exit_code == 0, result.output
    data = json.loads((narration.book.work_dir / 'audiobook' / 'audiobook_manifest.json').read_text())
    assert data['generated_count'] == 1 and data['combine_error'] is None
    assert data['combined_audio_path'] is None and data['published_audio_path'] is None
