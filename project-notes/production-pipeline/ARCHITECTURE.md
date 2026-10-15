# Revision-Aware Production

Status: critiqued and revised for implementation, 2026-10-14.
Related: [requirements](PRD.md), [plan](PLAN.md),
[abridgment specification](../../spec/ABRIDGMENT_SPEC.md).

## Contract

Every reusable result needs matching authoritative inputs, relevant settings,
successful completion, and intact outputs. File existence alone is insufficient.
Provider completion reasons are normalized at the LLM boundary. The stage that
produces an artifact owns its validation; consumers must not infer success from
nonempty files or reconstruct missing provenance.

The flow is source/preparation → drafting/repair → assembly/criticism, followed
by optional audio and graphic branches. Alignment provides the prose review
view. Review happens asynchronously on a separate website; an explicit optional
checkpoint can stop before expensive downstream stages.
Resume preserves human-edited drafts, while source or generation-setting
changes invalidate the stages whose inputs changed.

## Ownership

- Existing stage modules own their generation and format validation. Shared
  completion checks prevent standalone/group drafting divergence.
- A production-state module owns content/settings fingerprints, atomic state
  writes, stage status, output verification, and a per-book run lock. It does
  not generate book content or decide prose quality.
- A runner owns dependency ordering and failure/checkpoint propagation. It
  calls existing stage APIs, records the actual provider/settings used, and
  keeps CLI plan inspection free of paid work.
- An integrated graphic module owns a stable storyboard/frame manifest,
  provider calls, resumable frame generation, deterministic lettering, and
  export. Existing experimental scripts stay usable; reusable helpers may be
  moved into the package with compatibility imports where appropriate.
- A publication/sync boundary owns immutable revision IDs, review/release
  manifests, configured transport, and import deduplication. It does not judge
  creative quality or turn a review upload into a public release.
- ArtifactStore owns read-only discovery of text and media review artifacts.
  ReviewStore owns comments and their revision anchors, including media target
  identifiers. No model SDK is required to serve packaged review data.
- Packaging owns generated deploy artifacts only. Resolved input/output
  overlap is rejected before any destructive operation. Existing content is
  replaced only after a complete staged package has been built.

## State and Failure Rules

Use explicit pending/running/complete/failed/waiting-review states with input
fingerprints and output hashes. Interrupted running records are retryable;
failed output is not reused. Do not skip upstream validation because a final
export exists. A preview must not overwrite real artifact provenance.

Manual draft edits are downstream inputs; they must trigger fresh assembly,
alignment, audio, and graphics without forcing an unchanged-source draft to be
overwritten. A source change does require a fresh draft. Relevant prompt and
model settings belong in request fingerprints.

Media review indexes use safe relative file paths and stable target ids plus
content revision hashes. Audio targets include finite nonnegative timestamps;
graphic targets identify the frame/panel. Missing targets become orphaned;
revision changes become stale. Media comments must never be accidentally
consumed as paragraph-edit instructions.

## Common Change Patterns

- New stage: implement and validate its outputs, declare dependencies and
  settings, register it with the runner, add CLI/docs and resume/failure tests.
- Changed source/draft/settings: compare authoritative fingerprints, execute
  only affected stages, refresh review indexes and downstream provenance.
- New review target: update producer/index schema, ArtifactStore, comment
  validation/storage/export, client rendering, packaging, and security tests.
- Packaging changes: validate resolved boundaries first, stage complete
  artifacts, replace owned outputs, test failure preservation and overlays.

## Preparation and Publication Boundaries

`prepare_skips` mutates split chapter text and plan.json, and repair mutates
drafts. These cannot be independent immutable DAG outputs with hashes captured
before their consumers edit them. Preserve pristine prepared inputs, or group
each mutation family under one owner and record final hashes at its boundary.
Refresh `.orig` backups when source changes so old text cannot overwrite new
splits. Reapplying changed cuts must also remove previously injected kernels.

Generation-request provenance and accepted draft revision are separate facts.
An unchanged valid request may retain a human-edited draft; downstream work uses
the current prose hash. Missing provenance cannot prove a legacy draft came
from current source. An explicit adoption/validation policy must protect such
drafts without silently blessing them or overwriting them.

The runner validates all required drafts before assembly, because existing
standalone assembly deliberately writes partial work and published copies.
Stage adapters inspect returned failures/refusals as well as exceptions. A
critic's completed report and a creative-quality approval are different states.

Review publications identify immutable text/media revisions and exported
feedback preserves those anchors. Repeated remote imports merge stable comment
IDs and update changed records while preserving the review-apply ledger. The
normal loop is generate → publish review → asynchronous comments → import →
apply eligible feedback → regenerate → republish. It does not pause by default.
Public release is an explicit promotion of a complete selected revision, with
separate release history. Subsequent feedback remains permitted after release.
Transport is configurable and callable from CLI; offline tests replace remote
I/O. This task does not execute a deployment or schedule a live sync job.

## Missing Data and Forbidden Fallbacks

- Missing/corrupt provenance or output is not successful reuse; preview must
  never create a successful stage record or overwrite generated provenance.
- A source/settings change cannot be hidden by an existing draft/group file.
- A partial audio/graphic directory is not a complete selected output branch.
- A media target omitted from a newer whole-book overlay must not fall back to
  old baked media. Serve only validated manifest IDs and confined relative paths.
- A stale imported comment must not be silently rebound to current prose.
- Two sibling directory renames are not one atomic transaction. Packaging must
  stage, back up and roll back on failure, and describe crash limits truthfully.

## Critique Outcome

Ready for implementation; no new human approval gate. The concrete ownership,
failure and proof ambiguities above are resolved in this contract and the M1
brief. Source/API facts are in [IMPLEMENTATION-NOTES.md](IMPLEMENTATION-NOTES.md).
Remaining implementation choices: legacy draft adoption UI, publication
transport configuration, integrated graphic schema, and installed resource
layout. These are bounded engineering decisions, not reasons to defer the
authorized outcomes. Live provider quality and hosted deployment remain
explicitly outside offline proof.
