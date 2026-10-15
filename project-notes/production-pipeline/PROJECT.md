# Reliable Book Production Pipeline

## Summary

Build on Forage's AI abridgment pipeline and human review system to provide a
reliable, resumable workflow with optional audiobook and graphic-novel outputs.
The user authorized the four recommendations in the repository review: fix
the five defects, unify status/revisions/resume, integrate optional outputs,
and extend review to audio timestamps and graphic panels.

## Current Lifecycle Stage

Complete within the authorized offline scope. M1–M3 passed independent audits; all twelve acceptance criteria are satisfied. Live generation and deployment were not performed.

## Required Links

- Product requirements: [PRD.md](PRD.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation plan: [PLAN.md](PLAN.md)
- Prior findings: [repository review](../repository-review/AUDIT.md)

## Acceptance Criteria

- AC1: Packaging cannot delete source books or work artifacts when custom
  output paths overlap inputs, including resolved symlink paths. Failed
  packaging preserves previously published output.
- AC2: Standalone and grouped drafting reject incomplete/truncated provider
  responses consistently; disk reuse preserves recorded failure status.
- AC3: Alignment reuse requires current source and draft content. Revised
  text reaches proofreading and comment-staleness detection.
- AC4: Audio reuse requires matching text and synthesis settings and verified
  audio provenance. Preview/failure paths do not bless stale audio.
- AC5: A common CLI workflow plans and executes text with optional audio and
  graphic outputs, records stage results and revision fingerprints, resumes
  unchanged completed work, and reruns affected dependencies after changes.
- AC6: Failed stages stop dependent work with a nonzero CLI result. Partial
  output and interrupted runs are never recorded as complete. Concurrent
  writes to the same book run are prevented.
- AC7: Graphic production supports real storyboard/image/lettering/package
  execution behind explicit execution options, using configurable providers;
  it can resume without regenerating unchanged frames. No new live generation
  is needed to validate implementation.
- AC8: Human review can display/listen to produced media and attach comments
  to audio chunk timestamps or graphic panels, tied to artifact revisions.
  Comments round-trip through storage and export; changed/missing media is
  stale/orphaned. Existing prose review remains compatible.
- AC9: Media review artifacts can be packaged and served with the existing
  local/hosted overlay model. Media paths are confined to the artifact root.
- AC10: Tests cover all five regression fixes, runner success/failure/resume/
  revision changes, optional output branches, media API authorization,
  staleness, and packaging. README and CLI help describe the actual workflow.
- AC11: Review happens asynchronously on a separately hosted website. The
  pipeline prepares and can explicitly publish a versioned review revision,
  imports feedback from a configured remote export with stable IDs/revision
  anchors, applies eligible feedback once, and prepares a refreshed review
  publication. Re-import does not duplicate comments or reset the apply ledger.
- AC12: A separate explicit operation promotes a completed revision to public
  release. Review publication does not imply release. Released books continue
  accepting feedback and can publish newer revisions while preserving release
  history. Local commands and mocked transports prove this lifecycle; this
  session performs no live deployment or remote mutation.

## Scope and Constraints

- Preserve pre-existing model-default edits and comparison artifacts.
- No live LLM/TTS/image calls, deployment, remote messages, or publishing.
  Use isolated fixtures and mocked providers for verification.
- Existing text stage functions and graphic tooling should be reused where
  their contracts fit. Do not reproduce the experimental script collection
  wholesale or introduce a second competing text pipeline.
- Human review happens asynchronously on a separately hosted website. The
  pipeline continues automatically unless an operator requests a checkpoint.
  Review publication and public release are separate explicit operations.
- Local commit authorized by the user on 2026-10-15 for the completed working
  tree, including preserved pre-existing changes. No remote push was requested.
- Nova-specific compiler/build workflows in installed skills do not apply to
  this Python repository. README.md, CLAUDE.md, pyproject.toml, and the existing
  abridgment specification are the local authorities.

## Validation

Baseline: `.venv/bin/python -m pytest -q` => 110 passed, 6 Docker tests skipped.
Live-provider quality and deployed release behavior are outside offline proof
and must be reported as unverified rather than claimed complete.
