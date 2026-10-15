# M3 handoff: hosted review and continued publication

All four M3 audit findings are corrected and the final integrated gate passes:
680 tests passed, 6 Docker checks skipped in 72.01s. Independent resolution audit
passed all criteria with 165 focused tests and corrected original failure probes. The prior 629-pass gate is superseded by 51 additional regression cases. No deployment, external site mutation, live provider request or commit
was performed. All new storage/HTTP/generation proofs use temporary roots and fake
provider boundaries.

## Operator commands

- `forage publish-review BOOK REVISION --workspace /srv/forage`: verify a local
  snapshot, upload it, and explicitly advance hosted review only.
- `forage publish-release BOOK REVISION --workspace /srv/forage`: upload/verify
  and explicitly advance public release only. Existing `forage release` still
  changes local release selection; these commands distinguish hosted success.
- `forage review-pull BOOK --workspace /srv/forage`: reconcile full feedback,
  report eligibility, no models.
- `forage review-sync BOOK --workspace /srv/forage`: same free pull/report.
- `forage review-sync BOOK --workspace /srv/forage --apply --republish`: apply
  eligible prose feedback, refresh affected production outputs, upload the
  successful revision. Release remains explicit.
- `--segment CHAPTER` repeats to constrain application or target book-level notes.
  `--outputs text,audio,graphic` and `--production-options options.json` override
  saved operational settings. A configured media checkpoint still requires an
  explicit current-text acknowledgment through `forage run`.

Client selects one of `--site URL` / `FORAGE_REVIEW_URL` /
`metadata.review.url`, or `--local-root PATH` / `FORAGE_REVIEW_LOCAL_ROOT` /
`metadata.review.local_root`. Token comes from `FORAGE_ADMIN_TOKEN`, or the env
name supplied through `--token-env`; credentials never enter revision/state
exports. Local feedback defaults to `HOSTED_ROOT/BOOK/feedback.json` and accepts
`--feedback PATH`. It refuses a pending/failed projection marker.

Server config: `FORAGE_HOSTED_ROOT` (alias `FORAGE_PUBLICATION_DIR`), persistent
`FORAGE_REVIEW_DB`, existing review/admin tokens, signing key and host/proxy
settings. Positive integer limit overrides are `FORAGE_MAX_UPLOAD_BYTES`,
`FORAGE_MAX_EXPANDED_BYTES`, `FORAGE_MAX_UPLOAD_FILES`; defaults 128 MiB, 512 MiB,
10,000. Mutable DB and export paths cannot point into immutable publications.

## Package APIs and contracts

`HostedPublications(root)` in `forage.hosted_publication` provides:

- `upload(book_id, archive: bytes) -> manifest`; no pointer change.
- `promote(book_id, revision, channel='review', lock_held=False) -> pointer`.
- `status(book_id) -> {'review': pointer|None, 'release': pointer|None}`.
- `resolve(book_id, revision=None, channel='review') -> (Path, manifest)`.
- `book_ids() -> list[str]`.

`archive_snapshot(book, revision)` first/last verifies source snapshot bytes.
Only regular, unique archive entries with confined paths, valid inventory/hashes,
book/revision identity and bounded compressed/expanded/file counts are accepted.
Expansion is bounded before tar parsing across the entire decompressed stream,
including PAX/GNU metadata, headers, padding and trailing/concatenated streams.
Staged verified snapshots install under the per-book lock; duplicate content is
idempotent. No unchecked extractall, links, devices, unlisted files or private
runtime paths enter snapshots. Invalid promotion preserves the prior pointer.

`ReviewTransport(base_url=None, local_root=None, token=None, http_client=None,
feedback_path=None)` supplies `publish(book, revision, channel='review')` and
`fetch_feedback(book_id)`. Production HTTP uses stdlib, cookie login, timeout,
bounded responses and refuses redirects. `http_client` injects real TestClient
endpoints in offline tests. Successful publication requires exact server
confirmation of book/revision/channel. Local transport shares hosted validators.

`review_sync.pull_feedback(book, transport, lock_held=False)` reconciles into
`editorial/feedback_import.json` and derives `imported_edits.json`, leaving legacy
`edits.json` and application ledger intact. `sync_feedback(..., apply=False,
republish=False, production_options=None, segment_ids=None)` holds the book lock
through pull/application/regeneration and returns explicit stage success/failure.
Heavy pipeline imports occur only inside the explicit apply branch.

Feed schema: `{version:1,source_id,book_id,complete:true,comments:[...]}`. Records
preserve original ID, scope, target kind/ID, publication/text/target revisions,
original context/anchor, chunk-local seconds, author/body/status and creation/
update times. Source identity is durable in SQLite. Import keys are source/book/
comment; absent IDs in complete feeds become inactive for that source only,
with old versions/history retained. Current draft bytes and current plan determine
eligibility. Media, stale, orphaned, inactive and unanchored records do not enter
paid prose editing. Imported overlay reads rederive eligibility from authoritative
import state, so failed derived-cache writes cannot resurrect resolved feedback.
Imported application fingerprints include source identity while preserving legacy
local fingerprints and original remote comment IDs in the ledger.

M2 additions: `run_production(..., lock_held=False)` composes under an already-held
book lock. Runs persist nonsecret `requested_production_options` before execution
and `production_options` after success; sync prefers the requested settings when
retrying failed work. Both contain only supported operational options, with
resolved voice/art settings and model selections, for subsequent sync. Tokens,
provider API keys, continuation and adoption flags are excluded; state remains
private and never enters publication inventories. Normal model environment
routing precedence remains unchanged. Legacy media runs missing saved options
require explicit settings. Review application now rejects incomplete/truncated/
refused provider completion before prose or ledger writes.

## Recoverable application and sync completion

`forage.review_recovery` is provider-free. A durable
`editorial/review_apply_pending.json` stores validated decisions, prospective
ledger bytes and expected before/after hashes before changing prose. Recovery
checks all affected snapshot/draft/checks/ledger targets before completing atomic
writes and retiring intent. Existing decisions are retained. If current bytes
match neither expected version, it preserves the human edit and intent and blocks
publication rather than overwriting a conflict. Recovery itself makes no model call.

Standalone apply, free pull/sync and direct production recover before eligibility
or execution. Read-only preview/pending planning and direct snapshot creation
refuse unresolved intent. `recover_review_applications(book, lock_held=False)`
and `assert_review_applications_resolved(book)` are lightweight shared hooks;
`apply_review_feedback(...,lock_held=False)` now composes under the book lock.

Sync validates explicit options before applying feedback and asks the common free
production planner whether all selected stages/settings/output bytes are complete.
It reruns affected work for failed media, corrupt output and explicit branch/settings
changes even if prose is unchanged. Checkpoint acknowledgment is never treated as
proof of a completed snapshot. Genuinely unchanged cycles still make no provider calls.

## Hosted HTTP/UI surface

- Admin `POST /api/books/BOOK/revisions` receives gzip tar; supports first book.
- Admin `POST /api/books/BOOK/publication` accepts channel/revision.
- `GET /api/books/BOOK/publication` returns independent pointers/history.
- `GET /api/books/BOOK/feedback` returns the authoritative complete feed.
- `GET /api/books/BOOK/media` lists safe targets/URLs/comments.
- `GET /api/books/BOOK/revisions/REV/assets/INVENTORY_PATH` verifies membership
  and confinement; audio range responses and safe MIME types work.
- Existing chapters/comments accept `revision`/`channel` selection and pin a root
  for each response. New hosted comments must submit `publication_revision`;
  exact historical revisions are supported. Audio/graphic additionally submit
  scope, target_id, target_revision; audio requires finite nonboolean
  `timestamp_seconds >= 0`, bounded by duration if known.
- Unspecified current selection uses review first, falling back to release only
  if no review pointer exists. Explicit channel/revision selections remain strict.
  First-release-only books support all comment scopes and full feedback without
  an implicit review promotion; exact historical release anchors remain usable.
- `/b/BOOK` reviews current work. `/release/BOOK` shows current public release
  and its downloads; UI links preserve viewed revision, and media controls support
  timestamps/frame inspection, editing/resolution/deletion/export and staleness.

SQLite comments and pointers are authoritative. Hosted mutations serialize under
the book lock, write durable `feedback_pending`, and clear it only after atomic
full-feed cache publication. A projection failure after commit returns a warning
rather than claiming the committed mutation failed; local pulls refuse pending
cache, while HTTP reads remain authoritative. Repeat successful publication can
refresh the projection. Imported LLM responses are displayed only for the site's
source_id; legacy local response rows remain compatible.

## Packaging and file ownership

`forage.review_package` owns reusable packaging. The historical script imports
that installed module as a compatibility entrypoint. Media packaging validates
and copies only referenced asset/text paths, then revalidates staged hashes. It
retains verified immutable revisions needed by review/release history. The M1
resolved-overlap, staging, rollback and backup retention guarantees remain.
Selected whole-book overlays and hosted roots never fall back to removed baked
media. Runtime modules do not import `scripts`.

Implementation/test ownership for audit:

- Hosted archive/transport/sync and review_apply: `test_hosted_publication.py`,
  `test_review_transport.py`, `test_review_sync.py`, and audit-added
  `test_review_recovery.py` fault-boundary/direct-entrypoint proof.
- Web storage/auth/media/UI: `test_web_media.py` plus existing
  `test_webapp_security.py` and `test_store_ids.py`.
- CLI, package and full lifecycle: `test_review_lifecycle.py`,
  `test_review_packaging.py`, existing `test_artifact_safety.py`.
- Installed distribution: extended `test_distribution.py` builds/installs wheel
  outside checkout with `-I` and no PYTHONPATH; proves CLI local publish/release/
  pull/sync/help, package/static/resources and mocked graphics.
- Shared runner settings/lock: M2 runner regression suite plus lifecycle/sync
  assertions, including actual fake narration voice and art prompt preservation.

## Proof and limits

Final owning gate: `.venv/bin/python -m pytest -q` => **680 passed, 6 skipped
in 72.01s**, with eight TestClient timeout deprecation warnings. CLI help, Node
syntax and diff checks passed. Focused remediation gates: archive 47; web 113;
sync/recovery 64; final recovery/lifecycle 22. These are overlapping gates; their
counts are not additive. Independent resolution audit passed; no unresolved implementation or audit item remains.

The full lifecycle test produces fake-provider text/audio/graphic revision A,
uses real HTTP admin upload/review publication, creates reviewer prose/audio/
panel notes, pulls twice, applies one constrained fake-LLM correction, regenerates
and publishes B, verifies stale anchors, explicitly releases/downloads B, then
accepts further release-bound feedback and publishes/releases C. Original A/B
bytes, SQLite rows and release/review histories survive. Removing selected media
marks old targets orphaned. Unchanged repeat cycles make no provider-boundary
calls and retain the application ledger.

Web-only tests block model SDKs, Pillow and pipeline modules during app import,
startup, upload and media requests. No browser executable, browser tool,
Playwright or Selenium package is available; JavaScript syntax and HTTP/DOM source
contracts are checked, but interactive visual browser behavior is not certified.
Docker tests remain opt-in. Live provider creative quality and a real deployment
remain unverified. Exact final suite/help/syntax/diff evidence is in STATUS/LOG.
