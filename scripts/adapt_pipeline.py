"""
End-to-end adaptation loop:
1) Run baseline on given config.
2) Read failures.jsonl and suggest an updated LLM guard threshold to block all failures.
3) Write updated guard params to JSON.
4) Optionally re-run with the adapted guard and report before/after summaries.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from madlab.api import run_baseline
from madlab.agents.blue.llm_guard import LLMGuardV1
from madlab.cli import load_jsonl
from madlab.config_loader import load_run_config


def _write_temp_cfg(cfg: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yml")
    Path(tmp.name).write_text(json.dumps(cfg), encoding="utf-8")
    return Path(tmp.name)


def _choose_threshold(failures, base_params, start, end, steps):
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="Base YAML config for baseline run.")
    p.add_argument("--guard-config-out", required=True, help="Where to write updated llm_guard_v1 params (JSON).")
    p.add_argument("--baseline-run-name", default="adapt_baseline", help="Run name for baseline.")
    p.add_argument("--adapted-run-name", default="adapt_after", help="Run name for adapted rerun.")
    p.add_argument("--start", type=float, default=0.3, help="Start threshold.")
    p.add_argument("--end", type=float, default=0.95, help="End threshold.")
    p.add_argument("--steps", type=int, default=8, help="Thresholds to test.")
    p.add_argument("--rerun", action="store_true", help="If set, rerun with adapted guard and report summaries.")
    args = p.parse_args()

    # Baseline run
    cfg = load_run_config(args.config)
    cfg["run_name"] = args.baseline_run_name
    base_cfg_path = _write_temp_cfg(cfg)
    summary_before = run_baseline(str(base_cfg_path))
    run_dir = Path(cfg["io"]["out_dir"]) / cfg["run_name"] / "last_run"
    failures_path = run_dir / "failures.jsonl"
    failures = list(load_jsonl(failures_path)) if failures_path.exists() else []
    print(f"Baseline run complete. Failures: {len(failures)}. Summary: {summary_before}")

    guard_params = cfg.get("blue", {}).get("params", {}).get("llm_guard_v1")
    if not guard_params:
        raise SystemExit("No llm_guard_v1 params found in config; cannot adapt.")
    best = _choose_threshold(failures, guard_params, args.start, args.end, args.steps) if failures else None
    if best is None:
        print("No threshold found (or no failures). Writing original guard params.")
        updated_guard = guard_params
    else:
        updated_guard = {**guard_params, "mode": "score", "threshold": best}
        print(f"Suggested threshold: {best:.2f}")
    Path(args.guard_config_out).write_text(json.dumps(updated_guard, indent=2), encoding="utf-8")
    print(f"Wrote updated guard params to {args.guard_config_out}")

    if not args.rerun:
        return

    # Adapted rerun
    cfg_after = load_run_config(args.config)
    cfg_after["run_name"] = args.adapted_run_name
    cfg_after.setdefault("blue", {}).setdefault("params", {}).setdefault("llm_guard_v1", {}).update(updated_guard)
    adapted_cfg_path = _write_temp_cfg(cfg_after)
    summary_after = run_baseline(str(adapted_cfg_path))
    print(f"Adapted run complete. Summary: {summary_after}")
    print("Before/After:")
    print(f"ASR before: {summary_before['ASR']} -> after: {summary_after['ASR']}")
    print(f"FPR before: {summary_before['FPR']} -> after: {summary_after['FPR']}")


if __name__ == "__main__":
    main()
