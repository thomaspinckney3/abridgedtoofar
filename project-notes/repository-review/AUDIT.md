# Current Repository Review Audit

The findings below document the pre-fix repository. M1 retires the historical
`reproduce_findings.py` probes in favor of permanent offline regressions:
`tests/test_artifact_safety.py`, `tests/test_draft_completion.py`,
`tests/test_alignment_freshness.py`, and `tests/test_audiobook_reuse.py`.
See `../production-pipeline/STATUS.md` for implementation verification.

## 2026-10-14

### Verdict

Reviewed the current working tree at base commit `3644fc8`, including the
uncommitted model-default migration, drafting and assembly, review artifacts,
publishing, audiobook reuse, and the web application's storage/authentication
boundaries. Five correctness issues were reproduced locally. The audit does
not pass functional or forward-impact checks. The findings below predate the
uncommitted model-default changes; they are repository findings rather than
claims that the migration introduced them.

The existing suite passes: **110 passed, 6 skipped**. The skipped tests build
and run Docker containers. No live model, speech, deployment, or publishing
requests were made. All five reproductions use temporary directories and
mocked provider responses. Production code and existing book artifacts were
left unchanged.

### Findings

1. **[P1] Packaging a custom output directory can delete the source library.**
   - Evidence: `scripts/package_review_artifacts.py:49`, especially lines
     53–55.
   - `package()` recursively deletes the output directory's sibling `books/`
     before checking input availability. Running the script from the repository
     with `--out artifacts` consequently targets the real repository `books/`,
     including original sources, rather than just generated metadata.
   - Reproduction: `packaging_deletes_sources` creates an isolated repository
     with a source file and alignment, then packages to `<root>/artifacts`.
     The source file disappears and packaging returns success.
   - Fix direction: validate resolved source/destination relationships before
     deletion; confine cleanup to an owned staging directory and publish only
     after the package has been validated.

2. **[P1] Merged drafting accepts and publishes token-truncated chapters.**
   - Evidence: `forage/drafter.py:530`, `forage/drafter.py:539`,
     `forage/drafter.py:329`, `forage/assemble.py:105`.
   - `_draft_group()` marks every nonempty split body `drafted` without checking
     the response's stop reason. If output reaches every requested heading but
     stops partway through the final chapter, all members look complete.
     `_disk_draft_result()` likewise infers success from nonempty text.
   - Reproduction: `group_truncation` supplies two chapter headings with the
     second body ending at “Then he” and `stop_reason="max_tokens"`. Both checks
     files say `drafted`; assembly publishes the unfinished prose and reports
     zero missing segments.
   - Fix direction: validate completion before accepting group output and
     preserve incomplete status in both checks files and disk-derived results.

3. **[P2] Single-chapter drafting misses OpenAI's truncation reason.**
   - Evidence: `forage/drafter.py:713`, `forage/drafter.py:740`,
     `forage/llm.py:436`.
   - The OpenAI adapter forwards `choice.finish_reason` unchanged. Its token
     limit value is `length`, as confirmed in the installed SDK's
     `openai/types/chat/chat_completion.py`. The drafter only recognizes
     Anthropic's `max_tokens`, so a partial OpenAI draft is labeled complete.
     This affects explicit OpenAI drafting and cross-provider fallback.
   - Reproduction: `openai_truncation` supplies unfinished prose with
     `stop_reason="length"`; the result is `drafted` and assembly reports no
     missing segments.
   - Fix direction: normalize provider completion reasons at the LLM boundary
     or use a shared truncation predicate in all drafting paths.

4. **[P2] Proofreading silently retains old prose after a draft changes.**
   - Evidence: `forage/align.py:113`, `forage/webapp/store.py:672`,
     `forage/review_apply.py:294`, `forage/cli.py:1439`.
   - `align_book()` skips any chapter whose alignment JSON exists, without
     checking its embedded source/draft against current files. Drafting and
     review-apply can change the chapter without invalidating that JSON. A
     subsequent ordinary `forage proofread` still skips it, and the review app
     continues serving the old embedded draft. Comment staleness also compares
     against that old alignment, so it cannot reveal the new draft change.
   - Reproduction: `stale_alignment` creates an alignment, changes the draft,
     and calls `align_book()` again. It returns `already aligned`; the review
     store still serves “The old paragraph.”
   - Fix direction: compare stored source/draft content or hashes before reuse
     and invalidate affected alignments when a chapter is revised.

5. **[P2] Audiobook resume reuses obsolete audio and records a new text hash.**
   - Evidence: `forage/audiobook.py:224`, `forage/audiobook.py:238`,
     `forage/audiobook.py:285`, `forage/audiobook.py:514`.
   - `_old_chunk_entry()` detects a text-hash mismatch, but reuse depends only
     on the numbered audio file existing. After a prose edit, the default rerun
     therefore skips the old audio while rewriting the text file and manifest
     with the new content/hash. The combine path can publish that outdated
     narration. Changes to voice/model settings are also absent from reuse
     validation.
   - Reproduction: `stale_audio` generates one fake audio chunk, changes the
     input, and runs generation again. The second run makes no speech request,
     reports one skipped chunk, and associates the new text with old bytes.
   - Fix direction: require matching content and synthesis settings before
     reuse; do not replace provenance for audio that has not been regenerated.

### Commands Used

Run from the repository root:

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python project-notes/repository-review/reproduce_findings.py
git diff --check
```

The reproduction script asserts the observed defects, so a successful run
confirms that they exist. It is evidence for the review, not a passing
regression suite certifying correct behavior. The script never calls a live
provider and writes only beneath temporary directories.

### Completeness

- User request: review the current repository. Completed a review of the
  working diff and selected core paths, with five executable reproductions.
- No task-specific BRIEF.md or implementation acceptance checklist was given.
- Truthful state of the changed model defaults: exposed, not release-verified
  by this review. Request compatibility and output quality were not tested
  against live providers.
- The untracked model comparison manifest remains
  `prepared_awaiting_api_credentials`; it is preparation, not benchmark evidence.
- Validation limits: Docker integration, live deployment, browser behavior,
  live generation, and every experimental graphic-novel script were not
  exercised. This is not a certification of every repository path.
- Placeholder audit: no blocking scaffold found in the inspected paths;
  confirmed defects concern destructive cleanup, incomplete-output acceptance,
  and stale-artifact reuse.

### Structural Assessment

- Architecture: stage modules and file-backed artifacts give clear ownership;
  the observed defects occur where completion and freshness cross stage
  boundaries.
- Abstraction: truncation handling is duplicated between group and standalone
  drafting and depends on provider-specific strings.
- Semantic families: the two draft paths disagree on failure status; alignment
  and audio reuse independently treat existence as sufficient evidence of
  validity.
- Integrity: incomplete or obsolete artifacts can be reported as current;
  packaging can destroy inputs outside its selected output directory.
- Scope: existing user changes were preserved. This review added only this
  audit and its isolated reproduction script.

### Forward Impact

These issues can obscure model comparisons: an apparently successful run may
include truncated prose, and review or audio output may still reflect a prior
draft. Central completion-status normalization and artifact fingerprints would
make future model migrations and revision rounds easier to verify. Packaging
needs explicit input/output separation before broader automation.

### Remediation Mapping

- Protect packaging source/destination paths and stage output before replacing
  existing packages (finding 1).
- Unify draft completion checks and retain failure status when reading group
  members from disk (findings 2–3).
- Make alignment reuse depend on current source/draft content (finding 4).
- Make audio reuse depend on content and synthesis configuration, preserving
  accurate provenance (finding 5).

## 2026-10-14 — Product Goal Clarification

### Scope

The user clarified that the intended product is a mostly AI-driven book
abridgment pipeline, with optional audiobook and graphic-novel production and
a human review system. This expands the architectural assessment beyond the
five concrete correctness findings above. It does not authorize implementing
new features or running paid generation.

### Assessment

- Abridgment has an end-to-end driver for preparation, generation, criticism,
  repair, and assembly (`scripts/full_pipeline.py:1`).
- Human review supports source/draft comparison, comments, and AI-assisted
  incorporation of feedback (`forage/webapp/app.py:1`,
  `forage/review_apply.py:139`). The inspected review surface addresses prose;
  it does not provide equivalent audio-timestamp or graphic-panel review.
- Audiobook generation is exposed as an optional CLI stage
  (`forage/cli.py:622`, `forage/audiobook.py:157`), with the reuse defect already
  recorded above.
- Graphic-novel work has substantial storyboard, coherence, image QA,
  lettering, and packaging components. Its storyboard entrypoint explicitly
  identifies itself as outside the shipping abridgment pipeline
  (`scripts/graphic_novel_experiment.py:1`); frame packaging is a separate script
  (`scripts/package_graphic_novel_frames.py:1`).

### Recommended Direction

The repository has the major functional pieces. The next architectural priority
is reliable coordination: record input/output revisions and stage outcomes,
invalidate dependent artifacts after corrections, and make optional output
branches resumable through a consistent entrypoint. Human review checkpoints
should be configurable, with corrections traceable to the relevant text,
narration, or panels. These are design recommendations, not additional
reproduced defects or a claim that the existing system is release-verified.

The five confirmed defects should be addressed before relying on automated
reruns or model comparisons. Extend verification to generation failure,
revision propagation, and output reuse as those fixes are implemented.

No additional tests or paid stages were run for this clarification; this
assessment is based on reading the entrypoints and artifact consumers.
