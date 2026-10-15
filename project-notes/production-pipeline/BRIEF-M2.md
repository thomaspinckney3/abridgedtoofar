# Task Brief: M2 — Resumable production and optional outputs

## Objective and Boundary

Deliver one usable CLI workflow for reliable text production, optional real
audio/graphic generation, and local versioned review/public-release snapshots.
M3 adds hosted publication/feedback transport and the media review UI. M2 must
provide real callable implementations and the portable artifacts M3 consumes.
No live generation, deployment, remote mutation, commits or resets in this task.

Read README.md, CLAUDE.md, pyproject.toml, PROJECT.md, ARCHITECTURE.md, PLAN.md,
STATUS.md and IMPLEMENTATION-NOTES.md. Those are the package onboarding sources;
Nova compiler instructions do not apply. M1's BRIEF.md is immutable during its
audit. M1 baseline is 278 passed, 6 Docker skipped; inspect the audit result before
changing overlapping M1 code. Preserve model-default edits and book/work data.

## Acceptance Criteria

1. `forage run BOOK` previews the plan without paid work or changing completion
   provenance; an explicit execution option runs it. Output selection includes
   text, audio and graphic (text is the dependency of either media branch).
   Configuration/help exposes providers, relevant models/settings and workspace.
   Plan output explains reused/pending/stale/failed stages and why.
2. Shared library orchestration calls existing text functions in dependency
   order and handles refusals, returned errors, missing/corrupt outputs and
   exceptions. Required draft incompleteness stops before assembly/media;
   nonzero CLI exit and failed state identify the offending stage. A completed
   critic report may contain a quality hold; expose it without calling it a
   technical generation failure or silently treating it as approval.
3. Atomic state writes and a process-safe per-book run lock prevent concurrent
   runner/publication mutations. A dead/interrupted running record is retryable;
   missing/corrupt outputs cannot be skipped. Unchanged successful runs make no
   LLM/TTS/image calls. One failed optional branch does not erase valid artifacts
   in another branch; dependent work and snapshot completion remain blocked.
4. Hash actual inputs/settings, not mtimes or word counts. Same-length source,
   split-config, effective model, prompt/spec, cut/plan or synthesis changes
   invalidate their affected work. Preparation/repair must not self-invalidate
   forever by modifying another stage's hashed outputs. New source cannot be
   overwritten by stale `.orig` backups; removed cuts remove old injected kernels.
5. An edited successful draft is an accepted text revision when its generation
   inputs remain unchanged. Keep its bytes on resume; refresh assembly,
   alignment and selected media. Do not automatically repair it again solely
   because its own output hash changed. Preserve older drafts before source/
   generation-setting changes require regeneration. Legacy files with no
   provenance need an explicit documented adoption path; never silently infer
   their source/model provenance or destroy them.
6. Audio uses M1's generator with current work text explicitly, validates all
   result counts and manifest output hashes, and reports combination failures.
   Chunk-only output is a documented configurable mode; requesting combined
   audio cannot silently succeed when ffmpeg/combine fails. No arbitrary partial
   limit is a complete audiobook. Alignment errors also block review completion.
7. Graphics run storyboard → image-provider bytes → deterministic lettering →
   PDF/contact-sheet (or comparably usable documented export), for the selected
   full abridgment/chapter set. No implicit 1,600-word excerpt or prompt-only
   success. Validate storyboard targets and decoded images. Provider/model/style/
   size are configurable; image generation is a real adapter with mockable I/O.
   Interrupted/failed frame generation resumes valid frames without repayment;
   lettering-only changes retain valid art, and removed frames leave the index.
8. Successful selected outputs produce a validated portable media index and
   immutable local revision snapshot. Review publication and public release have
   separate pointers/history; snapshot preparation is not a remote publication.
   Explicit release promotion verifies the chosen complete revision's hashes;
   failed promotion preserves the prior release. Subsequent draft/review revisions
   and releases do not mutate historical snapshots or prevent ongoing feedback.
9. `scripts/full_pipeline.py` becomes a thin compatibility CLI over the same
   runner. Document defaults and map documented iterate/coherence/repair/pair/
   resume options accurately; invalid or deprecated unsupported options fail
   before paid work. No option may be silently ignored and no second stage loop
   remains. Existing standalone CLI stage commands stay usable.
10. Installed-wheel use works outside the checkout with a configured workspace;
    prompts, abridgment spec, graphics helpers and static assets are available.
    Neither artifacts nor replay cache are written into site-packages. Source
    fingerprint/audit paths use the same real resource contents as generation.
11. Offline tests prove all criteria and existing tests pass. README/help explain
    the actual automatic/asynchronous review lifecycle, cost boundary, adoption,
    resume and explicit release behavior. Record commands and truthful limits.

Maps to PROJECT AC5–AC7, M2 portions of AC9–AC12, and runner/optional-output/
distribution/local-publication rows. M3 retains hosted sync, media comments and
web/package integration; do not claim those complete here.

## Suggested Module and Interface Boundaries

Names below are concrete defaults, not a request to ask the user about routine
names. Implement the smallest cohesive functions; avoid a general workflow engine.

- `forage/production_state.py`: canonical JSON/content hashing, schema validation,
  atomic record writes, output verification and per-book lock. Stage records
  contain schema/stage version, status, input/settings digest, output path/hash
  inventory, actual provider metadata, error and timestamps. Timestamps never
  participate in content identity. It owns no generation or editorial judgment.
- `forage/production.py`: `plan_production(book, options)` and
  `run_production(book, options)` returning structured stage results. Own stage
  ordering, adapters for existing functions, result validation, summary/exit
  mapping, current accepted text revision and the lock. Config must be resolved
  once and passed explicitly, including requested output set.
- `forage/media.py`: small shared schema/validator for review targets and confined
  relative asset paths. Main worker owns it before delegating consumers.
- `forage/graphic.py` plus package-owned lettering/image helpers:
  `generate_graphic(book, *, text_revision, options) -> result` owns storyboard,
  art, lettering and export manifests, with injected/mocked provider boundary.
  Return output inventory and media target records; do not write global runner
  state, CLI registration or publication pointers from this module.
- `forage/publication.py`: `snapshot_revision(book, *, text_revision, outputs,
  media_index, stage_summary)` and `promote_release(book, revision_id)` validate,
  snapshot and atomically update separate local pointers/history. Reuse shared
  hashing/path rules; no model or remote calls. Accept explicit inventories,
  not arbitrary recursive work-directory copies.
- `forage/resources.py` or equivalent: workspace paths and immutable packaged
  resource resolution. Extend artifacts/prompts/llm/source_fingerprint/report
  consumers where required. Explicit workspace → existing env roots → documented
  local default; code resources and writable workspace are distinct concepts.
- `forage/cli.py`: thin option parsing and presentation for run/graphics/local
  snapshot/release commands. Main worker also owns compatibility script and docs.

The implementation worker may delegate the graphic adapter and local publication
lifecycle to focused child agents under the orchestrate workflow. Give each child
exclusive new module/helper/test files. Main owns state/runner/media schema/CLI/
resources/pyproject/README/STATUS; children return requested shared edits instead
of racing them. Agree the above return shapes first, then integrate and test.

## Hashing, Mutations and Resume Approach

Use canonical UTF-8 JSON (sorted keys, fixed separators, reject nonfinite values)
and SHA-256 of exact bytes; manifests hash sorted relative path/hash inventories.
Exclude timestamps, absolute paths, request duration and diagnostic counts from
revision identity. Include schema/algorithm version and effective options,
including stage/global model overrides and prompt/spec bytes. Capture actual
fallback provider and generation request metadata without leaking credentials.

Keep generation identity separate from accepted-text identity. Each draft/group
records its immutable source/prepared-plan/prompt/model input signature and
original generated output hash; current valid prose gets a distinct accepted
hash. Manual edits with unchanged generation inputs advance only accepted hash
and descendants. Changed provenance triggers archived regeneration. A group is
one generation unit; changed group inputs must bypass M1's valid-on-disk reuse,
not call draft_segment and falsely record the old group under new provenance.

Record mutable context (prior drafts/motif ledger) actually used for generation,
but do not recompute it from the final complete book and invalidate every draft
on resume. Treat that context as a generation snapshot, with a documented
regeneration rule; future or human-edited drafts do not silently become a new
initial-draft request. Quality repair similarly owns its final accepted result
and runs when its upstream inputs/config or explicit repair request changes.

Preparation needs a pristine split/plan base before applying skips. Either use
owned immutable intermediates or a preparation adapter whose subrecords track
pre-mutation snapshots and final prepared outputs. Avoid hashing mutable
chapters.json/chapters/plan files as if no later step changes them. Validate the
current manifest's members; orphaned old files do not satisfy missing new IDs.

For legacy adoption, an explicit `--adopt-existing` can validate current required
drafts/checks against current prepared plan and record them as user-adopted,
not provider-generated. Preserve prior files; report missing provenance in plan
and the precise action needed. No interaction or permission prompt is required.

Default review is asynchronous. If implementing the planned optional checkpoint,
bind continuation to the accepted text revision; a changed revision must not
reuse a previous acknowledgment. Do not make a synchronous checkpoint mandatory.

## Portable Media and Publication Contract for M3

Write `work/<book>/media_manifest.json` with version, book_id, text_revision and
`targets`. Each target has stable `id`, `kind` (`audio` or `graphic`), title,
optional segment_id, content `revision`, relative `path`, SHA-256 and MIME type.
Audio targets represent chunks and may include text path/hash and trustworthy
duration_seconds; absent duration remains null, not invented. Comments will use
chunk-local seconds. Graphic targets represent individual lettered frame/panel
images, with storyboard frame/page identity and source text revision. A target
revision must change when its content or semantic binding changes. File path
and timestamps alone are not revision identifiers.

Paths resolve relative to the book artifact root and must be confined after
symlink resolution. Stable IDs do not contain paths. Changing/removing targets
changes the current manifest; M3 can distinguish stale IDs from orphaned IDs.
Use verified producer manifests; do not glob leftover audio/images into review.

Local immutable snapshots can live under `work/<book>/publications/<revision>/`
with `revision.json` containing version, book_id, revision, text_revision,
selected outputs, creation time, stage/quality summary and file path/hash list.
Copy selected text, plan/alignment/checks needed for review and media assets;
rewrite paths for that snapshot root. Exclude source books, replay caches,
credentials and SQLite queues. Build in staging, verify all content, then expose
the immutable directory and update a separate review-current pointer. Repeating
identical content yields the same content revision. Adding optional outputs can
produce a new publication revision while retaining the same text_revision.

Release promotion points at an existing complete verified snapshot and appends
release history, leaving review-current independently editable. A stored hold
verdict remains visible; the explicit promotion is the operator's decision and
must not claim an automatic creative-quality guarantee. Historical
standalone `books/.../abridgment.*` copies remain compatibility outputs, not an
implicit new public-release operation. M3 will publish this snapshot/index and
attach imported comment anchors to these immutable revision identities.

## Existing Files to Reuse or Adapt

- `artifacts.py`, `chapter_split.py`, `chapter_classifier.py`, `summarizer.py`,
  `cuts.py`, `lean_plan.py`, `prepare_skips.py`: actual preparation APIs, including
  plan refusal and mutable `.orig` behavior described in IMPLEMENTATION-NOTES.
- `drafter.py`, `iterate.py`, `coherence.py`, `coherence_fix.py`, `assemble.py`,
  `book_critic.py`, `validate.py`, `align.py`: existing stage functions. Check
  structured return status rather than exception-only success. Don't call an
  implicit upstream generation path from zero-cost plan inspection.
- `audiobook.py`: M1 manifest has `request_sha256`, `audio_sha256`, `audio_size`
  per successful chunk; preview lives separately. Result now exposes
  combine_error; inspect it as well as chunk errors when combined output is
  requested. Preserve M1 tests.
- `graphic_action_spine.py` offers frame-based generation/validation;
  `letter_graphic_novel_frames.letter_frame` and shared page lettering helpers
  are portable candidates. The action-spine CLI and page storyboard CLI differ.
  Promote only needed helpers into `forage` with compatibility imports as needed;
  do not import script CLI side effects from installed runtime code.
- `package_graphic_novel_frames.py`: usable PDF/contact-sheet ideas, but globbing
  and absolute paths need the new manifest contract. Test Linux font fallback.
- `prompts.py`, `source_fingerprint.py`, `llm.py`, `cache_audit.py`, `report.py`,
  `pyproject.toml`, `prompts/*.md`, `spec/ABRIDGMENT_SPEC.md`: installed resource
  and writable workspace paths. Preserve the user's prompt/model edits. Use one
  authoritative prompt source or build-generated package resources with equality
  checks; do not create manually maintained divergent prompt copies.
- `scripts/full_pipeline.py`, `cli.py`, `README.md`: one shared execution path,
  public options and honest compatibility documentation.

## Validation and Completion

Add focused tests such as test_production_state, test_production_runner,
test_graphic_production, test_publication and test_distribution. Mock provider
transports and existing stage generation where appropriate; also exercise real
deterministic assembly/manifest/lettering/package paths with tiny temporary data.
Include an end-to-end fake-provider run through both media branches, failure and
resume, then edit prose and prove no draft regeneration but fresh descendants.

Test same-length source edits, changed model/prompt, removed cuts/frames, missing
or tampered output, refusal/returned error, interrupted state, lock contention,
group invalidation, legacy adoption and repeat unchanged resume. Publication
tests cover immutable bytes, distinct review/release pointers, no partial release,
failed-promotion preservation and a later revision after release. M3 media
consumer tests can use the same manifest fixture.

Run focused modules, then `.venv/bin/python -m pytest -q` at the M2 gate. Run
`.venv/bin/python -m forage.cli --help`, new subcommand help, legacy script help
and `git diff --check`. Build a wheel without live dependency resolution (e.g.
`python -m pip wheel --no-deps --no-build-isolation` into a temporary directory),
install it in a temporary environment using available dependencies, change cwd
outside the checkout and unset PYTHONPATH. Verify the imported package comes
from that installation, load actual prompts/spec, invoke CLI plan against a tiny
temporary workspace, and exercise graphics resources without paid calls. Record
the exact successful commands; an import from the source tree is not this proof.

Stay alive until foreground tests finish. Main worker updates STATUS with final
`[done] M2`, test counts, installed-package proof and limitations; update PLAN
completion rows. No commits are required. No declared regressions or blocking
open questions: resolve routine options/schema names within these contracts.
