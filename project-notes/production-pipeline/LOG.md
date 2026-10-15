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
