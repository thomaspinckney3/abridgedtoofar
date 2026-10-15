# Task Brief: M1 — Correct artifact safety and completion

## Objective

Fix the five reproduced defects so existing packaging, drafting, proofreading,
and audiobook commands reject unsafe, incomplete, or stale artifacts before the
new production runner depends on them. M1 does not implement that runner.

## Acceptance Criteria

1. `package(book_ids, out_dir)` rejects resolved overlap between either output
   (`out_dir` and sibling `books/`) and input roots, including ancestor,
   descendant, identical, and symlink aliases. Validate book IDs and confine
   selected inputs too. Invalid selection, missing explicit input, malformed
   JSON, or a copy/publication exception leaves inputs and previous published
   outputs intact. The normal `deploy/artifacts` + `deploy/books` layout and
   temporary bundle used by `publish_review_book._archive_book` remain usable.
2. Group and standalone drafting classify both `max_tokens` and OpenAI `length`
   as incomplete, including fallback and replay responses. Empty responses
   cannot be `drafted`. Every member of a truncated grouped response is marked
   incomplete even if its split body is nonempty. Assembly excludes these
   members and reports missing work. Preserve successful draft/cut semantics.
3. `_disk_draft_result` respects recorded failure status and does not turn
   truncated/error checks into success. Missing/corrupt checks are not evidence
   of successful group completion. A valid completed group is still generated
   once and reused by its other members; a failed nonempty group never appears
   successful merely because it is encountered again.
4. `align_book` reuses alignment only when stored source and draft paragraphs
   match current inputs. It regenerates after either changes or cache corruption
   and reports source/read/generation failures. Successful regeneration changes
   `ArtifactStore.chapter_view` and makes old paragraph comments stale. Existing
   alignments without new metadata can be compared using their embedded text.
5. Audio reuse requires a matching effective synthesis request and verified
   audio bytes from successful prior generation. Include voice, model, format,
   seed, language, normalization, voice settings, and stitching/context inputs;
   changed neighboring text must invalidate affected stitched chunks. Missing,
   empty, tampered, old-provenance, or failed audio cannot be silently skipped.
6. Dry runs and limited/failed runs never associate newly requested text/settings
   with old bytes. A dry run must not replace the successful manifest or its text
   sidecars. Combining/publication requires every selected current chunk to be
   successfully generated or validly reused; leftover old files outside a limit
   are not sufficient. Preserve old successful output until replacement succeeds.
7. Permanent offline tests prove each behavior, all existing tests pass, and the
   historical reproduction script is clearly retired or points to the new tests
   instead of asserting that fixed defects remain present.

Maps to PROJECT AC1–AC4 and the first three PLAN completion-matrix rows.

## Relevant Files

Read package onboarding first:

- `README.md` — commands, setup, stage behavior, review deployment and narration.
- `CLAUDE.md` — live paid calls require separate explicit approval; this task
  uses mocks only and does not need an approval gate.
- `pyproject.toml` — Python >=3.11, pytest/dev and optional web dependencies.
- `project-notes/production-pipeline/{PROJECT,PLAN,ARCHITECTURE,STATUS}.md` —
  requirements, ownership, proof, current state.
- `project-notes/repository-review/{AUDIT.md,reproduce_findings.py}` — evidence
  and temporary fixture patterns; the reproduction asserts defects, not fixes.

Read/modify the following according to the acceptance criteria:

- `scripts/package_review_artifacts.py` — destructive sibling cleanup, package
  layout and selected-book checks. `scripts/publish_review_book.py` and
  `Dockerfile` are consumers; preserve their layout contract.
- `forage/llm.py` — LLMResponse, provider completion values, replay load and
  fallback boundary. Existing model-default edits must survive.
- `forage/drafter.py` — `_draft_group`, `_disk_draft_result`, `draft_segment`,
  `_write_checks`; grouped initial drafting has a separate reuse path.
- `forage/assemble.py` — consumes `error`/`truncated` checks and counts missing
  members. Test integration; change only if needed for the completion contract.
- `forage/align.py` — `align_chapter`, `align_book`, paragraph normalization.
- `forage/webapp/store.py` and `forage/webapp/app.py` — existing chapter view,
  `anchor_hash`, comment staleness; integration proof need not change them.
- `forage/audiobook.py` — request formation, `_old_chunk_entry`, manifest,
  text sidecars, generated audio, combine/publication and result counts.
- `forage/artifacts.py` — Book and existing I/O helpers; do not broadly change
  global I/O semantics solely for this milestone.
- `tests/conftest.py`, `tests/test_deploy_config.py`,
  `tests/test_webapp_security.py` — existing isolated fixtures and compatibility
  tests. Add focused `tests/test_artifact_safety.py`,
  `tests/test_draft_completion.py`, `tests/test_alignment_freshness.py`, and
  `tests/test_audiobook_reuse.py` (or equivalent focused modules).
- `README.md` — update any reuse descriptions made inaccurate by the fixes.
- `project-notes/production-pipeline/STATUS.md` — replace current state while
  working; final marker records verification, with no commit required.

## Implementation Approach

1. Resolve and validate packaging boundaries before creating or removing output.
   Build the complete selected package in a fresh owned staging area. Validate
   all selected input and generated metadata before publication. Replace the
   two legacy output directories with backups/rollback on publication failure;
   never recursively delete an arbitrary sibling before validation.
2. Add a shared completion predicate/normalization at the LLM response boundary
   that also works for direct `LLMResponse` fixtures and old replay reasons.
   Apply it consistently after retries/fallbacks in both draft paths. Preserve
   partial diagnostic text if useful, but all consumer-visible checks must say
   incomplete. Keep raw provider reasons if useful for diagnosis.
3. Read checks in `_disk_draft_result`; preserve failure instead of reconstructing
   success from text. Make group retry/reuse decisions explicit without repeated
   regeneration per group member or a hidden change to successful group reuse.
4. Compare alignment's embedded normalized paragraphs with current source and
   draft before skipping. Corrupt/missing cache is a miss. Keep a previous valid
   alignment intact if regeneration fails and report the failure to the caller;
   do not claim it is current. Verify staleness through the existing review store.
5. Give generated audio durable request and output fingerprints. Reuse only
   successful entries whose current request and bytes match. Atomically replace
   audio/provenance after generation succeeds. Keep previews separate from real
   provenance, and gate combination on valid current entries instead of existence.
6. Add focused tests using temporary trees and mocked LLM/TTS responses. Test
   unchanged reuse as well as changed input, failure, and corrupt outputs. Update
   historical reproduction documentation and run the milestone gate.

These implement the architecture's completion, changed-input, and packaging
change patterns. M2 will consume these contracts; do not require a generic state
framework or preempt M2 orchestration to fix them.

## Constraints

- No live LLM/TTS/image requests; replay is not a guarantee of offline operation.
- No commits, pushes, deployments, existing book/work artifact edits, or resets.
  Preserve all pending model-default and comparison changes.
- Use the existing .venv and local package prerequisites. Installed Nova-specific
  compiler/build rules and the missing Nova onboarding reference do not apply.
- No new approval gate: the user already authorized the fixes and integration.
- Remain alive while foreground validation runs; do not background a test run
  and return with its result unknown.
- Be precise about publication atomicity: two sibling directory renames are not
  one filesystem transaction. Test rollback on the second replacement failure;
  do not claim crash-wide atomicity without an actual recovery mechanism.

## Done When

- Focused tests for all criteria pass, with isolated fake provider calls.
- `.venv/bin/python -m pytest -q` passes (baseline 110 passed, 6 Docker skipped).
- `git diff --check` passes.
- STATUS contains `[done] M1` with exact commands/results and the statement that
  changes are uncommitted by instruction; report READMEs read and prerequisites.
- No promised M1 branch is an unconditional success, placeholder, or silent
  fallback. Live provider quality and Docker execution are not claimed verified.

## Abstraction Context

- `Book` identifies source and workspace; sound minimal context. Use temporary
  Book instances in tests instead of redirecting the real repository.
- `LLMResponse` centralizes provider output but stop reasons leak provider
  strings. Extend one completion contract instead of adding unrelated string
  checks to every caller. Existing retry/fallback routing must remain usable.
- Draft checks already own completion metadata; `_disk_draft_result` currently
  bypasses that authority. Fix the bypass and retain assembly's checks contract.
- Alignment JSON already embeds both inputs. It can establish legacy freshness
  without introducing a parallel cache database or requiring hosted source files.
- Audiobook manifest is the natural owner of per-chunk provenance; currently
  existence-based decisions ignore it. Extend it, with a version/legacy policy,
  instead of using a second audio index just to decide generation reuse.
- Packaging owns generated deploy outputs only. Its two-directory layout is a
  consumer contract; safe staging belongs here, not in web read APIs.

## Declared Regressions

None. Historical defect probes may be retired explicitly, not silently inverted.

## Open Questions

None blocking. Routine schema/helper names are implementation choices. The
asynchronous hosted review lifecycle belongs to M2/M3 and does not affect M1.
