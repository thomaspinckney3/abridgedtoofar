# Implementation facts for M2 and M3

Read-only source inspection on 2026-10-14; no providers called and no existing
artifacts modified. This is implementation context, not a claim of runtime or
live creative-quality verification. M1 source may change these details.

## M2: actual stage APIs and ownership hazards

| Stage | Callable | Outputs and facts |
|---|---|---|
| Split | `chapter_split.split_to_disk(book)` | Writes `chapters.json`, `chapters/*.md`; supports TXT and EPUB. No freshness cache or obsolete-chapter cleanup. Reads adjacent `split_config.json` through `load_config`. |
| Classify | `chapter_classifier.classify_chapters(book)` | Calls model and writes `chapter_classifications.json`; return is classification dictionary. It does not skip merely because output exists. |
| Synopsis | `summarizer.summarize_book(book)` | Calls model, writes `book_synopsis.md` (plus chunk material for long books), returns text. Depends on chapter classifications. |
| Cuts | `cuts.generate_cuts(book)` | Calls model, writes `cuts.json`; depends on chapters, classifications, synopsis, forced-keep metadata. |
| Plan | `lean_plan.build_lean_plan(book)` | Writes `plan.json`; may call split/classify if files missing. Returns a refusal object for unsupported lengths; absence of exception does not imply usable segments. |
| Prepare | `prepare_skips.apply_skips(book)` | Mutates plan and chapter sources, writes `chapters/<id>.md.orig` backups, returns `SkipApply`. Uses `.orig` as future base. |
| Draft | `drafter.draft_segment(book, plan, sid, *, critic_feedback=None, previous_draft=None)` | Writes prose/checks and motif ledger; grouped initial drafting may reuse a nonempty file without rerunning. Solo initial drafting generally calls the model. M1 fixes completion only, not all runner invalidation. |
| Iterate | `iterate.iterate_segment(book, plan, sid, *, max_retries=..., redraft_first=False)` | Defaults to existing prose, writes snapshots and critic reports. Returns `final_verdict` and `exhausted`; failed/exhausted policies need explicit runner interpretation. |
| Coherence | `coherence.run_coherence(book)` | Reads plan and drafts; writes report with findings. Generation success differs from a clean creative verdict. |
| Repair | `coherence_fix.run_coherence_fixes(book, *, all_findings=True, pairs=None, max_retries=1, dry_run=False, ...)` | Reads report, modifies drafts/checks and snapshots; return has `pairs_failed`, `pairs_rejected`, `pairs_applied`, etc. Nonthrowing failures must fail the stage. |
| Assemble | `assemble.assemble_book(book, plan)` | Writes work AND `book.source_path.parent/abridgment.{md,txt}` whenever some prose exists. Reports partial/missing and budget overflow; not a complete-book publication gate. |
| Book critic | `book_critic.run_book_critic(book)` | Uses synopsis and assembled text; falls back to individual drafts if assembly missing. Returns verdict/counts/partial flag and writes report. Runner should require current assembly. |
| Validate | `validate.validate_book(book, plan)` | Mechanical report; clarify required errors vs advisory style/budget flags. |
| Align | `align.align_book(book)` | Returns `aligned`, `skipped`, `errors`; M1 fixes content reuse. Caller must inspect errors instead of assuming success. |
| Audio | `audiobook.generate_audiobook(book, *, voice_id, input_path=None, output_dir=None, model_id=..., ...)` | Writes audio manifest/chunks and optional published combined audio. Pass current work text explicitly: default prefers published text under books. Result includes errors/planned/generated/skipped but not combine_error; manifest carries that error. MP3 combine needs ffmpeg. |

`scripts/full_pipeline.py` is a top-level executable that parses sys.argv,
loads dotenv, and executes at import time. It runs split→classify→summarize→cuts
→plan→prepare→draft/iterate→coherence/repair→assembly→book critic, with optional
post-coherence. Do not import it as a library. Convert its CLI boundary into a
compatibility wrapper around shared runner logic while retaining documented
options. Its `--resume-drafts` uses progress events and source/target word counts,
which cannot detect same-length source changes or model/prompt changes.

Preparation mutates split/plan outputs, and repair mutates draft outputs.
Naïvely recording hashes before those mutations creates perpetual invalidation.
Use explicit immutable source snapshots/prepared inputs, or a cohesive owner for
each mutation family with final hashes captured at its boundary. On source
change, stale `.orig` backups must never replace freshly split content. Removed
cuts also need a pristine base; repeatedly applying only current cuts does not
remove old injected kernels or reset old skip flags.

Human-edited drafts must survive unchanged source/settings. Distinguish a prior
successful generated draft's request provenance from its current accepted text
revision; downstream stages use the current revision. Missing state is not
proof that existing arbitrary output is current. Adopt legacy drafts only via
an explicit documented validation policy or flag; do not silently overwrite
valuable legacy edits or bless source provenance that cannot be established.

`prompts.load_prompt` reads repository-root `prompts/<name>.md` and the drafter
reads `spec/ABRIDGMENT_SPEC.md`. `pyproject.toml` currently packages only
`forage*` and static web assets; prompt/spec/script availability in a wheel is
not guaranteed. Include runtime resources and resolve them through package
resources or an explicit workspace override; smoke-test outside the checkout.
`artifacts.ROOT/BOOKS_DIR/WORK_DIR` are currently package-location derived;
web-only FORAGE_WORK_DIR/BOOKS_DIR overrides do not configure CLI load_book.

LLM request keys include model, rendered/system/cached prompts, tokens, tools,
thinking. `llm.resolve_model_for_stage` honors stage env override then global
FORAGE_MODEL. Source fingerprints in logs are audit data, not replay-key inputs.
The runner must record effective settings, prompt/spec contents and actual
fallback model; FORAGE_REPLAY can issue live calls on a cache miss.

## M2: graphics facts

- `graphic_novel_experiment.main(argv)` produces plot/storyboard/text/image
  prompts, with page/panel layouts. Its default excerpt is only 1,600 words;
  do not treat that as whole-book graphic production. Imports policy/layout
  helpers from `scripts`, which are outside the installed package definition.
- `graphic_action_spine.py` is a separate frame-oriented adapter. The existing
  experimental tools have multiple incompatible shapes (`pages[].panels[]`
  and top-level `frames[]`). Select one documented integrated schema and stable
  IDs; reuse portable helpers with adapters rather than pretending all variants
  are a single interchangeable API.
- `letter_graphic_novel_frames.letter_frame(image_path, frame, out_path)` is a
  useful deterministic primitive. `letter_run` expects top-level `frames`,
  `generated_frames/frame_NNN.png`; writes lettered frames/layout JSON/PDF.
  Its imports depend on `scripts.letter_graphic_novel_pages`.
- Font candidates are Mac system fonts with Pillow default fallback. Linux
  execution is possible in principle, but reproducible layout requires a tested
  available font and supported Pillow fallback API; do not assume identical
  typography across machines.
- `package_graphic_novel_frames.package_frames(run_dir, *, chapters,
  lettered_dir_name, out_prefix, ...)` scans
  `chapter_NNN/<lettered_dir>/frame_*.png`, creates PDF/contact sheet, and emits
  absolute paths. Reuse image composition logic, but validate expected frame
  membership and emit portable relative review paths.
- Image prompts and image QA exist; the inspection found no integrated image
  generation callable. M2 needs a real configured image-provider adapter, not
  merely prompt export or an unconditional unsupported branch. Mock transport
  and image decoding for offline proof. Keep model/size/style/prompt and output
  hashes per frame so partial failures resume unchanged frames.
- Keep storyboard generation, art, lettering, and packaging revisions separate:
  a lettering edit should not require regenerating unchanged art. Final package
  completeness follows the manifest's expected targets, not directory globbing.

## M3: review extension points

`ArtifactStore` selects an entire book overlay when it contains alignment JSON;
otherwise it uses baked work data. It caches JSON by `(mtime_ns, size)`.
`chapter_view` renders embedded alignment paragraphs into blocks with
`anchor_hash`, and supplies chapter notes/diagnostics. No model invocation is
needed. Media should follow this same selected book root; do not fall back to
baked media when a newer overlay intentionally removed a target.

`ReviewStore` uses SQLite WAL and creates the comments table with no existing
schema-migration mechanism. Rows contain book_id, segment_id, draft_para,
anchor, quote, severity, kind, status, body, author, timestamps. `add` has an
explicit signature/INSERT list; `update` only allows mutable comment fields.
Add nullable target-kind/id/revision/timestamp fields with idempotent migration
and backward defaults. Do not force audio chunks into paragraph or chapter IDs.

App routes share `require_book`; writes use signed-session `require_write`,
publish uses `require_admin`. Payload author is ignored in favor of session
identity. `_decorate` computes scope/stale/orphaned for prose. Extend this and
`build_edits` consistently for media, while keeping prose `segments` export
unchanged. Place media feedback in a separate export collection and explicitly
filter it out of `review_apply._feedback_for_segment`/normalization.

Serve asset IDs looked up in a validated manifest, not an arbitrary URL path.
Check allowed media type and resolved containment under the selected book root,
including symlinks. Relative paths remain portable after packaging. Browser
audio playback needs normal FileResponse/range behavior; audio comments can
use chunk-local seconds and require finite nonnegative values (upper bounds
only when trustworthy duration metadata exists).

`static/app.js` uses DOM construction helper `h`, route-based renderIndex and
renderChapter, shared signed-cookie API helper, renderNote/comment composer,
and export/publish controls. Add explicit media navigation/rendering and reuse
comment lifecycle. Existing null draft_para means chapter note; media comments
must not be accidentally rendered as chapter notes by that shortcut.

`package_review_artifacts` is also used by `publish_review_book._archive_book`
and local mounted overlay installation. Extend the shared package shape with
media index and only referenced safe assets. Test the overlay path as well as
the baked layout; keep source books and replay/provider secrets out of bundles.

Review is asynchronous on a separate hosted website. Existing export endpoints
provide `/api/books/{book_id}/edits.json`; publishing that overlay locally is
admin-only, and production generation should import its export through a
configured transport instead of reading a local SQLite DB as if it were hosted.
Add import identity/revision metadata without clearing `review_apply_ledger`.
Expose pull/sync and review publication separately from public release promotion.
An external scheduler can invoke sync; no new daemon is required. Test imports
of duplicate, edited, stale, resolved and removed-target feedback, and continuing
this loop after release. Real credentials/deployment remain unverified/offline.

## Required offline proof beyond M1

Runner tests need unchanged resume, same-length source edit, prompt/model edit,
manual draft edit, missing/corrupt artifact, output membership shrink, failed
returned result, interruption, lock contention, revision-bound checkpoint,
and requested branch selection. Graphics must exercise storyboard→image bytes
→lettering→export with fake transport. Media tests need old DB migration,
timestamp validation, target/revision binding, stale/orphan distinction, auth,
path/symlink denial, packaged serving, overlays and prose-export compatibility.
Wheel install/CLI plan/resource smoke must run outside the source checkout.
