"""
Automatically make the `src/` directory importable when running repo-local Python commands.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.is_dir():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


try:
    _load_env_file(ENV_PATH)
except OSError:
    print(f"Warning: Could not read environment file at {ENV_PATH!r}")
    pass
