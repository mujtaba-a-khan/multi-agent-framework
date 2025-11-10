"""
Command-line interface for running baselines and evaluations.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import typer
import yaml
from rich import print as rprint
from tqdm import tqdm

from .arena.arena import run_round
from .eval.metrics import compute_summary
from .logging_utils.logger import RunLogger
from .models.targets import build_target
from .agents.red.basic import build_red
from .agents.blue.judge import build_blue_judge


CONFIG_HELP = "Path to baseline.yml"

app = typer.Typer(help="MADLab CLI", invoke_without_command=True)


@dataclass
class Suite:
    name: str
    path: Path


def load_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _run_baseline(config: str) -> None:
    with open(config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    seed = int(cfg.get("seed", 13))
    random.seed(seed)

    out_dir = Path(cfg["io"]["out_dir"])
    run_name = cfg.get("run_name", f"run_{int(time.time())}")
    run_dir = out_dir / run_name / "last_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build components
    target = build_target(cfg["target"])
    red = build_red(cfg["red"])
    blue_roles = cfg["blue"]["roles"]
    blue = [build_blue_judge()] if "judge_v0" in blue_roles else []

    # Gather suites
    suites: List[Suite] = [Suite(**s) for s in cfg["eval"]["suites"]]
    prompts: List[Dict] = []
    for s in suites:
        path = Path(s.path)
        prompts.extend(list(load_jsonl(path)))

    logger = RunLogger(run_dir)
    logger.write_config(cfg)

    # Execute rounds
    results = []
    for item in tqdm(prompts, desc="Running prompts"):
        attack_text = red.generate_attack(item["prompt"])
        out = run_round(prompt=item["prompt"], attack_text=attack_text, target=target, blue=blue)
        out["id"] = item["id"]
        results.append(out)
        logger.write_result(out)

    # Summarize
    summary = compute_summary(results)
    logger.write_summary(summary)

    rprint("[bold green]Done.[/bold green] Summary:")
    rprint(summary)


@app.command("run-baseline")
def run_baseline_cmd(config: str = typer.Option(..., help=CONFIG_HELP)) -> None:
    """
    Run a small baseline over configured suites and log results.
    """
    _run_baseline(config)


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(None, help=CONFIG_HELP),
) -> None:
    """
    When no subcommand is provided, run the baseline directly so previous scripts keep working.
    """
    if ctx.invoked_subcommand is None:
        if config is None:
            raise typer.BadParameter("Pass --config when invoking without a subcommand.")
        _run_baseline(config)


if __name__ == "__main__":
    app()
