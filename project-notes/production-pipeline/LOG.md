# Engineering Log

## 2026-10-14

- stage: implementation planning
- focus: reliable book production and review across text/audio/graphics
- outcome: accepted scope and acceptance criteria recorded; baseline is 110
  passed and 6 Docker tests skipped, with five independently reproduced bugs
- blockers: none for local implementation and mocked-provider verification
- next: fix unsafe packaging, incomplete draft acceptance, and stale alignment/
  audio reuse with permanent regression coverage

## 2026-10-14 — M1 artifact safety and completion

- Implemented resolved package boundary validation, selected-input validation,
  staged publication, exception rollback and retained recovery backups.
- Added provider-neutral response completion properties; single/group drafting
  and disk reuse now preserve failure. Assembly rejects unverified group splits.
- Alignment reuse compares embedded current inputs; regeneration validates the
  mapping and replaces cached output after success. Review comments become stale
  against revised paragraphs through the existing store.
- Audio manifest v2 validates effective request and output hashes. Preview uses
  a separate directory; failed/limited runs cannot combine obsolete chunks;
  successful file replacements and publication preserve previous output on error.
- README describes the corrected contracts. Historical bug probes are retired
  in favor of 162 permanent tests using temporary files and fake providers.
- Superseded M1 checkpoint: completion and alignment checks added; packaging
  and audio fixes in progress with isolated regression fixtures.
- Superseded validation checkpoint: four M1 regression modules passed 154 tests
  in 1.35s before final packaging coverage added eight more cases.
- Final validation: `.venv/bin/python -m pytest -q` returned 272 passed,
  6 skipped in 2.08s; `git diff --check` passed. Docker remains opt-in and
  no live provider quality is claimed verified.
- Changes remain uncommitted by instruction; preserved all prior model-default
  changes and did not modify existing book/work artifacts.

## 2026-10-14 — M1 audit remediation

- Independent audit identified recovery-backup deletion when audio rollback
  itself fails, and successful CLI status after a failed combined publication.
- Audio now retains the staging directory on rollback failure and records the
  exact backup-to-destination restoration path in the error. A permanent test
  verifies intact original bytes and actual restoration from that path.
- Added AudiobookResult.combine_error, visible CLI reporting and nonzero exit
  for failed or incomplete requested combined output. Explicit --no-combine
  remains a valid separate-chunk operation. README/help reflect this contract.
- Added six offline regressions, including CliRunner publication, combination
  and limited-output failures plus successful separate-chunk execution.
- Targeted gate: `.venv/bin/python -m pytest -q tests/test_audiobook_reuse.py`
  returned 50 passed in 1.62s. Full gate after the CLI change returned 278
  passed, 6 skipped in 7.04s. `git diff --check` passed. All ran foreground.
- Supersedes the prior M1 verification totals (272 passed/162 new cases).
  Current total is 168 new permanent tests. Independent resolution audit next;
  changes remain uncommitted by instruction, with no live calls or book edits.

## 2026-10-14 — Superseded M2 verification checkpoint

# Current Status

## Current Stage

[checkpoint] M2 implementation complete; final verification/documentation underway.
M1 passed independent resolution audit. Changes remain uncommitted.

## Current Focus

Shared content-aware runner, complete optional audio/graphic execution, immutable
local review snapshots/release promotion, and installed runtime resources.
Hosted feedback transport and media review UI remain M3 scope.

## Done

- Added atomic stage records, per-book process lock, pure preview/explicit run,
  generation/accepted-text identities, legacy adoption and archived regeneration.
- Reused text stage APIs; reconciled skip/plan edits against pristine preparation,
  detected incomplete provider responses and prevented stale alignment provenance.
- Integrated complete audio and graphics; frame/art/lettering caches resume.
- Added validated portable media index and immutable local snapshots with separate
  review/release pointers and atomic histories. Compatibility script shares runner.
- Packaged canonical prompt/spec bytes through build hook; CLI workspace/cache
  paths are separate from installed code. README describes actual workflows.
- Preserved model-default edits and existing book/work data; no live providers.

## Validation

- Graphics: 45 focused offline tests passed (9.04s).
- Publication: 78 focused offline tests passed (3.20s).
- Runner/state: 68 focused tests passed before installed-package prerequisite fix.
- Installed-wheel proof: 1 passed (3.72s); isolated package import outside checkout,
  all prompt/spec byte equality, static assets, CLI preview and mocked graphic PDF.
- Installed build prerequisites only: setuptools 68.1.2 and wheel 0.41.3 in .venv.
  Wheel build/install uses --no-deps/--no-build-isolation; no provider calls.
- Full suite gate running in foreground; final counts/checks to replace this line.
- No Docker execution, live-provider quality, remote mutation or deployment claimed.

## Blocked

None.

## Next

Finish M2 full gate/help/diff and handoff; independent M2 audit, then M3.

## Working State and Prerequisites

Read README.md, CLAUDE.md, pyproject.toml and all production-pipeline project/
brief/plan/architecture/status/audit artifacts. Build tool dependencies added after
the existing venv proved insufficient for wheel generation. No commits, pushes,
resets, existing book/work edits, Nova builds, live requests or deployments.

## 2026-10-14 — M2 unified production delivered

- Added atomic content/settings provenance, verified output inventories, per-book
  process locking, zero-cost preview and explicit execution over existing stages.
- Preparation retains pristine inputs; three-way plan edits avoid preserving
  derived skip flags, and removed kernels/source changes restore the correct base.
  Draft units archive superseded files, preserve original request/provider metadata,
  and accept successful manual/review-apply prose edits without redrafting.
- Added revision-bound optional pre-media checkpoint (default remains async),
  complete MP3/audio verification and actual storyboard/image/lettering/PDF adapters.
  Independent media failures preserve valid branches and block publication.
- Added strict shared media schema, immutable local snapshots, hash-verified
  explicit release promotion and separate review/release pointer histories.
- Refactored legacy full_pipeline into the shared runner; packaged canonical
  prompt/spec resources without maintained copies. Workspace/cache roots stay
  outside installed code; existing standalone commands remain usable.
- Targeted implementation probes corrected alignment model reuse, invalid audio
  formats, short chapter omissions, corrupt current pointers, volatile assembly
  identity, incomplete critic responses, and review_apply check-metadata reuse.
- Added 198 M2 offline test cases. Final foreground `.venv/bin/python -m pytest -q`
  completed with **476 passed, 6 skipped in 45.54s**, exit 0. Skips require Docker.
- Installed-wheel test passed within the final suite: `pip wheel --no-deps
  --no-build-isolation --wheel-dir TMP/wheels TMP/build-source`, then
  `pip install --no-deps --target TMP/installed TMP/wheels/forage-*.whl`; Python
  `-I` from TMP/outside with PYTHONPATH removed proved installed import location,
  every prompt/spec byte, static assets, CLI preview and mocked graphic/PDF output.
  Source staging copies only package/build/resources, never existing books/work.
- Build prerequisites were absent; installed setuptools==68.1.2 and wheel==0.41.3
  into the existing .venv. Dev dependencies now declare those requirements.
- CLI root/run/release and legacy wrapper help all exit 0; `git diff --check`
  passes. No running verification remains. README and HANDOFF-M2 describe the
  actual contracts and separate M3 hosted sync/media UI scope.
- No live-provider calls, existing books/work edits, remote mutations, commits,
  resets, pushes or deployments. Existing model-default changes preserved.
  Independent M2 audit is next; live creative quality is not certified.

## 2026-10-14 — M2 audit findings remediated

- Corrected all three independently reproduced M2 defects within existing scope.
  Generation units now correlate known chapter-member provenance across merge,
  split and rename, archive superseded bytes and regenerate without false legacy
  adoption errors. Unknown existing members still require explicit adoption.
- Preparation fingerprints only metadata consumed by each text stage. Audiobook
  voice/model/chunk changes preserve accepted human prose and refresh audio and
  dependent publication; unrelated publication metadata does not redraft text.
- Signature critics require completed provider output and explicit, correctly
  shaped identity, verdict, summary and findings. Error/refusal/malformed responses
  fail quality and block new snapshots; real editorial holds remain visible.
- Added 29 precise offline regressions, including adjacent group transitions,
  relevant text metadata, selected/unselected audio, malformed finding families,
  provider finish reasons, valid passes and valid editorial holds.
- Focused gate: **27 passed, 55 deselected in 24.45s**. Runner module before the
  final refusal regression: **83 passed in 45.52s**. Final foreground owning gate
  `.venv/bin/python -m pytest -q`: **505 passed, 6 skipped in 66.69s**, exit 0.
  Includes the isolated installed-wheel build/install/resource/CLI/graphics proof;
  Docker cases remain opt-in. CLI run help and `git diff --check` pass.
- STATUS and HANDOFF-M2 describe the corrected contracts. No verification process
  remains running; no live calls, commits, existing book/work edits or deployment.
  Independent resolution audit is next; the audit record was preserved.

## 2026-10-14 — Existing-group extension adoption correction

- Independent resolution verified the original three fixes and found an adjacent
  ownership gap: a recorded group ID bypassed adoption when its plan acquired an
  unowned existing chapter. Reproduced the exact auditor scenario with four new
  regressions, all failing against the prior guard.
- Unknown-member checks now run regardless of prior group records and before
  reuse or archival. Repeated refusal preserves every group draft/check, history,
  prior provenance and review pointer. Explicit adoption validates the expanded
  unit, preserves its files and records user-adopted provenance without attributing
  those bytes to the provider; missing checks/truncated/empty prose fail safely.
- Focused ownership/adoption gate: **9 passed, 79 deselected in 8.00s**.
  Final foreground `.venv/bin/python -m pytest -q`: **509 passed, 6 skipped in
  64.27s**, exit 0, including isolated installed-wheel verification. Final diff
  check passes. No test/build process remains running.
- Updated STATUS/HANDOFF-M2/PLAN; no live requests, commits, deployment or edits
  to existing books/work. Final independent focused resolution remains next.

## 2026-10-14 — M2 audit complete; hosted integration begins

- M2 final independent audit passed all criteria and functional, structural and forward-impact checks. No unresolved runner finding remains.
- Final gate: 509 passed, 6 Docker skipped; installed wheel, CLI help and diff checks pass.
- Next: implement hosted review upload, revision-bound prose/media feedback, reconciliation and explicit release lifecycle under BRIEF-M3.md.

Superseded M2 status moved here before beginning M3:

# Current Status

## Current Stage

[done] M2 implementation and all reported audit fixes; final resolution audit next.
M1 passed independent resolution audit. Changes remain uncommitted by instruction.

## Current Focus

All three original findings pass independent focused resolution. The adjacent
existing-group extension adoption guard is corrected and exact preservation,
refusal/adoption regressions and the final owning gate pass.
The final integration contract is in HANDOFF-M2.md; M3 brief is BRIEF-M3.md.

## Done

- Original five defects fixed and M1 independently audited.
- Shared atomic runner/state/lock, free preview, explicit execution, configured
  workspace/models, accepted text revisions, adoption and archived regeneration.
- Pristine preparation with editable cuts/plans; complete provider responses,
  current alignment provenance, optional revision-bound pre-media checkpoint.
- Actual optional MP3 audio and full selected-chapter storyboard/art/lettering/PDF
  branches with verified resume and portable revision-bound media indexes.
- Immutable local review snapshots, independent review/release histories and
  explicit verified release promotion; legacy script uses the shared runner.
- Installed prompt/spec/static/graphics resources and workspace-local caches.
  README/help/HANDOFF document the asynchronous lifecycle and current limits.
- Regrouping follows known member provenance and archives superseded drafts;
  synthesis/publication metadata preserves accepted text; malformed or incomplete
  signature critics fail quality and cannot publish a new snapshot.
- Extending a recorded group with unowned existing prose requires explicit
  adoption before archiving any group member. Adoption validates the whole unit.

## Validation

- Existing-group extension: all four exact regressions failed before the fix;
  ownership/adoption focused gate now **9 passed, 79 deselected in 8.00s**.
  Refusal and invalid adoption preserve group bytes/history/provenance; valid
  explicit adoption records user ownership and resumes without regeneration.
- Final `.venv/bin/python -m pytest -q`: **509 passed, 6 skipped in 64.27s**, exit 0.
  Includes all 33 audit-remediation cases and installed-wheel verification.
- Audit-remediation focused regression gate: **27 passed, 55 deselected in 24.45s**.
  Group merge/split/rename, metadata scope, malformed/truncated signature outputs.
  Runner module: **83 passed in 45.52s** before the final added refusal case.
- Prior remediation `.venv/bin/python -m pytest -q`: **505 passed, 6 skipped in 66.69s**, exit 0.
  Includes all 29 audit-remediation cases and installed-wheel verification.
- Pre-remediation `.venv/bin/python -m pytest -q`: **476 passed, 6 skipped in 45.54s**, exit 0.
  Includes 198 new M2 cases and all M1/existing cases. Docker tests remain opt-in.
- Installed-wheel build/install test in that gate passes outside the checkout,
  with Python -I, no PYTHONPATH, verified package location, exact prompt/spec bytes,
  static assets, free CLI plan and mocked graphics/PDF from the installed package.
- `.venv/bin/python -m forage.cli --help`, `run --help`, `release --help`, and
  `-m scripts.full_pipeline --help`: all exit 0. `git diff --check`: passes.
- All verification finished in foreground; no orphaned test/build process remains.

## Blocked

None. Live-provider quality, Docker execution and hosted deployment are unverified.
M3 hosted transport/feedback sync/media review UI remain outstanding.

## Next

Independent M2 resolution audit, then M3 against HANDOFF-M2.md and BRIEF-M3.md.

## Working State and Prerequisites

Read README.md, CLAUDE.md, pyproject.toml and project/PRD/plan/architecture/brief/
implementation-notes/status/audit artifacts. Added only missing build prerequisites
setuptools 68.1.2 and wheel 0.41.3 to .venv; dev extras now declare them. Preserved
pre-existing model upgrades and book/work data. No commits, pushes, resets, live
provider calls, remote publication, deployment or Nova builds. Base: 3644fc8.


## 2026-10-14 — M3 hosted review and continued publication

- stage: implementation and offline validation
- focus: separate hosted review site, periodic feedback incorporation, independent
  public releases and continued revision after release.
- outcome: real installed CLI and local/HTTP transport now verify/upload immutable
  snapshots, preserve independent review/release histories, and serve public
  release downloads. Server accepts first-book uploads under admin/session/origin
  guards and bounded archive validation. Review UI supports revision-pinned
  prose/audio/panel comments, timestamp capture, edit/resolve/delete/export and
  stale/orphan indicators. SQLite migration preserves old rows and stable source ID.
- Full feedback import preserves original anchors/source identities and historical
  application decisions, reconciles edited/resolved/removed notes, and checks live
  local prose before paid application. Media and inactive/stale/unanchored notes
  never enter prose repair. Repeated unchanged cycles do not call providers.
- Integration fixes: saved effective nonsecret production settings preserve voice
  and graphics choices across feedback regeneration; run_production lock-held
  composition prevents nested locks. Review apply rejects truncated/refused
  completions. Authoritative imported state wins over stale derived caches.
  Hosted feedback_pending markers and book locks prevent failed/concurrent cache
  projections from silently feeding old review status to local transport. Source
  namespaces prevent responses from one review site appearing under another's ID.
- Packaging logic moved into installed forage.review_package; compatibility script
  remains. Verified current media references and publication histories are copied;
  obsolete/private assets stay excluded. Original M1 overlap/rollback proof passes.
- Superseded checkpoints: packaging safety gate passed66 cases; then real HTTP
  lifecycle first caught __media__ scope disagreement, which was corrected before
  end-to-end completion. Web gate90 passed, hosted28 passed, final sync39 passed.
  Isolated full lifecycle plus installed wheel gate passed3 cases. M3 focused work
  progressed to the full repository gate; all checkpoints are now closed.
- validation: `.venv/bin/python -m pytest -q` => **629 passed, 6 skipped in
  100.89s**, exit0. The six skips are existing opt-in Docker checks. Two warnings
  are Starlette TestClient timeout deprecations; production stdlib timeout behavior
  is unchanged. This gate includes the installed-wheel proof outside checkout with
  no PYTHONPATH, actual HTTP A→B→C lifecycle and web-only dependency blocking.
- validation: top-level and run/release/publish-review/publish-release/review-pull/
  review-sync CLI help all passed. `node --check forage/webapp/static/app.js` and
  `git diff --check` passed. No browser executable/tool or Playwright/Selenium
  package was available, so interactive visual validation is not claimed.
- blockers: none for the defined offline implementation. Live creative quality,
  Docker execution, real deployment and interactive browser behavior remain
  explicitly unverified. No live API calls, real hosted mutations, dependency
  installs, existing book/work edits, commits or pushes were performed during M3.
- next: independent audit of M3's ten criteria and integrated project AC1–AC12,
  using HANDOFF-M3.md and permanent test ownership listed there.

## 2026-10-14 — M3 independent-audit remediation

- stage: correction and offline validation
- focus: the four confirmed audit failures: sync completion/settings, first-release
  feedback, actual archive expansion, and durable prose/application decisions.
- outcome: sync now validates explicit options before paid application and uses
  the shared free production planner for complete stage/settings/output validity.
  It retries failed acknowledged media and honors unchanged-prose output/voice
  changes. Requested nonsecret options persist before execution so failed new
  selections do not revert to old successful settings on the next sync.
- Release-only books now accept all five comment scopes and export feedback.
  Default selection prefers review, then release only when review is absent;
  explicit channel/revision remains strict. Historical release anchors and HTTP/
  local feed parity pass without manufacturing a review pointer.
- Archive upload bounds every decompressed byte before tar parsing, including
  PAX/GNU metadata, headers, padding, trailing tar and concatenated gzip streams.
  Compressed, actual expanded, regular-member and file-count checks remain;
  positive integer bounds are validated. Adequately bounded valid PAX snapshots
  still install successfully. Failed expansion leaves current pointers intact.
- New provider-free review_recovery writes durable decision/ledger intent before
  changing snapshot/draft/checks/ledger. Recovery checks all target before/after
  hashes, including the pre-request ledger, before finishing atomic writes.
  Existing decisions survive; conflicting intervening prose/ledger edits retain
  their bytes and intent and block publication. Standalone apply, pull/sync and
  direct production recover first; read-only plans and snapshots reject pending
  intent. Recovery after durable intent never repeats the model request.
- Focused proof: archive 47 passed; release-only/web/security/transport/packaging
  113 passed; sync/recovery 64 passed; final recovery/lifecycle 22 passed after the
  ledger-during-request conflict regression. Initial concurrent fixture runs
  encountered only the not-yet-written shared recovery module; reruns passed
  after that implementation landed. No workaround or skipped proof was accepted.
- validation: final `.venv/bin/python -m pytest -q` => **680 passed, 6 skipped,
  8 warnings in 72.01s**, exit0. The six skips remain opt-in Docker tests; eight
  warnings are existing Starlette TestClient timeout deprecations in HTTP proofs.
  This adds 51 regression cases to the prior 629-test gate.
- validation: all production/review/publication CLI help, Node app.js syntax,
  compilation in the recovery worker, and `git diff --check` passed. Isolated
  installed-wheel CLI/resources/graphics and web-only dependency proof are in
  the final full gate. Browser availability remains unchanged/unavailable.
- blockers: none for offline implementation. No live provider calls, real hosted
  mutation, dependency installs, existing book/work changes, commits or pushes.
- next: independent resolution audit of the four findings and integrated
  PROJECT AC1–AC12; no additional implementation remains pending this audit.

## 2026-10-14 — Complete project independently audited

- All four M3 findings resolved. Final independent audit passes all ten M3 criteria and all twelve project criteria across correctness, structure and forward impact.
- Final owning suite: 680 passed, 6 Docker skipped in 72.01s. Independent resolution: 165 focused tests plus original failure probes passed. Installed wheel, web-only runtime, CLI help, JavaScript syntax and diff checks passed.
- The offline implementation is complete. No live generation, actual publication/deployment or commits performed. Interactive browser and Docker execution remain unverified.
- Next: operator use of documented configuration and explicit production/publication commands; no implementation task remains in the authorized scope.

Superseded pre-resolution state retained below:

# Current Status

## Current Stage

[done] M3 audit remediation and final offline gate complete; resolution audit next.
M1/M2 passed independent audits. All four M3 findings have corrections and
permanent regressions; independent resolution certification is still pending.

## Current Focus

Audit the final changes against AUDIT.md findings 1–4 and PROJECT AC1–AC12.
HANDOFF-M3.md documents operational contracts, commands, recovery behavior,
configuration, test ownership and explicit verification limits.

## Done

- Original safety/completion/freshness fixes and resumable text/audio/graphics.
- Hosted immutable review/release publication, media comments, feedback sync,
  explicit apply/republish, continued public releases and installed packaging.
- M3 corrections: common-planner sync recovery/settings validity, release-only
  comments/feeds, complete decompressed archive bounds, durable review intent
  and ledger recovery with conflicts blocked across apply/sync/run/snapshot.

## Validation

- Final owning gate: **680 passed, 6 Docker skipped in 72.01s**, exit0.
- Includes checkpoint/media/settings retry, all application commit fault
  boundaries/conflicts, release-only lifecycle, expanded metadata bounds, real
  HTTP A→B→C lifecycle, isolated installed wheel and web-only dependency proof.
- CLI help, Node syntax and diff checks passed. Eight existing TestClient timeout
  deprecation warnings; no failed checks. 51 new cases since the prior 629 gate.

## Blocked

None. Live creative quality, Docker execution, deployment and interactive browser
behavior remain unverified. Browser executable/tools/Playwright/Selenium unavailable.

## Next

Independent M3 resolution audit; resolve any newly verified finding within scope.

## Working State and Prerequisites

README.md, CLAUDE.md, pyproject.toml, requirements-web.txt and project contracts
remain authoritative. Existing .venv/build tools used; no new dependencies.
Pre-existing model edits and work/_model_comparisons preserved. No real book/work
mutation, live generation, hosted deployment/publication, commits, pushes, resets
or Nova builds. Base: 3644fc8. Changes remain uncommitted by instruction.


## 2026-10-15 — Fly hosted storage deployment preparation

- Enabled FORAGE_HOSTED_ROOT=/data/hosted in Fly and Docker defaults, copied
  package build/resource hooks into the image, and corrected single-machine
  deployment guidance for both SQLite and publication storage.
- Corrected the container persistence INSERT to name its columns; readiness
  now waits for HTTP rather than a pre-existing database file. Added configured
  upload/promotion and real-image feedback/restart persistence coverage.
- Validation: 38 configuration/security tests passed; all 7 real Docker tests
  passed in 38.79s; installed resources and web-only imports passed outside /app;
  diff and entrypoint shell checks passed. No paid provider calls.
- Prepared 4.0 MB of artifacts for dragon_maiden, education, gatsby,
  secret_adversary and treasure_island, matching the live site's five book IDs.
- Deployment is authorized but not yet performed: Fly CLI reports no access
  token. Installed Fly CLI 0.4.118 and requested authentication.
- Next: authenticate, inspect existing Fly state, deploy and verify the live site.

## 2026-10-19 — Fly deployment complete

- Loaded the user-provided `FLY_API_TOKEN` from ignored `.env` without displaying
  the token. Inspected the existing app, machine, volume and secret names;
  retained the single-machine topology and all three existing app secrets.
- Backed up SQLite with its online backup API, downloaded and integrity-checked
  the backup, recorded hashes for 62 volume artifact files, and completed volume
  snapshot `vs_kk9PokZpY0Bhg2V5qJXBO6` before deployment.
- Rebuilt the prepared Docker image; all build layers were cached. Compared
  image metadata: filesystem layers and runtime configuration exactly match
  `forage-review:pytest`, which passed the seven real Docker tests on October 15.
  Pushed using temporary registry credentials, then removed those credentials.
- Deployed immutable image index
  `sha256:7c4f27818b64efc57c88ba434cbaaaba59d72ce0710123e1d58591f11de3dc25`
  with `--ha=false --update-only --strategy rolling`. Fly release v16 uses
  existing machine `87e005f0262398` and volume `vol_re176w7xje1gj214`; health and
  DNS checks passed. Running amd64 manifest:
  `sha256:2b6eac508658823fe2a1be24a2d6c8bd39c7f942006413895dc50abfd5864e0c`.
- Live verification passed: five identical book summaries, 133 chapter reads,
  all seven comments preserved, 62 artifact hashes unchanged, SQLite integrity,
  source-matching HTML/JS/CSS, closed schema endpoints and anonymous-write
  rejection. Reviewer/admin HTTPS sign-in and secure cookies work; reviewers
  cannot upload, while an empty admin upload reaches archive validation.
- Verified the actual server runs as uid 10001 and can write `/data/hosted` on
  the persistent mount. Removed the temporary storage probe. No new book or
  publication was created, no paid provider call was made, and no secrets were
  rotated. Full publication/restart behavior remains covered by the prior real
  Docker tests; interactive browser rendering was not exercised live.
- Evidence and operation helpers: `/mnt/data/tmp/forage-fly-20261019/`.
  STATUS.md contains the deployment and backup record. Deployment changes remain
  uncommitted; no Git push or reset was performed.

## 2026-10-19 — Comment attachment repair and requested regeneration

- Recovered all seven original reviewed passages from archived drafts. Five
  comments had been displayed against unrelated numeric positions after prior
  paragraph splits. Removed numeric fallback: exact anchors follow moved text;
  generation records validated original-to-revised passage bindings, including
  split passages and an explicit primary display paragraph. Unmatched notes
  stay visible separately. Exports preserve original text instead of substituting
  the current text at the old index; application blocks unverifiable targets.
- Added optional `ANTHROPIC_WORKSPACE_ID` routing. With the workspace provided
  by the user, ran the requested chapter regeneration against the original
  reviewed draft and then alignment using Sonnet 5.5. Six notes were applied;
  the hostel note was skipped because its introduction follows the source.
  One response field contained the comment ID instead of its feedback key.
  Corrected this metadata in the cached response and reran validation locally;
  no additional generation call was made. Raw response and correction retained.
- Installed the accepted draft/ledger through recoverable commit, preserving
  the previous live draft. Refreshed alignment and assembled book text. The
  revised chapter has 46 paragraphs and 1,001 words. Usage for the two calls is
  recorded in the book's `llm_calls.jsonl` with their staging execution directory.
- Published the chapter and deployed the attachment fix. The live read check
  caught owner-only generated file permissions after upload; corrected canonical
  packaging to make selected public copies readable without changing source
  permissions. Republished and deployed final release v18 using immutable image
  index `sha256:52a2d445d4b8cc6d83020fb0c6e85d3da5e7b03d44ba48cf1354d0a2ccc83162`.
- Validation: full suite 706 passed before final refinements; final affected
  suites 120 review, 68 packaging and 8 real Docker tests passed. Added regressions
  for moved/split/ambiguous targets, immutable original exports, validated apply
  bindings, owner-only pipeline inputs and service-account access to baked files.
- Live verification: all 133 chapters readable; all 46 revised paragraphs match
  the accepted output; seven notes at paragraphs 8, 9, 13, 14, 16, 18 and 39;
  original comment bodies, indices, anchors, timestamps and open statuses remain
  unchanged. Only chapter 002 alignment/checks and the ledger changed on the
  mounted artifact tree. Original-text exports and served web assets match.
  Browser checks show all seven notes and no JavaScript errors. In a local
  browser preview, Resolve → Reopen → edit retained the correct attachment and
  produced eligible feedback for another pipeline pass without a model call.
- Review workflow remains explicit: Accept accepts a comment for action;
  Resolve closes it after review; resolved notes can be reopened. Reviewers can
  add/edit feedback, but there is no web regeneration button or separate LLM
  revision approval workflow. The seven existing notes remain open for review.
- Backup and operation evidence: `/data/backups/comment-fix-20261019/` and
  `/mnt/data/tmp/forage-comment-fix-20261019/`. No secrets displayed, no token
  rotation, and no Git commit/push/reset. Follow-up changes remain uncommitted.

## 2026-10-19 — Explicit revision acceptance and further review

- Added Accept revision, Reject with comment, and Reopen revision controls to
  model responses. Rejection requires a comment and queues a new request;
  acceptance resolves the note. Reopening restores review without generation.
  Reviewers can update or cancel a pending rejection. Ordinary Accept is now
  labeled Accept comment to distinguish it from accepting an LLM revision.
- SQLite stores append-only revision decisions with reviewer identity, feedback,
  the response reviewed and chapter/publication context. Comment bodies and
  original anchors remain intact. An atomic version check rejects conflicting
  decisions and stale browser pages. A new response always requires its own
  acceptance; reverted prose cannot make a discarded correction reviewable.
- Feedback exports include the decision/request. Application fingerprints a
  rejection once, incorporates its follow-up wording, and verifies the reviewed
  chapter plus the pipeline's own passage binding before calling a provider.
  Accepted/reopened revisions are inactive until another rejection. Book-level
  requests automatically select the chapter named by their model response.
- Production snapshots now include sanitized `review_responses.json`; the
  snapshot depends on the decision ledger so even a skipped/no-change request
  publishes its new response. Hosted views read the pinned snapshot's responses.
  Failed review attempts refresh the authoritative feedback projection, avoiding
  an unnecessary stale local-transport marker after a concurrency conflict.
- Validation: full suite 721 passed before the final edge-case refinements;
  final affected suites 114 review/lifecycle, 56 security/store, 34 revision/anchor
  and 8 real Docker tests passed (overlapping selections). The hosted HTTP test
  completes accept/reopen/reject/apply/publish and a skipped follow-up using
  simulated provider responses. Browser preview tested required feedback,
  persistence across reloads, decision history and all seven paragraph locations.
- Deployed the tested image to the existing single Fly machine/volume as final
  release v20, immutable index
  `sha256:249dba5fa275ee09f9fdc405d913938a403cfc599b3838cb2059aef3bab09caf`;
  running amd64 manifest
  `sha256:3b00d4313513fec9f544661802c948df3fe85b99b5f94473845d7e863db432e6`.
  Health/DNS checks pass. Live verification covered all 133 chapter reads,
  unchanged text and original comment records, migration, authenticated rejection
  validation, seven visible acceptance/rejection controls, and opening/cancelling
  the rejection dialog. No live review decisions were submitted.
- All seven existing notes remain awaiting review. No paid model calls, prose
  regeneration, public-release promotion, token rotation, commits or pushes for
  this feature. Rejection is processed during the next explicit pipeline pass.
- Backup: `/data/backups/revision-workflow-20261019/`. Local evidence and
  operation helpers: `/mnt/data/tmp/forage-revision-workflow-20261019/`.
  Temporary browser/registry credentials removed; isolated preview stopped.


## 2026-10-20 — full Opus 5.5 book runs; provider balance blocked

- User requested complete Adams/Christie runs and explicitly preapproved cost.
  Added `forage.full_run`, using original chapter targets/omissions, pristine
  sources, batched whole-book preservation planning, counted two-pass drafting,
  source-aware eight-axis reviews, independent adjudication with local patch
  repairs, final reviews, existing book critic/validation/alignment/proofreading,
  and immutable local review snapshots. All new calls use Opus 5.5 medium.
- Isolated run: `work/_full_runs/2026-10-20-opus55/`. Original inputs hash-verified
  unchanged. Removed synthetic prefixes only in the isolated copies of Adams
  chapters 017/021 by using their pristine `.orig` sources. Existing website,
  reviewer state and original production artifacts were not regenerated.
- Paid run began 18:39 UTC. At 18:43 UTC Anthropic reported insufficient account
  credit. Five complete responses: fresh Adams synopsis and four validated
  planning batches covering 16 chapters. Completed usage cost $10.294680.
  Three interrupted planning requests have no final usage report; conservatively
  reserve $7.642055 against the $200 cap. Christie failed during free token
  preflight. No chapter drafts, reviews, repairs, alignment or new snapshots yet.
- Account funding requested. Resume after credits are available:
  `.venv/bin/python -u -m forage.full_run run --output work/_full_runs/2026-10-20-opus55 --workers 4 --max-usd 200 --max-calls 600 --retry-credit-errors`.
  Completed responses reuse exact request hashes. Explicit credit recovery keeps
  prior error records/reserves and logs new attempts; other unsettled requests
  remain blocked. No automatic paid retries were performed.
- Validation: initial fixed-target/full-run/production selection 116 passed;
  alignment/publication selection 94 passed; final affected selection 125 passed
  (overlapping selections). Includes a simulated complete snapshot with verified
  paragraph alignment and tests for evidence validation, local edit safety,
  exact response reuse and credit-error recovery accounting.


## 2026-10-20 — full-run retries, detailed reviews and provider credit stop

- Continued under the user's explicit full-run cost approval and funded retry
  requests. All 57 preservation plans, first drafts and counted second drafts
  completed with Opus 5.5. Added bounded 48k-output recovery for truncated
  counted revisions; incomplete prose was never installed.
- Adams completed 28 initial reviews/repairs and 28 second reviews/repairs.
  Repaired text is 72,290 words against 72,200; all 218 protected passages are
  present. Eighteen final reviews are saved. Christie completed 29 initial
  reviews/repairs, yielding 40,801 words against 40,600, and 22 second reviews.
- Added cross-process journal reservation locking and a shared provider-credit
  stop. The operational $200 cost/reserve cap settled at $183.594105 recorded
  cost; continued both books at $350 under existing full-cost approval. At
  20:29 UTC Anthropic again reported insufficient credit. All workers stopped.
  Totals: 350 complete responses, $194.368489 recorded token cost, 28 interrupted
  requests with unknown final usage and a $27.614790 conservative reserve.
- Final review candidates include genuine dangling references despite all
  protected quotations surviving. Prepared a minimal blocking-finding closure
  pass that forbids unrelated offsetting cuts and re-reviews the corrected
  book. It has not run. All ordinary review, repair and raw response artifacts
  are preserved. No final assembly/snapshot/alignment or website publication.
- Saved clearly labeled working-text exports, HTML progress report, partial
  integrity audit and durable retry instructions in the isolated workspace.
  `recovery/resume_both.py --retry-credit-errors` resumes both books after
  funding; `recovery/close_findings.py <book_id>` follows standard completion
  if substantive final blocking candidates remain.
- Latest focused tests: 16 passed. Original 72 input hashes remain unchanged.
  Further provider calls require available account credit; no additional cost
  permission is needed because the user already approved the full task.


## 2026-10-20 — completed full runs, credit diagnosis and restart verification

- Correction to earlier funding assumptions: the user reported ample Console
  credit. The unchanged `.env` key and requested workspace passed tiny and full
  Opus generation probes. The account balance was never verified; the provider's
  earlier low-credit error remains unexplained. Both books then finished without
  another credit error. Routing metadata is retained without credentials.
- Completed all 57 chapters with Opus 5.5, original targets and exclusions,
  counted two-pass drafting, two full review/repair cycles, and two focused
  closure passes. Closing fixes use exact source-backed patches without unrelated
  offsetting cuts; 64 identical complete review contexts were reused for free.
- Adams ends at 72,449 / 72,200 words with zero final must-fix candidates. Its
  whole-book hold maps to three intentionally omitted chapter events. Christie
  ends at 40,749 / 40,600, passes all 47 synopsis checks, and retains two final
  must-fix candidates (003 improvised-name setup; 004 alias-reason reply) for
  editorial review. Optional style/detail findings are preserved in the report.
- Final audit passed: all 72 original inputs unchanged; all 432 protected passages
  present; all saved review contexts and evidence valid; every local patch replayed
  exactly; all final alignments current; both immutable snapshots verified.
- Fixed default-runner resume so it verifies and retains the latest completed
  snapshot instead of replaying older phases over final repairs. 20 focused tests
  pass, and real completed-book resumes were verified without any generator call.
- 565 journaled responses: $281.992725 estimated token cost, plus
  $0.000140 for the diagnostic. 28 interrupted requests have unknown usage;
  conservative reserve $27.614790, not a verified charge. Provider prompt cache:
  0 read tokens, 3,730,097 write tokens. Only planning configured cache
  control; persistent response reuse is distinct and survives restarts.
- Final report, verification, current run manifest, diagnostic evidence, and
  final relevant implementation snapshots are saved in the isolated workspace.
  New book snapshots remain local; no website publication or Git commit/push.


## 2026-10-20 — published full-run editions through the pipeline

- User requested the website update and explicitly required using the pipeline.
  Ran `forage publish-review` for both final snapshots from the isolated full-run
  workspace against https://forage-review.fly.dev. Hosted review pointers advanced
  successfully at 21:44 UTC; no regeneration, paid model calls, application
  deployment, or direct hosted content edits were performed.
- Adams review revision:
  `89cd02779bd148f5ad38cf98d59456328b1914ba81d60f059310dbedba05b162`.
  Christie review revision:
  `c13ea7e54c8ca5916cfae075d4fa50982e45f6146743adc950ed91a30522e62f`.
- Verified all 57 hosted chapters against local paragraph alignments, including
  source text and indices; complete text downloads match the immutable snapshots.
  Read-only browser checks confirmed both revisions render without JavaScript
  errors. The other three books, public release pointers, and app v20 are unchanged.
- All seven prior Christie comments retain their content, original anchors,
  statuses, decisions and history. Their earlier-edition anchors are stale and
  unplaced in the new full regeneration; the browser displays them under
  "Notes awaiting a matching passage". No reviewer decisions were submitted.
- Evidence, CLI logs, before/after metadata, chapter verification and browser
  screenshots are saved in
  `work/_full_runs/2026-10-20-opus55/website-publication/`.
  Updated run/operator metadata to record the verified hosted publication.


## 2026-10-20 — pipeline findings and repair review live (v21)

- User approved publishing critic findings/repair history into the review UX and
  explicitly kept pipeline reruns outside the website. Added immutable
  `pipeline_review.json`, automatic full-run packaging, and provider-free
  `forage prepare-review` for previously completed runs. The stage validates
  current chapter context, evidence, exact historical patch replay, and the
  prior snapshot inventory without changing prose or calling a model.
- Publication imports stable pipeline items idempotently into the existing
  review database. Decisions reuse the existing revision API and history;
  findings offer dismiss/request/reopen, while chapter repair cards offer
  accept/reject/reopen. Evidence, adjudications and before/after patches remain
  available. Explicit requests feed external review-pull/review-sync; pending
  items and reopening alone do not queue generation. Subsequent responses need
  fresh review. Earlier-edition views exclude later pipeline items.
- Published Adams revision
  `62885e00511e10faf75e7e5344ba670f086ecb73ed3eff7c4af15daff3867ff4`
  (240 items) and Christie revision
  `1db5c7538c28c3f9499b6bdd69c7e415bf590f9966007eaa1d486be76cbb3466`
  (213 items) through `forage publish-review`. These include 57 chapter repair
  cards and both remaining Christie must-fix findings. Every previous snapshot
  file remains byte-identical; only the review package/manifest were added.
- Full suite: 760 passed, 8 container tests skipped there; all 8 actual container
  tests passed on the final deployable image. Final producer/lifecycle selection:
  25 passed (overlapping). Preview browser exercised both decision workflows,
  required feedback, persistence and history. Fixed details collapsing after a
  decision and null empty-section text observed in browser inspection.
- Created volume snapshot `vs_9K386K1QPeoT3j8Xnv4zax`. Deployed tested image
  `sha256:ca2aa6ebd286be41675a2564635669884bd0f00a4de3b22259c328011057581d`
  as Fly release v21 on the existing machine and volume. Secrets are unchanged;
  temporary registry/browser credential files were removed.
- Live verification: all 57 chapter texts/source mappings, 453 current pending
  review items, original full-text downloads, seven original comments and
  histories, other three books, release pointers, and health passed. Signed-in
  browser verified controls/evidence on both books without submitting decisions.
  No paid generation, Git commit, or push. Preview server stopped.
- Durable evidence: `work/_full_runs/2026-10-20-opus55/pipeline-review-publication/`.
  Updated run/operator publication metadata; remaining editorial decisions are
  still for the reviewer, including the two Christie coherence candidates.

## 2026-10-20 — audit corrections validated locally

- Fixed the completed-full-run/common-runner provenance mismatch with a verified
  origin adapter. New snapshots include source inventories; older workspaces
  verify their existing source manifest and immutable alignment evidence.
  Feedback refresh retains the original plan, fixed targets, exclusions and
  accepted prose. Shared downstream stages handle refresh and durable retries;
  no-op sync reuses the existing revision. Preflight validates provenance,
  accepted drafts and settings before feedback can issue a paid request.
- Unified text identity across both producers and feedback eligibility. Older
  snapshot IDs remain unchanged; book feedback can match their verified plan
  and draft bytes. Full-run resume follows the latest successful feedback
  publication. Original fidelity evidence is retained as historical evidence.
- Fixed revision freshness for a deliberately removed paragraph by requiring
  its recorded final chapter hash. Acceptance/reopening/rejection and restoring
  the passage through feedback now work; subsequent chapter edits still block
  stale decisions. A superseded pipeline item now returns HTTP 409 before
  indexing the filtered notes or writing a decision, preserving its history.
- Added 33 regression cases using actual full-run finalization, hosted HTTP
  feedback/decisions and mocked model transport, covering both new and legacy
  snapshots, no-op reuse, apply/republish, skipped responses, failed-refresh
  retry, invalid preflight inputs, deletion restoration and historical items.
- Validation: full suite 789 passed / 8 Docker skipped; actual container suite
  8 passed; final affected selection 182 passed including four additional
  preflight cases. Existing TestClient timeout deprecations remain warnings.
  `git diff --check` passed. Both real completed workspaces pass free planning
  with their existing revision IDs, unchanged plan/result/pointer bytes and no
  `production_state.json` creation. Updated README, architecture and status;
  appended audit resolution. No live mutations, paid calls, deployment, commit
  or push. Fixes are local; the deployed v21 code is unchanged.

## 2026-10-20 — audited fixes deployed as v22 (2026-10-21 UTC)

- User requested deployment. Refreshed the five-book baked payload, rebuilt
  the image through the real container suite, and passed all 8 tests. Saved
  a SQLite backup at `/data/backups/audit-fixes-20261021/review.db`, verified
  its integrity locally, and created volume snapshot `vs_vzAZpzYgLG7h3Bmjwl20q4Q`.
- Deployed immutable image
  `registry.fly.io/forage-review@sha256:c139be967d8d5e89612876f96ce7540da1dcbf7233f2400f2d72fdda58e35a76`
  using `--ha=false --update-only --strategy rolling`. Fly release v22 uses
  the existing `87e005f0262398` machine and `vol_re176w7xje1gj214` volume in iad.
  Health, smoke and DNS checks pass; environment and secret digests are unchanged.
- Verified all 64 deployed source files against the working tree, 676 stored
  artifact files against the backup, SQLite integrity and unchanged comments,
  review metadata and revision-decision tables. Public before/after captures
  match for all five books, 115 chapters, 460 comments, downloads and channel
  pointers. Existing full-run snapshots were not regenerated or republished.
- Authenticated validation and the deployed deletion-binding helper pass.
  Signed-in read-only browser checks pass for both remaining Christie findings,
  Adams repair controls, evidence, request dialogs and external-pipeline
  messaging, with no JavaScript errors or reviewer decisions submitted.
- No paid generation, Git commit or push. Temporary registry and browser
  credentials were removed. Evidence and operation scripts:
  `/mnt/data/tmp/forage-audit-deploy-20261021/verification.json` and neighboring
  files. Pipeline feedback generation remains an external operator action;
  deployment does not start a rerun.

## 2026-10-21 — chapter-first review layout live (v23)

- User accepted simplifying the internal critic section: prose now leads the
  chapter, with jump buttons for Suggested issues and Review history. Suggestions
  are compact and collapsed by default, with reader-facing priority and decision
  labels. Completed repairs, dismissed/outdated suggestions, draft diagnostics
  and detailed critic records live in a collapsed history panel after the text.
  Citation labels distinguish original source, earlier draft and reviewed draft.
- Existing response/decision APIs and stored evidence remain unchanged. Dismissed
  suggestions move to history; reopening returns them to the active list. The
  destination is revealed and keyboard focus follows the item. History disclosure
  survives same-chapter rerenders and resets on chapter/edition navigation.
- JavaScript syntax and diff checks pass; 41 affected tests and all 8 real-image
  container tests pass. Browser preview exercises both full decision cycles,
  persistence/export, source comparisons, request validation, chapter comments,
  desktop/mobile and public/reviewer states. No new dependencies or schema changes.
- Backed up SQLite and the volume (`vs_25RDp5Yq2X7HbRAPkA9JJ06`); a registry
  upload timed out once and succeeded on retry. Deployed immutable image
  `sha256:407bee1c6913de663e8d1b8468293d1101befc7d4c8a290b1b24b4f86e848d17`
  with rolling update, `--ha=false --update-only`, as release v23 on the existing
  machine/volume. Health, smoke and DNS checks pass; secrets and environment match.
- Live verification: all five books, 115 chapters, 460 comments, downloads and
  pointers match the pre-deploy captures. All 64 deployed source files match the
  working tree, 676 stored artifact hashes match the backup, and SQLite integrity
  and all application table rows are unchanged. Read-only desktop/mobile browser
  checks pass, without JavaScript errors or live reviewer decisions.
- Evidence, screenshots, backup and operation scripts:
  `/mnt/data/tmp/forage-review-layout-20261021/`. Temporary registry/browser
  credentials removed. No paid generation, Git commit or push.

## 2026-10-21 — approved review feedback incorporated and published

- Pulled the live feeds for all five books. One actionable paragraph note,
  `8b74e1d2dee2`, requested restoring hospital setup in Secret Adversary 002.
  Imported the complete current feeds for both full-run books, preserving the
  user's deletion of seven older Christie comments. Source and immutable-origin
  preflight passed before paid work; the user explicitly approved the estimated
  $1–2 run.
- Ran `forage review-sync secret_adversary --apply --republish --segment 002`
  against `work/_full_runs/2026-10-20-opus55` and the live review site. Opus 5.5
  restored the source's Sister Greenbank/doctor/chart clause in paragraph 8,
  adding 28 words. No other paragraph or chapter changed. Whole-book critic and
  chapter alignment completed normally: 47/47 synopsis claims present and all
  214 protected passages retained. Three completed provider calls have an
  estimated token cost of $0.704138, including prompt cache writes.
- Pipeline publication confirmed review revision
  `4dd94ce6dd03ec0a930ec12484b8ba10b4a961b674864059a12a7cabb21bd793`.
  Verified all 29 hosted chapters, alignment mappings, complete downloads and
  old/new immutable snapshot inventories. All 214 comment bodies, statuses and
  original anchors remain unchanged; the applied note has a verified current
  binding and a pending revision decision. Other book pointers, Adams prose and
  the public release channel remain unchanged.
- Signed-in and public browser checks confirm the source restoration, attached
  note, explanation, pending Accept/Reject controls and mobile layout, with no
  JavaScript errors or live decisions submitted. Fresh free pull reports zero
  pending requests; free production planning reuses every completed stage.
  App release remains v23; no deployment, code edit, Git commit or push.
- Evidence, exact paragraph diff, usage log, publication acknowledgement and
  desktop/mobile screenshots: `/mnt/data/tmp/forage-feedback-20261021/`.
  Temporary browser session credentials were removed.

## 2026-10-21 — persistent user accounts replace shared tokens

- Implemented AccountStore in the existing persistent review database. Passwords
  are salted scrypt hashes (N=32768/r=8/p=3); session cookies contain random
  256-bit identifiers whose hashes are stored server-side. Each request resolves
  current account permissions. Logout, password changes and account deletion
  revoke sessions; deletion preserves all review records and attribution.
- Added username/password login, admin-only list/create/remove endpoints and
  Users UI, plus a personal password-change/sign-out menu. Case-insensitive
  usernames are unique. Last-admin/self-removal protections run in the write
  transaction. Admin mutations recheck the actor after expensive hashing.
  Account responses omit password/session hashes, and auth responses are no-store.
- Updated CLI publishing transport, operational smoke checks, test fixtures,
  bootstrap documentation and deployment examples to use accounts. Legacy
  login tokens and signed role cookies are removed rather than retained as a
  fallback. Initial admin creation uses a hidden local prompt or one-time
  bootstrap secrets; existing accounts are never overwritten at startup.
- Validation: 797 full-suite tests passed, 8 Docker tests skipped there; all 9
  real-image tests passed, including restart without bootstrap credentials and
  password persistence. 26 focused account tests and 106 affected tests overlap
  the suite. Updated HTTP smoke checks passed. Dedicated real-browser checks
  exercised create/remove, reviewer restrictions, password change, deleted-user
  rejection and desktop/mobile layouts without JavaScript errors.
- Backed up SQLite and 780 artifact hashes under `/data/backups/accounts-20261021`
  and created snapshot `vs_KA4ewADgkzQTZovyPVOQDKD`. Deployed tested image index
  `sha256:46f3b456a35bce9717d59549226e249a9a8b1ff21de298ba5828db2669aa615e`
  as v24 on the existing single machine/volume. Created initial `admin` and
  dedicated `pipeline` accounts, configured local publishing credentials, then
  removed legacy and bootstrap Fly secrets; the resulting restart is v25.
- Live verification: all 65 source files match, all 780 stored artifact hashes
  and all 454 review records are unchanged, and every public response/download
  across five books and 115 chapters matches the pre-deploy capture. SQLite
  integrity passes. Real old shared credentials and correctly signed legacy
  cookies are rejected. New admin and pipeline accounts authenticate. Browser
  verifies admin management controls, password form, logout and mobile layout.
- Operation evidence, screenshots, immutable image and rollback metadata:
  `/mnt/data/tmp/forage-accounts-20261021/`. Initial admin credentials and retired
  secrets are in owner-only files outside the repo. No paid model calls, Git
  commit or push. Account migration is release-verified.
