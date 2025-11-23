"""
Policy/regex-style guard for simple prompt/output screening.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Pattern


DEFAULT_PATTERNS = [
    r"ignore (all )?safety",
    r"disable safety",
    r"jailbreak",
    r"prompt injection",
]


def _compile(patterns: List[str]) -> List[Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


@dataclass
class PolicyGuardV1:
    patterns: List[Pattern]

    def judge(self, prompt: str, output: str) -> str:
        """
        Block if any pattern matches prompt or output.
        """
        text = f"{prompt}\n{output}"
        for pat in self.patterns:
            if pat.search(text):
                return "block"
        return "allow"


def build_policy_guard(cfg: Dict) -> PolicyGuardV1:
    patterns = cfg.get("patterns") if cfg else None
    compiled = _compile(patterns or DEFAULT_PATTERNS)
    return PolicyGuardV1(patterns=compiled)
