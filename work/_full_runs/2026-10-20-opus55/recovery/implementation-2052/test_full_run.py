from pathlib import Path
import json

import pytest

from forage.full_run import (
    AXES, Journal, apply_replacements, evidence_check, prepare, validate_review,
)


def preservation():
    return {"target_words": 8, "verbatim": [{"id": "V1", "text": "This must survive."}]}


def test_local_replacements_preserve_untouched_text_and_count():
    text = "This must survive.\n\nAn optional sentence.\n\nThe ending remains."
    result = apply_replacements(text, [{"old": "An optional sentence.", "new": ""}], preservation())
    assert result == "This must survive.\n\nThe ending remains."


@pytest.mark.parametrize("replacements", [
    [{"old": "absent", "new": ""}],
    [{"old": "", "new": "new"}],
    [{"old": "This must survive.", "new": "This changed."}],
    [{"old": "survive.\n\nThe", "new": ""}, {"old": "The ending", "new": ""}],
])
def test_invalid_or_destructive_patches_rejected(replacements):
    with pytest.raises(ValueError):
        apply_replacements("This must survive.\n\nThe ending remains.", replacements, preservation())


def test_duplicate_patch_anchor_rejected():
    with pytest.raises(ValueError, match="unique"):
        apply_replacements("This must survive. Same. Same.",
                           [{"old": "Same.", "new": ""}], preservation())


def test_evidence_requires_exact_paragraph():
    docs = {"007.source": ["one paragraph", "the actual evidence"]}
    evidence_check([{"document": "007.source", "paragraph": 2, "quote": "actual evidence"}], docs)
    with pytest.raises(ValueError):
        evidence_check([{"document": "007.source", "paragraph": 1, "quote": "actual evidence"}], docs)


def test_review_requires_full_coverage_and_both_evidence_endpoints():
    docs = {"007.source": ["source"], "007.revision": ["draft"]}
    review = {
        "chapter": "007", "coverage": [{"axis": a} for a in AXES],
        "verdict": "needs_repair", "dependencies": [],
        "findings": [{"id": "F1", "axis": "dialogue", "priority": "must_fix",
                      "evidence": [{"document": "007.source", "paragraph": 1, "quote": "source"}]}],
    }
    with pytest.raises(ValueError, match="source and revision"):
        validate_review(review, "007", docs, 0)
    review["findings"][0]["evidence"].append(
        {"document": "007.revision", "paragraph": 1, "quote": "draft"})
    assert validate_review(review, "007", docs, 0) == review
    review["coverage"].pop()
    with pytest.raises(ValueError, match="eight axes"):
        validate_review(review, "007", docs, 0)


def test_journal_accounts_for_unknown_billing_and_refuses_blind_retry(tmp_path):
    from forage.production_state import digest
    request = {"prompt": "text", "model": "anthropic:claude-opus-5-5",
               "thinking": "medium", "max_tokens": 16000}
    folder = tmp_path / digest(request)
    folder.mkdir()
    (folder / "started.json").write_text(json.dumps({"maximum_cost_usd": 1.2}))
    journal = Journal(tmp_path, client=object())
    assert journal.totals() == {"attempts": 1, "responses": 0,
                                "cost_usd": 0, "unsettled_reserve_usd": 1.2}
    with pytest.raises(RuntimeError, match="already attempted"):
        journal(**request)


def test_provider_metadata_excludes_secrets_and_cookies():
    from types import SimpleNamespace
    from forage.full_run import response_metadata
    response = SimpleNamespace(status_code=200, headers={
        "request-id": "request-1", "anthropic-organization-id": "org-1",
        "anthropic-workspace-id": "workspace-1", "anthropic-ratelimit-requests-remaining": "10",
        "authorization": "secret", "x-api-key": "secret", "set-cookie": "session=secret",
    })
    metadata = response_metadata(response)
    assert metadata["headers"]["anthropic-organization-id"] == "org-1"
    assert metadata["headers"]["anthropic-workspace-id"] == "workspace-1"
    assert "secret" not in json.dumps(metadata)
    assert response_metadata(None) == {}


def test_journal_exact_response_reuse_has_no_network_call(tmp_path):
    from forage.production_state import digest
    from forage.llm import LLMResponse
    from dataclasses import asdict
    request = {"prompt": "text", "model": "anthropic:claude-opus-5-5",
               "thinking": "medium", "max_tokens": 16000}
    folder = tmp_path / digest(request)
    folder.mkdir()
    response = LLMResponse("done", request["model"], 10, 10, 1, "end_turn")
    (folder / "response.json").write_text(json.dumps({"completion": asdict(response)}))
    assert Journal(tmp_path, client=object())(**request).text == "done"


def test_funded_account_resume_retains_old_billing_reserve(tmp_path):
    from forage.production_state import digest
    from types import SimpleNamespace
    request = {"prompt": "text", "model": "anthropic:claude-opus-5-5",
               "thinking": "medium", "max_tokens": 16000}
    folder = tmp_path / digest(request)
    folder.mkdir()
    (folder / "started.json").write_text(json.dumps({"maximum_cost_usd": 1.2}))
    (folder / "error.json").write_text(json.dumps({"error": "Your credit balance is too low"}))
    usage = {"input_tokens": 100, "output_tokens": 10}
    result = SimpleNamespace(id="response", model="claude-opus-5-5", stop_reason="end_turn",
                             usage=SimpleNamespace(model_dump=lambda **kw: usage),
                             content=[SimpleNamespace(type="text", text="done")])

    class Stream:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get_final_message(self):
            return result

    client = SimpleNamespace(messages=SimpleNamespace(
        count_tokens=lambda **kw: SimpleNamespace(input_tokens=100),
        stream=lambda **kw: Stream()))
    journal = Journal(tmp_path, client=client, retry_credit_errors=True)
    assert journal(**request).text == "done"
    assert journal.totals()["attempts"] == 2
    assert journal.totals()["unsettled_reserve_usd"] == 1.2
    assert (folder / "error.json").exists()
    assert (folder / "attempt-002/response.json").exists()
    assert Journal(tmp_path, client=object())(**request).text == "done"


def test_credit_resume_does_not_repeat_unrelated_unknown_failure(tmp_path):
    from forage.production_state import digest
    request = {"prompt": "text", "model": "anthropic:claude-opus-5-5",
               "thinking": "medium", "max_tokens": 16000}
    folder = tmp_path / digest(request)
    folder.mkdir()
    (folder / "started.json").write_text(json.dumps({"maximum_cost_usd": 1.2}))
    (folder / "error.json").write_text(json.dumps({"error": "Network connection lost"}))
    with pytest.raises(RuntimeError, match="already attempted"):
        Journal(tmp_path, client=object(), retry_credit_errors=True)(**request)


def test_incomplete_prose_is_recovered_with_a_distinct_bounded_request():
    from forage.full_run import validated_prose
    from forage.llm import LLMResponse
    calls = []
    def generate(**request):
        calls.append(request)
        if len(calls) == 1:
            return LLMResponse("Truncated chapter", request["model"], 1, 32000, 1, "max_tokens")
        return LLMResponse('Complete prose.\n<!-- FORAGE_CHAPTER_NOTES {"infeasible": false} -->',
                           request["model"], 1, 100, 1, "end_turn")
    request = dict(model="anthropic:claude-opus-5-5", prompt="Original fixed target.",
                   stage="revision:017", max_tokens=32000)
    prose, notes = validated_prose(generate, request)
    assert prose == "Complete prose."
    assert len(calls) == 2
    assert calls[1]["max_tokens"] == 48000
    assert calls[1]["stage"] != calls[0]["stage"]
    assert calls[1]["prompt"].startswith(request["prompt"])
    assert request["max_tokens"] == 32000


def test_repeated_truncation_fails_without_exposing_partial_prose():
    from forage.full_run import validated_prose
    from forage.llm import LLMResponse
    calls = []
    def generate(**request):
        calls.append(request)
        return LLMResponse("Partial", request["model"], 1, 1, 1, "max_tokens")
    with pytest.raises(ValueError, match="incomplete"):
        validated_prose(generate, dict(model="anthropic:claude-opus-5-5",
                                      prompt="Fixed target.", stage="revision:017"))
    assert len(calls) == 2


def test_credit_failure_stops_other_journals_before_network(tmp_path):
    from types import SimpleNamespace
    calls = []
    def count(**request):
        calls.append(request)
        raise RuntimeError("Your credit balance is too low")
    client = SimpleNamespace(messages=SimpleNamespace(count_tokens=count))
    journal = Journal(tmp_path, client=client)
    with pytest.raises(RuntimeError, match="credit balance"):
        journal(prompt="first")
    with pytest.raises(RuntimeError, match="stopped locally"):
        Journal(tmp_path, client=object())(prompt="second")
    assert len(calls) == 1
    assert (tmp_path / "credit_blocked.json").exists()
    Journal(tmp_path, client=object(), retry_credit_errors=True)
    assert not (tmp_path / "credit_blocked.json").exists()


def test_stream_credit_error_retains_routing_and_local_stop_preserves_evidence(tmp_path):
    from types import SimpleNamespace

    class Stream:
        response = SimpleNamespace(status_code=200, headers={
            "request-id": "request-1", "anthropic-organization-id": "org-1",
            "anthropic-workspace-id": "workspace-1", "set-cookie": "secret-cookie",
        })
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get_final_message(self):
            raise RuntimeError("Your credit balance is too low")

    client = SimpleNamespace(api_key="secret-key", messages=SimpleNamespace(
        count_tokens=lambda **kw: SimpleNamespace(input_tokens=100),
        stream=lambda **kw: Stream()))
    journal = Journal(tmp_path, client=client)
    with pytest.raises(RuntimeError, match="credit balance"):
        journal(prompt="first")
    marker = (tmp_path / "credit_blocked.json").read_text()
    with pytest.raises(RuntimeError, match="stopped locally"):
        journal(prompt="second")
    assert (tmp_path / "credit_blocked.json").read_text() == marker
    transport = json.loads(next(tmp_path.rglob("transport.json")).read_text())
    assert transport["headers"]["request-id"] == "request-1"
    assert transport["headers"]["anthropic-workspace-id"] == "workspace-1"
    saved = "".join(p.read_text() for p in tmp_path.rglob("*.json"))
    assert "secret-key" not in saved and "secret-cookie" not in saved


def test_finish_produces_verified_review_snapshot_with_current_alignment(tmp_path):
    from forage.artifacts import Book
    from forage.full_run import finish, write
    from forage.llm import LLMResponse
    from forage.publication import verify_revision
    source = tmp_path / "books/sample/source.txt"
    source.parent.mkdir(parents=True)
    text = "This must survive. The ending remains."
    source.write_text(text)
    root = tmp_path / "work/sample"
    for name in ("chapters", "segments", "preservation", "fidelity/final_review"):
        (root / name).mkdir(parents=True, exist_ok=True)
    book = Book("sample", source, {"title": "Sample", "author": "A. Author"}, root)
    (root / "chapters/001.md").write_text(text)
    (root / "book_synopsis.md").write_text("The ending remains.")
    plan = {"title": "Sample", "author": "A. Author",
            "_meta": {"computed": {"target_word_count": 6}},
            "segments": [{"id": "001", "title": "One", "diegetic_status": "diegetic",
                          "source_word_count": 6, "target_word_count": 6, "signatures": []}]}
    write(root / "plan.json", plan)
    write(root / "preservation/001.json", {**preservation(), "target_words": 6})
    for name in ("chapters.json", "chapter_classifications.json", "cuts.json"):
        write(root / name, {})
    write(root / "fidelity/final_review/001.json",
          {"verdict": "no_material_findings", "findings": []})

    def generate(**req):
        if req["stage"].startswith("align"):
            value = [{"draft_para": 0, "source_paras": [0], "note": "verbatim"}]
        else:
            value = [{"sentence": 1, "status": "present", "evidence": "The ending remains."}]
        return LLMResponse(json.dumps(value), "anthropic:claude-opus-5-5", 1, 1, .1, "end_turn")

    result = finish(book, {"001": text}, generate, 1, "final_review")
    assert result["status"] == "complete"
    assert result["unresolved_must_fix"] == 0
    assert result["exact_target_chapters"] == 1
    assert verify_revision(book, result["review_revision"])["revision"] == result["review_revision"]
    assert not (root / "release_current.json").exists()
    alignment = json.loads((root / "alignments/001.json").read_text())
    assert alignment["draft_paragraphs"] == [text]
