# Drafting Dialogue Attribution Audit

## 2026-08-06

### Verdict

- Audited the drafter prompt update for source-backed dialogue attribution. Functional, structural, and forward-impact checks pass: both current and legacy prose drafter prompts now instruct the LLM to preserve speaker clarity, avoid adjacent quote-only ambiguity, and never invent unsupported speaker tags.

### Findings

No findings.

### Completeness

- Truthful state: exposed.
- Acceptance criteria: all addressed. The prompt update is present in `prompts/draft_lean.md` and `prompts/draft_segment.md`.
- Completion matrix: N/A.
- Implementation approach steps: all done.
- Done-when conditions: all met for prompt exposure. No LLM drafting run was performed.
- Files listed in brief: N/A.
- Architectural intent: achieved. The behavior lives in drafter prompts, matching the stage responsible for first-pass generation.
- Deferred items: none.
- Placeholder audit: clean.

### Structural Assessment

- Architecture: clean. No `docs/architecture/` directory exists; the change stays inside drafting prompts.
- Abstraction: clean. The main drafter and legacy segment drafter receive equivalent rules.
- Semantic families: unified. Dialogue paragraphing and source-backed attribution are expressed as invariants in both prompt paths.
- Patterns: consistent. Prompt language matches existing named-person continuity constraints and source-grounding rules.
- Integrity: clean. The prompts allow adding tags/action beats only when source-supported and explicitly forbid invented attribution.
- Scope: clean.

### Forward Impact

- Clean. Future drafts should avoid the repeated review failure where compressed dialogue preserves lines but drops speaker identity.
- Small fix now: none.

### Commands Used

- `rg -n "dialog|speaker|attribut|quote|unattributed" prompts spec forage -g '*.md' -g '*.py'`
- `rg -n "Dialogue attribution invariant|Preserve dialogue attribution|Preserve standard fiction dialogue|speaker remains clear|quote-led dialogue" prompts/draft_lean.md prompts/draft_segment.md`
- `nl -ba prompts/draft_lean.md | sed -n '8,28p;76,96p'`
- `nl -ba prompts/draft_segment.md | sed -n '1,22p;122,142p'`

## 2026-08-06 Review-Apply Dialogue Guard

### Verdict

- Audited the review-apply hardening after Secret Adversary chapter 2 showed an LLM response claiming attribution was fixed while the current chapter still had unattributed dialogue. Functional, structural, and forward-impact checks pass: review-apply now prompts against introducing quote-only dialogue runs and deterministically rejects revisions that add a new run of unattributed dialogue turns.

### Findings

No findings.

### Completeness

- Truthful state: exposed.
- Acceptance criteria: all addressed for future review-apply runs. The already-published Secret Adversary text still requires a paid rerun to repair content.
- Completion matrix: N/A.
- Implementation approach steps: all done.
- Done-when conditions: all met for code/prompt behavior. No paid LLM rerun was performed.
- Files listed in brief: N/A.
- Architectural intent: achieved. The prompt steers the model and `forage.review_apply` validates the resulting draft before writing the segment or ledger.
- Deferred items: current content repair is pending explicit paid-LLM approval.
- Placeholder audit: clean.

### Structural Assessment

- Architecture: clean. The validation lives in review-apply, the stage that writes revised drafts and ledger responses.
- Abstraction: clean. The new helper compares revised quote-only runs against preexisting quote-only runs so paragraph shifts alone do not fail, but new ambiguous source-restored dialogue does.
- Semantic families: unified. The behavior matches the current review app dialogue-lint concern while remaining local to the pipeline stage.
- Patterns: consistent. Existing `ValueError` rejection flow is used.
- Integrity: clean. The code no longer trusts the model's `changed_paragraphs` and reason as sufficient evidence that a dialogue-attribution repair succeeded.
- Scope: clean.

### Forward Impact

- Clean. Future review-apply runs should fail closed instead of publishing a misleading comment response when a revision introduces unclear speakers.
- Small fix now: none.

### Commands Used

- `.venv/bin/python -m py_compile forage/review_apply.py scripts/check_review_app.py`
- `.venv/bin/python - <<'PY' ... _validate_revision_consistency historical before/after ...`
- `.venv/bin/python scripts/check_review_app.py --book secret_adversary`
- `nl -ba forage/review_apply.py | sed -n '20,46p;540,625p'`
- `nl -ba prompts/review_apply_segment.md | sed -n '1,32p'`
- `nl -ba scripts/check_review_app.py | sed -n '330,368p'`

## 2026-08-07 Review-Apply Feedback Trust Boundary

### Verdict

- Review-apply now treats human comments as untrusted reviewer claims rather
  than instructions. The bad Secret Adversary hostel edit was rolled back from
  the automatic snapshot, the latest response for that comment was corrected to
  a skipped/correction entry, and validation now rejects hidden paragraph edits
  that the LLM fails to declare.

### Findings

No findings for the immediate hardening. Residual product risk remains: free-form
comments still give the LLM broad natural-language input. A stronger future
review model should collect a predefined defect type plus exact word/span
selection in the affected paragraph, with free-form text demoted to optional
context that is not sent as an instruction.

### Completeness

- Truthful state: exposed.
- Acceptance criteria: immediate rollback and pipeline hardening completed.
- Deferred items: structured review taxonomy and word-level defect anchoring.

### Commands Used

- `rg -n "hostel|Southern Belgravia|palatial suite" work/secret_adversary/chapters/002.md work/secret_adversary/segments/002*.md`
- `.venv/bin/python -m forage.cli assemble secret_adversary`
- `.venv/bin/python -m forage.cli validate secret_adversary`
- `.venv/bin/python -m forage.cli review-apply secret_adversary --segment 002 --edits work/secret_adversary/editorial/live_edits_secret_adversary_new_comment.json`
- `.venv/bin/python scripts/check_review_app.py --book secret_adversary`
