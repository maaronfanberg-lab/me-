#!/usr/bin/env python3
"""Development-only calibration for meaningful-pair refractory selection.

The two frozen historical blocks are explicitly no longer confirmatory evidence.
This script maps a small, fixed parameter grid to find out whether the mechanism
family can materially reduce semantic pair reuse while preserving retrieval
utility. It cannot grant shadow/live permission. Any chosen candidate must be
frozen and tested on a new prospective Community block collected after the
retrieval-time evidence recorder was installed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from endogenous_workspace_artifact_tape import build_exact_tape
from endogenous_workspace_replay import normalize_tape
from endogenous_semantic_refractory_v6 import (
    future_rank_utility,
    mean_consecutive_pair_overlap,
    mean_immediate_utility,
    run_selector,
)

DECAYS = (0.50, 0.72, 0.90, 1.00)
PENALTIES = (0.18, 0.30, 0.45, 0.60, 0.80, 1.00)
K = 4
HORIZON = 4
DISCOUNT = 0.80
UTILITY_FLOOR = 0.95
RELATIVE_REDUCTION_FEASIBILITY_FLOOR = 0.10

SOURCES = {
    "historical_replica": {
        "run_id": 33532383600,
        "artifact_id": 9810274251,
        "sha256": "fac6b5a981eaf5171210b885dd519376536fd32e0ba223d98ab8b53a991f3d85",
        "range": (1, 58),
    },
    "discovery_anchor": {
        "run_id": 33533326825,
        "artifact_id": 9810957121,
        "sha256": "fdab00caf21df61e63802c33e7d2cd63c7e213cb463a3e81a780a719e0803c1f",
        "range": (62, 75),
    },
}


def _load_tape(root: str | Path, source: dict) -> dict:
    raw = build_exact_tape(
        root,
        min_ticks=12,
        artifact_run_id=int(source["run_id"]),
        artifact_sha256=str(source["sha256"]),
    )
    expected = tuple(int(x) for x in source["range"])
    actual = (int(raw["metadata"]["time_step_start"]), int(raw["metadata"]["time_step_end"]))
    if actual != expected:
        raise ValueError(f"frozen development range changed: expected {expected}, got {actual}")
    return normalize_tape(raw)


def _metrics(tape: dict, decay: float, penalty: float) -> dict:
    baseline = run_selector(tape, k=K, decay=decay, penalty=0.0)
    candidate = run_selector(tape, k=K, decay=decay, penalty=penalty)
    base_overlap = mean_consecutive_pair_overlap(baseline)
    cand_overlap = mean_consecutive_pair_overlap(candidate)
    absolute = base_overlap - cand_overlap
    relative = absolute / base_overlap if base_overlap > 0 else 0.0
    base_immediate = mean_immediate_utility(baseline)
    cand_immediate = mean_immediate_utility(candidate)
    base_future = future_rank_utility(baseline, tape, horizon=HORIZON, discount=DISCOUNT)
    cand_future = future_rank_utility(candidate, tape, horizon=HORIZON, discount=DISCOUNT)
    return {
        "baseline_pair_overlap": base_overlap,
        "candidate_pair_overlap": cand_overlap,
        "absolute_pair_overlap_reduction": absolute,
        "relative_pair_overlap_reduction": relative,
        "immediate_utility_ratio": cand_immediate / base_immediate if base_immediate else 0.0,
        "future_utility_ratio": cand_future / base_future if base_future else 0.0,
    }


def run_calibration(artifact_roots: dict[str, str | Path]) -> dict:
    tapes = {label: _load_tape(artifact_roots[label], source) for label, source in SOURCES.items()}
    rows = []
    for decay in DECAYS:
        for penalty in PENALTIES:
            blocks = {label: _metrics(tape, decay, penalty) for label, tape in tapes.items()}
            worst_relative = min(float(m["relative_pair_overlap_reduction"]) for m in blocks.values())
            worst_immediate = min(float(m["immediate_utility_ratio"]) for m in blocks.values())
            worst_future = min(float(m["future_utility_ratio"]) for m in blocks.values())
            utility_safe = worst_immediate >= UTILITY_FLOOR and worst_future >= UTILITY_FLOOR
            rows.append(
                {
                    "refractory_decay": decay,
                    "refractory_penalty": penalty,
                    "blocks": blocks,
                    "worst_block_relative_pair_overlap_reduction": worst_relative,
                    "worst_block_immediate_utility_ratio": worst_immediate,
                    "worst_block_future_utility_ratio": worst_future,
                    "utility_safe": utility_safe,
                }
            )

    safe = [row for row in rows if row["utility_safe"]]
    safe.sort(
        key=lambda row: (
            -float(row["worst_block_relative_pair_overlap_reduction"]),
            float(row["refractory_penalty"]),
            float(row["refractory_decay"]),
        )
    )
    chosen = safe[0] if safe else None
    feasible = bool(
        chosen
        and float(chosen["worst_block_relative_pair_overlap_reduction"])
        >= RELATIVE_REDUCTION_FEASIBILITY_FLOOR
    )
    candidate = None
    if chosen is not None:
        candidate = {
            "refractory_decay": chosen["refractory_decay"],
            "refractory_penalty": chosen["refractory_penalty"],
            "worst_block_relative_pair_overlap_reduction": chosen["worst_block_relative_pair_overlap_reduction"],
            "worst_block_immediate_utility_ratio": chosen["worst_block_immediate_utility_ratio"],
            "worst_block_future_utility_ratio": chosen["worst_block_future_utility_ratio"],
        }

    return {
        "experiment": "endogenous_semantic_refractory_calibration_v7",
        "evidence_role": "development_only_not_confirmatory",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "activated_shadow_mode": False,
        "grid": {
            "decays": list(DECAYS),
            "penalties": list(PENALTIES),
            "k": K,
            "future_horizon_ticks": HORIZON,
            "future_discount": DISCOUNT,
            "utility_floor": UTILITY_FLOOR,
            "relative_reduction_feasibility_floor": RELATIVE_REDUCTION_FEASIBILITY_FLOOR,
        },
        "rows": rows,
        "candidate": candidate,
        "results": {
            "mechanism_family_feasible_on_development_blocks": feasible,
            "candidate_available_for_prospective_preregistration": feasible,
            "shadow_mode_permitted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Development-only semantic refractory calibration.")
    parser.add_argument("--historical-replica", required=True)
    parser.add_argument("--discovery-anchor", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_calibration(
        {
            "historical_replica": args.historical_replica,
            "discovery_anchor": args.discovery_anchor,
        }
    )
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": result["candidate"], "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
