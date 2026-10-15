# Implementation Plan

## Objective

Deliver the four user-approved improvements as cohesive, locally verifiable
changes. All execution tests use temporary artifacts and mocked external calls.

## M1 — Correct artifact safety and completion (done; independently audited)

- Fix all five repository findings in packaging, LLM/drafter, alignment, audio.
- Add regression tests proving correct behavior and preserving existing APIs.
- Update the old reproduction script so it is clearly historical or replaced
  by links to permanent regression tests; do not leave it claiming fixed bugs.
- Proof: focused pytest tests for the five fixes, then the owning full suite.
- Independently useful outcome: existing commands stop losing inputs or
  accepting truncated/stale artifacts.

## M2 — Unified resumable production with optional outputs (done; independently audited)

- Measure existing stage cache/overwrite behavior and graphic helper contracts.
- Add atomic revision/state handling, lock, and dependency-aware run planning.
- Expose a zero-cost CLI preview and explicit execution, output selection, and
  optional pre-media checkpoint. Default review is asynchronous, not blocking.
  Preserve existing CLI commands.
- Execute the text stages through shared functions; keep legacy full-pipeline
  entrypoint compatible while avoiding a second divergent orchestration path.
- Integrate optional audio and complete graphic generation/export with
  configurable providers and per-frame resume. Include required package data.
- Define revision manifests and distinct review-publication/public-release
  state. Include local publication preparation and explicit release promotion;
  M3 connects the hosted feedback loop and media review surface.
- Test manual edits, source/prompt/model changes, missing/corrupt outputs,
  provider failures, interrupted runs, checkpoints, and selected branches.
- Proof: targeted runner/graphic/CLI tests plus package smoke verification.
- Independently useful outcome: one command coordinates reliable production.

## M3 — Media-aware human review and final integration (done; independently audited)

- Expose audio playback and graphic-panel inspection in the existing review UI.
- Add validated revision-anchored media comments, SQLite migration, stale/
  orphan detection, and export without changing prose comment semantics.
- Serve media via confined paths; preserve authentication and origin guards.
- Extend packaging and overlays to include media manifests/files when present.
- Add explicit CLI review-publication and configured remote feedback import/sync
  operations using reusable transport boundaries. Deduplicate imported feedback,
  preserve revision anchors and apply ledger, and republish updated revisions.
  Test continued review/republication after explicit public release. Do not
  perform a live deployment, remote mutation, or schedule installation here.
- Update README/help, project audit, and a completion matrix with exact proof.
- Proof: media API/store/package tests, client syntax/browser checks when
  available, complete pytest suite, CLI help/plan and installed package smoke.
- Independently useful outcome: human review covers all produced formats.

## Completion Matrix

| Contract | Proof required | State |
|---|---|---|
| Safe package replacement | overlap/symlink/input failure/old-output tests | done; independent M1 resolution audit passed |
| Draft completion | both providers, group/single/disk-reuse tests | done; independent M1 resolution audit passed |
| Fresh review/audio | changed content/settings and failure/preview tests | done; independent M1 resolution audit passed |
| Runner | plan/execute/resume/edit/fail/lock/checkpoint CLI tests | done; independent M2 final resolution audit passed; 509-case offline gate |
| Optional outputs | audio and storyboard/image/lettering/export tests | implemented; full selected content, offline mocked transports verified |
| Media review | storage migration, auth, timestamp/panel, stale/orphan tests | done; release-only and full media lifecycle independently audited; 680-case final gate passes |
| Hosted artifacts | package/overlay/asset confinement and serving tests | implemented; verified total archive expansion/transport/media packaging and overlay/range tests pass |
| Distribution | wheel contains runtime modules/prompts/static assets | implemented; isolated installed-wheel CLI publication/release/pull/sync/resource/graphic smoke passes |
| Asynchronous review loop | publication revision, import/dedupe/apply/republish and old-anchor tests | done; real test-HTTP A→B→C, common-planner retries and durable interrupted-apply recovery independently audited |
| Public release lifecycle | explicit promotion, history, continued review/republication tests | complete offline HTTP/local promotion, release-only feedback, historical assets and continued releases pass |

## Final M3 Remediation Evidence

The four independent M3 findings are corrected: common-planner completeness and
settings recovery; release-only feedback; bounded total decompressed archive
streams; and recoverable application intent/ledger commits with conflict guards.

`.venv/bin/python -m pytest -q` => **680 passed, 6 Docker skipped in 72.01s**.
This includes 51 additional negative regression cases beyond the prior 629 gate,
installed distribution, real HTTP lifecycle, web-only imports and interrupted
commit recovery. CLI help, Node syntax and diff checks pass. Eight TestClient
timeout deprecations are test-only warnings. Independent resolution audit passed all criteria with 165 focused tests and corrected original failure probes.
No browser tooling was available; visual behavior, live-provider quality, Docker
and deployment remain unverified. Exact contracts: [HANDOFF-M3.md](HANDOFF-M3.md).

## Validation Commands

- `.venv/bin/python -m pytest -q` (baseline 110 passed, 6 Docker skipped).
- Focused new test modules after each implementation change.
- `.venv/bin/python -m forage.cli --help` and run/media subcommand help.
- `node --check forage/webapp/static/app.js` if Node is available.
- Wheel build/install smoke in a temporary directory; no paid calls.
- `git diff --check`.

## Critique and Working Tree

- Architecture/plan critique: complete; concrete ownership and cache hazards
  are addressed in ARCHITECTURE.md and measured source interfaces recorded in
  IMPLEMENTATION-NOTES.md. M1–M3 passed independent audits; final contracts are in HANDOFF-M2.md and HANDOFF-M3.md. User clarified asynchronous hosted
  review/import/republish and separate explicit release; criteria include it.
- Existing model upgrade edits remain in place. No commits, reset, checkout,
  remote publication, or changes to existing books/work artifacts are needed.
