"""
Write configs/results/summaries to a run directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class RunLogger:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        (self.run_dir / "results.jsonl").touch(exist_ok=True)

    def write_config(self, cfg: Dict[str, Any]) -> None:
        p = self.run_dir / "config.json"
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def write_result(self, rec: Dict[str, Any]) -> None:
        with (self.run_dir / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def write_summary(self, summary: Dict[str, Any]) -> None:
        p = self.run_dir / "summary.json"
        p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
