#!/usr/bin/env python3
"""Locked v2 exact-artifact trial for prediction-error selection.

Primary outcome is rank-sensitive and prospective. A consolidation credit earns
more when that exact memory returns sooner and at a better Stanford retrieval
rank within the preregistered horizon. This avoids the binary-reappearance
saturation that made the v1 historical proxy uninformative.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Mapping

from endogenous_workspace_prediction_error import PredictionConfig, run_prediction_error_arm
from endogenous_workspace_replay import ARM_C, ReplayConfig, load_tape, run_arm

PREREG_SCHEMA_VERSION = 2
PRIMARY_METRIC = "discounted_future_retrieval_rank_delta_pe_minus_yoked"


def load_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("preregistration must be a JSON object")
    if int(payload.get("schema_version", 0)) != PREREG_SCHEMA_VERSION:
        raise ValueError("unsupported preregistration schema")
    if payload.get("status") != "locked_before_first_exact_artifact_prediction_error_trial":
        raise ValueError("v2 preregistration is not locked")
    if payload.get("primary_metric") != PRIMARY_METRIC:
        raise ValueError(f"primary metric must be {PRIMARY_METRIC!r}")
    seeds = payload.get("seeds")
    if not isinstance(seeds, list) or len(seeds) < 8 or len({int(x) for x in seeds}) != len(seeds):
        raise ValueError("v2 requires at least 8 distinct locked seeds")
    minimum_effect = float(payload.get("minimum_effect_size"))
    if not math.isfinite(minimum_effect) or minimum_effect <= 0:
        raise ValueError("minimum_effect_size must be positive and finite")
    return dict(payload)


def _rank_maps(tape: dict) -> list[dict[str, int]]:
    maps: list[dict[str, int]] = []
    for tick in tape["ticks"]:
        ranked = sorted(
            tick["rows"],
            key=lambda row: (-float(row["retrieval_score"]), row["candidate"].candidate_id),
        )
        maps.append({row["candidate"].candidate_id: rank for rank, row in enumerate(ranked, start=1)})
    return maps


def discounted_future_rank_score(
    run: dict,
    tape: dict,
    horizon: int,
    discount: float,
) -> dict:
    if horizon < 1:
        raise ValueError("future horizon must be positive")
    if not 0.0 < discount <= 1.0:
        raise ValueError("future discount must be in (0, 1]")
    rank_maps = _rank_maps(tape)
    total = 0.0
    credits = 0
    nonzero = 0
    for index, tick in enumerate(run["trace"]):
        credited = [str(x) for x in tick.get("consolidated_ids", [])]
        for candidate_id in credited:
            credits += 1
            best = 0.0
            for offset in range(1, horizon + 1):
                future_index = index + offset
                if future_index >= len(rank_maps):
                    break
                rank = rank_maps[future_index].get(candidate_id)
                if rank is None:
                    continue
                score = (discount ** (offset - 1)) / float(rank)
                best = max(best, score)
            if best > 0:
                nonzero += 1
            total += best
    return {
        "credits": credits,
        "nonzero_future_matches": nonzero,
        "mean_discounted_future_rank_score": (total / credits) if credits else None,
    }


def _yoke_fallback_rate(run_c: dict) -> float:
    selected = sum(len(tick.get("selected_ids", [])) for tick in run_c["trace"])
    fallback = sum(int(tick.get("yoke_fallback_count", 0) or 0) for tick in run_c["trace"])
    return (fallback / selected) if selected else 1.0


def _verify_evidence(tape: dict, prereg: Mapping) -> None:
    metadata = tape.get("metadata", {})
    source = prereg.get("evidence_source", {})
    if metadata.get("exact_node_metadata") is not True:
        raise ValueError("v2 requires exact Stanford node metadata")
    if int(metadata.get("artifact_run_id") or 0) != int(source.get("community_run_id") or 0):
        raise ValueError("tape artifact run does not match preregistration")
    expected_digest = str(source.get("artifact_sha256") or "")
    if expected_digest and str(metadata.get("artifact_sha256") or "") != expected_digest:
        raise ValueError("tape artifact digest does not match preregistration")
    if int(metadata.get("tick_count") or 0) < int(prereg.get("minimum_tape_ticks", 0)):
        raise ValueError("exact artifact tape is shorter than preregistered minimum")


def run_locked_trial(tape_path: str | Path, prereg_path: str | Path) -> dict:
    prereg = load_prereg(prereg_path)
    tape = load_tape(tape_path)
    _verify_evidence(tape, prereg)

    k = int(prereg["k"])
    horizon = int(prereg["future_horizon_ticks"])
    discount = float(prereg["future_discount"])
    prediction = PredictionConfig(
        alpha=float(prereg["prediction_alpha"]),
        absence_decay=float(prereg["prediction_absence_decay"]),
    )

    seed_rows: list[dict] = []
    for raw_seed in prereg["seeds"]:
        seed = int(raw_seed)
        config = ReplayConfig(k=k, seed=seed)
        pe = run_prediction_error_arm(tape, config, prediction)
        yoked = run_arm(tape, ARM_C, config, yoke_schedule=pe["yoke_schedule"])
        pe_score = discounted_future_rank_score(pe, tape, horizon, discount)
        c_score = discounted_future_rank_score(yoked, tape, horizon, discount)
        if pe_score["mean_discounted_future_rank_score"] is None or c_score["mean_discounted_future_rank_score"] is None:
            raise ValueError("v2 produced no eligible consolidation credits")
        delta = float(pe_score["mean_discounted_future_rank_score"]) - float(
            c_score["mean_discounted_future_rank_score"]
        )
        capacity_matched = all(
            len(a.get("selected_ids", [])) == len(b.get("selected_ids", []))
            for a, b in zip(pe["trace"], yoked["trace"])
        )
        credit_matched = all(
            int(a.get("credit_count", 0)) == int(b.get("credit_count", 0))
            for a, b in zip(pe["trace"], yoked["trace"])
        )
        seed_rows.append(
            {
                "seed": seed,
                "pe_score": round(float(pe_score["mean_discounted_future_rank_score"]), 6),
                "yoked_score": round(float(c_score["mean_discounted_future_rank_score"]), 6),
                PRIMARY_METRIC: round(delta, 6),
                "pe_credits": pe_score["credits"],
                "yoked_credits": c_score["credits"],
                "pe_nonzero_future_matches": pe_score["nonzero_future_matches"],
                "yoked_nonzero_future_matches": c_score["nonzero_future_matches"],
                "yoke_fallback_rate": round(_yoke_fallback_rate(yoked), 6),
                "capacity_matched": capacity_matched,
                "yoked_credit_counts": credit_matched,
            }
        )

    deltas = [float(row[PRIMARY_METRIC]) for row in seed_rows]
    median_delta = statistics.median(deltas)
    positive_count = sum(delta > 0 for delta in deltas)
    minimum_effect = float(prereg["minimum_effect_size"])
    minimum_positive = int(prereg["minimum_positive_seeds"])
    max_fallback = float(prereg["maximum_yoke_fallback_rate"])
    yoke_invalid = any(float(row["yoke_fallback_rate"]) > max_fallback for row in seed_rows)
    structural_invalid = any(
        not row["capacity_matched"] or not row["yoked_credit_counts"] for row in seed_rows
    )
    supported = (
        median_delta >= minimum_effect
        and positive_count >= minimum_positive
        and not yoke_invalid
        and not structural_invalid
    )
    return {
        "experiment": "endogenous_workspace_prediction_error_exact_artifact_v2",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "primary_metric": PRIMARY_METRIC,
        "preregistration": prereg,
        "tape_metadata": tape.get("metadata", {}),
        "results": {
            "status": "SUPPORTED_FOR_NEXT_OFFLINE_STAGE" if supported else "NOT_SUPPORTED_BY_V2_TRIAL",
            "median_primary_effect": round(float(median_delta), 6),
            "minimum_effect_required": minimum_effect,
            "positive_seed_count": positive_count,
            "minimum_positive_seeds_required": minimum_positive,
            "yoke_invalid": yoke_invalid,
            "structural_invalid": structural_invalid,
        },
        "seeds": seed_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked v2 prediction-error artifact trial.")
    parser.add_argument("--tape", required=True)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_locked_trial(args.tape, args.prereg)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["results"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
