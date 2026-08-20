# Repository cleanup audit

## 2026-08-19

### Verdict

- Passes functional, structural, and forward-impact review. The cleanup removes the approved dead modules, legacy prime/prepass planning path, compatibility alias, duplicate book variants, historical snapshots, quarantined cache, and stale prime artifacts. The lean book pipeline, graphic-novel command group, editorial web app, deployment files, current replay cache, and audiobook generator remain exposed. Existing in-progress graphic-novel work was preserved.

### Findings

None.

### Completeness

- Truthful state: exposed
- Acceptance criteria: all addressed
- Completion matrix: all applicable cells proven by CLI discovery, import/compile checks, a lean draft-request construction check, and the full zero-LLM test suite
- Implementation approach steps: all done
- Done-when conditions: all met
- Files listed in brief: all high-confidence removal candidates handled; conditional graphic experiment extraction and historical graphic-run pruning remain intentionally outside this removal because live stages or active work still depend on them
- Architectural intent: achieved; `lean_plan` is now the sole supported prose-plan builder and fails explicitly for legacy plans at `forage/drafter.py:320`
- Deferred items: none from the approved high-confidence removal set
- Placeholder audit: clean

### Structural Assessment

- Architecture: clean. The graphic command remains registered at `forage/cli.py:58`, the deterministic lean plan command at `forage/cli.py:198`, audiobook generation at `forage/cli.py:561`, and the web editor at `forage/cli.py:1520`.
- Abstraction: clean. Remaining panel-capacity callers now import the owning `forage.graphic.geometry` module directly.
- Semantic families: unified around the lean plan and shared graphic geometry paths.
- Patterns: consistent.
- Integrity: clean. Legacy plans fail explicitly rather than silently falling back to a removed prompt.
- Scope: clean. Pre-existing modified and untracked graphic-novel work was not deleted or rewritten by the cleanup, apart from the two direct geometry-import updates and removal of the documented compatibility alias.

### Forward Impact

- Clean. Removing old plan shapes reduces compatibility branches while retaining all four requested product surfaces.
- Small fix now: none.

### Verification

- `.venv/bin/python -m compileall -q forage scripts`
- `.venv/bin/python -m pytest tests -q` — 437 passed, 6 skipped
- `.venv/bin/python -m forage.cli --help`
- `.venv/bin/python -m forage.cli audiobook --help`
- `git diff --check HEAD`
- Repository search confirmed no remaining source or documentation references to the removed prime, prepass, dialogue-split, segment-extract, legacy draft prompt, panel-capacity alias, or sweep script.

## 2026-08-19 — post-removal verification

### Verdict

- No functional regression was found in the retained lean book pipeline, graphic-novel pipeline, editorial web app/deployment, or audiobook generator. The full unit suite, gated Docker suite, real-browser review workflow, deterministic graphic stages, audiobook dry run, web artifact packaging, CLI discovery, local-import scan, prompt scan, and source-fingerprint path scan all passed. The removal does not pass all three audit dimensions without qualification because the cleanup left legacy raw artifacts behind and the source-fingerprint mapping edit made every retained replay-cache fingerprint report stale. Neither finding prevents cache reuse or pipeline execution.

### Findings

1. Source-provenance reporting was globally invalidated by a stage-local cleanup.
   - evidence:
     - `forage/source_fingerprint.py:18`
     - `forage/source_fingerprint.py:24`
     - `forage/source_fingerprint.py:27`
     - `forage/cache_audit.py:634`
   - `forage/source_fingerprint.py` fingerprints itself as a common dependency. Removing the legacy stage entries therefore changes every stage fingerprint, including unrelated classify, summarize, coherence, graphic, and review stages. All 718 valid retained cache files now report stale. Cache lookup remains key-based and still returns hits, but the provenance audit can no longer distinguish caches affected by this cleanup from unaffected ones.
   - commands used:
     - `.venv/bin/python -m forage.cli cache-audit gatsby`
     - `.venv/bin/python - <<'PY' ... compare_source_fingerprint(group, fp) ... PY` — reported `{'stale': 718}` across 26 stage groups

2. Sixteen legacy prime/prepass outputs remain after their producing stages were removed.
   - evidence:
     - `forage/artifacts.py:6`
     - `forage/artifacts.py:7`
     - `work/gatsby/prime.raw.md`
     - `work/education/plan.raw.md`
     - `work/mobydick/plan.unprimed.json`
   - Seven `prime.raw.md` files, eight `plan.raw.md` files, and one `plan.unprimed.json` remain tracked, totaling about 0.94 MiB. No remaining source code reads them. The artifact-layout docstring also still calls `plan.json` a pre-pass output and advertises `plan.raw.md`.
   - commands used:
     - `find work -mindepth 2 -maxdepth 2 -type f -name 'plan.raw.md' -print | sort`
     - `find work -type f \( -name '*unprimed*' -o -name '*prepass*' -o -name '*prime*' \) -not -path 'work/.replay_cache/*' -print | sort`
     - `rg -n "plan\\.raw\\.md|prime\\.raw\\.md" forage scripts tests README.md docs CLAUDE.md`

3. The new legacy-plan rejection path has no automated regression test.
   - evidence:
     - `forage/drafter.py:317`
     - `forage/drafter.py:320`
   - A manual construction check proved that all 16 current plans build a `draft_lean` request and a synthetic `prepass` plan raises the intended `ValueError`. No test currently exercises either `build_draft_segment_request` or the unsupported-builder error, so future changes could accidentally restore fallback behavior or reject valid lean plans without a focused failure.
   - commands used:
     - `rg -n "build_draft_segment_request|unsupported plan builder|legacy plan|builder.*lean_plan" tests`
     - `.venv/bin/python - <<'PY' ... build_draft_segment_request(...) ... PY`

### Completeness

- Truthful state: exposed
- Acceptance criteria: retained systems function; cleanup completeness is missing the 16 artifacts in finding 2
- Completion matrix: deterministic/runtime-free paths and deployment are proven; paid LLM, image, and ElevenLabs calls were not issued
- Implementation approach steps: removal and retained-surface verification are done; findings remain
- Done-when conditions: functional preservation met; structural and forward-impact conditions need findings 1–3 addressed
- Files listed in brief: high-confidence code and directory removals completed; legacy raw outputs were overlooked
- Architectural intent: lean planning is the only supported prose-plan path, but cache-provenance precision regressed
- Deferred items: paid live calls were not run because repository policy requires explicit approval; their request construction and dry-run paths passed
- Placeholder audit: clean

### Structural Assessment

- Architecture: issue — source-fingerprint self-inclusion causes a mapping-only edit to invalidate unrelated stage provenance.
- Abstraction: clean — graphic capacity callers use `forage.graphic.geometry` directly.
- Semantic families: unified around lean planning and shared graphic geometry.
- Patterns: consistent.
- Integrity: clean for runtime behavior; no swallowed errors or compatibility fallbacks remain.
- Scope: clean — pre-existing active graphic work remains present, and the audit itself did not alter production code.

### Forward Impact

- Risks — cache audit output is now globally stale, remaining raw plan files invite confusion about whether prepass is still supported, and the unsupported-builder contract lacks focused regression coverage.
- Small fix now: remove the 16 raw legacy outputs and stale artifact doc lines; add a focused lean/legacy request-builder test; adjust historical fingerprint handling so removing dead stage definitions does not mark unrelated groups stale.

### Remediation Mapping

- Cache provenance:
  - Resolve finding 1 by preserving historical stage definitions outside the common self-fingerprint or versioning the mapping independently from stage implementation inputs.
- Legacy artifact cleanup:
  - Resolve finding 2 by deleting the enumerated raw outputs and updating `forage/artifacts.py:6-7` to describe the lean plan.
- Draft-plan contract coverage:
  - Resolve finding 3 with tests for a valid `lean_plan` request and explicit rejection of a legacy or missing builder.
