"""
Target model wrappers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


class BaseTarget:
    """Abstract target interface."""

    def generate(self, prompt: str) -> str:  # pragma: no cover
        """
        Produce a model response for the given prompt.
        """
        raise NotImplementedError


@dataclass
class DummyTarget(BaseTarget):
    """A deterministic echo-like target so the pipeline works without API keys."""

    def generate(self, prompt: str) -> str:
        return "DUMMY: " + prompt[:200]


def build_target(cfg: dict) -> BaseTarget:
    """
    Factory for target models.

    Args:
        cfg: Target configuration containing name and params.

    Returns:
        An instantiated target model wrapper.
    """
    name = cfg.get("name", "dummy")
    params: Dict = cfg.get("params", {}) or {}
    if name == "dummy":
        return DummyTarget()

    if name.startswith("openai:") or name == "openai":
        from .openai_target import OpenAITarget

        if ":" in name:
            _, model_alias = name.split(":", 1)
            if model_alias:
                params.setdefault("model", model_alias)
        return OpenAITarget(**params)

    if name == "trainable_dummy":
        from .trainable_target import TrainableTarget

        return TrainableTarget(**params)

    # Fallback to dummy to avoid breaking runs if config is mis-specified.
    return DummyTarget()
