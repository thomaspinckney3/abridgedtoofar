# Current Status

## Current Stage

[account authentication deployed — 2026-10-21] Fly v25 replaces shared-token
login with username/password accounts. Administrators use **Users** to create
reviewer/admin accounts and remove existing accounts. Removal revokes sessions
and preserves review notes. The last administrator and self-deletion are
protected; the account menu supports password changes and sign-out. Passwords
use salted scrypt hashes; revocable sessions are stored as hashes in SQLite.
Old token login and valid legacy signed cookies are rejected.

The initial `admin` account is ready; its credentials were saved in the private
operator handoff. A separate `pipeline` administrator account is configured in
the ignored local `.env` for publication. All three old token/signing-key secrets
and both one-time bootstrap secrets have been removed from Fly. Existing accounts
and sessions survive restart; bootstrap never resets an existing password.

Validation: 797 full-suite tests pass (8 container tests skipped in that run),
all 9 real-container tests pass, and the updated HTTP smoke checks pass. Isolated
desktop/mobile browser tests cover account creation/removal and password changes.
Live browser checks verify admin login, management controls, password form and
logout. All 65 source files match the tested image, all 780 stored artifact files
and 454 review records are unchanged, and all five books/115 chapters/downloads
match pre-deploy captures. Database integrity and legacy-login rejection pass.
Release-verified. Evidence: `/mnt/data/tmp/forage-accounts-20261021/`.

[review feedback incorporated — 2026-10-21] The user's approved pipeline pass
applied comment `8b74e1d2dee2` in The Secret Adversary chapter 002. Paragraph 8
now restores the source's Sister Greenbank/doctor/chart anecdote, providing the
setup for Tommy's hospital reference. Only that paragraph changed (+28 words).
The review edition is live at
`https://forage-review.fly.dev/b/secret_adversary?c=002`, revision
`4dd94ce6dd03ec0a930ec12484b8ba10b4a961b674864059a12a7cabb21bd793`.

The external `review-sync --apply --republish --segment 002` used the original
full-run workspace and configured Opus 5.5 models. Three paid calls applied the
note, reran the whole-book critic and refreshed chapter alignment; usage-based
cost estimate is $0.704138. All 47 synopsis checks pass and all 214 protected
passages remain intact. All 29 live chapters and complete downloads match the
verified snapshot. The 214 current comments retain their content and status;
the user's note is attached to the correction and awaits revision review. The
seven earlier comments deleted by the user were not restored. Other chapters,
books, release channels and the original immutable snapshot are preserved.
Read-only signed-in/public desktop/mobile browser checks pass. A fresh feedback
pull has zero actionable requests, and free production planning reuses every
stage. App release remains v23. Evidence:
`/mnt/data/tmp/forage-feedback-20261021/verification.json` and adjacent files.

[review layout deployed — 2026-10-21] Fly v23 puts chapter prose first.
Header jump buttons lead to compact Suggested issues and a collapsed Review
history panel below the text. Completed repairs, dismissed/outdated suggestions,
draft diagnostics and detailed critic records remain in history. Existing
decisions, evidence and request controls are preserved, with reader-facing labels.
Dismiss/reopen actions reveal the item's new location and retain keyboard focus.

Validation: 41 affected API/configuration tests and all 8 final-image container
tests pass. Isolated browser checks exercise dismiss/reopen/request and
accept/reopen/reject, reload persistence, feedback export, desktop/mobile and
public/reviewer access. Live read-only browser checks pass. All 115 chapters,
460 comments, downloads and publication pointers are unchanged; all 64 source
files match the tested code and 676 stored artifact hashes match the backup.
SQLite integrity and unchanged application tables are verified. Deployment is
release-verified, with no live decisions or paid generation. Evidence:
`/mnt/data/tmp/forage-review-layout-20261021/verification.json` and adjacent files.

[audit fixes deployed — 2026-10-20, 2026-10-21 UTC] All four findings from the
uncommitted workflow audit are corrected; these first shipped as Fly v22. Full-run
publications now provide verified provenance to the common feedback refresh
runner; new text identities are shared and older editions use byte-verified
compatibility. Verified paragraph deletions support decisions and restoration
requests. Superseded pipeline findings return HTTP 409 without changing history.
Preflight rejects invalid source/plan inputs, incomplete drafts and unsupported
refresh settings before feedback generation.

Validation: 789 suite tests passed (8 Docker tests skipped in that invocation),
then all 8 real-container tests passed. After strengthening draft preflight,
182 affected tests passed, including four additional cases; 33 regression cases
were added in total. Both actual full-run workspaces pass read-only refresh
planning with their existing revision IDs and no production-state writes.
On the user's subsequent deployment request, rebuilt and tested the final
image (all 8 container tests passed again), backed up SQLite and the volume,
and deployed v22 to the existing machine. Live health, all 115 chapters across
five books, complete downloads, publication pointers and all 460 review records
are verified unchanged. All 64 source files match locally; 676 stored artifact
hashes and every application database table match the backup. Signed-in browser
controls and authenticated validation pass. Secrets, environment and volume
are unchanged. Deployment is **release-verified**; paid editorial generation
remains covered by offline simulations only. No reviewer decisions, paid model
calls, Git commit or push. Evidence: `/mnt/data/tmp/forage-audit-deploy-20261021/`.

[published for editorial review — 2026-10-20] Both full text pipelines
finished under the user's full-cost approval using Opus 5.5 throughout.
Workspace: `work/_full_runs/2026-10-20-opus55/`; open `report.html` for the text,
source comparisons, measurements, and final findings.

- Adams: 28 included chapters, 72,449 words / 72,200 target; all 218 protected
  passages intact; zero final chapter-level must-fix candidates. The book critic
  retains a hold for three events in chapters intentionally excluded by the
  preserved plan (Grant, Chicago, gold standard). The scope assessment is saved.
- Christie: 29 chapters, 40,749 words / 40,600 target; all 214 protected passages
  intact; whole-book critic passes all 47 synopsis checks. Two final chapter-level
  candidates remain for editorial review: chapter 003's improvised-name setup and
  chapter 004's reply after the omitted reason for using an alias.

Both runs include preservation planning, counted two-pass drafting, two detailed
review/repair cycles, two focused closing passes, fresh checks of changed contexts,
assembly, book critic, validation, paragraph alignment, and verified immutable
local snapshots. 64 reviews with identical complete contexts were reused without
provider calls. Original inputs remain unchanged. Both new review editions are
now live at https://forage-review.fly.dev through `forage publish-review`.
All 57 hosted chapters and complete text downloads match the verified snapshots;
browser checks passed without JavaScript errors. Seven existing Christie comments
are preserved as stale, unplaced notes from the earlier edition. Public release
channels remain unchanged. Publication evidence is saved in
`work/_full_runs/2026-10-20-opus55/website-publication/`.

Release v21 adds the Pipeline review section to each chapter. The pipeline
published 240 Adams items and 213 Christie items: final findings (including both
remaining Christie must-fix candidates) and 57 chapter repair-history cards.
Reviewers can dismiss/reopen findings, request changes with a comment, and
accept/reject/reopen repairs. Evidence and historical before/after patches are
visible. Requests feed the existing external review pipeline; the website never
starts a rerun. New full runs package these items automatically; `prepare-review`
adds them to completed runs without generation or prose changes.

Verified all 57 live chapters, all 453 pending/current pipeline items, unchanged
complete text downloads, seven unchanged original comments, and signed-in
browser controls without submitting any live decisions. Preview browser exercised
the complete decision lifecycle. Validation: 760 suite tests and 8 real-container
tests pass; 25 final affected tests overlap the suite count. Evidence is saved in
`work/_full_runs/2026-10-20-opus55/pipeline-review-publication/`.

Final integrity audit passed (`verification.json`): 72 unchanged input hashes,
all 432 protected passages, every review context/evidence citation, exact patch
replay, current paragraph alignments, and both snapshot inventories. Completed-run
resume preserves the latest repaired snapshot without generation. 20 focused
runner tests pass.

Recorded token-cost estimate, including the tiny diagnostic: $281.992865.
28 interrupted requests lack final usage; $27.614790 remains conservatively
reserved, not asserted as an actual charge. No provider calls are running.

The unchanged `.env` credential worked after verified tiny and full-size probes.
Earlier provider low-credit errors did not establish an empty Console balance;
account balance was not accessible, and the cause remains unconfirmed. No funding
or credential change was needed for the successful resumed work. Provider prompt
cache reads were zero: only planning configured caching, with a five-minute TTL.
Persistent exact-response reuse survives restarts; provider prompt-cache efficiency
remains a future improvement.

[done] M1–M3 are complete and independently audited. The authorized Fly
deployment completed on 2026-10-19; the revised review layout is release v23. The existing single machine
and volume are healthy at https://forage-review.fly.dev, with persistent hosted
publication storage enabled.

Before the full-book run, The Secret Adversary chapter 002 was regenerated,
aligned and republished with all seven comments attached to verified passages;
six revisions were applied and the hostel note was skipped with an explanation.
The new full-book edition supersedes that draft. All seven original notes remain
open and visible under "Notes awaiting a matching passage", with stale/unplaced
attachments. Original anchors and previous decisions are preserved.

Reviewers now have Accept revision, Reject with comment, and Reopen revision.
Decisions retain their history and exact response identity. Rejection queues
feedback for the next pipeline pass; acceptance and reopening do not generate
text. All seven existing notes remain awaiting the user's review.

## Delivered

- Corrected the original five artifact safety, completion and freshness defects.
- Unified resumable text production with optional audio/graphic outputs,
  preserved human edits, verified revisions and independent release histories.
- Separately hosted review with prose/audio/panel comments, explicit publication,
  free feedback pull, durable apply/refresh/republish and continued public releases.
- Recovery for interrupted application and media generation; revision-bound
  feedback, bounded uploads, safe packaging and installed/web-only runtime paths.

## Validation

- Revision workflow: **721 full-suite tests passed**, followed by final focused
  checks (**114 review/lifecycle tests, 56 security/store tests, 34 final
  revision/anchor tests and 8 real Docker tests**). These counts overlap.
  The real HTTP/storage/pipeline integration uses simulated provider responses
  and covers accept → reopen → reject → regenerate → republish, including a
  skipped request that still needs a newly published model response.
- Release v20: all 133 chapter endpoints, unchanged prose/artifact checksums
  and original comment records, database migration, authenticated validation,
  and signed-in browser controls verified. Browser preview also exercised
  decisions across reloads, required rejection feedback and persistent history.
  No real reviewer decisions or paid model calls were made for this feature.
- Attachment follow-up: the full suite passed **706 tests** before the final
  display-location and package-permission refinements. Final affected suites:
  **120 review tests, 68 packaging tests and 8 real Docker tests passed**.
  Live release v18 passes all 133 chapter reads, exact regenerated-prose and
  comment-binding checks, original-text export checks and a browser inspection
  of all seven notes. Resolve → Reopen → edit follow-up was exercised in a
  browser preview and produces safely located pending feedback without an API call.
- The publisher now gives selected public artifacts readable file/directory
  permissions. This fixes owner-only atomic writes becoming unreadable after
  upload or when baked into a container running as the service account.
- Live release v16: HTTPS health, all five unchanged book summaries and 133
  chapter endpoints, all seven existing comments, and 62 unchanged volume
  artifact files verified. SQLite integrity, reviewer/admin sign-in, secure
  cookies, upload permissions, closed schema endpoints, anonymous-write
  rejection, and served HTML/JS/CSS all pass. Hosted storage is on `/data` and
  writable by the non-root server; an empty admin upload reaches archive
  validation without changing book content.
- The deployment rebuild has exactly the filesystem layers and runtime
  configuration of the previously tested Docker image. Existing Fly secret
  digests are unchanged. Fly health and DNS checks pass.
- Prior full implementation suite: **680 passed, 6 Docker skipped in 72.01s**.
- Deployment follow-up: **38 configuration/security tests and all 7 real Docker
  tests passed**. Upload, publication, feedback and restart persistence verified
  with the image defaults. Installed resources/web-only imports also pass.
- Final independent resolution: **165 focused tests passed**, original failure
  probes corrected; all M3 criteria and PROJECT AC1–AC12 pass.
- Installed wheel, real test-HTTP A→B→C lifecycle, web-only imports, CLI help,
  JavaScript syntax and diff checks passed. TestClient timeout warnings are
  test-harness deprecations, not failures.
- Evidence: AUDIT.md final resolution; commands/configuration: README.md and
  HANDOFF-M3.md. PLAN.md contains the completed contract matrix.

## Limits

Revision requests are consumed by the next `review-sync --apply --republish`
or exported review-apply pass. The website does not run a background generator.
Acceptance closes the review note; it does not promote a public release.

Two authorized Sonnet 5.5 calls regenerated and aligned chapter 002 using the
user-supplied Anthropic workspace. The response used a comment ID in one
feedback-key field; the saved response was recovered by correcting only that
metadata, with no extra provider call or prose changes. Six source-supported
changes were reviewed and published; other chapters were preserved. Full
upload/promotion/restart persistence was verified by the earlier real Docker
tests; live verification checked the mounted storage and authenticated receiver
without promoting a test publication. Fly CLI 0.4.118 is installed at
/home/tp/.fly/bin/flyctl; the app-scoped token is loaded from the ignored `.env`
only by the deployment helper, without displaying it or adding it to the image.

## Working State

Local commit authorized on 2026-10-15 for the complete working tree, including
pre-existing model updates and work/_model_comparisons fixtures. Chapter 002,
its alignment/decision ledger and assembled book text now include the requested
regeneration. No Git push or reset was performed. Fly deployment is complete;
deployment, attachment, regeneration and revision-workflow changes remain uncommitted.
Repository README.md, CLAUDE.md, pyproject.toml and requirements-web.txt were
followed. Existing .venv/build prerequisites used; no new dependencies in M3.
Implementation base: 3644fc8; delivery commit: 148c158. Deployment follow-up
changes are uncommitted. Prepared deploy/artifacts contains the same five book
IDs currently served by https://forage-review.fly.dev. Test image: forage-review:pytest
(image index sha256:407bee1c6913de663e8d1b8468293d1101befc7d4c8a290b1b24b4f86e848d17).

## Deployment Record

- App/release: `forage-review` v25, region `iad`, one machine `87e005f0262398`.
- Existing volume: `vol_re176w7xje1gj214`, mounted at `/data` (1 GiB).
- Deployed image index:
  `registry.fly.io/forage-review@sha256:46f3b456a35bce9717d59549226e249a9a8b1ff21de298ba5828db2669aa615e`.
- Running amd64 image manifest:
  `sha256:02ea60c0d07202531530debb888d0025ff17cf7fb5901547acf53df780654817`.
- Account migration backup: `/data/backups/accounts-20261021/review.db`, volume
  snapshot `vs_KA4ewADgkzQTZovyPVOQDKD`, created 2026-10-21T19:13:32Z.
- Before account migration (v23):
  `registry.fly.io/forage-review@sha256:407bee1c6913de663e8d1b8468293d1101befc7d4c8a290b1b24b4f86e848d17`.
  A rollback to that token-based image also requires restoring its retired
  authentication secrets from the private operation backup.
- Before review layout (v22):
  `registry.fly.io/forage-review@sha256:c139be967d8d5e89612876f96ce7540da1dcbf7233f2400f2d72fdda58e35a76`.
- Review-layout backup snapshot: `vs_25RDp5Yq2X7HbRAPkA9JJ06`, created
  2026-10-21T17:31:51Z, five-day retention. SQLite backup:
  `/data/backups/review-layout-20261021/review.db`, downloaded and integrity-checked
  at `/mnt/data/tmp/forage-review-layout-20261021/review-before.db`. Operation
  scripts, before/after captures and browser screenshots are in that directory.
- Before audit fixes (v21):
  `registry.fly.io/forage-review@sha256:ca2aa6ebd286be41675a2564635669884bd0f00a4de3b22259c328011057581d`.
- Audit-fix backup snapshot: `vs_vzAZpzYgLG7h3Bmjwl20q4Q`, created
  2026-10-21T00:44:35Z, five-day retention. SQLite backup:
  `/data/backups/audit-fixes-20261021/review.db`, downloaded and integrity-checked
  at `/mnt/data/tmp/forage-audit-deploy-20261021/review-before.db`. Commands,
  source checksums, before/after captures and browser screenshots are in the
  same local directory. Temporary registry/browser credentials were removed.
- Before revision workflow (v18):
  `registry.fly.io/forage-review@sha256:52a2d445d4b8cc6d83020fb0c6e85d3da5e7b03d44ba48cf1354d0a2ccc83162`.
- Before attachment fix (v16):
  `registry.fly.io/forage-review@sha256:7c4f27818b64efc57c88ba434cbaaaba59d72ce0710123e1d58591f11de3dc25`.
- Pre-deployment volume snapshot: `vs_kk9PokZpY0Bhg2V5qJXBO6`, created
  2026-10-19T19:37:25Z, five-day retention. SQLite backup:
  `/data/backups/review-pre-deploy-20261019.sqlite3`, also downloaded and
  integrity-checked at `/mnt/data/tmp/forage-fly-20261019/review-pre-deploy.sqlite3`.
- Local operation scripts and before/after JSON evidence:
  `/mnt/data/tmp/forage-fly-20261019/`. Temporary Docker registry credentials
  were removed after pushing. Deployment used the immutable image index with
  `--ha=false --update-only --strategy rolling`.
- Attachment/regeneration backup: `/data/backups/comment-fix-20261019/`
  contains SQLite, artifact archive and checksums; SQLite also downloaded to
  `/mnt/data/tmp/forage-comment-fix-20261019/review-before.db`. Operation scripts,
  raw/corrected response, chapter backups, live API evidence and browser
  screenshots are in `/mnt/data/tmp/forage-comment-fix-20261019/`.
- Revision-workflow backup: `/data/backups/revision-workflow-20261019/`.
  Local database copy, test logs, signed-in browser screenshots and deployment
  scripts: `/mnt/data/tmp/forage-revision-workflow-20261019/`. Temporary registry
  credentials and browser session files were removed after verification.
