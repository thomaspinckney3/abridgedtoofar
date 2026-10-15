# Task Brief: M3 — Hosted review, feedback sync and public release

## Objective and Inputs

Complete the asynchronous loop: publish a verified revision to the separate
review website, collect prose/audio/panel comments, fetch and apply eligible
feedback, regenerate and republish, explicitly release a chosen revision, and
continue the same loop after release. Implement real CLI/client/server paths;
test with temporary storage, TestClient and fake providers. Do not run live
paid requests, deploy, mutate a remote site, schedule jobs, or commit.

Read README.md, CLAUDE.md, pyproject.toml, requirements-web.txt, PROJECT.md,
PRD.md, ARCHITECTURE.md, PLAN.md, current STATUS/AUDIT and HANDOFF-M2.md. Re-read
the final M2 handoff after integration: its current marked-in-progress contract
is the planning baseline, not permission to overwrite concurrent M2 changes.
This brief does not modify M1/M2 artifacts or production code during planning.

## Acceptance Criteria

1. Operational CLI commands publish a selected verified local revision to a
   configured HTTP review site or local hosting root, fetch feedback, and
   explicitly publish a public release. Local snapshot creation remains distinct
   from confirmed remote publication. Non-successful transport, verification or
   pointer updates produce nonzero exit and preserve prior successful state.
2. This webapp implements the matching hosted upload/pointer/export endpoints;
   it can accept a first book without requiring pre-existing alignments. Uploaded
   snapshots are immutable and independently verified. Review and release
   pointers/history are separate; replacing either never deletes comments,
   imported/application ledgers or historical revision bytes.
3. Visitors can view/download the current public release and identify its
   revision, while reviewers can use the newer review revision. New review
   publication does not advance public release. Release/history remain usable
   after later feedback, regeneration and explicit newer release.
4. Audio playback and graphic frame/panel inspection are reachable in the UI.
   Users can post audio comments at chunk-local seconds and graphic comments
   against a stable target ID. Comments can be edited/resolved/deleted/exported;
   old prose/book/chapter review remains compatible. No SDK or generation is
   required on the hosted server.
5. Comments persist original publication/text/target revision anchors. Client
   submits the revision it actually viewed; server validates it rather than
   attaching the comment to whichever artifact is current at POST time. Changed
   target means stale; missing target means orphaned. Audio time is finite,
   nonnegative and within duration when known; booleans/NaN/infinity are invalid.
   Missing duration is not fabricated. Media comments never become prose edits.
6. Feedback export/import retains stable source/comment IDs, original anchors,
   note, author, creation/update timestamps and status. Repeated identical pulls
   do not duplicate or reprocess feedback. Changed/resolved/deleted remote
   comments reconcile without deleting historical local application decisions.
   An interrupted/invalid import leaves prior complete import usable.
7. Pull is free of model calls. Explicit apply/sync execution uses the existing
   constrained prose review-apply stage and its durable ledger; it filters media,
   stale, orphaned and inactive imported feedback. Local freshness is checked
   against current draft bytes, not merely the remote server's stale flag or
   cached alignment. Eligible changes rerun M2 descendants without redrafting
   accepted prose, and a republish option uploads the new verified revision.
   Repeating the unchanged full cycle is idempotent. Public release stays explicit.
8. Admin auth is required for artifact upload and pointer promotion; reviewers
   cannot publish/release. Existing origin/host/session/rate guards remain.
   Files are served only through validated inventories/target IDs with resolved
   root confinement. Malformed archives, path escapes, duplicate entries,
   symlinks/hardlinks/devices, extra files and hash/book/revision mismatches are
   rejected before pointer changes. Bounded upload/expanded-size/file-count
   limits prevent an archive from exhausting the host.
9. Local, baked and mounted-overlay media work. A current whole-book revision
   that removed a media target never falls back to an older baked target.
   Packaging includes only verified referenced assets/indexes and preserves M1
   overlap/rollback guarantees. Installed runtime imports no `scripts` modules.
10. Complete offline tests, UI syntax/browser proof where available and installed
    package smoke pass. A web-only import/start/request test succeeds without
    anthropic/openai/Pillow and other pipeline-only dependencies. README/help
    document credentials/config, all commands and the asynchronous lifecycle.

These complete PROJECT AC8–AC12 and final integration of AC1–AC7. No additional
user approval is required for this implementation and its offline verification.

## Existing Contracts and Concrete Gaps

- M2 `publication.verify_revision(book, revision_id)` verifies the exact snapshot
  inventory and identity; `snapshot_revision` and `promote_release` maintain
  independent local pointers/history. Reuse these checks, rather than accepting
  client `status=complete`. Hosted verification must not need an original book.
- `media.validate_media_manifest(index, root, verify_files=True)` validates
  version=1 targets with stable id, kind, path/hash/MIME and target revision.
  Paths are relative to the selected book artifact root. Audio time is local to
  its chunk. M2 `production_state` provides hashing, atomic writes and book lock.
- The current app has cookie login, admin/reviewer roles and public reads. It
  has no revision upload, remote-release, or authenticated publishing transport.
  Existing `POST .../publish` writes edits.json; do not repurpose it ambiguously.
- ArtifactStore currently chooses a whole-book alignment overlay, otherwise
  baked data. Add hosted immutable revision selection ahead of that fallback;
  pin the selected root for each response so a pointer switch cannot mix views.
- ReviewStore's comments table has no explicit migration mechanism. Add an
  idempotent migration; its durable DB must stay outside publication directories.
- `build_edits` currently exports current paragraph text, omits original anchor/
  revision, and filters open/accepted rows. `_decorate` only understands prose.
  Preserve original revision-bound context and extend both consistently.
- `review_apply` normalizes every item in `segments` and `book_comments`; its
  fingerprint excludes current paragraph/staleness deliberately. It does not
  itself reject imported stale/media feedback. Add an explicit eligibility
  boundary without destroying existing local overlay compatibility or ledger keys.
- requirements-web intentionally excludes model SDKs/Pillow. Server modules may
  depend on stdlib + existing web dependencies and lightweight artifact helpers;
  never import CLI, production runner or generation modules at server import.

## Small Transport and Hosted Storage Surface

Use a package-owned `review_transport.py` client and lightweight
`hosted_publication.py` storage boundary (names can change coherently).
Configuration: base URL, token through environment/config (never logged), or
explicit local root. Local and HTTP operations use the same snapshot validator
and pointer semantics. Standard-library HTTP is sufficient; no new runtime
httpx or multipart dependency is needed.

For HTTP, reuse `POST /api/session` with the configured admin token and a client
cookie jar. Supply request timeouts, bounded response reads and clear errors;
do not forward credentials on cross-origin redirects. Tests inject TestClient
transport. A machine request without Origin is valid; a bad/null Origin must
still fail on every unsafe endpoint. No new anonymous administrative capability.

Recommended concrete endpoints:

| Endpoint | Contract |
|---|---|
| `POST /api/books/{book}/revisions` | Admin uploads a gzip tar of exactly one verified snapshot root; return revision ID. Idempotent for identical content. |
| `POST /api/books/{book}/publication` | Admin JSON `{channel: "review" or "release", revision}` advances only that pointer to an already verified stored revision. |
| `GET /api/books/{book}/publication` | Current review/release identities and history, no private paths or tokens. |
| `GET /api/books/{book}/feedback` | Versioned authoritative full feedback snapshot, including statuses and original anchors, stable site/source ID and completeness marker. |
| `GET /api/books/{book}/media` | Media targets for the requested verified revision/channel, with safe asset URLs. |
| revision-scoped asset/download route | ID/inventory lookup, confined file response; audio range requests and correct safe MIME. |

Endpoint names are defaults; implement both sides together and document any
coherent alternatives. New-book upload validates book ID directly, not the old
`require_book` dependency. Existing review routes can accept a revision/channel
selector and default to review-current. Add a public-release route/link that
actually serves release content/downloads, not just a stored pointer label.

Use a configured writable hosted root, e.g. `<root>/<book>/publications/<hash>`
plus review_current/release_current JSON. Reuse M2 layout and lightweight
verification, creating only the minimum Book/context required. Upload into
owned staging, validate tar members and all hashes, install immutable bytes,
then advance a pointer under the per-book lock. A valid but unpointed revision
after interruption is safe; a failed upload must not affect the active revision.
Do not extract archives with unchecked `extractall`. Never replace the entire
hosting root, DB, feedback export directory or unrelated books.

Publication CLI should support one explicit publish-review and publish-release
operation (or equivalent channel option) on an existing verified revision.
Remote release must report remote success distinctly from M2 local promotion.
Historical Fly script may remain a documented compatibility path or become a
wrapper, but HTTP/local installed CLI must work independently of Fly and scripts.

## Feedback and Comment Identity

Extend comment rows with explicit scope/target kind, stable media target ID,
publication revision, text revision, target revision and optional timestamp.
Keep existing paragraph anchor and original context; safe nullable defaults
retain old rows. Store chapter/book revision anchors for new comments too.
Use server identity, not payload author. Validate requested revision and target
at comment creation; either support explicit historical revisions or return a
clear conflict when the viewed revision changed. Never silently re-anchor.

Keep the existing prose edits export shape and add a separate `media_comments`
collection. A full sync feed can wrap those with all statuses and a durable
site/source identifier. Persist that source ID in the review DB/host state so
restart does not create a new source. Use `(source_id, book_id, comment_id)` for
import identity; compare stable comment version/body/updated_at for edits.
Preserve unchanged timestamps and original anchors. Missing IDs in an explicitly
complete full feed become remotely removed/inactive for that source, not a purge
of local history or comments from another source. No incremental cursor protocol
is necessary for this milestone.

Keep imported feedback state separate from review_apply_ledger.json. Atomically
reconcile the validated remote snapshot, then derive eligible prose edits.json;
media, inactive, stale, orphaned or unknown-anchor imported items remain visible
in sync reports but do not enter paid prose application. A legacy unanchored
remote record must not invent source provenance; report why it is ineligible.
Existing trusted local overlay behavior may remain compatible. Do not refresh
updated_at on every import or add volatile import metadata to feedback keys.

Expose pull and plan/apply separately. A practical `review-sync --apply
--republish` may orchestrate pull → existing apply_review_feedback → M2 run →
publish-review; without --apply it makes no model calls. Use the existing lock
with an explicit lock-held composition contract rather than nested deadlock.
If no eligible feedback or no accepted prose changed, skip unnecessary paid
regeneration. If application or generation fails, do not republish partial work.
External cron can invoke the command; do not install a scheduler in this task.

## UI, Packaging and File Ownership

The UI uses static app.js DOM helpers, existing comment components and signed
cookies. Add reachable prose/audio/graphic navigation, target titles, audio
controls plus timestamp capture, frame images, media composer, revision labels,
and visible stale/orphaned notes. Keep media notes out of existing `draft_para
=== null` chapter-note shortcuts. Use textContent/DOM construction for notes;
do not render untrusted feedback as HTML. Update CSP only as needed for same-site
media. A release view should expose review/comment links for its exact revision.

Extend package_review_artifacts through package-owned reusable packaging logic
or a safe helper, so hosted and installed paths do not import scripts. Keep old
deploy layout/overlays working while copying validated media assets/indexes and
revision metadata when present. Existing packaged review-apply responses should
remain visible; keep any response projection outside immutable publication bytes
and do not ship private queues/provider credentials.

Implementation can delegate with exclusive ownership:

- **Web/media worker:** webapp/store.py, app.py, static assets, media/revision
  routes and their store/security/UI tests. Own migrations, export, hosted
  revision discovery and session/origin dependencies. Coordinate receiver calls
  through lightweight storage functions; no generation imports.
- **Feedback/transport worker:** new package transport/storage/sync modules,
  review_apply eligibility changes and their focused tests. Own archive
  validation, HTTP/local clients, reconciliation and lifecycle composition.
  Do not edit webapp files or CLI; return exact registrations/options needed.
- **Main M3 worker:** cli.py, script/package compatibility, shared-schema
  coordination, docs/dependency packaging, final end-to-end tests and STATUS.
  Agree feed/receiver interfaces first; integrate child outputs without concurrent
  edits. Changes to shared M2 publication/media APIs stay main-owned.

## Proof and Done Criteria

Use real TestClient endpoints and temporary independent local/hosted roots for
one end-to-end cycle: produce fake-provider revision A → admin HTTP upload/review
publication → reviewer prose/audio/panel comments → pull twice → one constrained
fake-LLM apply → M2 regeneration → publish B → verify stale/orphaned anchors and
intact DB/A history → release B → further feedback → publish/release C, preserving
B and avoiding reapplication of unchanged comments. Include public release
downloads and unchanged review/release pointer separation.

Focused tests must also cover old SQLite migration/reopen, original anchors,
edited/resolved/deleted full-feed reconciliation, local draft advanced after
remote export, failed/partial import, unknown source/schema/book, media exclusion,
auth roles, author spoofing, wrong/null origin, first upload, malformed archives,
path/symlink/hardlink escapes, extra/duplicate files, limits, corrupt hashes,
failed pointer replacement, concurrent publication, local transport parity,
media HTTP range/MIME, baked/overlay removal and M1 packaging preservation.

Run focused modules, `.venv/bin/python -m pytest -q`, CLI help/plan and
`git diff --check`. Run `node --check forage/webapp/static/app.js`. If a browser
is available, exercise navigation, sign-in, audio timestamp and panel comments,
resolve/export and stale rendering against a temporary server; otherwise state
the exact unavailable browser limitation rather than claiming visual proof.

Build/install the wheel outside the checkout, unset PYTHONPATH, and verify CLI
publish/pull/help/local transport plus web static/resource imports from the
installed package. Test web import/start/media/upload with pipeline-only imports
blocked or a web-only temporary environment using available pinned dependencies.
Do not install unpinned web dependencies or perform live requests as validation.
Keep all verification foreground and wait for completion.

Update README/help and the final PLAN completion matrix with exact evidence.
Main worker writes final `[done] M3` STATUS, test counts and residual limits for
independent audit. No placeholders, inaccessible command paths, fabricated
remote success or promised-but-unimplemented receiver may count as complete.
