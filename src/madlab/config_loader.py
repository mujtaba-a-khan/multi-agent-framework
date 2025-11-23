"""
Config helpers to load run configs, model presets, and eval suite paths.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from .env import PROJECT_ROOT, ensure_env_loaded


CONFIG_DIR = PROJECT_ROOT / "configs"
MODELS_FILE = CONFIG_DIR / "models.yml"
EVAL_SUITES_FILE = CONFIG_DIR / "eval_suites.yml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    """
    Load a YAML file safely.

    Args:
        path: Absolute path to a YAML file.

    Returns:
        Parsed YAML as a dictionary. Empty dict if file is missing.
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _split_target_name(name: str) -> Tuple[str, str]:
    """
    Split a target name like 'openai:gpt-4o-mini' into provider/model parts.
    """
    if ":" in name:
        provider, model_name = name.split(":", 1)
        return provider, model_name
    return name, ""


def _apply_model_presets(run_cfg: Dict[str, Any], model_presets: Dict[str, Any]) -> None:
    """
    Merge model presets into the run config target.params if available.

    Args:
        run_cfg: Run configuration dictionary (mutated in place).
        model_presets: Dictionary of provider -> model -> params defaults.
    """
    target_cfg = run_cfg.get("target", {}) or {}
    target_name = target_cfg.get("name", "")
    params = target_cfg.get("params", {}) or {}
    provider, model_name = _split_target_name(target_name)
    defaults = model_presets.get(provider, {}).get(model_name, {}) if model_name else {}
    merged = {**defaults, **params}
    target_cfg["params"] = merged
    run_cfg["target"] = target_cfg


def _apply_eval_suite_paths(run_cfg: Dict[str, Any], eval_registry: Dict[str, Any]) -> None:
    """
    Fill suite paths from the registry when only a suite name is provided.

    Args:
        run_cfg: Run configuration dictionary (mutated in place).
        eval_registry: Dictionary of suite_name -> path.
    """
    suites_cfg = run_cfg.get("eval", {}).get("suites", []) or []
    for suite in suites_cfg:
        if "path" not in suite and "name" in suite:
            registry_path = eval_registry.get("suites", {}).get(suite["name"])
            if registry_path:
                suite["path"] = registry_path


def load_run_config(config_path: str) -> Dict[str, Any]:
    """
    Load a run YAML config and apply model presets and eval suite paths.

    Args:
        config_path: Path to the primary run config YAML.

    Returns:
        Fully merged run config dictionary.
    """
    ensure_env_loaded()
    run_cfg = _load_yaml(Path(config_path))
    model_presets = _load_yaml(MODELS_FILE)
    eval_registry = _load_yaml(EVAL_SUITES_FILE)
    _apply_model_presets(run_cfg, model_presets)
    _apply_eval_suite_paths(run_cfg, eval_registry)
    return run_cfg
