#!/usr/bin/env python3
"""Diagnostic Falcon runner for Cedar Hollow JSON-schema branch ordering.

This experiment changes only the order of already-feasible ``oneOf`` schema
branches. The normal Falcon adapter, prompt, feasibility rules, and WorldEngine
validation/mutation path remain unchanged.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from falcon_live import FalconBackend
from living_world import WorldEngine, load_config

ALL_BRANCHES = ("rest", "observe", "move", "talk", "help", "work")


def parse_branch_order(value: str) -> tuple[str, ...]:
    order = tuple(part.strip().lower() for part in str(value or "").split(",") if part.strip())
    if len(order) != len(ALL_BRANCHES) or set(order) != set(ALL_BRANCHES):
        raise ValueError(
            "branch order must contain each action exactly once: " + ",".join(ALL_BRANCHES)
        )
    return order


class OrderedFalconBackend(FalconBackend):
    """Diagnostic-only Falcon adapter with an explicit schema branch order."""

    def __init__(self, *, branch_order: tuple[str, ...], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if len(branch_order) != len(ALL_BRANCHES) or set(branch_order) != set(ALL_BRANCHES):
            raise ValueError("branch_order must be a permutation of all six action types")
        self.branch_order = tuple(branch_order)

    def _response_schema(self, observation: dict[str, Any]) -> dict[str, Any]:
        feasible = self._feasibility_constraints(observation)
        available = {
            "rest": True,
            "observe": True,
            "move": bool(feasible["move_locations"]),
            "talk": bool(feasible["interaction_targets"]),
            "help": bool(feasible["interaction_targets"]),
            "work": bool(feasible["work_resources"]),
        }
        branches = [
            self._action_schema(action_type, observation)
            for action_type in self.branch_order
            if available[action_type]
        ]
        return {"oneOf": branches}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Cedar with a diagnostic Falcon schema branch order.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("world.json"))
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--actors-per-tick", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("runs") / f"falcon-schema-order-{int(time.time())}",
    )
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--branch-order", required=True)
    args = parser.parse_args()

    branch_order = parse_branch_order(args.branch_order)
    backend = OrderedFalconBackend(
        branch_order=branch_order,
        endpoint=args.endpoint,
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    engine = WorldEngine(
        load_config(args.config),
        backend=backend,
        output_dir=args.output,
        seed=args.seed,
        actors_per_tick=args.actors_per_tick,
        checkpoint_every=args.checkpoint_every,
    )
    metrics = engine.run(args.ticks)
    metadata = {
        "experiment": "cedar-schema-order",
        "branch_order": list(branch_order),
        "seed": args.seed,
        "temperature": args.temperature,
        "ticks": args.ticks,
        "actors_per_tick": args.actors_per_tick,
        "note": "Only JSON-schema oneOf branch order differs from the normal Falcon runner.",
    }
    (args.output / "schema-order.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(args.output), "schema_order": metadata, "metrics": metrics},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
