"""
Structured guard: deterministic allow/deny rules with simple signature and allowlist checks.
Designed as a formal safeguard layer against prompt-injection and untrusted actions.
"""
from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, List, Optional

# Default allowlisted actions; if provided, at least one must be present when require_allowlist=True
DEFAULT_ALLOWED_ACTIONS = ["READ", "SUMMARIZE", "CLASSIFY", "REFUSE"]
# Default forbidden actions/patterns indicating injection or unsafe operations
DEFAULT_DENY_TOKENS = ["delete", "drop table", "rm -rf", "shutdown", "ignore system", "disregard instructions"]


@dataclass
class StructuredGuardV1:
    denylist: List[str]
    allowlist: Optional[List[str]] = None
    secret_env: str = "MADLAB_GUARD_SECRET"
    require_signature: bool = False
    injection_patterns: Optional[List[str]] = None
    regex_patterns: Optional[List[str]] = None
    require_allowlist: bool = False
    allowed_actions: Optional[List[str]] = None

    def _verify_signature(self, prompt: str, output: str, signature: Optional[str]) -> bool:
        """
        Optional lightweight integrity check: require HMAC over prompt+output.
        """
        if not signature:
            return False
        secret = os.getenv(self.secret_env)
        if not secret:
            return False
        msg = f"{prompt}::{output}".encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    def judge(self, prompt: str, output: str, signature: Optional[str] = None) -> str:
        """
        Deterministic guard:
        - Block if any denylist term appears.
        - If allowlist provided, require one of them.
        - Optionally block known prompt-injection patterns.
        - Optionally require a valid signature to allow.
        """
        text = f"{prompt}\n{output}".lower()
        if any(term.lower() in text for term in self.denylist):
            return "block"
        if self.injection_patterns:
            for pat in self.injection_patterns:
                if pat.lower() in text:
                    return "block"
        if self.regex_patterns:
            for pat in self.regex_patterns:
                if re.search(pat, text, flags=re.IGNORECASE):
                    return "block"
        if self.allowlist:
            has_allow = any(term.lower() in text for term in self.allowlist)
            if self.require_allowlist and not has_allow:
                return "block"
        if self.allowed_actions and self.require_allowlist:
            if not any(action.lower() in text for action in self.allowed_actions):
                return "block"
        if self.require_signature and not self._verify_signature(prompt, output, signature):
            return "block"
        return "allow"


def build_structured_guard(cfg: Dict) -> StructuredGuardV1:
    cfg = cfg or {}
    denylist = cfg.get("denylist", [])
    allowlist = cfg.get("allowlist")
    secret_env = cfg.get("secret_env", "MADLAB_GUARD_SECRET")
    require_signature = cfg.get("require_signature", False)
    injection_patterns = cfg.get("injection_patterns")
    allowed_actions = cfg.get("allowed_actions", DEFAULT_ALLOWED_ACTIONS)
    denylist = denylist or DEFAULT_DENY_TOKENS
    return StructuredGuardV1(
        denylist=denylist,
        allowlist=allowlist,
        secret_env=secret_env,
        require_signature=require_signature,
        injection_patterns=injection_patterns,
        regex_patterns=cfg.get("regex_patterns"),
        require_allowlist=cfg.get("require_allowlist", False),
        allowed_actions=allowed_actions,
    )
