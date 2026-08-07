# Single-Book Review Publishing Audit

## 2026-08-06

### Verdict

- Audited the mounted artifact overlay and `publish_review_book.py` workflow for the public review app. Functional, structural, and forward-impact checks pass: the app can serve baked artifacts, override one book from `/data`, and publish one revised book to Fly without a rebuild or restart after the one-time overlay-aware deployment.

### Findings

No findings.

### Completeness

- Truthful state: release-verified.
- Acceptance criteria: all addressed. A single book can be packaged, uploaded, swapped into the Fly volume, and read by the live app without redeploying again.
- Completion matrix: N/A.
- Implementation approach steps: all done. `ArtifactStore` resolves overlay roots before baked roots at `forage/webapp/store.py:392`, `forage/webapp/store.py:433`, and `forage/webapp/store.py:491`; the publisher packages and swaps one book at `scripts/publish_review_book.py:57`, `scripts/publish_review_book.py:96`, and `scripts/publish_review_book.py:132`; Fly env exposes `/data` overlay roots at `fly.toml:20`.
- Done-when conditions: all met. The deployed app reports health and chapter data from the public API.
- Files listed in brief: N/A.
- Architectural intent: achieved. Artifact reading remains owned by `ArtifactStore`, artifact packaging reuses `scripts/package_review_artifacts.py`, and mutable production state remains on the Fly volume.
- Deferred items: none.
- Placeholder audit: clean. No placeholder branch, TODO, or test-only production path was introduced.

### Structural Assessment

- Architecture: clean. No `docs/architecture/` directory exists in this repository; surrounding code shows the web app storage boundary is `ArtifactStore`, and the change stays there.
- Abstraction: clean. Overlay selection is centralized in `_book_work_dir` and `_book_books_dir`, so alignments, segment checks, diagnostics, metadata, and review-apply ledgers use the same selected root.
- Semantic families: unified. Baked and mounted artifacts share the same on-disk shape.
- Patterns: consistent. Book ids use the existing validation pattern, JSON reads retain cached stat-based behavior, and the publisher follows the repository's script style.
- Integrity: clean. Remote publish validates book ids, uploads a tarball with the expected `artifacts/<book>` and optional `books/<book>` shape, swaps with `.next`/`.prev` directories, and removes the staged archive after success.
- Scope: clean. Changes are limited to webapp artifact resolution, publishing automation, deployment env/docs, and smoke coverage.

### Forward Impact

- Clean. Future automation can call `python scripts/publish_review_book.py <book>` after alignment/packaging without rebuilding the public app. The baked baseline remains a fallback if a mounted book directory is removed.
- Small fix now: none.

### Commands Used

- `.venv/bin/python -m py_compile forage/webapp/store.py scripts/package_review_artifacts.py scripts/publish_review_book.py scripts/check_review_app.py`
- `.venv/bin/python scripts/publish_review_book.py secret_adversary --package-only /tmp/secret_adversary-review.tgz`
- `.venv/bin/python scripts/publish_review_book.py secret_adversary --local-root /tmp/forage-review-volume-20260806`
- `FORAGE_ARTIFACT_OVERLAY_DIR=/tmp/forage-review-volume-20260806/artifacts FORAGE_BOOKS_OVERLAY_DIR=/tmp/forage-review-volume-20260806/books .venv/bin/python - <<'PY' ...`
- `.venv/bin/python scripts/check_review_app.py --book secret_adversary`
- `fly deploy --app forage-review`
- `.venv/bin/python scripts/publish_review_book.py secret_adversary`
- `.venv/bin/python - <<'PY' ... urllib.request.urlopen('https://forage-review.fly.dev/...') ...`
- `fly ssh console --app forage-review -C "sh -lc 'find /data/artifacts/secret_adversary/alignments -maxdepth 1 -name \"*.json\" | wc -l'"`
- `fly ssh console --app forage-review -C "sh -lc 'test -f /data/books/secret_adversary/metadata.json && echo metadata-ok'"`

## 2026-08-06 Inline Critic Removal

### Verdict

- Audited the review-surface change that removes consumed coherence-critic findings from inline review diagnostics. Functional, structural, and forward-impact checks pass: the public review app now exposes current draft-derived flags only, while preserving the useful dialogue/name lint workflow.

### Findings

No findings.

### Completeness

- Truthful state: release-verified.
- Acceptance criteria: all addressed. Inline critic content from `coherence_report.json` is no longer read, packaged, or shown in the deployed review app.
- Completion matrix: N/A.
- Implementation approach steps: all done. `ArtifactStore.diagnostics()` reads `name_lint_report.json` and generated dialogue lint only at `forage/webapp/store.py:584`; packaging copies only `name_lint_report.json` at `scripts/package_review_artifacts.py:37`; the UI labels the remaining checks as flags at `forage/webapp/static/app.js:227`, `forage/webapp/static/app.js:283`, and `forage/webapp/static/app.js:511`.
- Done-when conditions: all met. Local smoke tests passed, the app was deployed, and the public API reports no `coherence` diagnostic sources.
- Files listed in brief: N/A.
- Architectural intent: achieved. The review app no longer surfaces pre-repair critic findings and still keeps current checks in the existing diagnostic channel.
- Deferred items: none.
- Placeholder audit: clean.

### Structural Assessment

- Architecture: clean. No `docs/architecture/` directory exists; the change stays inside the webapp artifact/read layer, packaging script, client labels, and tests.
- Abstraction: clean. The diagnostic source selection remains centralized in `ArtifactStore.diagnostics()`.
- Semantic families: unified. Current review flags continue through the same API/client path; stale coherence critic artifacts are removed at the source.
- Patterns: consistent. Existing diagnostic counters and filter state are retained; labels and tests were updated to match the narrower meaning.
- Integrity: clean. The change removes a stale source instead of hiding rendered cards while keeping API data unchanged.
- Scope: clean. No unrelated runtime behavior changed.

### Forward Impact

- Clean. Future review rounds focus on actionable current draft flags plus human notes, reducing reviewer noise.
- Small fix now: none.

### Commands Used

- `.venv/bin/python -m py_compile forage/webapp/store.py scripts/package_review_artifacts.py scripts/check_review_app.py`
- `.venv/bin/python - <<'PY' ... ArtifactStore diagnostics source counts ...`
- `.venv/bin/python scripts/package_review_artifacts.py dragon_maiden education gatsby secret_adversary`
- `.venv/bin/python scripts/check_review_app.py --book secret_adversary`
- `fly deploy --app forage-review`
- `.venv/bin/python - <<'PY' ... urllib.request.urlopen('https://forage-review.fly.dev/...') ...`
- `.venv/bin/python scripts/publish_review_book.py secret_adversary`
- `fly ssh console --app forage-review -C "sh -lc 'test ! -e /data/artifacts/secret_adversary/coherence_report.json && echo no-mounted-coherence-report'"`
