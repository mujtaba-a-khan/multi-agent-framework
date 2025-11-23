"""
List summaries across run directories for quick comparison.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    rows = []
    for path in glob.glob("logs/runs/*/last_run/summary.json"):
        with open(path, "r", encoding="utf-8") as f:
            s = json.load(f)
        run_dir = str(Path(path).parent)
        rows.append(
            {
                "run_dir": run_dir,
                "ASR": s.get("ASR"),
                "FPR": s.get("FPR"),
                "n_harmful": s.get("n_harmful"),
                "n_harmless": s.get("n_harmless"),
                "lat_ms_total": (s.get("latency_ms_avg") or {}).get("total"),
            }
        )
    if not rows:
        print("No summaries found.")
        return
    df = pd.DataFrame(rows).sort_values("run_dir")
    print(df.to_string(index=False))
    out_path = Path("logs/summary_comparison.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
