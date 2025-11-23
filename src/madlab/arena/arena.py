"""
Arena orchestrates Red -> Target -> Blue flow for a single round.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional


def run_round(
    prompt: str,
    attack_payload,
    target,
    blue: List,
    blue_mode: str,
    block_action: str,
    prefilter: Optional[Dict],
    is_harmful: bool,
) -> Dict:
    """Run a single red -> target -> blue pass with timing.

    Args:
        prompt: Benign or harmful user prompt.
        attack_payload: Red output; can be a string or dict with text/trace.
        target: Target model wrapper implementing `generate`.
        blue: Blue role instances (e.g., Judge, LLM guard) implementing `judge`.
        blue_mode: How to aggregate blue decisions (e.g., 'first_block').
        block_action: How to handle blocked outputs ('none', 'mask').
        prefilter: Optional dict of prefilter rules (e.g., patterns).
        is_harmful: Ground-truth flag from the labeled dataset.

    Returns:
        Dict containing prompt, attack text, target output, blue decision, label, timing, and traces.
    """
    t0 = time.perf_counter()

    # Prefilter on raw user prompt
    prefilter_blocked = False
    prefilter_reason = None
    if prefilter:
        patterns = prefilter.get("patterns", [])
        lowered = prompt.lower()
        for p in patterns:
            if p.lower() in lowered:
                prefilter_blocked = True
                prefilter_reason = p
                break

    attack_text = attack_payload if isinstance(attack_payload, str) else attack_payload.get("text", "")
    attack_trace = [] if isinstance(attack_payload, str) else attack_payload.get("trace", [])

    if prefilter_blocked:
        target_output = "[BLOCKED BY PREFILTER]"
        t_target0 = t_target1 = time.perf_counter()
        blue_decision = "block"
        t_blue0 = t_blue1 = time.perf_counter()
    else:
        composed = f"{attack_text}\n\nUSER: {prompt}"
        t_target0 = time.perf_counter()
        target_output = target.generate(composed)
        t_target1 = time.perf_counter()

        blue_decision = "allow"
        t_blue0 = time.perf_counter()
        def decide(role):
            kwargs = {"prompt": prompt, "output": target_output}
            return role.judge(**kwargs)

        if blue_mode == "all":
            decisions = [decide(role) for role in blue]
            blue_decision = "block" if any(v == "block" for v in decisions) else "allow"
        else:  # default: short-circuit on block
            for role in blue:
                if decide(role) == "block":
                    blue_decision = "block"
                    break
        t_blue1 = time.perf_counter()

    t1 = time.perf_counter()

    if blue_decision == "block" and block_action == "mask":
        target_output = "[BLOCKED]"

    label = {"is_harmful": is_harmful, "allowed": blue_decision == "allow"}
    return {
        "prompt": prompt,
        "attack_text": attack_text,
        "attack_trace": attack_trace,
        "target_output": target_output,
        "blue_decision": blue_decision,
        "label": label,
        "prefilter": {"blocked": prefilter_blocked, "reason": prefilter_reason} if prefilter else None,
        "timing": {
            "t_total_ms": round((t1 - t0) * 1000.0, 3),
            "t_target_ms": round((t_target1 - t_target0) * 1000.0, 3),
            "t_blue_ms": round((t_blue1 - t_blue0) * 1000.0, 3),
        },
    }
