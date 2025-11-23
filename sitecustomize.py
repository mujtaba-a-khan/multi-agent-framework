"""
Automatically make the `src/` directory importable when running repo-local Python commands.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.is_dir():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

try:
    from madlab.env import ensure_env_loaded
except Exception:
    # Fall back to the legacy inline loader if madlab isn't importable yet.
    def _fallback_load_env(path: Path) -> None:
        try:
            lines = path.read_text().splitlines()
        except (FileNotFoundError, OSError):
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
            import os

            os.environ.setdefault(key, value)

    _fallback_load_env(Path(__file__).resolve().parent / ".env")
else:
    ensure_env_loaded()
