"""Offline regressions for counted, source-grounded two-pass abridgment."""
from copy import deepcopy
import json
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from forage import target_revision as tr
from forage.artifacts import Book, write_json
from forage.cli import app
from forage.llm import LLMResponse


SOURCE = "A named speaker spoke softly.\n\nThe little boat drifted slowly home."


def response(prose, *, revision=False, reason="end_turn", paragraphs=None, **notes):
    value = {"summary": "Editorial summary.", "risks": []}
    if revision:
        value.update(infeasible=False, cut_evaluation=[
            {"paragraph_ids": paragraphs or [2], "action": "compress",
             "reason": "Remove repetition.", "dependency_check": "The destination survives."}])
    value.update(notes)
    text = prose + "\n<!-- FORAGE_CHAPTER_NOTES\n" + json.dumps(value) + "\n-->"
    return LLMResponse(text, "anthropic:fixture", 10, 10, 0, reason)


@pytest.fixture
def plan():
    return {
        "id": "001", "title": "Test", "target_words": 8,
        "verbatim": [{"id": "V1", "text": "A named speaker", "paragraph": 1}],
        "essential": ["Retain the speaker and journey"], "optional": ["Repeated description"],
        "dependencies": [], "continuity_checks": ["Speaker stays identified"],
        "sections": [{"name": "Chapter", "weight": 1, "words": 8}],
    }


def test_two_calls_receive_measured_count_and_preserve_both_versions(tmp_path, plan):
    revised = "A named speaker spoke.\n\nThe boat drifted home."
    fake = Mock(side_effect=[response(SOURCE), response(revised, revision=True)])
    out = tmp_path / "run"
    result = tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=out, generate=fake)
    assert fake.call_count == 2
    second = fake.call_args_list[1].args[0]["prompt"]
    assert "contains 11 words" in second
    assert "Remove a net 3 words" in second
    assert '"words": 5' in second and '"words": 6' in second
    assert result["revision"]["words"] == 8
    assert result["status"] == "measured_checks_pass"
    assert result["measured_changes"]["net_words_removed"] == 3
    assert (out / "initial.md").read_text() == SOURCE + "\n"
    assert (out / "revision.md").read_text() == revised + "\n"
    with pytest.raises(FileExistsError):
        tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=out, generate=fake)
    assert fake.call_count == 2


@pytest.mark.parametrize("text, issue", [
    (SOURCE, "Fixed target"),
    ("The speaker spoke.\n\nThe little boat drifted home.", "Required exact text"),
])
def test_failed_measurements_remain_visible_no_extra_call(tmp_path, plan, text, issue):
    fake = Mock(side_effect=[response(SOURCE), response(text, revision=True)])
    result = tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=tmp_path/"run", generate=fake)
    assert fake.call_count == 2 and result["status"] == "needs_review"
    assert any(issue in s for s in result["issues"])


@pytest.mark.parametrize("stage", ["initial", "revision"])
@pytest.mark.parametrize("reason", ["max_tokens", "length", "content_filter"])
def test_incomplete_response_never_becomes_a_final_draft(tmp_path, plan, stage, reason):
    replies = [response(SOURCE, reason=reason)] if stage == "initial" else [
        response(SOURCE), response(SOURCE, revision=True, reason=reason)]
    fake = Mock(side_effect=replies)
    out = tmp_path / "run"
    with pytest.raises(ValueError, match="incomplete"):
        tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=out, generate=fake)
    assert not (out / "result.json").exists()
    assert not (out / f"{stage}.md").exists()
    assert (out / "failed.json").exists()


def test_invalid_cut_references_rejected(tmp_path, plan):
    fake = Mock(side_effect=[response(SOURCE), response(SOURCE, revision=True, paragraphs=[999])])
    with pytest.raises(ValueError, match="invalid draft paragraph"):
        tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=tmp_path/"run", generate=fake)
    assert not (tmp_path/"run/result.json").exists()


def test_restoration_feedback_and_notes_excluded(plan):
    request, context = tr.revision_request({}, SOURCE, plan, "A named speaker")
    assert "Restore 5 words" in request["prompt"]
    assert context["measurements"]["words"] == 3
    assert tr.split_response(response(SOURCE).text)[0] == SOURCE
    with pytest.raises(ValueError, match="one final"):
        tr.split_response(response(SOURCE).text + "\nExtra chapter prose.")


def test_impossible_plan_rejected_before_spending(tmp_path, plan):
    plan["sections"][0]["words"] = 7
    fake = Mock(side_effect=AssertionError("must not call"))
    with pytest.raises(ValueError, match="sum"):
        tr.run_chapter(metadata={}, source=SOURCE, plan=plan, output_dir=tmp_path/"run", generate=fake)
    fake.assert_not_called()


def planning_fixture():
    source = "A named speaker spoke softly. " + "Scene detail. " * 50
    chapters = [dict(id="001", title="A chapter", number=1, source=source, target_words=20)]
    generated = {
        "voice_profile": "Understatement", "book_context": "A journey",
        "chapters": [dict(
            id="001", verbatim=[dict(paragraph=1, text="A named speaker", purpose="Identity")],
            essential=["The speaker remains"], optional=["Repeated scene detail"],
            dependencies=[dict(local_evidence="spoke softly", other_evidence="A later payoff",
                               other_chapter="Later", instruction="Retain the setup")],
            sections=[dict(name="Opening", weight=2), dict(name="Ending", weight=1)],
            continuity_checks=["The payoff remains"], infeasible=False, risks=[])]
    }
    return source + "\n\nA later payoff.", chapters, generated


def test_planning_evidence_and_exact_allocation():
    source, selected, generated = planning_fixture()
    validated = tr.validate_plans(source, selected, generated)[0]
    assert [s["words"] for s in validated["sections"]] == [13, 7]
    assert "words" not in generated["chapters"][0]["sections"][0]
    assert "ceiling_words" not in validated
    bad = deepcopy(generated)
    bad["chapters"][0]["dependencies"][0]["other_evidence"] = "Invented evidence"
    with pytest.raises(ValueError, match="absent"):
        tr.validate_plans(source, selected, bad)
    bad["chapters"][0]["dependencies"][0]["other_evidence"] = "spoke softly"
    with pytest.raises(ValueError, match="only locally"):
        tr.validate_plans(source, selected, bad)


def test_prompt_has_one_target_and_no_legacy_allowance(plan):
    for name in ["preservation_plan", "draft_fixed_target", "revise_fixed_target"]:
        tr.fixed_target_audit(tr.load_prompt(name).body_template)
    bad = deepcopy(plan)
    bad["ceiling_words"] = 10
    with pytest.raises(ValueError, match="allowance"):
        tr.fixed_target_audit(json.dumps(bad))


def test_book_command_runs_pipeline_and_leaves_production_untouched(tmp_path, monkeypatch):
    source, selected, generated = planning_fixture()
    root = tmp_path / "workspace"
    bookdir = root / "books" / "sample"
    work = root / "work" / "sample"
    bookdir.mkdir(parents=True)
    (bookdir/"sample.txt").write_text(source)
    (work/"chapters").mkdir(parents=True)
    (work/"chapters/001.md").write_text(selected[0]["source"])
    write_json(work/"plan.json", {"segments": [{"id": "001", "title": "Test", "target_word_count": 20}]})
    (work/"segments").mkdir()
    (work/"segments/001.md").write_text("Previously accepted production text.")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    fake = Mock(side_effect=[
        LLMResponse(json.dumps(generated), "anthropic:fixture", 1, 1, 0, "end_turn"),
        response(selected[0]["source"]),
        response("A named speaker spoke softly. " + "Scene detail. " * 7 + "End.", revision=True, paragraphs=[1]),
    ])
    monkeypatch.setenv("FORAGE_WORKSPACE", str(root))
    monkeypatch.setattr(tr, "complete", fake)
    out = tmp_path/"experiment"
    result = CliRunner().invoke(app, ["draft-two-pass", "sample", "--segment", "001", "--output-dir", str(out)])
    assert result.exit_code == 0, result.output
    assert fake.call_count == 3
    assert (out/"001/result.json").exists()
    assert all(p.read_bytes() == content for p, content in before.items())


def test_changes_count_additions_as_well_as_deletions():
    result = tr.measured_changes("one two three four", "one five six")
    assert result["removed_words"] == 3 and result["added_words"] == 2
    assert result["net_words_removed"] == 1


def test_literal_book_language_is_not_mistaken_for_target_instructions(tmp_path, plan):
    source = "The town was overrun by the invading army."
    plan["verbatim"][0]["text"] = "overrun"
    fake = Mock(side_effect=[response(source), response(source, revision=True, paragraphs=[1])])
    result = tr.run_chapter(metadata={}, source=source, plan=plan,
                            output_dir=tmp_path/"run", generate=fake)
    assert result["status"] == "measured_checks_pass"
    assert "overrun" in fake.call_args.args[0]["prompt"]


def test_alternate_length_field_rejected_even_when_nested(plan):
    plan["sections"][0]["ceiling_words"] = 10
    with pytest.raises(ValueError, match="allowance fields"):
        tr.plan_target_audit(plan)
