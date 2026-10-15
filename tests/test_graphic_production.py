"""Offline proofs for the installed graphics pipeline, with real PNG/PDF exports."""
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from forage import graphic
from forage.artifacts import Book
from forage.llm import LLMResponse
from forage.media import validate_media_manifest
from forage.production_state import digest, verify_inventory


@pytest.fixture
def book(tmp_path):
    work = tmp_path / "work" / "novel"
    (work / "segments").mkdir(parents=True)
    source = tmp_path / "source.txt"
    source.write_text("Original unabridged source, deliberately different.")
    plan = {"segments": [{"id": "001", "title": "Arrival", "target_word_count": 100, "diegetic_status": "diegetic"},
                         {"id": "002", "title": "Departure", "target_word_count": 100, "diegetic_status": "diegetic"}]}
    (work / "plan.json").write_text(json.dumps(plan))
    (work / "segments" / "001.md").write_text("Alice arrived at the harbor, holding the old letter.")
    (work / "segments" / "002.md").write_text("At dawn Alice sailed away to search for her brother.")
    return Book("novel", source, {"title": "The Letter"}, work)


@pytest.fixture
def providers(monkeypatch):
    calls = {"storyboard": [], "image": []}
    monkeypatch.delenv("FORAGE_MODEL", raising=False)
    monkeypatch.delenv("FORAGE_GRAPHIC_STORYBOARD_MODEL", raising=False)

    def story(**kwargs):
        calls["storyboard"].append(kwargs)
        frames = [{"id": unit["id"], "image_prompt": f"Illustrate the scene: {unit['text']}",
                   "caption": unit["text"].strip()[:400]} for unit in json.loads(kwargs["prompt"])["units"]]
        return LLMResponse(json.dumps({"frames": frames}), kwargs["model"], 100, 100, 0.1, "end_turn")

    def image(**kwargs):
        calls["image"].append(kwargs)
        return png(kwargs["size"])

    monkeypatch.setattr(graphic, "complete", story)
    monkeypatch.setattr(graphic, "generate_image", image)
    return calls


def png(size="1024x1024"):
    buffer = io.BytesIO()
    image = Image.new("RGB", tuple(map(int, size.split("x"))), "#145181")
    image.save(buffer, format="PNG")
    image.close()
    return buffer.getvalue()


def generate(book, **options):
    return graphic.generate_graphic(book, text_revision=digest("text revision"), options=options)


def test_end_to_end_covers_every_chapter_with_portable_targets(book, providers):
    result = generate(book)
    assert result["metadata"]["chapters"] == ["001", "002"]
    assert len(result["targets"]) == 2
    assert verify_inventory(book.work_dir, result["outputs"])
    index = {"version": 1, "book_id": book.book_id, "text_revision": digest("text revision"), "targets": result["targets"]}
    validate_media_manifest(index, book.work_dir)
    assert (book.work_dir / "graphic/book.pdf").read_bytes().startswith(b"%PDF-1.4")
    assert b"/Count 2" in (book.work_dir / "graphic/book.pdf").read_bytes()
    with Image.open(book.work_dir / result["targets"][0]["path"]) as lettered:
        assert lettered.height > 1024
    assert len(providers["image"]) == 2
    assert "Original unabridged" not in str(providers["storyboard"])
    assert not (book.work_dir / "production_state.json").exists()


def test_unchanged_rerun_has_identical_outputs_and_zero_provider_calls(book, providers):
    first = generate(book)
    second = generate(book)
    assert first == second
    assert len(providers["storyboard"]) == len(providers["image"]) == 2


def test_more_than_1600_words_have_complete_contiguous_coverage(book, providers):
    text = " ".join(f"word{i}" for i in range(1701)) + "\n"
    (book.work_dir / "segments/001.md").write_text(text)
    result = generate(book, graphic_chapters=["001"])
    storyboard = json.loads((book.work_dir / "graphic/storyboard.json").read_text())
    frames = storyboard["frames"]
    assert len(frames) == 10
    assert frames[0]["source_start"] == 0
    assert frames[-1]["source_end"] == len(text)
    assert all(a["source_end"] == b["source_start"] for a, b in zip(frames, frames[1:]))
    assert "word1700" in providers["storyboard"][-1]["prompt"]
    assert len(result["targets"]) == len(providers["image"]) == 10


def test_art_failure_retries_only_failed_and_later_frames(book, providers, monkeypatch):
    image = graphic.generate_image

    def failing(**kwargs):
        if len(providers["image"]) == 1:
            raise RuntimeError("provider unavailable")
        return image(**kwargs)

    monkeypatch.setattr(graphic, "generate_image", failing)
    with pytest.raises(RuntimeError, match="graphic-002-0001.*provider unavailable"):
        generate(book)
    assert len(list((book.work_dir / "graphic/art").glob("*.json"))) == 1
    assert not (book.work_dir / "graphic/graphic_manifest.json").exists()
    monkeypatch.setattr(graphic, "generate_image", image)
    result = generate(book)
    assert len(providers["image"]) == 2
    assert len(providers["storyboard"]) == 2
    assert verify_inventory(book.work_dir, result["outputs"])


def test_storyboard_failure_keeps_completed_batches(book, providers, monkeypatch):
    original = graphic.complete

    def fail_second(**kwargs):
        if len(providers["storyboard"]) == 1:
            raise RuntimeError("storyboard unavailable")
        return original(**kwargs)

    monkeypatch.setattr(graphic, "complete", fail_second)
    with pytest.raises(RuntimeError, match="storyboard unavailable"):
        generate(book)
    assert len(list((book.work_dir / "graphic/storyboards").glob("*.json"))) == 1
    monkeypatch.setattr(graphic, "complete", original)
    generate(book)
    assert len(providers["storyboard"]) == 2


@pytest.mark.parametrize("failure", ["omitted", "reordered", "unknown_id", "empty_caption", "truncated"])
def test_incomplete_storyboard_blocks_art(book, providers, monkeypatch, failure):
    def bad(**kwargs):
        units = json.loads(kwargs["prompt"])["units"]
        frames = [{"id": unit["id"], "image_prompt": "Harbor scene", "caption": "Alice arrives."} for unit in units]
        if failure == "omitted":
            frames = []
        elif failure == "reordered":
            frames.reverse()
        elif failure == "unknown_id":
            frames[0]["id"] = "elsewhere"
        elif failure == "empty_caption":
            frames[0]["caption"] = ""
        return LLMResponse(json.dumps({"frames": frames}), kwargs["model"], 1, 1, 0.1, "length" if failure == "truncated" else "end_turn")

    (book.work_dir / "segments/001.md").write_text(" ".join(["narrative"] * 40))
    monkeypatch.setattr(graphic, "complete", bad)
    with pytest.raises(ValueError, match="storyboard|caption"):
        generate(book, graphic_words_per_frame=20)
    assert providers["image"] == []


@pytest.mark.parametrize("data", [b"not an image", b"", png("32x32")])
def test_invalid_provider_images_are_never_cached_as_success(book, providers, monkeypatch, data):
    monkeypatch.setattr(graphic, "generate_image", lambda **kwargs: data)
    with pytest.raises(RuntimeError, match="graphic frame"):
        generate(book)
    assert not list((book.work_dir / "graphic/art").glob("*.json"))


def test_lettering_settings_and_manual_caption_edit_retain_paid_art(book, providers):
    first = generate(book)
    second = generate(book, graphic_font_size=32)
    assert first["targets"][0]["sha256"] != second["targets"][0]["sha256"]
    path = book.work_dir / "graphic/storyboard.json"
    storyboard = json.loads(path.read_text())
    storyboard["frames"][0]["caption"] = "An editor revised this caption."
    path.write_text(json.dumps(storyboard))
    third = generate(book, graphic_font_size=32)
    assert second["targets"][0]["sha256"] != third["targets"][0]["sha256"]
    assert len(providers["image"]) == len(providers["storyboard"]) == 2


def test_manual_invalid_storyboard_is_reported_without_paid_replacement(book, providers):
    generate(book)
    path = book.work_dir / "graphic/storyboard.json"
    storyboard = json.loads(path.read_text())
    storyboard["frames"].pop()
    path.write_text(json.dumps(storyboard))
    with pytest.raises(ValueError, match="current graphic/storyboard.json is invalid"):
        generate(book)
    assert len(providers["image"]) == len(providers["storyboard"]) == 2


def test_same_length_prose_edit_only_regenerates_affected_chapter(book, providers):
    first = generate(book)
    path = book.work_dir / "segments/001.md"
    path.write_text(path.read_text().replace("Alice", "Edith"))
    second = graphic.generate_graphic(book, text_revision=digest("new text revision"), options={})
    assert len(providers["storyboard"]) == len(providers["image"]) == 3
    assert [t["id"] for t in first["targets"]] == [t["id"] for t in second["targets"]]
    assert first["targets"][1]["path"] == second["targets"][1]["path"]
    assert first["targets"][1]["revision"] != second["targets"][1]["revision"]


def test_removed_selected_frames_never_leak_from_old_directories(book, providers):
    first = generate(book)
    second = generate(book, graphic_chapters=["001"])
    assert len(second["targets"]) == 1
    old = first["targets"][1]["path"]
    assert (book.work_dir / old).exists()
    assert old not in {item["path"] for item in second["outputs"]}
    assert b"/Count 1" in (book.work_dir / "graphic/book.pdf").read_bytes()
    assert len(providers["image"]) == 2


@pytest.mark.parametrize("change", ["model", "size", "style", "image_prompt", "storyboard_prompt"])
def test_request_setting_changes_invalidate_correct_cache(book, providers, monkeypatch, change):
    first = generate(book)
    options = {}
    if change == "model":
        options["graphic_model"] = "gpt-image-1.5"
    elif change == "size":
        options["graphic_size"] = "1536x1024"
    elif change == "style":
        options["graphic_style"] = "Engraving in black ink"
    elif change == "image_prompt":
        monkeypatch.setattr(graphic, "IMAGE_PROMPT", graphic.IMAGE_PROMPT + "Fine outlines.")
    else:
        monkeypatch.setattr(graphic, "STORYBOARD_PROMPT", graphic.STORYBOARD_PROMPT + "Preserve atmosphere.")
    result = generate(book, **options)
    assert verify_inventory(book.work_dir, result["outputs"])
    if change == "storyboard_prompt":
        assert len(providers["storyboard"]) == 4
        # Identical resulting scene prompts do not repay identical art.
        assert len(providers["image"]) == 2
    else:
        assert len(providers["image"]) == 4
    assert first["metadata"]["settings"] != result["metadata"]["settings"]


def test_corrupt_cached_art_is_regenerated_but_corrupt_lettering_is_local(book, providers):
    generate(book)
    manifest = json.loads((book.work_dir / "graphic/graphic_manifest.json").read_text())
    (book.work_dir / manifest["frames"][0]["art"]["path"]).write_bytes(b"corrupt")
    generate(book)
    assert len(providers["image"]) == 3
    (book.work_dir / manifest["frames"][1]["lettered"]["path"]).write_bytes(b"corrupt")
    result = generate(book)
    assert verify_inventory(book.work_dir, result["outputs"])
    assert len(providers["image"]) == 3


def test_symlink_output_escape_rejected_before_provider_call(book, providers, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (book.work_dir / "graphic").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        generate(book)
    assert providers == {"image": [], "storyboard": []}
    assert not list(outside.iterdir())


@pytest.mark.parametrize("options", [{"graphic_provider": "unknown"}, {"graphic_model": "dall-e-3"},
                                     {"graphic_words_per_frame": 0}, {"graphic_words_per_frame": True},
                                     {"graphic_chapters": []}, {"graphic_chapters": ["../escape"]},
                                     {"graphic_size": "auto"}, {"graphic_quality": "bad"},
                                     {"graphic_caption_height": float("nan")}, {"graphic_font_size": 1}])
def test_bad_settings_fail_without_io(options, book, providers):
    with pytest.raises(ValueError):
        generate(book, **options)
    assert providers == {"image": [], "storyboard": []}


def test_real_adapter_uses_sdk_and_decodes_base64(monkeypatch):
    import openai
    captured = []

    def generate(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())])

    monkeypatch.setattr(openai, "OpenAI", lambda: SimpleNamespace(images=SimpleNamespace(generate=generate)))
    data = graphic.generate_image(provider="openai", model="gpt-image-1", prompt="A harbor.", size="1024x1024", quality="low")
    assert data == png()
    assert captured == [{"model": "gpt-image-1", "prompt": "A harbor.", "n": 1, "size": "1024x1024", "quality": "low", "output_format": "png"}]


def test_storyboard_model_env_is_fingerprinted(monkeypatch):
    monkeypatch.delenv("FORAGE_MODEL", raising=False)
    monkeypatch.delenv("FORAGE_GRAPHIC_STORYBOARD_MODEL", raising=False)
    first = graphic.graphic_settings({})
    monkeypatch.setenv("FORAGE_GRAPHIC_STORYBOARD_MODEL", "openai:custom-model")
    second = graphic.graphic_settings({})
    assert first["storyboard_model"] != second["storyboard_model"]
    assert second["storyboard_model"] == "openai:custom-model"


def test_missing_late_chapter_stops_before_paid_work(book, providers):
    (book.work_dir / "segments/002.md").unlink()
    with pytest.raises(FileNotFoundError):
        generate(book)
    assert providers == {"image": [], "storyboard": []}


def test_selected_cut_or_unknown_chapter_fails_before_paid_work(book, providers):
    path = book.work_dir / "plan.json"
    plan = json.loads(path.read_text())
    plan["segments"][1]["skipped"] = True
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="cut"):
        generate(book, graphic_chapters=["002"])
    with pytest.raises(ValueError, match="unknown"):
        generate(book, graphic_chapters=["999"])
    assert providers == {"image": [], "storyboard": []}


def test_graphics_does_not_accept_unimplemented_partial_limit(book, providers):
    with pytest.raises(ValueError, match="unsupported graphics options"):
        generate(book, graphic_limit=1)
    assert providers == {"image": [], "storyboard": []}


def test_caption_renderer_fails_instead_of_clipping_text():
    with pytest.raises(ValueError, match="cannot fit without clipping"):
        graphic.letter_frame(png("64x64"), "A caption that cannot possibly fit in the tiny panel.")


@pytest.mark.parametrize("data", [[], [SimpleNamespace(b64_json=None)], [SimpleNamespace(b64_json="invalid%%")]])
def test_adapter_rejects_empty_or_invalid_provider_result(monkeypatch, data):
    import openai
    monkeypatch.setattr(openai, "OpenAI", lambda: SimpleNamespace(images=SimpleNamespace(generate=lambda **kwargs: SimpleNamespace(data=data))))
    with pytest.raises(ValueError, match="image provider"):
        graphic.generate_image(provider="openai", model="gpt-image-1", prompt="Harbor", size="1024x1024", quality="auto")


def test_global_model_config_is_used_for_storyboard_unless_overridden(monkeypatch):
    monkeypatch.delenv("FORAGE_MODEL", raising=False)
    monkeypatch.delenv("FORAGE_GRAPHIC_STORYBOARD_MODEL", raising=False)
    assert graphic.graphic_settings({"model": "openai:global"})["storyboard_model"] == "openai:global"
    assert graphic.graphic_settings({"model": "openai:global", "graphic_storyboard_model": "anthropic:explicit"})["storyboard_model"] == "anthropic:explicit"


def test_short_required_chapters_are_covered_and_explicitly_selectable(book, providers):
    path = book.work_dir / "plan.json"
    plan = json.loads(path.read_text())
    plan["segments"][0]["source_word_count"] = 9
    plan["segments"][1]["source_word_count"] = 10
    path.write_text(json.dumps(plan))
    complete = generate(book)
    assert [target["segment_id"] for target in complete["targets"]] == ["001", "002"]
    selected = generate(book, graphic_chapters=["001"])
    assert [target["segment_id"] for target in selected["targets"]] == ["001"]
    assert len(providers["image"]) == len(providers["storyboard"]) == 2
