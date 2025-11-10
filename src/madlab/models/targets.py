"""
Target model wrappers.
"""
from __future__ import annotations

from dataclasses import dataclass


class BaseTarget:
    def generate(self, prompt: str) -> str:  # pragma: no cover
        raise NotImplementedError


@dataclass
class DummyTarget(BaseTarget):
    """A deterministic echo-like target so the pipeline works without API keys."""

    def generate(self, prompt: str) -> str:
        return "DUMMY: " + prompt[:200]


def build_target(cfg: dict) -> BaseTarget:
    name = cfg.get("name", "dummy")
    if name == "dummy":
        return DummyTarget()

    if name.startswith("openai:") or name == "openai":
        from .openai_target import OpenAITarget

        params = dict(cfg.get("params", {}))
        if ":" in name:
            _, model_alias = name.split(":", 1)
            if model_alias:
                params.setdefault("model", model_alias)
        return OpenAITarget(**params)

    # Fallback to dummy to avoid breaking runs if config is mis-specified.
    return DummyTarget()
