# M2 handoff to hosted review integration

M2 is implemented and verified offline. No remote publication or live creative
quality is certified. M3 owns hosted transport, feedback sync and media review UI.

## Entry points and mutation ownership

- `production.plan_production(book, options=None) -> dict`: read-only/free preview.
- `production.run_production(book, options=None) -> dict`: executes shared stages
  under `production_state.book_lock(book)` and returns book_id, execute, outputs,
  success, failed_stage, stages, text_revision, review_revision. Stage results
  contain status, reason and optional metadata. Failed stages block dependents.
- Options are dictionaries resolved by `resolve_options`. `outputs` accepts text,
  audio, graphic (text is implicit). Default quality is coherence plus bounded
  repair; `iterate` is opt-in. CLI `forage run --help` exposes normal configuration.
- Preview is the default CLI behavior; `--execute` is the explicit spending
  boundary. `scripts/full_pipeline.py` is a thin shared-runner wrapper.
- `checkpoint_before_media` defaults false. If enabled, `continue_revision` must
  match the current text SHA-256. Stored acknowledgment is invalid after edits.
- `load_book(id, workspace=None, create=True)` supports explicit workspace and
  environment roots; preview uses create=False. Installed resources are immutable
  and writable artifacts/replay cache live in the workspace.

`production_state.json` is private execution state. Atomic records distinguish
original generation input/request/check hashes from current accepted text.
Successful prose edits, including `review_apply` changes to checks metadata,
are retained without redrafting or reapplying quality repair solely due to the
edit. The next run refreshes assembly/criticism/alignment and selected media.
M3 can call existing review_apply then run_production; no ledger reset or hidden
adoption is required for a previously successful run. Legacy drafts require
explicit adopt_existing, valid required checks/prose, and user-adopted provenance.

Draft provenance follows chapter membership across merged, split or renamed
generation groups. Known members are archived and regenerated when their unit
changes; an unknown existing member still requires explicit adoption.
An existing group ID does not confer ownership of newly added chapter files:
unknown members block reuse/regeneration before any member is archived. Explicit
adoption validates the complete expanded unit, preserves its bytes and records
user-adopted provenance; missing or incomplete drafts/checks fail without archival.

Preparation fingerprints only metadata consumed by its text stages. Changing audiobook voice,
model or chunk settings preserves accepted prose and refreshes selected audio
and its publication descendants; unrelated publication metadata does not redraft.

Optional signature iteration requires a completed provider response with matching
segment/critic identity, an explicit pass/regenerate verdict, summary and validated
findings. Error/refusal, missing fields, malformed findings or incomplete provider
completion fail the quality stage and block new snapshots. Valid editorial holds
remain visible quality results and are distinct from technical failures.

## Portable media index

`work/BOOK/media_manifest.json` has version=1, book_id, text_revision (64-char
SHA-256), targets list. Each target has stable path-free id, kind (`audio` or
`graphic`), title, revision (content plus semantic binding SHA-256), path (relative
to artifact root), sha256, mime_type. Optional segment_id, text_path/text_sha256,
duration_seconds, frame/page identities are preserved. Unknown duration is null;
audio comment timestamps are chunk-local. Audio IDs use `audio-NNNN`; graphics
use `graphic-SEGMENT-NNNN`.

`media.validate_media_manifest(index, root, verify_files=True) -> dict` validates
the schema and optional files, returning the original index; invalid input raises
ValueError or OSError. It confines paths after symlink resolution. MIME types are
restricted to expected image/audio media. Producer-specific revision formulas
are allowed; consumers compare revision values rather than recomputing them.
Targets come from current producer manifests, never directory globbing. Removed
IDs disappear from this index even when obsolete cached files remain on disk.

The integrated audio path produces MP3 (all chunks, optional combined output)
from the current work abridgment. `audio-chunks-only` is explicit complete mode;
combined mode fails if ffmpeg/combination fails. Graphics cover all selected
positive-target diegetic chapters, including short chapters, with one full-page
lettered frame per consecutive prose unit and PDF/contact sheets. OpenAI art
and storyboard transports are real adapters and were tested with mocks.

## Immutable local publication APIs

`publication.snapshot_revision(book, *, text_revision, outputs, media_index,
stage_summary, lock_held=False) -> dict` builds `publications/REVISION/` and
updates review_current.json. The caller either lets it acquire book_lock or passes
lock_held=True inside that lock. `outputs` is an explicit list of {path,sha256}
entries relative to book.work_dir, including assembled text, plan, alignments and
all selected media files. `stage_summary` has status=complete, selected_outputs,
stages mapping stage names to complete/reused results, and quality information.
It requires completed assembly/alignment and selected audio/graphic stages.

The returned dict is the revision manifest plus absolute local `path`,
`review_current` and `release_current` pointers. `revision.json` contains version,
book_id, revision, text_revision, selected_outputs, creation time, normalized
stage_summary and file inventory. It copies selected files (never hard-links),
keeps relative media paths, excludes source/private runtime files, validates all
hashes and rejects immutable-directory collisions/tampering. The runner strips
volatile assembly timestamps/machine paths from exported reports.

`publication.verify_revision(book, revision_id) -> dict` verifies the immutable
snapshot, all hashes, manifest identity, required review artifacts and media index
without mutation. Call this before remote transfer.

`publication.promote_release(book, revision_id) -> dict` verifies a complete
existing snapshot under the book lock and updates release_current.json. Returns
the revision manifest plus absolute local path and the `release_current` pointer. CLI: `forage release BOOK REVISION [--workspace PATH]`.
Promotion is an explicit operator decision; stored quality holds stay visible.

review_current.json and release_current.json each have version, book_id, channel,
revision, text_revision, path (`publications/REVISION`), selected_outputs, at,
and an embedded history list of the same event fields. Each pointer/history
advancement is one atomic write. Identical repeat publication does not append a
duplicate event. Release changes never overwrite review-current. Failed promotion
preserves the prior release, and historical snapshots survive later revisions.

Snapshot creation is local preparation, not a hosted upload. M3 should transport
only verified inventory assets/index and preserve published revision IDs on
feedback imports. Keep stable remote feedback identities, source revision anchors
and the review-apply ledger across duplicate pulls, edits, resolved/removed-target
feedback and subsequent releases. Do not treat local SQLite state as hosted data.

## Offline proof

Tests cover preview/execution/adoption, manual and review-apply prose edits,
source/model/prompt/split/plan/cut invalidation, group merge/split/rename provenance,
audio-only metadata invalidation with accepted prose preserved, interrupted
runs, lock contention, failed independent branches, alignment settings, optional
revision-bound checkpoint, immutable history, malformed/truncated provider
outputs, frame resume and complete media generation with mocked transports.
`tests/test_distribution.py` builds a wheel with --no-deps --no-build-isolation,
installs with --no-deps --target into a temporary directory, runs Python -I from
outside checkout with PYTHONPATH absent, proves the imported package location,
compares every prompt/spec byte, checks static assets and CLI plan, and produces
mocked graphics/PDF from installed code. Existing venv needed setuptools 68.1.2
and wheel 0.41.3 installed as build prerequisites; dev extras now declare them.

Exact final suite/help/diff outcomes are in STATUS.md and LOG.md. All generation
validation used temporary workspaces and mocked providers. No existing books/work
artifacts, commits, deployments, remote messages or live paid calls were changed.
