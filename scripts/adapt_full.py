"""
End-to-end adaptation: update guard rules and a trainable target from failures, then rerun.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Dict, List

from madlab.api import run_baseline
from madlab.agents.blue.llm_guard import LLMGuardV1
from madlab.config_loader import load_run_config
from madlab.cli import load_jsonl
from madlab.models.trainable_target import TrainableTarget


def _temp_cfg(cfg: Dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yml")
    Path(tmp.name).write_text(json.dumps(cfg), encoding="utf-8")
    return Path(tmp.name)


def suggest_guard_threshold(failures: List[Dict], base_params: Dict, start: float, end: float, steps: int):
    thresholds = [start + i * ((end - start) / max(1, steps - 1)) for i in range(steps)]
    for t in thresholds:
        params = {**base_params, "mode": "score", "threshold": t}
        guard = LLMGuardV1(**params)
        blocked = sum(
            1
            for rec in failures
            if guard.judge(prompt=rec["prompt"], output=rec.get("target_output", "")) == "block"
        )
        if blocked == len(failures):
            return t
    return None


def update_structured_rules(cfg: Dict, failures: List[Dict]) -> Dict:
    """
    Expand structured guard denylist with tokens from failures.
    """
    blue_params = cfg.get("blue", {}).setdefault("params", {})
    rules = blue_params.setdefault("structured_v1", {})
    denylist = set(rules.get("denylist", []))
    for rec in failures:
        for token in rec["prompt"].split():
            if len(token) > 6:
                denylist.add(token.lower())
    rules["denylist"] = sorted(denylist)
    return cfg


def update_trainable_target(cfg: Dict, failures: List[Dict]) -> None:
    """
    If target is trainable_dummy, persist failed prompts into its blocklist.
    """
    tgt = cfg.get("target", {})
    if tgt.get("name") != "trainable_dummy":
        return
    params = tgt.setdefault("params", {})
    blocklist_path = Path(params.get("blocklist_path", "data/blocklist.json"))
    target = TrainableTarget(blocklist_path=str(blocklist_path))
    target.update_blocklist([rec["prompt"] for rec in failures])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="Baseline config YAML.")
    p.add_argument("--run-name-before", default="adapt_full_before", help="Run name for baseline.")
    p.add_argument("--run-name-after", default="adapt_full_after", help="Run name for adapted run.")
    p.add_argument("--guard-out", required=True, help="Path to write updated llm_guard_v1 params.")
    p.add_argument("--start", type=float, default=0.3)
    p.add_argument("--end", type=float, default=0.95)
    p.add_argument("--steps", type=int, default=8)
    args = p.parse_args()

    # Baseline run
    cfg_before = load_run_config(args.config)
    cfg_before["run_name"] = args.run_name_before
    summary_before = run_baseline(str(_temp_cfg(cfg_before)))
    failures_path = Path(cfg_before["io"]["out_dir"]) / cfg_before["run_name"] / "last_run" / "failures.jsonl"
    failures = list(load_jsonl(failures_path)) if failures_path.exists() else []
    print(f"Baseline done. Failures: {len(failures)}. Summary: {summary_before}")

    # Adapt guard threshold
    guard_params = cfg_before.get("blue", {}).get("params", {}).get("llm_guard_v1")
    best = suggest_guard_threshold(failures, guard_params, args.start, args.end, args.steps) if guard_params else None
    if guard_params:
        if best:
            guard_params["mode"] = "score"
            guard_params["threshold"] = best
            print(f"Updated guard threshold to {best:.2f}")
        Path(args.guard_out).write_text(json.dumps(guard_params, indent=2), encoding="utf-8")

    # Adapt structured guard rules
    cfg_after = update_structured_rules(load_run_config(args.config), failures)
    # Adapt trainable target blocklist
    update_trainable_target(cfg_after, failures)
    cfg_after["run_name"] = args.run_name_after
    # Inject updated guard params into cfg_after
    if guard_params:
        cfg_after.setdefault("blue", {}).setdefault("params", {}).setdefault("llm_guard_v1", {}).update(guard_params)

    summary_after = run_baseline(str(_temp_cfg(cfg_after)))
    print(f"Adapted run done. Summary: {summary_after}")
    print(f"ASR: {summary_before.get('ASR')} -> {summary_after.get('ASR')}")
    print(f"FPR: {summary_before.get('FPR')} -> {summary_after.get('FPR')}")


if __name__ == "__main__":
    main()
