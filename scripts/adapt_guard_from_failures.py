"""
Suggest an updated LLM guard threshold using failures.jsonl.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from madlab.agents.blue.llm_guard import build_llm_guard
from madlab.cli import load_jsonl


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--failures", required=True, help="Path to failures.jsonl")
    p.add_argument("--guard-config", required=True, help="Guard config JSON (llm_guard_v1 params)")
    p.add_argument("--start", type=float, default=0.3, help="Start threshold")
    p.add_argument("--end", type=float, default=0.95, help="End threshold")
    p.add_argument("--steps", type=int, default=8, help="Number of thresholds to test")
    p.add_argument("--update-config", action="store_true", help="If set, write the suggested threshold back to the guard config JSON.")
    args = p.parse_args()

    failures = list(load_jsonl(Path(args.failures)))
    guard_cfg = json.loads(Path(args.guard_config).read_text())
    thresholds = [args.start + i * ((args.end - args.start) / max(1, args.steps - 1)) for i in range(args.steps)]

    best = None
    for t in thresholds:
        cfg = {**guard_cfg, "mode": "score", "threshold": t}
        guard = build_llm_guard(cfg)
        blocked = 0
        for rec in failures:
            verdict = guard.judge(prompt=rec["prompt"], output=rec.get("target_output", ""))
            if verdict == "block":
                blocked += 1
        if blocked == len(failures):
            best = t
            break
    if best is not None:
        print(f"Suggested threshold to block all {len(failures)} failures: {best:.2f}")
        if args.update_config:
            guard_cfg["threshold"] = best
            Path(args.guard_config).write_text(json.dumps(guard_cfg, indent=2), encoding="utf-8")
            print(f"Updated guard config written to {args.guard_config}")
    else:
        print("No threshold tested blocked all failures; consider expanding guard or rules.")


if __name__ == "__main__":
    main()
