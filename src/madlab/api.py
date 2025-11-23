"""
Programmatic entrypoints mirroring the CLI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .cli import load_jsonl, _build_red_agents
from .arena.arena import run_round
from .config_loader import load_run_config
from .logging_utils.logger import RunLogger
from .eval.metrics import compute_summary
from .models.targets import build_target
from .agents.blue.judge import build_blue_judge
from .agents.blue.llm_guard import build_llm_guard
from .agents.blue.policy import build_policy_guard
from .agents.blue.structured import build_structured_guard


def run_baseline(config_path: str, on_progress=None) -> Dict:
    """
    Run a baseline programmatically and return the summary.

    Args:
        config_path: Path to a YAML config file.
        on_progress: Optional callback(processed, total) invoked per sample.

    Returns:
        Summary dictionary.
    """
    cfg = load_run_config(config_path)
    out_dir = Path(cfg["io"]["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir / cfg.get("run_name", "run_api") / "last_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    target = build_target(cfg["target"])
    red = _build_red_agents(cfg["red"])
    blue_cfg = cfg["blue"]
    blue_roles = blue_cfg["roles"]
    blue_params = blue_cfg.get("params", {})
    blue_mode = blue_cfg.get("mode", "first_block")
    prefilter_cfg = blue_cfg.get("prefilter", {})
    block_action = blue_cfg.get("block_action", "none")
    blue = []
    if "judge_v0" in blue_roles:
        blue.append(build_blue_judge())
    if "llm_guard_v1" in blue_roles:
        blue.append(build_llm_guard(blue_params.get("llm_guard_v1", {})))
    if "policy_v1" in blue_roles:
        blue.append(build_policy_guard(blue_params.get("policy_v1", {})))
    if "structured_v1" in blue_roles:
        blue.append(build_structured_guard(blue_params.get("structured_v1", {})))

    suites = [suite for suite in cfg["eval"]["suites"]]
    prompts: List[Dict] = []
    for s in suites:
        for rec in load_jsonl(Path(s["path"])):
            rec["_suite"] = s["name"]
            prompts.append(rec)

    logger = RunLogger(run_dir)
    logger.write_config(cfg)

    results = []
    total = len(prompts)
    processed = 0
    for item in prompts:
        attack_payload = red.generate_attack(item["prompt"])
        out = run_round(
            prompt=item["prompt"],
            attack_payload=attack_payload,
            target=target,
            blue=blue,
            blue_mode=blue_mode,
            block_action=block_action,
            prefilter=prefilter_cfg,
            is_harmful=bool(item.get("is_harmful", False)),
        )
        out["id"] = item["id"]
        results.append(out)
        logger.write_result(out)
        if out["label"]["is_harmful"] and out["label"]["allowed"]:
            logger.write_failure(out)
        processed += 1
        if on_progress:
            on_progress(processed, total)

    summary = compute_summary(results)
    logger.write_summary(summary)
    return summary
