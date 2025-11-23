"""
Environment loading helpers for MADLab.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List


def _detect_project_root(markers: Iterable[str] = ("pyproject.toml", ".git")) -> Path:
    """
    Walk up from this file and return the first directory that contains one of the markers.
    Falls back to the parent of this file if no marker is found (e.g., installed package).
    """
    here = Path(__file__).resolve()
    for directory in here.parents:
        for marker in markers:
            if (directory / marker).exists():
                return directory
    # When installed, the repo markers probably don't exist—use the package directory.
    return here.parent


PROJECT_ROOT = _detect_project_root()
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_file(path: Path) -> None:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return
    except OSError as exc:
        # Mirror prior behavior: warn once but keep going.
        print(f"Warning: Could not read environment file at {path!r}: {exc}")
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@lru_cache(maxsize=1)
def ensure_env_loaded(extra_paths: Iterable[Path] | None = None) -> None:
    """
    Idempotently load environment variables from the project .env (and any extras).
    Later lookups for variables set in the shell will win because we only use setdefault.
    """
    paths: List[Path] = [DEFAULT_ENV_PATH]
    if extra_paths:
        for p in extra_paths:
            if p not in paths:
                paths.append(p)

    for path in paths:
        _load_env_file(path)
