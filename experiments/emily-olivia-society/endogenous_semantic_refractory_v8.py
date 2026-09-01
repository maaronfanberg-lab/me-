#!/usr/bin/env python3
"""Prospective, native-evidence-only semantic refractory evaluator.

This module cannot start a Community run, send dialogue, write Stanford memory,
or enable the experimental workspace. It evaluates one already-completed
Community artifact collected strictly after the v8 preregistration boundary.
Legacy checkpoint reconstruction and hybrid evidence fail closed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Mapping

from endogenous_workspace_artifact_tape import build_exact_tape
from endogenous_workspace_replay import normalize_tape
from endogenous_semantic_refractory_v6 import (
    future_rank_utility,
    mean_consecutive_pair_overlap,
    mean_immediate_utility,
    run_selector,
)

PREREG_COMMIT = "ea69132cee9ce89bba3137c7d81ba81af0f3298b"
PREREG_COMMITTED_AT = "2026-09-01T19:08:36Z"
EXPECTED_EXPERIMENT = "endogenous_semantic_refractory_v8_prospective"


def _utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def load_locked_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("experiment") != EXPECTED_EXPERIMENT:
        raise ValueError("unexpected v8 preregistration")
    candidate = payload.get("candidate")
    evidence = payload.get("evidence")
    metrics = payload.get("metrics")
    decision = payload.get("decision")
    if not all(isinstance(item, Mapping) for item in (candidate, evidence, metrics, decision)):
        raise ValueError("incomplete v8 preregistration")

    # These values were frozen by PREREG_COMMIT. Refuse silent parameter drift.
    expected_candidate = {"refractory_decay": 0.5, "refractory_penalty": 1.0, "k": 4}
    if {key: candidate.get(key) for key in expected_candidate} != expected_candidate:
        raise ValueError("v8 candidate parameters differ from the frozen preregistration")
    if evidence.get("required_source") != "native_retrieval_time_metadata":
        raise ValueError("v8 requires native retrieval-time metadata")
    if evidence.get("legacy_checkpoint_reconstruction_allowed") is not False:
        raise ValueError("legacy checkpoint reconstruction must remain disabled")
    if int(evidence.get("minimum_exact_turns", 0)) != 12:
        raise ValueError("v8 minimum exact turn count changed")
    if float(metrics.get("relative_pair_overlap_reduction_minimum", -1)) != 0.20:
        raise ValueError("v8 semantic reduction gate changed")
    if float(metrics.get("immediate_retrieval_utility_ratio_minimum", -1)) != 0.95:
        raise ValueError("v8 immediate utility gate changed")
    if float(metrics.get("future_rank_utility_ratio_minimum", -1)) != 0.95:
        raise ValueError("v8 future utility gate changed")
    if decision.get("prospective_pass_can_permit_live_behavioral_influence") is not False:
        raise ValueError("v8 may not permit live behavioral influence")
    return dict(payload)


def build_native_only_tape(
    artifact_root: str | Path,
    *,
    run_id: int,
    artifact_sha256: str,
    artifact_created_at: str,
    min_ticks: int,
) -> tuple[dict, dict]:
    if _utc(artifact_created_at) <= _utc(PREREG_COMMITTED_AT):
        raise ValueError("artifact does not postdate the v8 preregistration boundary")
    raw = build_exact_tape(
        artifact_root,
        min_ticks=min_ticks,
        artifact_run_id=int(run_id),
        artifact_sha256=str(artifact_sha256),
    )
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
    if metadata.get("chosen_metadata_mode") != "retrieval_time_evidence":
        raise ValueError("prospective v8 refuses checkpoint-join or hybrid evidence")
    ticks = raw.get("ticks")
    if not isinstance(ticks, list) or len(ticks) < min_ticks:
        raise ValueError("insufficient native prospective ticks")
    if any(tick.get("metadata_source") != "retrieval_time_evidence" for tick in ticks):
        raise ValueError("every selected v8 tick must use retrieval-time evidence")

    session_ids = {str(tick.get("session_id") or "").strip() for tick in ticks}
    if "" in session_ids or len(session_ids) != 1:
        raise ValueError("v8 prospective evidence must come from exactly one named session epoch")
    steps = [int(tick["time_step"]) for tick in ticks]
    if any(current != previous + 1 for previous, current in zip(steps, steps[1:])):
        raise ValueError("v8 prospective evidence must be one contiguous time-step block")

    return normalize_tape(raw), {
        **dict(metadata),
        "session_id": next(iter(session_ids)),
        "artifact_created_at": artifact_created_at,
        "preregistration_commit": PREREG_COMMIT,
        "preregistration_committed_at": PREREG_COMMITTED_AT,
    }


def _finite_positive(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return number


def evaluate_native_tape(tape: dict, prereg: Mapping) -> dict:
    candidate = prereg["candidate"]
    metrics = prereg["metrics"]
    k = int(candidate["k"])
    decay = float(candidate["refractory_decay"])
    penalty = float(candidate["refractory_penalty"])
    horizon = int(metrics["future_horizon_ticks"])
    discount = float(metrics["future_discount"])

    baseline = run_selector(tape, k=k, decay=decay, penalty=0.0)
    semantic = run_selector(tape, k=k, decay=decay, penalty=penalty)
    sanity = run_selector(tape, k=k, decay=decay, penalty=0.0)

    baseline_overlap = _finite_positive(mean_consecutive_pair_overlap(baseline), "baseline semantic overlap")
    semantic_overlap = float(mean_consecutive_pair_overlap(semantic))
    if not math.isfinite(semantic_overlap) or semantic_overlap < 0:
        raise ValueError("semantic overlap must be finite and non-negative")
    relative_reduction = (baseline_overlap - semantic_overlap) / baseline_overlap

    baseline_immediate = _finite_positive(mean_immediate_utility(baseline), "baseline immediate utility")
    semantic_immediate = float(mean_immediate_utility(semantic))
    immediate_ratio = semantic_immediate / baseline_immediate

    baseline_future = _finite_positive(
        future_rank_utility(baseline, tape, horizon=horizon, discount=discount),
        "baseline future utility",
    )
    semantic_future = float(future_rank_utility(semantic, tape, horizon=horizon, discount=discount))
    future_ratio = semantic_future / baseline_future

    values = (relative_reduction, semantic_immediate, immediate_ratio, semantic_future, future_ratio)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("v8 metric computation produced a non-finite value")

    sanity_exact = [row["selected_ids"] for row in baseline["trace"]] == [
        row["selected_ids"] for row in sanity["trace"]
    ]
    gates = {
        "relative_pair_overlap_reduction": relative_reduction >= float(metrics["relative_pair_overlap_reduction_minimum"]),
        "immediate_utility": immediate_ratio >= float(metrics["immediate_retrieval_utility_ratio_minimum"]),
        "future_utility": future_ratio >= float(metrics["future_rank_utility_ratio_minimum"]),
        "zero_penalty_sanity": sanity_exact,
    }
    return {
        "baseline_consecutive_meaningful_pair_overlap": round(baseline_overlap, 6),
        "semantic_refractory_consecutive_meaningful_pair_overlap": round(semantic_overlap, 6),
        "relative_pair_overlap_reduction": round(relative_reduction, 6),
        "immediate_retrieval_utility_ratio": round(immediate_ratio, 6),
        "future_rank_utility_ratio": round(future_ratio, 6),
        "gate_pass": gates,
        "all_gates_pass": all(gates.values()),
    }


def run_prospective(
    prereg_path: str | Path,
    artifact_root: str | Path,
    *,
    run_id: int,
    artifact_id: int,
    artifact_sha256: str,
    artifact_created_at: str,
    artifact_head_sha: str,
) -> dict:
    prereg = load_locked_prereg(prereg_path)
    min_ticks = int(prereg["evidence"]["minimum_exact_turns"])
    tape, provenance = build_native_only_tape(
        artifact_root,
        run_id=run_id,
        artifact_sha256=artifact_sha256,
        artifact_created_at=artifact_created_at,
        min_ticks=min_ticks,
    )
    measured = evaluate_native_tape(tape, prereg)
    observational_shadow = bool(measured["all_gates_pass"])
    return {
        "experiment": EXPECTED_EXPERIMENT,
        "evidence_role": "prospective_confirmatory_single_block",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "activated_shadow_mode_during_test": False,
        "started_community_run": False,
        "altered_the_room": False,
        "source": {
            "community_run_id": int(run_id),
            "artifact_id": int(artifact_id),
            "artifact_sha256": str(artifact_sha256),
            "artifact_created_at": artifact_created_at,
            "artifact_head_sha": str(artifact_head_sha),
            "tape": provenance,
        },
        "candidate": dict(prereg["candidate"]),
        "metrics": measured,
        "results": {
            "prospective_gate_passed": observational_shadow,
            "observational_shadow_mode_permitted": observational_shadow,
            "live_behavioral_influence_permitted": False,
            "status": "PROSPECTIVE_PASS" if observational_shadow else "PROSPECTIVE_FAIL",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one fresh native-evidence Community artifact under v8.")
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--artifact-id", required=True, type=int)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--artifact-created-at", required=True)
    parser.add_argument("--artifact-head-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run_prospective(
        args.prereg,
        args.artifact_root,
        run_id=args.run_id,
        artifact_id=args.artifact_id,
        artifact_sha256=args.artifact_sha256,
        artifact_created_at=args.artifact_created_at,
        artifact_head_sha=args.artifact_head_sha,
    )
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"source": result["source"], "metrics": result["metrics"], "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
