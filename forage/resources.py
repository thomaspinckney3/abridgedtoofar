"""Immutable code resources are separate from the writable book workspace."""
from pathlib import Path
import os

PACKAGE_DIR = Path(__file__).resolve().parent


def resource_path(relative: str) -> Path:
    # A checkout has the authoritative editable resources. Wheels receive
    # those same bytes from the build hook, never a second maintained copy.
    checkout = PACKAGE_DIR.parent / relative
    if (PACKAGE_DIR.parent / "pyproject.toml").is_file() and checkout.is_file():
        return checkout
    path = PACKAGE_DIR / "_resources" / relative
    if not path.is_file():
        raise FileNotFoundError(f"missing packaged resource: {relative}")
    return path


def workspace_root(workspace=None) -> Path:
    return Path(workspace or os.environ.get("FORAGE_WORKSPACE") or Path.cwd()).expanduser().resolve()


def workspace_dirs(workspace=None) -> tuple[Path, Path]:
    root = workspace_root(workspace)
    if workspace is not None:
        return root / "books", root / "work"
    return (Path(os.environ.get("FORAGE_BOOKS_DIR") or root / "books").resolve(),
            Path(os.environ.get("FORAGE_WORK_DIR") or root / "work").resolve())
