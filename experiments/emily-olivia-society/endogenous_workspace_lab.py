#!/usr/bin/env python3
"""Run private endogenous-attention pulses without producing dialogue.

This is a lab harness for the Emily + Olivia Stanford workspaces. It never sends
messages and never asks the language model to generate inner monologue. It only
retrieves existing Stanford memories, updates the experimental fast/slow
workspace state, and prints structured ignition diagnostics.
"""
from __future__ import annotations

import argparse
import json
import os

from community_cycle import load_agents, next_community_time_step
from endogenous_workspace import ENV_FLAG, pulse_agent


def run_lab(pulses: int, persist: bool) -> dict:
    if pulses < 1 or pulses > 50:
        raise ValueError("pulses must be between 1 and 50")

    os.environ[ENV_FLAG] = "1"
    agents = load_agents()
    base_time_step = next_community_time_step(agents)
    results: list[dict] = []

    for offset in range(pulses):
        for agent in agents:
            other = next(candidate for candidate in agents if candidate.agent_id != agent.agent_id)
            result = pulse_agent(
                agent,
                other.name,
                time_step=base_time_step + offset,
                observed_text="",
            )
            results.append(
                {
                    "agent": agent.name,
                    "pulse_index": offset + 1,
                    "time_step": base_time_step + offset,
                    "diagnostics": result.diagnostics,
                    "broadcast_present": bool(result.broadcast_context),
                }
            )

    if persist:
        for agent in agents:
            agent.brain.save(str(agent.workspace))

    return {
        "experiment": "endogenous_workspace_v1",
        "mode": "private_memory_attention_only",
        "produced_dialogue": False,
        "pulses_per_agent": pulses,
        "persisted": persist,
        "start_time_step": base_time_step,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run private endogenous-attention pulses for Emily and Olivia."
    )
    parser.add_argument("--pulses", type=int, default=6)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist the slow workspace traces into the existing Stanford workspaces.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit the experiment. This harness never sends dialogue.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("Refusing to run automatically. Add --run to permit the experiment.")
    print(json.dumps(run_lab(args.pulses, args.persist), indent=2))


if __name__ == "__main__":
    main()
