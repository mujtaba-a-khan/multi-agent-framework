"""
Simple trainable target that can learn to block patterns from failures.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .targets import BaseTarget


@dataclass
class TrainableTarget(BaseTarget):
    """
    Mimics a target that can be fine-tuned to refuse known-bad prompts.
    """

    blocklist_path: str = "data/blocklist.json"
    max_echo: int = 200
    _blocklist: List[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        path = Path(self.blocklist_path)
        if path.exists():
            try:
                self._blocklist = json.loads(path.read_text())
            except json.JSONDecodeError:
                self._blocklist = []

    def generate(self, prompt: str) -> str:
        """
        Return a refusal if prompt matches known-bad patterns; otherwise echo.
        """
        lowered = prompt.lower()
        if any(pat.lower() in lowered for pat in self._blocklist):
            return "[REFUSED BY TRAINED TARGET]"
        return "TRAINABLE: " + prompt[: self.max_echo]

    def update_blocklist(self, patterns: List[str]) -> None:
        """
        Extend the blocklist and persist to disk.
        """
        new = [p for p in patterns if p not in self._blocklist]
        if not new:
            return
        self._blocklist.extend(new)
        Path(self.blocklist_path).write_text(json.dumps(self._blocklist, indent=2), encoding="utf-8")
