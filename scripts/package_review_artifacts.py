#!/usr/bin/env python3
"""Compatibility entrypoint for package-owned review artifact packaging."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forage import review_package

if __name__ == "__main__":
    raise SystemExit(review_package.main())
else:
    # Preserve script-import callers while keeping all runtime logic installed.
    sys.modules[__name__] = review_package
