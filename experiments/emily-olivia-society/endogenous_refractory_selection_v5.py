#!/usr/bin/env python3
"""Offline test of identity-specific refractory retrieval selection.

The candidate mechanism is deliberately small: a selected memory receives a
short-lived inhibition term that decays every tick. This creates internal
selection-history feedback while preserving a fixed K and using no generated
text. The experiment compares it directly with Stanford retrieval on frozen
Emily + Olivia evidence blocks.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Mapping

from endogenous_workspace_artifact_tape import build_exact_tape
from endogenous_workspace_replay import normalize_tape

SCHEMA_VERSION = 5


def load_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("preregistration must be an object")
    if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported refractory preregistration schema")
    if payload.get("status") != "locked_before_refractory_selection_execution":
        raise ValueError("refractory preregistration is not locked")
    params = payload.get("parameters")
    gates = payload.get("co_primary_gates")
    if not isinstance(params, Mapping) or not isinstance(gates, Mapping):
        raise ValueError("parameters and co-primary gates are required")
    for key in ("refractory_decay", "refractory_penalty", "future_discount"):
        value = float(params[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and non-negative")
    if int(params["k"]) < 1 or int(params["future_horizon_ticks"]) < 1:
        raise ValueError("k and future horizon must be positive")
    return dict(payload)


def _rank_retrieval(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (-float(row["retrieval_score"]), row["candidate"].candidate_id),
    )


def run_selector(tape: dict, *, k: int, decay: float, penalty: float) -> dict:
    refractory: dict[str, float] = {}
    trace: list[dict] = []
    for tick in tape["ticks"]:
        decayed = {}
        for candidate_id, value in refractory.items():
            next_value = float(value) * float(decay)
            if next_value >= 0.001:
                decayed[candidate_id] = next_value
        refractory = decayed

        ranked = []
        for row in tick["rows"]:
            candidate_id = row["candidate"].candidate_id
            inhibition = float(refractory.get(candidate_id, 0.0))
            effective = float(row["retrieval_score"]) - float(penalty) * inhibition
            ranked.append({**row, "effective_score": effective, "refractory_before": inhibition})
        ranked.sort(
            key=lambda row: (
                -float(row["effective_score"]),
                -float(row["retrieval_score"]),
                row["candidate"].candidate_id,
            )
        )
        selected = ranked[: min(int(k), len(ranked))]
        selected_ids = [row["candidate"].candidate_id for row in selected]
        for candidate_id in selected_ids:
            refractory[candidate_id] = 1.0
        trace.append(
            {
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "selected_retrieval_scores": [float(row["retrieval_score"]) for row in selected],
            }
        )
    return {"trace": trace}


def mean_consecutive_overlap(run: dict) -> float:
    trace = run["trace"]
    values = []
    for previous, current in zip(trace, trace[1:]):
        a = set(previous["selected_ids"])
        b = set(current["selected_ids"])
        union = a | b
        values.append((len(a & b) / len(union)) if union else 0.0)
    return sum(values) / len(values) if values else 0.0


def mean_immediate_utility(run: dict) -> float:
    values = [score for tick in run["trace"] for score in tick["selected_retrieval_scores"]]
    return sum(values) / len(values) if values else 0.0


def future_rank_utility(run: dict, tape: dict, *, horizon: int, discount: float) -> float:
    future_maps = []
    for tick in tape["ticks"]:
        future_maps.append(
            {
                row["candidate"].candidate_id: float(row["retrieval_score"])
                for row in tick["rows"]
            }
        )
    values = []
    for index, tick in enumerate(run["trace"]):
        for candidate_id in tick["selected_ids"]:
            best = 0.0
            for offset in range(1, horizon + 1):
                future_index = index + offset
                if future_index >= len(future_maps):
                    break
                score = float(future_maps[future_index].get(candidate_id, 0.0))
                discounted = score * (float(discount) ** (offset - 1))
                if discounted > best:
                    best = discounted
            values.append(best)
    return sum(values) / len(values) if values else 0.0


def evaluate_tape(tape: dict, prereg: Mapping) -> dict:
    params = prereg["parameters"]
    gates = prereg["co_primary_gates"]
    k = int(params["k"])
    decay = float(params["refractory_decay"])
    penalty = float(params["refractory_penalty"])
    horizon = int(params["future_horizon_ticks"])
    discount = float(params["future_discount"])

    baseline = run_selector(tape, k=k, decay=decay, penalty=0.0)
    refractory = run_selector(tape, k=k, decay=decay, penalty=penalty)
    sanity = run_selector(tape, k=k, decay=decay, penalty=float(prereg["sanity_ablation"]["refractory_penalty"]))

    baseline_overlap = mean_consecutive_overlap(baseline)
    refractory_overlap = mean_consecutive_overlap(refractory)
    overlap_reduction = baseline_overlap - refractory_overlap
    baseline_immediate = mean_immediate_utility(baseline)
    refractory_immediate = mean_immediate_utility(refractory)
    immediate_ratio = refractory_immediate / baseline_immediate if baseline_immediate else 0.0
    baseline_future = future_rank_utility(baseline, tape, horizon=horizon, discount=discount)
    refractory_future = future_rank_utility(refractory, tape, horizon=horizon, discount=discount)
    future_ratio = refractory_future / baseline_future if baseline_future else 0.0
    sanity_exact = all(
        a["selected_ids"] == b["selected_ids"]
        for a, b in zip(baseline["trace"], sanity["trace"])
    )

    passes = {
        "overlap_reduction": overlap_reduction >= float(gates["minimum_consecutive_selection_overlap_reduction"]),
        "immediate_utility": immediate_ratio >= float(gates["minimum_immediate_retrieval_utility_ratio"]),
        "future_utility": future_ratio >= float(gates["minimum_future_rank_utility_ratio"]),
        "sanity_ablation": sanity_exact,
    }
    return {
        "baseline_consecutive_overlap": round(baseline_overlap, 6),
        "refractory_consecutive_overlap": round(refractory_overlap, 6),
        "consecutive_overlap_reduction": round(overlap_reduction, 6),
        "baseline_immediate_retrieval_utility": round(baseline_immediate, 6),
        "refractory_immediate_retrieval_utility": round(refractory_immediate, 6),
        "immediate_retrieval_utility_ratio": round(immediate_ratio, 6),
        "baseline_future_rank_utility": round(baseline_future, 6),
        "refractory_future_rank_utility": round(refractory_future, 6),
        "future_rank_utility_ratio": round(future_ratio, 6),
        "sanity_zero_penalty_matches_retrieval": sanity_exact,
        "gate_pass": passes,
        "all_gates_pass": all(passes.values()),
    }


def run_experiment(prereg_path: str | Path, artifact_roots: Mapping[str, str | Path]) -> dict:
    prereg = load_prereg(prereg_path)
    block_results = []
    for evidence in prereg["frozen_evidence"]:
        label = str(evidence["label"])
        if label not in artifact_roots:
            raise ValueError(f"missing artifact root for {label}")
        raw = build_exact_tape(
            artifact_roots[label],
            min_ticks=12,
            artifact_run_id=int(evidence["community_run_id"]),
            artifact_sha256=str(evidence["artifact_sha256"]),
        )
        expected_start, expected_end = [int(x) for x in evidence["expected_exact_range"]]
        if int(raw["metadata"]["time_step_start"]) != expected_start or int(raw["metadata"]["time_step_end"]) != expected_end:
            raise ValueError(
                f"{label} exact range changed: got {raw['metadata']['time_step_start']}-{raw['metadata']['time_step_end']}, "
                f"expected {expected_start}-{expected_end}"
            )
        tape = normalize_tape(raw)
        block_results.append(
            {
                "label": label,
                "source_run_id": int(evidence["community_run_id"]),
                "source_artifact_id": int(evidence["artifact_id"]),
                "tape_metadata": raw["metadata"],
                "metrics": evaluate_tape(tape, prereg),
            }
        )

    all_blocks_pass = all(block["metrics"]["all_gates_pass"] for block in block_results)
    if not bool(prereg["co_primary_gates"].get("must_pass_all_evidence_blocks", True)):
        all_blocks_pass = any(block["metrics"]["all_gates_pass"] for block in block_results)
    return {
        "experiment": "endogenous_refractory_selection_v5",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "activated_shadow_mode": False,
        "preregistration": prereg,
        "blocks": block_results,
        "results": {
            "status": "SUPPORTED_FOR_PROSPECTIVE_REPLICATION" if all_blocks_pass else "NOT_SUPPORTED_BY_FROZEN_BLOCKS",
            "all_required_blocks_pass": all_blocks_pass,
            "shadow_mode_permitted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked refractory-selection test on frozen artifacts.")
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--historical-replica", required=True)
    parser.add_argument("--discovery-anchor", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_experiment(
        args.prereg,
        {
            "historical_replica": args.historical_replica,
            "discovery_anchor": args.discovery_anchor,
        },
    )
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"blocks": result["blocks"], "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
