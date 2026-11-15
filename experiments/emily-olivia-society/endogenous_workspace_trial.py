#!/usr/bin/env python3
"""Run the locked multi-seed historical proxy trial for scarcity consolidation.

This is the first non-pilot trial around Endogenous Workspace v1. It is still
strictly offline: no LLM calls, no dialogue, no Stanford writes, no live feature
enablement, and no Room access.

The primary metric is deliberately prospective rather than cosmetic. For every
consolidation credit, ask whether that exact memory ID reappears in the recorded
Stanford retrieval pool within a fixed future horizon. Arm B should beat the
matched yoked-shuffle arm C if its content selection carries useful temporal
signal rather than merely causing perturbation.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Mapping

from endogenous_workspace_replay import ReplayConfig, load_tape, run_experiment

PREREG_SCHEMA_VERSION = 1
PRIMARY_METRIC = "future_retrieval_credit_hit_rate_delta_b_minus_c"


def load_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, Mapping):
        raise ValueError("preregistration must be a JSON object")
    if int(payload.get("schema_version", 0)) != PREREG_SCHEMA_VERSION:
        raise ValueError("unsupported preregistration schema")
    if payload.get("status") != "locked_before_first_real_history_replay":
        raise ValueError("preregistration is not in the locked pre-run state")
    if payload.get("primary_metric") != PRIMARY_METRIC:
        raise ValueError(f"primary_metric must be {PRIMARY_METRIC!r}")
    seeds = payload.get("seeds")
    if not isinstance(seeds, list) or len(seeds) < 8 or len(set(int(x) for x in seeds)) != len(seeds):
        raise ValueError("preregistration requires at least 8 distinct locked seeds")
    minimum_effect = float(payload.get("minimum_effect_size"))
    if not math.isfinite(minimum_effect) or minimum_effect <= 0:
        raise ValueError("minimum_effect_size must be positive and finite")
    return dict(payload)


def _candidate_ids_by_tick(tape: dict) -> list[set[str]]:
    out: list[set[str]] = []
    for tick in tape["ticks"]:
        ids = {
            row["candidate"].candidate_id
            for row in tick["rows"]
        }
        out.append(ids)
    return out


def future_credit_hit_rate(run: dict, tape: dict, horizon: int) -> dict:
    if horizon < 1:
        raise ValueError("future horizon must be positive")
    future_ids = _candidate_ids_by_tick(tape)
    hits = 0
    credits = 0
    eligible_ticks = 0
    trace = run["trace"]
    for index, tick in enumerate(trace):
        if index + 1 >= len(future_ids):
            continue
        window_end = min(len(future_ids), index + 1 + horizon)
        future_union: set[str] = set()
        for future_index in range(index + 1, window_end):
            future_union.update(future_ids[future_index])
        credited = [str(x) for x in tick.get("consolidated_ids", [])]
        if not credited:
            continue
        eligible_ticks += 1
        for candidate_id in credited:
            credits += 1
            if candidate_id in future_union:
                hits += 1
    return {
        "hits": hits,
        "credits": credits,
        "eligible_ticks": eligible_ticks,
        "hit_rate": (hits / credits) if credits else None,
    }


def _yoke_fallback_rate(run_c: dict) -> float:
    total_selected = 0
    fallback = 0
    for tick in run_c["trace"]:
        total_selected += len(tick.get("selected_ids", []))
        fallback += int(tick.get("yoke_fallback_count", 0) or 0)
    if total_selected == 0:
        return 1.0
    return fallback / total_selected


def run_locked_trial(tape_path: str | Path, prereg_path: str | Path) -> dict:
    prereg = load_prereg(prereg_path)
    tape = load_tape(tape_path)
    minimum_ticks = int(prereg["minimum_tape_ticks"])
    if len(tape["ticks"]) < minimum_ticks:
        raise ValueError(f"tape has {len(tape['ticks'])} ticks; preregistration requires {minimum_ticks}")

    horizon = int(prereg["future_horizon_ticks"])
    k = int(prereg["k"])
    seed_rows: list[dict] = []
    for raw_seed in prereg["seeds"]:
        seed = int(raw_seed)
        result = run_experiment(tape, ReplayConfig(k=k, seed=seed))
        b = future_credit_hit_rate(result["runs"]["B"], tape, horizon)
        c = future_credit_hit_rate(result["runs"]["C"], tape, horizon)
        if b["hit_rate"] is None or c["hit_rate"] is None:
            raise ValueError("trial produced no eligible consolidation credits for the primary metric")
        delta = float(b["hit_rate"]) - float(c["hit_rate"])
        seed_rows.append(
            {
                "seed": seed,
                "b_future_credit_hit_rate": round(float(b["hit_rate"]), 6),
                "c_future_credit_hit_rate": round(float(c["hit_rate"]), 6),
                PRIMARY_METRIC: round(delta, 6),
                "b_hits": b["hits"],
                "b_credits": b["credits"],
                "c_hits": c["hits"],
                "c_credits": c["credits"],
                "ignition_vs_retrieval_rank_correlation": result["metrics"].get(
                    "ignition_vs_retrieval_rank_correlation"
                ),
                "early_stop_retrieval_relabel_warning": bool(
                    result["metrics"].get("early_stop_retrieval_relabel_warning")
                ),
                "yoke_fallback_rate": round(_yoke_fallback_rate(result["runs"]["C"]), 6),
                "capacity_matched": bool(result["metrics"].get("capacity_matched")),
                "yoked_credit_counts": bool(result["metrics"].get("yoked_credit_counts")),
            }
        )

    deltas = [float(row[PRIMARY_METRIC]) for row in seed_rows]
    median_delta = statistics.median(deltas)
    positive_count = sum(delta > 0 for delta in deltas)
    minimum_effect = float(prereg["minimum_effect_size"])
    minimum_positive = int(prereg["minimum_positive_seeds"])
    max_corr = float(prereg["fail_if_ignition_retrieval_rank_correlation_exceeds"])
    max_fallback = float(prereg["maximum_yoke_fallback_rate"])

    corr_invalid = any(
        row["early_stop_retrieval_relabel_warning"]
        or (
            row["ignition_vs_retrieval_rank_correlation"] is not None
            and float(row["ignition_vs_retrieval_rank_correlation"]) > max_corr
        )
        for row in seed_rows
    )
    yoke_invalid = any(float(row["yoke_fallback_rate"]) > max_fallback for row in seed_rows)
    structural_invalid = any(
        not row["capacity_matched"] or not row["yoked_credit_counts"]
        for row in seed_rows
    )
    supported = (
        median_delta >= minimum_effect
        and positive_count >= minimum_positive
        and not corr_invalid
        and not yoke_invalid
        and not structural_invalid
    )

    return {
        "experiment": "endogenous_workspace_scarcity_consolidation_history_proxy_v1",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "primary_metric": PRIMARY_METRIC,
        "preregistration": prereg,
        "tape_metadata": tape.get("metadata", {}),
        "results": {
            "status": "SUPPORTED_FOR_NEXT_OFFLINE_STAGE" if supported else "NOT_SUPPORTED_BY_PROXY_TRIAL",
            "median_primary_effect": round(float(median_delta), 6),
            "minimum_effect_required": minimum_effect,
            "positive_seed_count": positive_count,
            "minimum_positive_seeds_required": minimum_positive,
            "rank_relabel_invalid": corr_invalid,
            "yoke_invalid": yoke_invalid,
            "structural_invalid": structural_invalid,
        },
        "seeds": seed_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked offline EW history proxy trial.")
    parser.add_argument("--tape", required=True)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = run_locked_trial(args.tape, args.prereg)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["results"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
