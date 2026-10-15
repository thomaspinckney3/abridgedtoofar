# M1 — Artifact safety and completion audit

## 2026-10-14

### Verdict

M1 is exposed and substantially implemented, but does not yet pass all three
audit dimensions. Packaging, draft completion/status reuse, and alignment
freshness satisfy the scoped contract. Audio provenance and ordinary failure
preservation work, but rollback failure can delete the only recovery copy, and
the newly caught publication failure is invisible in the CLI's success result.
Resolve the two findings before marking M1 complete. This audit does not certify
M2/M3 or the full project: runner, graphics integration, media review, hosted
feedback synchronization, and explicit public release remain outstanding.

Read README.md, CLAUDE.md, pyproject.toml, BRIEF.md, PROJECT.md, PLAN.md,
ARCHITECTURE.md, STATUS.md, the historical review, changed production code, and
the four new test modules. Existing model-default edits were excluded from M1.
No live calls, existing book/work mutations, production fixes, or commits were
performed.

### Findings

1. **[P2] Failed audio rollback deletes the previous successful chunk's backup.**
   - Evidence: `forage/audiobook.py:638`, `forage/audiobook.py:658`,
     `forage/audiobook.py:664`.
   - `_replace_chunk_output` stages replacements and recovery copies inside a
     `TemporaryDirectory`. If the audio rename succeeds, the sidecar rename
     fails, and restoring `0.old` also raises, exiting the context unconditionally
     deletes the recovery directory. The old audio is then permanently gone,
     while new audio and the old sidecar remain. The error path therefore breaks
     BRIEF AC6's preservation requirement. Packaging handles the corresponding
     failure by retaining recovery backups; audio should do the same and report
     their location. Add an offline regression for publication-plus-rollback
     failure, beyond the existing successful-rollback case.
   - Command used: rollback probe below. Observed `audio_after_failure: b'new
     audio'`, `sidecar_after_failure: previous text`, `recovery_backups: []`.

2. **[P2] Audio publication failures now return successful CLI status without a visible error.**
   - Evidence: `forage/audiobook.py:350`, `forage/audiobook.py:353`,
     `forage/audiobook.py:392`, `forage/cli.py:803`, `forage/cli.py:868`.
   - The new publication exception handler preserves the old public file, but
     stores the failure only in the manifest's `combine_error`. It neither
     increments a failure count nor exposes the error on `AudiobookResult`.
     The existing CLI prints `errors 0` and exits 0. Before this handler, a
     publication `OSError` propagated as failure. A requested replacement can
     now fail while automation and the operator receive success. Expose actual
     combination/publication failures through the result and CLI, with a nonzero
     exit and visible cause; preserve the intentional separate-chunk behavior
     where applicable. This also gives M2 an explicit failure contract instead
     of requiring it to infer success from the generated chunk count.
   - Command used: CLI publication probe below. Observed `cli_exit_code: 0`,
     `manifest_error_count: 0`, a nonempty publication error in the manifest,
     and `failure_visible_in_cli: False`.

### Completeness

- Truthful state: **exposed**, not release-verified; findings remain.
- BRIEF AC1: passed. Resolved overlap/aliases, IDs and selected-input confinement,
  malformed input, copy/rename failures, rollback backup retention, empty
  discovery, default selection, normal deploy layout, and one-book archive are
  covered. Two renames are correctly documented as not crash-atomic.
- BRIEF AC2: passed. Shared `LLMResponse` completion properties cover
  `max_tokens`/`length`, single/group/fallback/replay/reduced-thinking paths,
  empty responses, cut/success behavior, and assembly rejection.
- BRIEF AC3: passed. Disk results consult recorded checks; corrupt/missing
  group provenance cannot certify completion. Successful groups reuse once;
  failed groups preserve failure and retry at the next first-member pass.
- BRIEF AC4: passed. Embedded paragraph comparisons handle legacy caches;
  invalid caches regenerate. Source/read/provider/invalid mapping/write errors
  are reported and preserve the previous alignment. Integration proves current
  `ArtifactStore.chapter_view` and stale old comments after regeneration.
- BRIEF AC5: passed. Versioned request hashes cover effective synthesis
  settings, provider/context/request IDs. Byte hashes, sizes, sidecars and prior
  successful status gate reuse; neighbor changes invalidate stitched chunks.
- BRIEF AC6: **incomplete**. Preview separation, limits, failed generation,
  successful rollback, verified combination and ordinary publication failure
  preserve prior bytes. Findings 1–2 cover unresolved rollback and observable
  failure behavior.
- BRIEF AC7: **incomplete proof for findings 1–2**. Existing new regressions
  pass, and the historical script is explicitly retired. New permanent cases
  must prove both remediations.
- Completion matrix: first three M1 rows have broad offline proof, with the
  audio failure exceptions above; all M2/M3 rows remain pending.
- Implementation approach: steps 1–4 complete; step 5 incomplete on rollback
  preservation and failure visibility; step 6 needs the additional regressions.
- Done-when conditions: focused tests and diff check pass; full suite gate is
  recorded below. `[done] M1` in STATUS is premature while these findings remain.
- Files listed in brief: relevant owners changed; publication/web consumers and
  shared artifact I/O properly reused without unnecessary edits. No missing
  planned production component for M1 beyond the findings.
- Architectural intent: correct ownership and provenance mechanisms, with the
  two failure-contract gaps above. No competing cache/index framework added.
- Deferred items: no M1 scope may be silently deferred. M2/M3 are separate
  planned milestones, not proof of completion of the user's full request.
- Placeholder audit: no newly introduced placeholder implementation found;
  inspected success/failure branches, including the silent failure in finding 2.

### Verification

- Independently ran `.venv/bin/python -m pytest -q
  tests/test_artifact_safety.py tests/test_draft_completion.py
  tests/test_alignment_freshness.py tests/test_audiobook_reuse.py`:
  **162 passed in 1.35s**, exit 0.
- Independently ran `git diff --check`: exit 0.
- Full M1 gate, reported in STATUS and by the parent implementation session:
  `.venv/bin/python -m pytest -q`: **272 passed, 6 Docker tests skipped in
  2.08s**, exit 0. Not redundantly rerun by this audit.
- Both additional probes below used temporary trees and mocked providers/file
  operations. They made no live calls and did not mutate repository artifacts.
- Docker execution, live generation quality, and hosted deployment remain
  unverified; no release verification is claimed for them.

### Structural assessment

- Architecture: ownership is appropriate. LLM completion is centralized;
  alignment uses authoritative embedded inputs; audio owns request/output
  provenance; packaging owns staged output replacement.
- Abstraction: no competing state database or duplicated pipeline introduced.
  Audio's replacement helper needs the same recovery principle already used by
  packaging, without requiring a broad filesystem abstraction.
- Semantic families: single/group/replay completion and generated/reused audio
  use shared predicates. Rollback retention currently diverges between package
  and audio outputs (finding 1).
- Patterns: existing module/result conventions retained. The expanded
  `generate_audiobook` remains a long function with request construction,
  generation, combination and publication concerns; M2 should consume an
  explicit result contract, and further orchestration should not accumulate in
  this function.
- Integrity: fail-closed provenance checks are sound; finding 2 is a newly
  swallowed publication failure at the public command boundary.
- Scope: M1 changes are focused. Pending model/default/comparison work was
  preserved and not attributed to this milestone.

### Forward impact

M2 can build on the new completion/freshness contracts once the two audio
findings are fixed. It must also inspect alignment's returned errors and validate
draft completeness before existing partial assembly, as ARCHITECTURE.md already
requires. These existing API semantics are not M1 omissions. Small fix now:
retain recoverable audio backups and expose requested publication failure on the
audio result before the runner relies on it.

### Remediation mapping

- M1: retain audio staging/backups if rollback cannot restore the previous
  output; raise an error naming the recovery path; test intact backup bytes.
- M1: expose actual publication/combination failure to the caller and CLI;
  test nonzero exit and visible cause on failed requested publication while old
  public bytes remain intact.
- M1 audit follow-up: rerun the affected audio/CLI tests and the milestone gate
  after changes, append the resolution audit, then update STATUS and PLAN.

### Reproduction commands

Rollback failure:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from forage.audiobook import AudiobookChunk, _replace_chunk_output
with TemporaryDirectory(prefix='forage-m1-audit-') as temp:
    root = Path(temp)
    audio = root / 'audio' / '0001.mp3'
    sidecar = root / 'chunks' / '0001.txt'
    audio.parent.mkdir(); sidecar.parent.mkdir()
    audio.write_bytes(b'previous successful audio')
    sidecar.write_text('previous text\n')
    chunk = AudiobookChunk('0001', 'new text', sidecar, audio, 'unused')
    original_replace = Path.replace
    def fail_sidecar_and_restore(self, target):
        if self.name in {'1.new', '0.old'}:
            raise OSError('injected publication/rollback failure')
        return original_replace(self, target)
    try:
        with patch.object(Path, 'replace', fail_sidecar_and_restore):
            _replace_chunk_output(chunk, b'new audio')
    except OSError as error:
        print(type(error).__name__, str(error))
    print('audio_after_failure:', audio.read_bytes())
    print('sidecar_after_failure:', sidecar.read_text().strip())
    print('recovery_backups:', list(root.rglob('*.old')))
PY
```

Publication failure:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from typer.testing import CliRunner
from forage import audiobook, cli
from forage.artifacts import Book
with TemporaryDirectory(prefix='forage-m1-cli-audit-') as temp:
    root = Path(temp)
    source = root / 'books' / 'sample' / 'source.txt'
    source.parent.mkdir(parents=True)
    source.write_text('Original book')
    (source.parent / 'abridgment.txt').write_text('New narration')
    public_audio = source.parent / 'audiobook.mp3'
    public_audio.write_bytes(b'old public audio')
    book = Book('sample', source, {}, root / 'work' / 'sample')
    def combine(paths, output_path, **kwargs):
        output_path.write_bytes(b'new combined audio')
        return output_path, None
    original_replace = Path.replace
    def fail_publication(self, target):
        if target == public_audio:
            raise OSError('injected publication failure')
        return original_replace(self, target)
    with patch.dict('os.environ', {'ELEVENLABS_API_KEY': 'offline'}), patch.object(cli, 'load_book', return_value=book), patch.object(audiobook.ElevenLabsClient, 'text_to_speech', return_value=(b'new audio', {})), patch.object(audiobook, 'combine_audio_chunks', side_effect=combine), patch.object(Path, 'replace', fail_publication):
        result = CliRunner().invoke(cli.app, ['audiobook', 'sample', '--voice-id', 'fixture'])
    manifest = json.loads((book.work_dir / 'audiobook' / 'audiobook_manifest.json').read_text())
    print('cli_exit_code:', result.exit_code)
    print('manifest_error_count:', manifest['error_count'])
    print('manifest_combine_error:', manifest['combine_error'])
    print('failure_visible_in_cli:', 'publication failure' in result.output)
PY
```

# M1 — Resolution audit

## 2026-10-14

### Verdict

**M1 passes functional, structural, and forward-impact review against its
bounded offline acceptance contract.** Both findings from the initial audit
above are resolved. This verdict covers M1 only. M2/M3, live-provider quality,
Docker execution, hosted deployment, and a public release are not certified.

### Findings and resolution evidence

1. **Original finding 1 resolved: failed audio rollback retains recovery bytes.**
   - `forage/audiobook.py:645` creates an explicitly managed staging directory;
     `forage/audiobook.py:677` retains it on restore failure and raises an
     `AudiobookError` identifying recovery paths; cleanup at
     `forage/audiobook.py:688` respects that decision.
   - Repeated the original simultaneous sidecar-publication/backup-restore
     failure injection, adapting the exception handler to the new
     `AudiobookError`. Independently asserted exactly one `0.old` backup,
     original audio bytes intact, old sidecar intact, and the backup's exact
     path included in the error. All assertions passed.
   - Permanent proof:
     `tests/test_audiobook_reuse.py:392` additionally restores the retained
     backup to demonstrate that the reported path is sufficient for recovery.

2. **Original finding 2 resolved: requested combined-output failure is explicit.**
   - `forage/audiobook.py:66` adds `AudiobookResult.combine_error`, populated at
     `forage/audiobook.py:411`; incomplete narration, combine errors and
     publication errors populate this field. `forage/cli.py:804` exits nonzero,
     and `forage/cli.py:873` displays the cause.
   - Reran the exact original CLI publication probe from the preceding audit.
     It now exits **1** and displays `combine_error` with the injected cause.
     The original probe's contiguous substring check prints `False` at the
     default 80-column width because Rich wraps `publication` and `failure`
     across lines; inspected the captured output and asserted both fragments
     and the error label are present. This is formatting, not a hidden failure.
   - `error_count` remains the number of failed synthesis chunks, correctly 0
     when synthesis succeeds and publication fails; the separate result field
     and nonzero CLI result now preserve both facts.
   - Permanent proof: `tests/test_audiobook_reuse.py:425` covers publication,
     returned/raised combination errors and limited incomplete output with
     visible causes, nonzero exits and preserved public bytes.
     `tests/test_audiobook_reuse.py:468` proves explicit `--no-combine` succeeds.

### Completeness

- Truthful state: **release-verified for the scoped M1 offline contract**;
  this is not certification of a hosted deployment or completion of the full
  production-pipeline project.
- BRIEF AC1–AC5: prior passing assessments remain valid; these components were
  not changed by the remediation.
- BRIEF AC6: passed after both audio failure-contract repairs.
- BRIEF AC7: passed. Six new permanent offline regression cases cover the
  remediations, the historical defect script remains retired, and the final
  full gate passes.
- Completion matrix: M1's three rows pass; all M2/M3 rows remain outstanding.
- Implementation steps and done-when conditions: all M1 items satisfied within
  the explicit offline scope. STATUS records the final gate and uncommitted
  working-tree state. No M1 deferral or placeholder remains.
- Files/architecture: repair remains in the owning audio result, output
  replacement helper and CLI, with matching tests and README/help updates.

### Verification

- Independently ran `.venv/bin/python -m pytest -q
  tests/test_audiobook_reuse.py`: **50 passed in 0.56s**, exit 0.
- Independently ran `git diff --check`: exit 0.
- Independently reran both original failure scenarios as described above, using
  temporary trees and mocked providers/file operations only.
- Final full gate from the implementation session and STATUS:
  `.venv/bin/python -m pytest -q`: **278 passed, 6 Docker tests skipped in
  7.04s**, exit 0. Not redundantly repeated by this focused resolution audit.
- No live requests, existing book/work mutations, production fixes, dependency
  installations, or commits were performed by this audit.

### Structural assessment

Architecture, abstraction, semantic families, integrity and scope pass for M1.
Audio and packaging now both retain recovery artifacts when rollback cannot
finish. The audio result exposes completion failure without redefining the
chunk-generation counters. Explicit separate-chunk operation remains valid;
requesting combined publication now requires that output to succeed, documented
in README and CLI help. No new placeholder or silent-success branch was found
in the repaired paths.

### Forward impact

M1 is ready for M2 consumption. The runner should inspect both `error_count`
and `combine_error`, and the existing structured alignment/draft failures, as
planned. No additional M1 remediation is required. The earlier advisory about
keeping new orchestration out of the already long audio function remains an
implementation guide for M2, not a blocking M1 defect.

# M2 — Unified production independent audit

## 2026-10-14

### Verdict

**FAIL pending three corrections.** M2 exposes the proposed production,
optional-output, installed-resource and local-publication contracts, with
substantial offline coverage. Three independently reproduced cases violate
generation/accepted-revision ownership or fail-closed quality handling. They
prevent certification across functional correctness, integrity and forward
impact. This is the complete M2 audit, not certification of a tested subset.
M3's hosted transport/media review and live provider quality remain outside M2.

### Findings

1. **[P1] Changing audiobook metadata regenerates text and replaces an accepted
   human revision.**
   - Evidence: `forage/production.py:252` hashes the entire `book.metadata`
     dictionary into the split identity; `forage/production.py:355` includes
     preparation identity in every draft generation identity;
     `forage/production.py:377` archives and removes those drafts for regeneration.
   - Reproduction B below completes a text run, accepts a manual prose edit,
     then changes only `metadata.audiobook.voice_id`. The next text-only run
     succeeds but draft calls increase from **2 to 4**, and the active human
     edit is replaced. Its archive survives, but the current accepted revision
     is silently superseded for an unrelated synthesis setting.
   - Scope input fingerprints to the metadata actually consumed by each stage.
     Narration settings should invalidate audio, leaving source preparation,
     accepted prose and unrelated outputs intact. Prove this using a metadata
     change, not only the corresponding explicit runner option.

2. **[P2] A changed generation-unit ID misclassifies previously generated
   member drafts as legacy and blocks ordinary regrouping.**
   - Evidence: `forage/production.py:348` groups segments by the current group
     ID; `forage/production.py:360` looks up only that unit; the legacy branch
     at `forage/production.py:367` ignores other records that already own the
     same member paths.
   - Reproduction A below changes two previously generated standalone segments
     to group `g001`. Execution fails at `drafting` with “legacy drafts lack
     provenance; use --adopt-existing”, despite successful generation records
     for both members. The existing group-model-change regression only changes
     inputs under an unchanged group ID and does not cover this transition.
   - Recognize prior ownership of member artifacts across regrouping, splitting
     and renamed units; archive and regenerate affected known units. Reserve
     legacy adoption for genuinely unowned existing files. Do not bless old
     output under the new grouping merely to get past the guard.

3. **[P2] A malformed/error signature-critic response becomes a successful
   iteration and allows a completed snapshot.**
   - Evidence: `forage/critics.py:88` validates termination but not the returned
     critic schema; `forage/critics.py:94` and `forage/critics.py:96` default
     missing verdict/findings to `pass` and `[]`. `forage/iterate.py:85` then
     derives a pass from that empty list, which the new adapter accepts at
     `forage/production.py:423`.
   - Reproduction C below uses the real signature critic/iteration path with
     only its provider boundary mocked to return
     `{"error":"cannot evaluate this chapter"}` and a normal stop reason.
     The run reports `success=true`, quality `complete`, both iterations
     `pass`, and produces a review revision.
   - Validate the required critic object/fields and returned errors before
     recording success or deriving editorial verdicts. A valid empty findings
     list may pass; an absent/invalid findings field or explicit technical
     error must fail quality and block assembly/media/snapshot. Add permanent
     malformed/error/refusal tests through the real iteration adapter.

### Reproduction evidence

Exact command run from `/mnt/data/forage`; all fixtures use temporary
workspaces and mock provider boundaries. The fixture also forbids unexpected
live Anthropic/OpenAI calls. These probes were run against the audited M2
implementation before remediation:

```bash
.venv/bin/python - <<'PY'
import importlib.util, json, tempfile
from pathlib import Path
import pytest
from forage import production as p
from forage.production_state import atomic_json
from forage.llm import LLMResponse
spec = importlib.util.spec_from_file_location('audit_fixture', 'tests/test_production_runner.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

# A: known singleton -> new group identity.
with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
    book, calls = t.pipeline.__wrapped__(Path(d), mp)
    t.run_ok(book)
    path = book.work_dir / 'plan.json'
    plan = json.loads(path.read_text())
    for segment in plan['segments']:
        segment['group_id'] = 'g001'
    plan['merged_groups'] = {'g001': {'member_ids': ['001', '002'],
        'combined_target_word_count': 100, 'combined_source_word_count': 1000}}
    atomic_json(path, plan)
    result = p.run_production(book)
    print('A', result['success'], result['failed_stage'], result['stages']['drafting'])

# B: narration-only metadata must preserve accepted prose.
with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
    book, calls = t.pipeline.__wrapped__(Path(d), mp)
    t.run_ok(book)
    path = book.work_dir / 'segments/001.md'
    path.write_text('Human accepted revision.\n')
    t.run_ok(book)
    before = calls.copy()
    book.metadata['audiobook'] = {'voice_id': 'a-different-narrator'}
    result = p.run_production(book)
    print('B', result['success'], before['draft'], calls['draft'],
          path.read_text() == 'Human accepted revision.\n')

# C: real critic/iterate code must reject provider JSON errors.
with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
    book, calls = t.pipeline.__wrapped__(Path(d), mp)
    mp.setattr('forage.critics.complete', lambda **kw: LLMResponse(
        '{"error":"cannot evaluate this chapter"}', 'mock', 1, 1, 0, 'stop'))
    result = p.run_production(book, {'iterate': True})
    quality = json.loads((book.work_dir / 'production_quality.json').read_text())
    print('C', result['success'], result['stages']['quality']['status'],
          [row['final_verdict'] for row in quality['iteration']],
          bool(result['review_revision']))
PY
```

Observed outcomes: A `False drafting` with the erroneous legacy-adoption
failure; B `True 2 4 False`; C `True complete ['pass', 'pass'] True`.

### Completeness

- **Truthful state: exposed; not release-verified.** All three findings require
  correction and acceptance proof before marking M2 complete. The prior
  `[done] M2` implementation status is not an independent acceptance result.
- BRIEF-M2 AC1: assessed free preview, explicit execution, output selection,
  models/workspace and stage reasons; implemented with read-only preview proof.
- AC2: stage-return validation, refusal/truncation handling, required draft
  gates, CLI nonzero status and visible book-critic holds are implemented;
  **missing malformed/error signature-critic handling (finding 3)**.
- AC3: atomic state, OS-released per-book lock, interrupted retry, verified
  inventories, unchanged reuse and independent optional branch preservation
  are implemented and covered by focused/full-gate tests.
- AC4: source/split/prompt/model bytes and mutable preparation are tracked;
  removed cuts restore pristine chapters and `.orig` cannot overwrite a new
  split. **Synthesis-only metadata incorrectly invalidates text (finding 1);
  changed group identities cannot resume normally (finding 2).**
- AC5: ordinary manual edits and `review_apply` check changes retain accepted
  prose without automatic repair, and refresh descendants. Changed generation
  archives drafts; explicit legacy adoption is exposed. **Accepted prose
  preservation is violated by finding 1; known regrouping is confused with
  legacy adoption by finding 2.**
- AC6: current work text is passed explicitly to audio; chunk totals/hashes,
  combined-output failures and required alignment success are validated.
  Chunk-only is explicit; no partial limit is exposed as complete production.
- AC7: real mockable storyboard/OpenAI image adapters, decoded image checks,
  full selected chapter coverage, per-frame resume, deterministic lettering,
  PDF/contact sheets and current-manifest membership are implemented. Model/
  style/size/density/lettering controls are exposed; installed graphics are
  exercised offline.
- AC8: explicit confined inventories, portable targets, immutable copied
  revisions, hash verification and separate atomic review/release histories
  are implemented. Later accepted revisions preserve historical snapshots;
  failed promotion leaves the release pointer intact. These are local APIs,
  as intended for M2.
- AC9: compatibility script is a thin shared-runner caller. Documented
  iterate/coherence/repair/pair/resume flags map to the shared implementation;
  unsupported arguments fail before execution. Standalone commands remain.
- AC10: source resources are copied by the build hook from their authoritative
  prompt/spec files; package paths are separate from workspace/replay writes.
  The recorded wheel test builds/installs without dependency resolution,
  runs outside checkout with `-I` and no `PYTHONPATH`, verifies the imported
  location/resources, free CLI plan and mocked graphics/PDF.
- AC11: the recorded M2 full gate passes, but it lacks regression cases for
  findings 1–3. README/help accurately describe asynchronous review, optional
  checkpoint, execution/cost boundary, adoption, resume and local promotion.
- Completion matrix: M2 runner/optional-media/distribution/local-publication
  portions are assessed above; **runner revision/failure cells remain failing**.
  M3 media comments, hosted sync, packaging/overlay integration and hosted
  release transport are explicitly scheduled in BRIEF-M3, not silently
  deferred M2 requirements.
- Approach/files: state, runner, media, graphic, publication and resource
  boundaries are implemented; relevant existing stage adapters, CLI,
  compatibility script, package setup, tests and documentation are updated.
  Done-when conditions are missing the three corrections and proof. No new
  requirement or judgment-call deferral is introduced by this audit.
- Placeholder audit: no production test-only dispatch, unconditional empty
  success or unimplemented M2 media adapter was found. Graphic cache parsing
  failures intentionally trigger validated regeneration. The signature critic
  defaults in finding 3 are a semantic silent-success defect.

### Verification

Independently ran the following focused positives after inspecting the owning
code and existing tests; **10 passed in 6.07s**, exit 0:

```bash
.venv/bin/python -m pytest -q tests/test_production_runner.py::test_full_text_resume_and_quality_hold tests/test_production_runner.py::test_manual_revision_preserves_draft_and_does_not_repair tests/test_production_runner.py::test_group_generation_bypasses_old_group_cache_after_model_change tests/test_production_runner.py::test_removed_cuts_restore_pristine_source tests/test_production_runner.py::test_review_apply_check_updates_preserve_accepted_prose tests/test_production_runner.py::test_both_real_media_branches_resume_after_edit tests/test_production_runner.py::test_optional_checkpoint_is_bound_to_accepted_text_revision tests/test_publication.py::test_release_is_explicit_and_independent_of_later_review tests/test_graphic_production.py::test_art_failure_retries_only_failed_and_later_frames tests/test_production_state.py::test_book_lock_is_process_safe_and_releases
```

Implementation gate evidence reviewed in STATUS/HANDOFF: `.venv/bin/python -m
pytest -q` reported **476 passed, 6 Docker skipped in 45.54s**, including the
installed-wheel test. CLI `--help`, `run --help`, `release --help`, legacy
script help and `git diff --check` were recorded passing. This audit did not
redundantly rerun that full gate. The three additional negative probes above
explain why a passing existing gate does not yet satisfy M2 acceptance.

No production edits, live requests, existing book/work mutations, dependency
installs, remote operations or commits were performed by this audit. Only this
append-only audit section was written in the repository.

### Structural Assessment

- Architecture/abstraction: stage execution, state/hash/lock, media schema,
  graphics and publication have the intended ownership; the compatibility CLI
  uses the shared runner. No second text pipeline or script-runtime import was
  found. Resource build copies preserve one authoritative source.
- Semantic families: singleton/group provenance needs prior artifact ownership
  across changed group IDs (finding 2), not a separate legacy path for already
  generated chapters. Stage fingerprints must distinguish text metadata from
  narration configuration (finding 1).
- Integrity: technical error responses must not become editorial approval
  through default field values (finding 3). Existing book-critic, alignment,
  media and immutable-snapshot error boundaries are materially stronger.
- Scope: changes serve the requested pipeline; pre-existing model-default
  edits were treated as preserved input, not attributed to M2 defects.

### Forward Impact and Remediation Mapping

M3 can consume the documented portable index and verified immutable snapshots,
but reliable feedback incorporation requires fixes 1 and 2 before its lifecycle
is certified. Otherwise a narration setting or revised cut/group plan can
replace accepted human text or stall a known book. Fix 3 prevents hosted review
from receiving a snapshot whose optional quality stage only appeared to run.

- M2 remediation: restrict metadata fingerprints to actual stage inputs;
  prove narration metadata preserves accepted prose and only refreshes audio.
- M2 remediation: resolve ownership across generation-unit changes; prove
  singleton→group, group→singleton and renamed/regrouped members archive and
  regenerate without legacy adoption.
- M2 remediation: validate signature-critic results at their owning boundary;
  prove malformed/error/refusal objects fail the real iteration path and block
  descendants while valid empty findings remain supported.
- Re-audit these corrections and their focused regressions; run the required
  owning gate after production changes, then append the resolution verdict.

# M2 — First remediation resolution audit

## 2026-10-14

### Verdict

**FAIL: one residual AC5 provenance defect remains.** All three original
negative scenarios now behave correctly, and 29 independently run remediation
tests pass. The new member-ownership approach also handles merge/split/rename
of known units. However, adding an unowned existing chapter to an already
recorded group bypasses the adoption requirement and replaces its prose. M2
cannot pass functional correctness/integrity and forward impact until that
remaining branch is corrected. This is an assessment of all original M2
criteria, retaining the first audit's unaffected coverage, not a subset pass.

### Findings

1. **[P1] An existing group record bypasses protection for a newly added,
   unowned member.**
   - Evidence at this audit: `forage/production.py:382` correctly identifies
     `unknown_existing`, but `forage/production.py:383` requires `not previous`
     to enter the adoption guard. The archive/regeneration path begins at
     `forage/production.py:393` when a prior record exists for the group ID.
   - Complete `g001` with chapters `001`/`002`, then add chapter `003` with
     human-authored prose and no provenance to that same group. A normal run
     reports success, regenerates all three drafts, and replaces the unowned
     chapter. Its old bytes are archived, but explicit adoption was required
     before replacing active legacy prose. The new regression for mixed
     provenance only uses a new group ID, so it does not exercise this branch.
   - Guard unknown existing members regardless of prior unit-ID records, before
     archiving or generation. Explicit adoption may accept the valid expanded
     unit as user-adopted; invalid member checks must still reject adoption.

Exact independently executed scenario, reduced to the residual probe:

```bash
.venv/bin/python - <<'PY'
import importlib.util, json, tempfile
from pathlib import Path
import pytest
from forage import production as p
from forage.production_state import atomic_json
spec = importlib.util.spec_from_file_location('audit_fixture', 'tests/test_production_runner.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
    book, calls = t.pipeline.__wrapped__(Path(d), mp)
    t.run_ok(book)
    t._set_group(book, 'g001')
    t.run_ok(book)
    plan_path = book.work_dir / 'plan.json'
    plan = json.loads(plan_path.read_text())
    plan['segments'].append({**plan['segments'][0], 'id': '003', 'title': 'Chapter 3'})
    plan['merged_groups']['g001']['member_ids'].append('003')
    plan['merged_groups']['g001']['combined_target_word_count'] += 50
    plan['merged_groups']['g001']['combined_source_word_count'] += 500
    (book.work_dir / 'chapters/003.md').write_text('The new chapter has its source. ' * 50)
    prose = book.work_dir / 'segments/003.md'
    prose.write_text('Unowned human-authored chapter.\n')
    atomic_json(prose.with_suffix('.checks.json'), {'status': 'drafted'})
    atomic_json(plan_path, plan)
    before = calls.copy()
    result = p.run_production(book)
    print(result['success'], result['failed_stage'], calls['draft'] - before['draft'],
          prose.read_text() == 'Unowned human-authored chapter.\n')
PY
```

Observed before the next correction: `True None 3 False`.

### Resolved original findings

- Original finding 1: **resolved**. `forage/production.py:252` no longer hashes
  the complete metadata object into split identity. The consumed fields are
  assigned to classifier, synopsis, cuts and plan at
  `forage/production.py:273`. Cross-checked against actual metadata reads in
  `chapter_classifier.py`, `summarizer.py`, `cuts.py`, `lean_plan.py`, and the
  draft/critic prompt paths; relevant genre, identity, preservation and plan
  settings remain dependencies. Audio/publication metadata is excluded from
  text generation. Original narrator-change probe now reports `True 2 2 True`:
  successful run, unchanged draft-call count, exact human bytes retained.
- Original finding 2: **original case resolved; adjacent AC5 case above open**.
  `forage/production.py:359` constructs prior member ownership and records
  members/previous units for regenerated drafts. The original singleton→group
  probe now succeeds; permanent tests also verify actual merged drafting,
  split and rename, archives, provider provenance and unchanged resume.
- Original finding 3: **resolved**. `forage/critics.py:33` validates identity,
  verdict, summary and required findings schema, including explicit error/
  refusal. `forage/critics.py:109` requires provider completion before this
  validation and writes successful artifacts only afterward. The validator
  matches `prompts/critic_signature.md`; no prompt-contract strengthening was
  invented for this fix. Original error-object probe now returns
  `success=False`, `failed_stage=quality`, quality `failed`, no review pointer.
  Valid empty findings pass, while valid findings can retain an editorial hold.

### Completeness and structural assessment

- Truthful state: **exposed, not release-verified** until the residual defect
  and its regression proof are resolved. No M2 acceptance item was descoped.
- AC1–AC3: prior assessment stands; error/refusal signature responses now
  satisfy the missing quality-failure contract. Preview, explicit execution,
  failures, locks, recovery and reuse remain covered.
- AC4: original invalidation/preparation coverage stands; synthesis-only
  metadata now leaves text and unselected/unaffected media intact.
- AC5: known group merge/split/rename and ordinary accepted revisions pass,
  but **expanded existing groups containing an unowned member still fail**
  the explicit-adoption contract.
- AC6–AC10: audio, complete graphics, local publication/release, compatibility
  wrapper and installed distribution retain the first audit's passing
  assessments; these boundaries were not changed by the remediation.
- AC11: the original gate is superseded by the recorded 505-test passing gate,
  including 29 remediation cases; the residual case lacks permanent coverage.
  README/help and HANDOFF describe the intended lifecycle accurately, except
  the member-protection assertion is not yet true for this one branch.
- Completion matrix/approach/files: all M2 components are implemented and
  assessed; the runner provenance cell and M2 done-when remain open. M3's
  explicitly separate hosted work remains unimplemented, as planned.
- Architecture/abstraction: fixes live with stage-input selection, draft
  ownership and critic schema validation. These are the correct owners.
- Semantic families/integrity: the remaining `not previous` special case
  splits the legacy protection rule by unit ID instead of artifact ownership.
  Correct it once at the shared guard. No additional placeholder, unrelated
  production edit or architectural shortcut was found in these corrections.
- Forward impact: preserve unknown active prose before M3 integrates imported
  reviews and changing plans. No new hosted/media interface change is needed.

### Verification and prerequisites

- Re-read final STATUS and HANDOFF-M2 and inspected all three corrections and
  adjacent tests. Initial onboarding remains applicable: README.md, CLAUDE.md
  and pyproject.toml were read in the original M2 audit; their repository/cost
  rules match this remediation. No Nova-specific build/test workflow applies.
- Verified installed prerequisites without changes: setuptools **68.1.2**,
  wheel **0.41.3**, pytest **9.1.1**, Pillow **12.3.0**.
- Independently reran the original three stimuli with temporary fixtures and
  mocked providers. All original outcomes now satisfy their intended contract;
  the residual probe above does not.
- `.venv/bin/python -m pytest -q tests/test_production_runner.py -k
  'generation_unit_members or regrouping_does_not or audio_metadata or
  publication_metadata or text_metadata or malformed_signature or
  valid_signature or truncated_signature'`: **25 passed, 59 deselected in
  13.55s**, exit 0.
- `.venv/bin/python -m pytest -q
  tests/test_production_runner.py::test_complete_shaped_signature_response_requires_provider_completion`:
  **4 passed in 1.10s**, exit 0. Covers `length`, `max_tokens`, `content_filter`
  and absent stop reason with otherwise complete-shaped critic JSON.
- `git diff --check`: exit 0. All audit tests finished in the foreground.
- Reviewed STATUS's owning gate: `.venv/bin/python -m pytest -q` => **505
  passed, 6 Docker skipped in 66.69s**, including installed-wheel proof. No
  redundant full-suite run was performed by this focused audit.
- Only this audit section was appended. No production edits, dependency
  installs, existing book/work mutations, live requests, remote actions or
  commits were performed.

### Remediation mapping

- M2: protect unknown members when extending an existing recorded group;
  prove no generation/archival before refusal, explicit valid adoption,
  invalid-check rejection and subsequent stable resume. Re-audit that guard
  and its focused regression before the final M2 pass.

# M2 — Final resolution audit

## 2026-10-14

### Verdict

**PASS for the complete M2 offline contract.** The remaining existing-group
adoption defect is resolved. All three original findings and the adjacent
provenance finding now pass functional, structural and forward-impact review.
This verdict inherits the complete AC1–AC11 assessment in the initial M2 audit
and the first resolution audit, with no outstanding M2 criterion or silent
deferral. It does not certify M3 hosted feedback/media review, Docker execution,
live-provider creative quality or a deployed public release.

### Findings and resolution evidence

No unresolved actionable M2 finding remains.

- The ownership guard at `forage/production.py:378` now runs for every unknown
  existing member, regardless of whether the current generation-unit ID has
  a prior record. It precedes both verified reuse at
  `forage/production.py:391` and archival at `forage/production.py:396`.
- Without explicit adoption, the expanded existing group fails at drafting
  before member mutation or generation. This preserves legacy prose rather
  than using the existing group record as authority over its new member.
- Explicit adoption at `forage/production.py:384` validates every required
  member. Valid adoption preserves bytes and records the whole unit as
  `user-adopted` with `generated=None`; it does not attribute old prose to a
  provider. Missing checks, truncated status and empty prose all fail before
  archival. This shared guard also covers new unit IDs and ordinary legacy
  adoption; known merge/split/rename regeneration still works.

### Independent verification

Re-ran the residual scenario from the preceding audit section with the same
temporary book, group `g001`, new chapter `003`, existing unowned prose and
`drafted` checks. Added snapshots/assertions for every file under `segments/`
and `.production/draft_history/`, all `draft_units` records and the review
pointer. The observed outcome is now:

```text
REFUSAL False drafting 0 True all draft/check/history/provenance/pointer bytes unchanged
ADOPTION user-adopted ['001', '002', '003'] no drafting; stable resume
```

After refusal, explicit adoption succeeded without drafting and preserved
chapter `003` verbatim. A following normal run made no further mocked provider
calls. The permanent regression also proves repeated refusal has no member
side effects and checks preservation of all group files after adoption.

Exact focused command independently run:

```bash
.venv/bin/python -m pytest -q tests/test_production_runner.py -k 'existing_group or generation_unit_members or regrouping_does_not or legacy_adoption'
```

Result: **9 passed, 79 deselected in 8.29s**, exit 0. This includes the four
new residual regression cases, known merge/split/rename, new-group mixed
ownership and ordinary legacy adoption. `git diff --check` also passed.
Foreground execution completed before this verdict.

Reviewed the final STATUS/LOG evidence: `.venv/bin/python -m pytest -q` =>
**509 passed, 6 Docker skipped in 64.27s**, exit 0, including isolated installed
wheel verification. That owning gate was not redundantly rerun. The preceding
independent audit already ran all 29 original remediation cases and the three
original negative probes successfully; this final change only moves/removes
the condition on the shared member-adoption guard.

### Completeness

- Truthful state: **release-verified within M2's explicitly offline scope**.
  Installed-package behavior and local revision/release artifacts are verified;
  this phrase is not certification of a hosted deployment or full-project
  completion.
- AC1: free plan inspection, explicit execution, selected outputs, options,
  workspace and stage explanations pass by the initial complete assessment.
- AC2: dependency/failure handling, required-draft gate, nonzero CLI failure,
  valid quality holds and malformed/error critic rejection pass.
- AC3: atomic records, process-safe lock, interrupted retry, intact-output
  verification, unchanged reuse and independent optional branches pass.
- AC4: actual content/settings invalidation and mutation-safe preparation
  pass; narration-only metadata no longer changes text provenance.
- AC5: accepted manual/review edits, archived regeneration, changed group
  identity, unknown legacy-member protection, deliberate adoption and stable
  resume now **all pass**, including an expanded existing group.
- AC6–AC7: current-text audio, complete chunk/combined validation, alignment
  completion, full selected graphics, provider adapters, per-frame resume,
  lettering and usable exports retain their passing assessments.
- AC8: portable validated indexes, immutable copied snapshots, independent
  review/release histories and verified explicit promotion pass.
- AC9–AC10: shared compatibility CLI, supported-option mapping, standalone
  stages, installed runtime/resources and workspace-local artifacts/cache pass.
- AC11: permanent regressions, final owning gate, installed-wheel proof,
  documentation/help and truthful offline limitations pass.
- Completion matrix: all M2 runner, optional-output, distribution and local
  publication/release cells are proven. M3 media review, hosted transport,
  packaging/overlay integration and continued hosted feedback remain the
  explicitly planned next milestone, not deferred M2 acceptance work.
- Approach, files, done-when: M2 steps and all three-dimensional audit
  conditions are met. No new M2 placeholder or unverified acceptance exception
  remains.

### Structural assessment and forward impact

Architecture and abstraction pass: member ownership is checked in the draft
owner before reuse/archive, with no added workflow or alternate generation
path. Semantic families are unified by the same legacy guard for existing and
new unit IDs. Integrity passes: no implicit provenance or provider generation
claim is manufactured, and failed adoption preserves active prose. Scope is
limited to the reported defect and its tests/documentation.

M2 is ready for M3 to consume its runner, accepted-text revisions, portable
media index and verified immutable-publication APIs. No interface rework or
additional M2 remediation is required by this audit.

The previously read README.md, CLAUDE.md and pyproject.toml onboarding and
verified build prerequisites remain applicable. No prerequisite installation,
production edit, existing book/work mutation, live request, remote operation or
commit was performed during this audit; only this section was appended.

# M3 — Hosted review and complete-project integration audit

## 2026-10-14

### Verdict

**FAIL: four confirmed correctness/integrity findings remain.** The operational
CLI, matching HTTP receiver, revision-aware media UI, import reconciliation,
local/installed packaging and full offline A→B→C lifecycle are implemented and
exposed. Independent negative probes found a false-success sync recovery path,
a release-only feedback failure, an archive expansion-limit gap and an
interrupted application that loses the durable decision history. These prevent
certifying the complete M3/project contract despite the passing owning suite.
This is a full criteria assessment, not a pass of a tested subset.

Read onboarding README.md, CLAUDE.md, pyproject.toml and requirements-web.txt;
PROJECT/PRD/ARCHITECTURE/PLAN/STATUS/BRIEF-M3/HANDOFF-M3 and prior M1/M2 resolution
audits. The main audit and two focused read-only child audits used only local
temporary books, real TestClient HTTP, mocked providers and injected failures.
No production code, dependencies, existing books/work, remote service or commit
was changed. Only this audit section was appended.

### Findings

1. **P1 — Sync can report success and republish obsolete output after a failed
   acknowledged media run; the same shortcut ignores explicit output/settings
   changes when prose is unchanged.**
   - `forage/review_sync.py:263` loads production state and a verified old
     pointer, but the refresh predicate at `:280` compares only text hashes.
     `forage/production.py:581`–`:584` stores the acknowledged current text hash
     before audio/graphic/snapshot completion. Thus `state.text_revision` is not
     evidence that the corresponding revision was completed.
   - After revision A, apply a prose comment, acknowledge its new media
     checkpoint, inject an audio failure, then retry sync. The retry returns
     `success=True`, `production={"status":"unchanged"}`, performs no new media
     work, and republishes A although the accepted current draft is newer and
     the audio stage is failed. This can repeatedly hide the failed generation.
   - Independently, a text-only complete book plus an empty feed and explicit
     `production_options={"outputs":["text","audio"],"audio_voice_id":"new-voice",
     "audio_combine":False}` returns the same unchanged success and republishes
     the old text-only revision. Saved outputs remain `["text"]`. The CLI
     exposes these as overrides at `forage/cli.py:1909`–`:1912`; supplied
     unsupported options can likewise evade runner validation on this path.
   - Remediation must derive refresh/completeness from the successful immutable
     snapshot plus actual stage/output/settings validity (or call the common
     free planner), preserving no-provider-call reuse for a genuinely unchanged
     run. A checkpoint acknowledgment cannot stand in for successful media.
     Test both checkpoint retry and explicit settings/output changes.

2. **P2 — A valid first public release cannot receive or export feedback unless
   a separate review pointer already exists.**
   - `forage/webapp/app.py:465` reads the submitted historical revision, but
     `:466` selects default review-current before using it at `:469`.
     `feedback` at `:405` also depends on default review-current;
     `ReviewTransport.fetch_feedback` uses that endpoint without a selector.
   - A first `publish-release` succeeds and `/chapters?channel=release` returns
     200 with usable revision/downloads. Posting a correctly anchored audio or
     prose comment returns 404 `no review publication for sample`.
     `/feedback` returns 404, while `/feedback?revision=RELEASE_SHA` returns 200.
     `review` remains absent, as required by separate channel semantics.
   - Honor an explicit viewed revision before requiring review-current; define
     the authoritative feed/current-view selection for a release-only book.
     Keep release/review pointers independent. Cover new and historical release
     comments, lifecycle mutations and HTTP/local feedback parity without
     manufacturing a review promotion.

3. **P2 — Archive expanded-size limits do not cover bytes consumed by tar
   metadata before regular members are yielded.**
   - `forage/hosted_publication.py:100` opens gzip tar directly; `:101` iterates
     parsed members, and `:107`–`:109` count only their declared regular-file
     sizes. Python tar parsing processes PAX/GNU extended metadata before that
     loop gets the corresponding member.
   - A small, otherwise valid snapshot with a 64 KiB PAX comment was accepted
     with `max_expanded_bytes=1219`: regular files totaled 1119 bytes, while the
     actual decompressed tar stream was 81920 bytes. No hashes, identities or
     pointers were forged; the accepted metadata simply bypassed the configured
     resource bound. The focused child also reproduced the same with 1 MiB
     metadata. This contradicts BRIEF criterion 8's expanded-resource limit.
   - Bound the actual decompressed stream, including headers and metadata,
     before handing unchecked expansion to tar parsing. Preserve separate
     compressed/file-count/member checks and reject over-limit input before
     installation/pointer changes. Add finite PAX/GNU metadata cases and ensure
     a normal snapshot still succeeds under a sufficient configured limit.

4. **P2 — Interrupted review application can later publish changed prose with
   no durable application decision or history.**
   - `forage/review_apply.py:294`–`:303` writes the new draft/checks before
     `_record_feedback_use` at `:308`; the ledger is written only at `:755`.
     The application and decision are not a recoverable transaction.
   - Inject `OSError` only for `write_json(default_ledger_path(book), ...)`.
     The first sync raises after changing prose. Restore writes and retry:
     original imported feedback is now stale, so no decision is applied or
     recovered; sync reports success and publishes the changed revision while
     the ledger still does not exist. Observed: draft_changed=True,
     ledger_exists=False, retry_success=True, counts={stale:1}, provider_calls=1,
     new_revision_published=True.
   - This ordering predates M3, but the new durable apply/retry contract depends
     on it. Persist a recoverable application intent/decision with expected
     before/after hashes before changing accepted prose, then finish or safely
     reconcile it on retry. Atomic ledger replacement alone does not close the
     gap between prose and decision writes. No unresolved application should
     silently become a publishable success; preserve existing ledger entries.

### Exact negative probes

Run each Python block using `.venv/bin/python - <<'PY'` from the repository root.
All fixtures create temporary roots and intercept provider boundaries. These
probes intentionally show the pre-remediation behavior; the assertions/output
must change after correction.

Finding 1, checkpoint recovery (run by the focused feedback audit):

```python
from tempfile import TemporaryDirectory
from pathlib import Path
from pytest import MonkeyPatch
from tests.test_production_runner import pipeline, _media_mocks
from tests.test_review_sync import comment, feed, FeedTransport, fake_apply_provider
from forage import production, review_sync
from forage.production_state import load_state
with TemporaryDirectory() as d, MonkeyPatch.context() as mp:
    book, calls = pipeline.__wrapped__(Path(d), mp)
    _media_mocks(mp, calls)
    opts = {"outputs":["audio"], "audio_voice_id":"fixture",
            "audio_combine":False, "checkpoint_before_media":True}
    waiting = production.run_production(book, opts)
    first = production.run_production(book, {**opts,
        "continue_revision":waiting["text_revision"]})
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]),
                              root=Path(d)/"hosted")
    transport.publish(book, first["review_revision"])
    seen = []
    fake_apply_provider(book, mp, seen)
    review_sync.sync_feedback(book, transport, apply=True, republish=True)
    new_text = review_sync.current_text_revision(book)
    real_audio = production.generate_audiobook
    def fail_audio(*a, **kw):
        raise RuntimeError("offline simulated audio failure")
    mp.setattr(production, "generate_audiobook", fail_audio)
    failed = production.run_production(book, {**opts,"continue_revision":new_text})
    mp.setattr(production, "generate_audiobook", real_audio)
    before = calls.copy()
    retry = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert failed["failed_stage"] == "audio"
    assert load_state(book)["text_revision"] == new_text
    assert retry["success"] and retry["production"] == {"status":"unchanged"}
    assert transport.published[-1][0] == first["review_revision"]
    assert calls == before
```

Finding 1, independent option-change probe:

```python
from tempfile import TemporaryDirectory
from pathlib import Path
from pytest import MonkeyPatch
from tests.test_production_runner import pipeline, run_ok
from tests.test_review_sync import FeedTransport, feed
from forage.review_sync import sync_feedback
from forage.production_state import load_state
with TemporaryDirectory() as d, MonkeyPatch.context() as mp:
    book, calls = pipeline.__wrapped__(Path(d), mp)
    first = run_ok(book)
    transport = FeedTransport(feed(book, []))
    result = sync_feedback(book, transport, apply=True, republish=True,
        production_options={"outputs":["text","audio"],
                            "audio_voice_id":"new-voice", "audio_combine":False})
    assert result["success"] and result["production"] == {"status":"unchanged"}
    assert load_state(book)["production_options"]["outputs"] == ["text"]
    assert transport.published[-1][0] == first["review_revision"]
```

Finding 2, independently repeated after the focused hosted audit:

```python
from tempfile import TemporaryDirectory
from pathlib import Path
from tests.test_web_media import hosted, publish, media_note
with TemporaryDirectory() as d:
    h = hosted.__wrapped__(Path(d))
    publish(h, channel="release")
    client, storage, _, _, revision, _ = h
    assert client.get("/api/books/sample/chapters?channel=release").status_code == 200
    response = media_note(h)
    assert response.status_code == 404
    assert response.json()["detail"] == "no review publication for sample"
    assert client.get("/api/books/sample/feedback").status_code == 404
    assert client.get(f"/api/books/sample/feedback?revision={revision}").status_code == 200
    assert storage.status("sample")["review"] is None
```

Finding 3, independent bounded metadata probe:

```python
import gzip, io, tarfile
from tempfile import TemporaryDirectory
from pathlib import Path
from tests.test_publication import publication_input
from forage.publication import snapshot_revision
from forage.hosted_publication import HostedPublications, archive_snapshot
with TemporaryDirectory() as d:
    root = Path(d)
    book, options = publication_input.__wrapped__(root)
    revision = snapshot_revision(book, **options)["revision"]
    original = archive_snapshot(book, revision)
    output = io.BytesIO()
    file_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as source, \
         tarfile.open(fileobj=output, mode="w:gz", format=tarfile.PAX_FORMAT) as target:
        for i, member in enumerate(source):
            body = source.extractfile(member).read()
            file_bytes += len(body)
            if i == 0:
                member.pax_headers["comment"] = "x" * 65536
            target.addfile(member, io.BytesIO(body))
    archive = output.getvalue()
    maximum = file_bytes + 100
    host = HostedPublications(root/"host", max_expanded_bytes=maximum)
    result = host.upload(book.book_id, archive)
    print(file_bytes, maximum, len(gzip.decompress(archive)), result["revision"] == revision)
    # Observed: 1119 1219 81920 True
```

Finding 4, independently repeated after the focused feedback audit:

```python
from tempfile import TemporaryDirectory
from pathlib import Path
from pytest import MonkeyPatch
from tests.test_production_runner import pipeline, run_ok
from tests.test_review_sync import comment, feed, FeedTransport, fake_apply_provider
from forage import review_apply, review_sync
with TemporaryDirectory() as d, MonkeyPatch.context() as mp:
    book, calls = pipeline.__wrapped__(Path(d), mp)
    first = run_ok(book)
    transport = FeedTransport(feed(book, [comment(book, first["review_revision"])]),
                              root=Path(d)/"host")
    seen = []
    fake_apply_provider(book, mp, seen)
    ledger = review_apply.default_ledger_path(book)
    draft = book.work_dir/"segments/001.md"
    before = draft.read_bytes()
    real = review_apply.write_json
    def fail_ledger(path, data):
        if path == ledger:
            raise OSError("offline ledger write interruption")
        return real(path, data)
    mp.setattr(review_apply, "write_json", fail_ledger)
    try:
        review_sync.sync_feedback(book, transport, apply=True, republish=True)
    except OSError:
        pass
    mp.setattr(review_apply, "write_json", real)
    retry = review_sync.sync_feedback(book, transport, apply=True, republish=True)
    assert draft.read_bytes() != before and not ledger.exists()
    assert retry["success"] and retry["pull"]["counts"] == {"stale":1}
    assert len(seen) == 1 and transport.published[-1][0] != first["review_revision"]
```

### Completeness against BRIEF-M3

| Criterion | Assessment and evidence |
|---|---|
| 1: Operational CLI/HTTP/local transport and explicit success/failure | **Fail pending finding 1**: all four commands are exposed; CLI local success/error and real HTTP round trip pass (`test_review_lifecycle.py:151`, `test_review_transport.py:28`), but sync false-success/retry and ignored overrides remain. Publication failures otherwise retain the old pointer. |
| 2: Matching receiver, first-book upload, immutable history/separate pointers | **Pass** for functional publication semantics; `test_hosted_publication.py:38` and `test_web_media.py:84` cover first upload/history/identity/failed promotion. Resource bounding is assessed separately under8. SQLite/import/ledger storage is outside snapshots. |
| 3: Release view/download and continued independent lifecycle | **Fail pending finding2**: A→B→C review-then-release, old bytes and downloads pass (`test_review_lifecycle.py:43`); first release without review cannot receive/pull feedback. |
| 4: Reachable media review/lifecycle and legacy prose compatibility | **Fail for release-only comments, finding2**; ordinary review routes pass audio/panel CRUD/export and original-author tests (`test_web_media.py:108`). Static UI actually creates audio/image controls, target composers and revision-preserving links; JS syntax passes. Browser unavailable limit is truthful. |
| 5: Original anchors, raced revision, stale/orphan, strict timestamps | **Pass** for implemented anchored paths: explicit historical revisions do not silently re-anchor; validation rejects missing/wrong target revision, boolean/nonfinite/negative/out-of-range time; unknown duration stays unknown (`test_web_media.py:132`–`:168`, `:277`). Release-only reachability is finding2, not an anchor-corruption issue. |
| 6: Stable full-feed identities, reconciliation/history and interrupted import | **Pass**: source-qualified IDs, durable site identity, status/deletion/history reconciliation, validate-before-write, atomic authoritative import and derived-cache failure recovery (`test_review_sync.py:46`–`:144`, old SQLite migration `test_web_media.py:207`). Ledger durability failure is criterion7/finding4. |
| 7: Free pull, eligible exactly-once durable apply, descendants, repeat/republish | **Fail pending findings1 and4**. Free pull, current-local-byte checks, stale/orphan/media/inactive exclusion, constrained complete-response apply and normal repeat idempotence pass (`test_review_sync.py:153`–`:310`), but checkpoint retry and application commit interruption are not durable. |
| 8: Auth/origin/session/path/archive/resource safety | **Fail pending finding3**. Admin/reviewer separation, existing origin/host/rate guards, MIME/range, verified confined inventories, malicious member types/names/duplicates/extras/hash identity and regular-size/count limits pass. Expanded metadata bytes escape the configured bound. |
| 9: Media packaging, whole-book overlays, M1 safety and installed boundaries | **Pass**. Exact current referenced media and text assets, staged revalidation, full immutable history, removed-overlay no-fallback and original resolved-overlap/rollback tests pass (`test_review_packaging.py`, `test_artifact_safety.py`, `test_web_media.py:238`). Runtime imports do not depend on `scripts`; script is compatibility entrypoint. |
| 10: Offline/full/installed/web-only proof and docs/help | **Pass for proof infrastructure/exposure**, not a substitute for fixing1–4. Owning gate629passed6Docker skipped; independent focused236pass below. Isolated wheel includes resources and operational local CLI (`test_distribution.py:10`). Web-only import/start/upload/media blocks SDK/Pillow/pipeline imports (`test_web_media.py:335`). README/help document current interfaces and limitations; settings claims require finding1 repair. |

### Project acceptance integration

- **AC1–AC4 pass**: prior independently resolved packaging/completion/alignment/
  audio proofs remain applicable; relocated package implementation still passes
  the complete original safety suite. No new bypass of those contracts found.
- **AC5/AC6 incomplete at integrated sync surface**: the common runner remains
  available and tested, but the sync shortcut bypasses its freshness/completion
  decisions (finding1); application durability also gates safe continued work.
- **AC7 pass**: prior full selected-content graphic adapter/storyboard/art/
  lettering/package/resume proof remains applicable; M3 does not add a parallel
  graphic generator. Actual creative quality remains outside offline proof.
- **AC8 incomplete** only for release-only reachability (finding2); normal media
  review/anchors/CRUD/export/staleness passed and is implemented rather than
  scaffolded.
- **AC9 pass** for packaging/overlay/path serving; uploaded expansion-resource
  integrity additionally fails BRIEF8 as finding3.
- **AC10 incomplete** until new negative regressions close the verified gaps;
  the required command/docs/test/distribution infrastructure is present.
- **AC11 incomplete**: normal async loop/idempotence passes, but failed checkpoint
  retry and application/decision recovery are findings1/4.
- **AC12 incomplete**: explicit separate release/history and ordinary continued
  release feedback pass, but a valid release-only publication cannot participate
  in the promised loop (finding2).

Truthful state: **exposed**, not yet release-verified even within offline scope.
All criteria, completion-matrix cells and approach steps are accounted for;
there is no silent scope deferral. Files named by the brief were implemented or
coherently moved into package-owned modules. No absent transport/receiver,
placeholder provider dispatch or fabricated remote confirmation was found.
The `pass` branches inspected are an exception class, stale-cache regeneration
and documented artifact discovery; none is an unimplemented public operation.
The four failures above are real error/edge paths, not stylistic objections.

### Verification

Independently completed in the main audit:

```text
.venv/bin/python -m pytest -q tests/test_review_lifecycle.py tests/test_review_packaging.py tests/test_artifact_safety.py
68 passed, 1 TestClient timeout deprecation warning in 2.46s

.venv/bin/python -m pytest -q tests/test_hosted_publication.py tests/test_review_transport.py tests/test_web_media.py tests/test_webapp_security.py tests/test_store_ids.py
129 passed, 1 TestClient timeout deprecation warning in 6.35s

node --check forage/webapp/static/app.js
exit0
.venv/bin/python -m forage.cli review-sync --help
exit0; explicit apply/republish, transport/workspace and output/settings overrides present

git diff --check
exit0
```

The focused feedback child independently completed
`.venv/bin/python -m pytest -q tests/test_review_sync.py`: **39passed in8.57s**.
Total distinct focused tests in this audit: **236passed**. All foreground test
sessions finished before verdict. The supplied owning full gate **629passed,
6Docker skipped in100.89s**, including isolated installed-wheel proof, was read
and not redundantly rerun. No browser executable/tool/Playwright/Selenium was
available; interactive visual behavior, live-provider quality, Docker execution
and deployed operation remain explicitly unverified, as the brief permits.

### Structural assessment

- **Architecture:** package-owned hosted storage/transport/sync and light web
  imports follow the intended ownership. Existing constrained apply and common
  production runner are reused. The sync freshness shortcut duplicates only
  part of the runner's state semantics and is the root of finding1; fix at that
  boundary rather than add special-case retry flags.
- **Abstraction/semantic families:** local and HTTP publication share validators
  and pointer semantics; prose/media schema, storage, API, UI and packaging were
  updated together. Default-current selection has an accidental assumption that
  review must precede release (finding2). Existing application writes need a
  shared recoverable commit boundary (finding4), not per-call compensations.
- **Integrity:** stable ID and authoritative-cache recovery are sound; no silent
  import schema fallback or media-to-prose conversion was found. Findings1/4
  silently report later success after incomplete work; finding3 leaves the
  configured resource bound incomplete.
- **Patterns/function scope:** the inherited application/store/controller files
  are large, but new behavior has named storage/transport/schema helpers and
  follows existing conventions. No size/style-only blocker is raised. Preserve
  this ownership when correcting the four findings.
- **Scope:** pre-existing model-default updates and comparison artifacts remain
  untouched. No unrelated formatter/refactor churn or live execution was added
  by the audit. All four repairs fit the already authorized lifecycle contract.

### Forward impact and remediation mapping

The new interfaces are usable and support the intended separately hosted,
asynchronous workflow. Shipping the current retry semantics would make periodic
sync unreliable exactly when provider/disk failures occur; public release as an
independent entry point also needs to work. No broad architectural rewrite is
needed, but durable accepted-prose/decision recovery must be solved explicitly.

- **Sync/completion owner:** finding1; compare valid completed revision/settings
  and stage evidence, retry failed descendants, honor explicit option changes,
  preserve unchanged no-provider-call behavior and media-checkpoint requirements.
- **Web selection/feedback owner:** finding2; release-only and exact historical
  revision comments, full feed/exports/CRUD/projection without implicit review
  promotion; keep normal review-current semantics and old overlays compatible.
- **Hosted archive owner:** finding3; enforce total decompression bound before
  metadata parsing, with sufficient normal-archive and finite metadata tests.
- **Review-apply owner:** finding4; recoverable transaction/journal for prose,
  checks and immutable decision identities; cover interruption at each boundary,
  preserve pre-existing ledger rows, avoid re-calling models on recoverable retry,
  and prevent publication while recovery is unresolved.
- **Milestone gate:** add precise regressions, run owning gates after changes,
  append a resolution audit and then update STATUS/PLAN/completion matrix. No
  user re-approval is needed for these already-authorized corrections.

# M3 — Complete-project resolution audit

## 2026-10-14

### Verdict

**PASS for the complete M3 and integrated project offline contract.** All four
findings from the preceding M3 audit are resolved. Independent repetitions of
the original scenarios and adjacent failure/lifecycle checks pass. This verdict
inherits the complete prior M1/M2 audits and M3 criterion-by-criterion assessment;
no project acceptance criterion remains silently deferred or uncertified within
the authorized offline scope. Live-provider quality, Docker execution,
interactive browser behavior and an actual deployment remain unverified.

The updated HANDOFF-M3/STATUS/LOG and changed implementations/tests were read.
The audit remained read-only except for this appended section. No paid request,
real book/work mutation, remote publication, dependency installation or commit
was performed. Main and focused child test sessions all completed before this
verdict.

### Findings and resolution evidence

No unresolved actionable finding remains.

1. **Sync completion and option changes — resolved.**
   - `forage/review_sync.py:266` prefers persisted requested settings when
     retrying failed work; `:278` validates options before paid application;
     `:288` asks the common free production planner to assess all dependencies,
     selected settings and output bytes. A checkpoint text hash is no longer
     used as proof that media/snapshot generation succeeded.
   - `forage/production.py:671` persists supported nonsecret requested options
     before execution; successful options remain separately recorded at `:675`.
     Continuation/adoption flags and provider credentials are not persisted.
     A failed attempt to add audio no longer silently reverts the next sync to
     the last successful text-only selection.
   - Independently reran the original checkpoint/audio-failure probe from the
     preceding audit, changing its assertions to require correct recovery.
     Observed: retry_success=True, new_revision=True, apply_calls=1,
     new_tts_calls=1. The accepted prose was not redrafted. A following complete
     sync/republish made zero additional provider calls and returned unchanged.
   - Permanent adjacent cases at `tests/test_review_sync.py:326`–`:410` cover
     original checkpoint failure, adding/removing audio and changing voice with
     no prose change, unknown options rejected before any apply call, and
     preserving/retrying newly requested settings after failure. All pass.
     Common planner inspection confirms failed/running/missing/corrupt output
     records cannot certify completion, while valid reuse is provider-free.

2. **Release-only feedback — resolved.**
   - `forage/webapp/store.py:439` centralizes selected-root resolution: an
     unspecified current view prefers review, then uses release only when
     review is absent. Explicit channel/revision selectors remain strict.
     `selected` pins the resulting root at `:453`; no pointer is fabricated.
     `forage/webapp/app.py:460` accepts the explicit viewed revision before
     making any default-current assumption.
   - The focused hosted audit repeated the original first-release-only probe:
     correctly anchored comments now succeed, default full feedback is usable,
     and HTTP/local projected feeds agree. Review remains absent and explicit
     `channel=review` remains 404. Public release downloads remain reachable.
   - New tests at `tests/test_web_media.py:109` cover all five scopes and
     edit/resolve/delete/export/projection; adjacent historical-release tests
     retain original revision anchors and mark them stale against later release
     content. Existing review-first A→B→C behavior remains valid.

3. **Expanded archive resource bound — resolved.**
   - `forage/hosted_publication.py:109` decompresses into owned staging with a
     hard byte cap before invoking tar parsing at `:115`. The count includes
     PAX/GNU metadata, headers, padding, trailing content and concatenated gzip
     streams. Oversized input raises before parsing/installing a snapshot.
     Existing unique-regular-member, inventory/hash, file-count and compressed
     limits remain; `:66` rejects nonpositive/noninteger limit configuration.
   - The focused hosted audit repeated the original finite 1 MiB PAX metadata
     scenario: it now rejects with the expanded-stream-limit error and preserves
     existing pointers. Exact-size ordinary archives pass; an insufficient
     bound rejects. Staging is removed on failure.
   - Permanent tests `tests/test_hosted_publication.py:178`–`:230` cover PAX/GNU
     metadata, header overhead, trailing/concatenated streams, exact limit,
     truncated gzip, invalid limits and permitted metadata under a sufficient
     cap. These tests are bounded local fixtures, not live resource probes.

4. **Durable review application — resolved.**
   - `forage/review_apply.py:329` prepares the prospective complete ledger and
     decisions before committing; `forage/review_recovery.py:122` atomically
     persists a durable intent before any snapshot/draft/checks/ledger changes.
     It records exact expected before/after hashes and prospective final bytes.
   - Recovery at `forage/review_recovery.py:181` validates every affected target
     before additional writes, performs atomic/fsynced replacements, verifies
     final bytes and then retires the intent. Prior ledger entries are retained.
     Any intervening draft/checks/ledger edit outside expected before/after bytes
     stops recovery and preserves both the edited file and pending intent.
   - The focused recovery audit repeated the original ledger-write failure
     without a pre-existing ledger, injecting the error at the new durable
     ledger write boundary. The first call leaves durable intent and does not
     publish. Retry restores exactly one decision for note-1, makes no second
     model call, retires intent and publishes the new complete revision.
   - `tests/test_review_recovery.py:56` parametrizes interruption around intent,
     before-image, draft, checks, ledger and finalization; `:95` covers conflicting
     human changes; `:115` proves standalone apply, free pull and direct
     production recover before eligibility/execution. Read-only plan/dry-run and
     new snapshot creation refuse unresolved intent (`production.py:635`,
     `publication.py:275`). In-flight human draft/ledger changes are rejected
     before committing the provider response (`test_review_recovery.py:143`).
   - Explicitly publishing an already verified immutable historical snapshot
     remains possible while working-copy recovery is pending. That operation
     cannot capture uncommitted prose and does not bypass the new-snapshot guard.

### Independent verification

Main audit:

```text
.venv/bin/python -m pytest -q tests/test_review_sync.py tests/test_review_lifecycle.py
47 passed, 1 TestClient timeout deprecation warning in 17.70s

Original checkpoint/audio-failure probe + unchanged repeated cycle
passed; new revision, one total apply call, no redraft, no calls on unchanged repeat

git diff --check
exit0
node --check forage/webapp/static/app.js
exit0
```

Focused recovery child:

```text
.venv/bin/python -m pytest -q tests/test_review_recovery.py
20 passed in 6.60s
Original no-prior-ledger interruption/retry probe
passed; exactly one recovered decision, no repeated model call
```

Focused hosted/web child:

```text
.venv/bin/python -m pytest -q tests/test_hosted_publication.py tests/test_web_media.py tests/test_review_transport.py
98 passed, 7 TestClient timeout warnings in 10.92s
Original release-only and finite PAX metadata probes
passed with corrected success/rejection semantics
```

Total distinct focused tests in this resolution audit: **165 passed**. The final
owning `.venv/bin/python -m pytest -q` gate reported **680 passed, 6 Docker skipped
in 72.01s**, including 51 added remediation cases, installed-wheel CLI/resources,
web-only imports and the real TestClient lifecycle. That full gate was reviewed
rather than redundantly rerun. TestClient timeout deprecation warnings are
harness-only. All installed/runtime, resource and legacy compatibility proof
from the original full assessment remains applicable.

### Completeness

Truthful state: **release-verified within the explicitly offline acceptance
contract**. This does not claim a deployed release or live creative-quality
certification.

All ten BRIEF-M3 criteria:

1. **Pass:** operational publish-review/publish-release/pull/sync interfaces,
   HTTP/local parity and nonzero failure retain prior proof; finding1 now closes
   false-success sync and unvalidated/ignored option paths.
2. **Pass:** matching first-book receiver, verified immutable snapshots,
   independent review/release pointers and persistent history remain proven.
3. **Pass:** release view/download and subsequent lifecycle retain prior proof;
   finding2 now includes first release without prior review publication.
4. **Pass:** reachable audio/panel UI and all comment lifecycle operations,
   legacy prose compatibility and provider-free hosting retain prior proof;
   release-only comment paths now also work. Browser limits remain explicit.
5. **Pass:** exact viewed/original anchors, concurrent pointer separation,
   stale/orphan handling, strict timestamps and media exclusion remain proven.
6. **Pass:** source-qualified stable identities, full-feed reconciliation,
   history retention, validate-before-write and authoritative atomic-import
   recovery remain proven; added recovery happens before eligibility projection.
7. **Pass:** free pull, explicit constrained apply, eligibility against actual
   local bytes, durable exactly-once decisions, failed-descendant recovery,
   no-redraft refresh and unchanged no-call behavior now all pass.
8. **Pass:** inherited auth/session/origin/host/rate, inventory/path/member/hash
   proofs remain; finding3 closes the expanded metadata/resource bound.
9. **Pass:** inherited current-only media packaging, baked/mounted overlays,
   removed-target no-fallback, M1 rollback safety and installed package ownership
   remain valid. Recovery's private intent is not a publication asset.
10. **Pass:** final full offline gate, independent focused proof, installed
    wheel/web-only operation, documentation and help are complete. JavaScript
    syntax passes; unavailable interactive browser proof is stated accurately.

All twelve PROJECT acceptance criteria:

- **AC1–AC4 pass:** independently resolved M1 safe packaging, completion,
  alignment freshness and narration provenance remain verified.
- **AC5–AC6 pass:** common runner/planner and sync now share full completion,
  freshness/settings and failure semantics; locks and recoverable application
  keep incomplete work from becoming new successful publications.
- **AC7 pass:** complete optional graphic generation/export/resume retains its
  independent M2 proof; no parallel generator or placeholder was introduced.
- **AC8–AC9 pass:** revision-aware media review, persistence/export/staleness,
  packaging/overlay/path serving now include independent release-only usage.
- **AC10 pass:** permanent original and remediation regressions, docs/help,
  installed artifacts and final gates cover the requested matrix.
- **AC11 pass:** separate hosted asynchronous publication/pull/apply/refresh/
  republish, stable imports and durable no-repeat decisions now include retry
  and interruption recovery, not only the normal A→B→C lifecycle.
- **AC12 pass:** explicit public promotion stays separate from review; both
  histories, old releases and continued release-bound feedback remain usable.

All completion-matrix cells, brief approach steps and done-when conditions are
satisfied in scope. No judgment-call deferral, inaccessible implementation,
fabricated provider success or unresolved placeholder remains. The unchanged
live-provider, Docker, browser and deployment limitations are explicit scope or
verified environment constraints, not hidden acceptance omissions.

### Structural assessment and forward impact

All three audit dimensions pass. Sync reuses the common production planner
rather than maintaining a partial competing freshness test. Requested versus
completed configuration is explicit. Default revision selection is centralized
without merging review and release state. Expanded-byte validation precedes tar
interpretation. Durable application has a small provider-free owning module,
shared consistently by all working-copy mutation/publication entry points, with
conflicts visible instead of silently overwriting human work.

The existing text/media/API/storage/UI/packaging semantic families remain
coherent, and no additional refactor or style-only blocker is warranted.
Corrections are within the four verified findings and preserve existing model
updates and comparison artifacts. Periodic external sync can now resume the
verified failure paths without losing application decisions or certifying an
obsolete working revision. No further remediation is required by this audit.
