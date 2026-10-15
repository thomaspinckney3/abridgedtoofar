"""Retired historical defect probes from the 2026-10-14 repository audit.

The original probes asserted that defects were present. M1 fixes those defects;
permanent offline regression tests now assert the correct behavior. Run:

    .venv/bin/python -m pytest -q tests/test_artifact_safety.py \
        tests/test_draft_completion.py tests/test_alignment_freshness.py \
        tests/test_audiobook_reuse.py

All fixtures use temporary trees and fake providers. See AUDIT.md for the
original findings and project-notes/production-pipeline/STATUS.md for validation.
"""

if __name__ == "__main__":
    print("Retired defect probes: run the permanent tests/test_{artifact_safety,"
          "draft_completion,alignment_freshness,audiobook_reuse}.py regressions.")
