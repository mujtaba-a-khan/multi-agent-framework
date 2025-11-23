"""
Run paired configs (e.g., single vs layered) and report summaries.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd):
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    print(proc.stdout)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--single", required=True, help="Config for single-layer run.")
    p.add_argument("--ensemble", required=True, help="Config for layered run.")
    args = p.parse_args()

    run_cmd(["python", "-m", "madlab.cli", "--config", args.single])
    run_cmd(["python", "-m", "madlab.cli", "--config", args.ensemble])
    print("Pair complete. Use scripts/compare_runs.py or scripts/hypothesis_check.py to compare.")


if __name__ == "__main__":
    main()
