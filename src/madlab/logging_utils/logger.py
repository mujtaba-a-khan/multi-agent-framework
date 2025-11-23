"""
Write configs/results/summaries to a run directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class RunLogger:
    """Persist config, per-sample results, and summary artifacts."""

    def __init__(self, run_dir: Path) -> None:
        """
        Initialize the logger and ensure result file exists.

        Args:
            run_dir: Directory for run artifacts.
        """
        self.run_dir = run_dir
        (self.run_dir / "results.jsonl").touch(exist_ok=True)
        (self.run_dir / "failures.jsonl").touch(exist_ok=True)

    def write_config(self, cfg: Dict[str, Any]) -> None:
        """
        Write the resolved config to disk.

        Args:
            cfg: Configuration dictionary.
        """
        p = self.run_dir / "config.json"
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def write_result(self, rec: Dict[str, Any]) -> None:
        """
        Append a single result record as JSONL.

        Args:
            rec: Result dictionary for one sample.
        """
        with (self.run_dir / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def write_summary(self, summary: Dict[str, Any]) -> None:
        """
        Write the summary statistics to disk.

        Args:
            summary: Summary metrics dictionary.
        """
        p = self.run_dir / "summary.json"
        p.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def write_failure(self, rec: Dict[str, Any]) -> None:
        """
        Append a failure record (harmful but allowed) for replay/adaptation.

        Args:
            rec: Failure dictionary.
        """
        with (self.run_dir / "failures.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
