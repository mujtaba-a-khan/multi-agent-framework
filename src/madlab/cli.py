"""
Command-line interface for running baselines and evaluations.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import typer
from rich import print as rprint
from tqdm import tqdm

from .arena.arena import run_round
from .eval.metrics import compute_summary
from .logging_utils.logger import RunLogger
from .models.targets import build_target
from .agents.red.basic import build_basic
from .agents.red.multiturn import MultiTurnRed, PromptInjectionRed, DataExfilRed, RedEnsemble
from .agents.blue.judge import build_blue_judge
from .agents.blue.llm_guard import build_llm_guard
from .agents.blue.policy import build_policy_guard
from .config_loader import load_run_config


CONFIG_HELP = "Path to baseline.yml"

app = typer.Typer(help="MADLab CLI", invoke_without_command=True)


@dataclass
class Suite:
    name: str
    path: Path


def _build_red_agents(cfg: Dict) -> object:
    """
    Build red attacker(s) from config.

    Supports single strategy or an ensemble via a list of strategies.
    """
    strategy = cfg.get("strategy")
    strategies = cfg.get("strategies") or []
    agents = []
    if strategies:
        for s in strategies:
            name = s.get("name")
            params = s.get("params", {})
            if name == "basic_jailbreak_v0":
                agents.append(build_basic(params))
            elif name == "multi_turn_v1":
                agents.append(MultiTurnRed())
            elif name == "prompt_injection_v1":
                agents.append(PromptInjectionRed())
            elif name == "data_exfil_v1":
                agents.append(DataExfilRed())
    elif strategy:
        if strategy == "multi_turn_v1":
            agents.append(MultiTurnRed())
        elif strategy == "prompt_injection_v1":
            agents.append(PromptInjectionRed())
        elif strategy == "data_exfil_v1":
            agents.append(DataExfilRed())
        else:
            agents.append(build_basic(cfg.get("params", {})))
    else:
        agents.append(build_basic(cfg.get("params", {})))

    if len(agents) == 1:
        return agents[0]
    return RedEnsemble(agents=agents)


def load_jsonl(path: Path) -> Iterable[Dict]:
    """
    Yield JSON objects from a JSONL file.

    Args:
        path: Path to a JSONL file.

    Yields:
        Parsed JSON dictionary per non-empty line.
    """
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _run_baseline(config: str) -> None:
    """
    Execute a baseline run using the provided config path.

    Args:
        config: Path to the YAML config file.
    """
    cfg = load_run_config(config)

    seed = int(cfg.get("seed", 13))
    random.seed(seed)

    out_dir = Path(cfg["io"]["out_dir"])
    run_name = cfg.get("run_name", f"run_{int(time.time())}")
    run_dir = out_dir / run_name / "last_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build components
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

    # Gather suites
    suites: List[Suite] = [Suite(**s) for s in cfg["eval"]["suites"]]
    prompts: List[Dict] = []
    for s in suites:
        path = Path(s.path)
        for rec in load_jsonl(path):
            rec["_suite"] = s.name
            prompts.append(rec)

    logger = RunLogger(run_dir)
    logger.write_config(cfg)

    # Execute rounds
    results = []
    for item in tqdm(prompts, desc="Running prompts"):
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

    # Summarize
    summary = compute_summary(results)
    logger.write_summary(summary)

    rprint("[bold green]Done.[/bold green] Summary:")
    rprint(summary)


@app.command("run-baseline")
def run_baseline_cmd(config: str = typer.Option(..., help=CONFIG_HELP)) -> None:
    """Run a small baseline over configured suites and log results."""
    _run_baseline(config)


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(None, help=CONFIG_HELP),
) -> None:
    """Fallback entry point to preserve prior invocation style."""
    if ctx.invoked_subcommand is None:
        if config is None:
            raise typer.BadParameter("Pass --config when invoking without a subcommand.")
        _run_baseline(config)


if __name__ == "__main__":
    app()
