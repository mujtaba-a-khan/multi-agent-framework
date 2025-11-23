"""
Calibrate LLM guard threshold to target FPR on a labeled dev set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from madlab.cli import load_jsonl
from madlab.agents.blue.llm_guard import build_llm_guard


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dev", required=True, help="Path to labeled JSONL with is_harmful field.")
    p.add_argument("--config", required=True, help="Guard config JSON file (matching llm_guard_v1 params).")
    p.add_argument("--target_fpr", type=float, default=0.05, help="Desired max FPR.")
    p.add_argument("--start", type=float, default=0.1, help="Start threshold.")
    p.add_argument("--end", type=float, default=0.9, help="End threshold.")
    p.add_argument("--steps", type=int, default=9, help="Number of thresholds to test.")
    args = p.parse_args()

    guard_cfg = json.loads(Path(args.config).read_text())
    data = list(load_jsonl(Path(args.dev)))
    thresholds = [args.start + i * ((args.end - args.start) / max(1, args.steps - 1)) for i in range(args.steps)]

    best = None
    for t in thresholds:
        guard_cfg["threshold"] = t
        guard_cfg["mode"] = "score"
        guard = build_llm_guard(guard_cfg)
        harmless = [r for r in data if not r.get("is_harmful", False)]
        fp = 0
        for rec in harmless:
            verdict = guard.judge(prompt=rec["prompt"], output=rec.get("output", ""))
            if verdict == "block":
                fp += 1
        fpr = fp / max(1, len(harmless))
        if best is None or fpr <= args.target_fpr and fpr < best[1]:
            best = (t, fpr)
        print(f"Threshold {t:.2f} -> FPR {fpr:.4f}")

    if best:
        print(f"\nSuggested threshold: {best[0]:.2f} (FPR={best[1]:.4f})")
    else:
        print("No threshold met target FPR; pick manually.")


if __name__ == "__main__":
    main()
