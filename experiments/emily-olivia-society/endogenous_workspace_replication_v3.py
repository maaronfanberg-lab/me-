#!/usr/bin/env python3
"""Independent artifact replication + destructive ablations for prediction error.

This is offline only. It discovers prior Emily + Olivia Community Run artifacts
using a preregistered selection rule, freezes a non-overlapping exact Stanford
retrieval tape from each artifact, then evaluates prediction-error selection and
predeclared ablations. It never calls an LLM, sends dialogue, writes Stanford
memory, or enables any live workspace mechanism.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Mapping

from endogenous_workspace_artifact_tape import build_exact_tape
from endogenous_workspace_replay import ARM_C, ReplayConfig, normalize_tape, run_arm
from endogenous_workspace_trial_v2 import discounted_future_rank_score

PREREG_SCHEMA_VERSION = 3
ARTIFACT_NAME = "emily-olivia-community-results"


def _request_json(url: str, token: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "emily-olivia-ew-replication-v3",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_artifact(repo: str, artifact_id: int, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/artifacts/{artifact_id}/zip"],
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip() or "artifact download failed")


def _load_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("preregistration must be a JSON object")
    if int(payload.get("schema_version", 0)) != PREREG_SCHEMA_VERSION:
        raise ValueError("unsupported v3 preregistration schema")
    if payload.get("status") != "locked_before_independent_replication_and_ablation":
        raise ValueError("v3 preregistration is not locked")
    selection = payload.get("artifact_selection")
    if not isinstance(selection, Mapping):
        raise ValueError("artifact_selection is required")
    gate = payload.get("replication_gate")
    ablation = payload.get("ablation_gate")
    if not isinstance(gate, Mapping) or not isinstance(ablation, Mapping):
        raise ValueError("replication_gate and ablation_gate are required")
    if int(selection.get("minimum_independent_artifacts", 0)) < 3:
        raise ValueError("v3 requires at least three independent artifacts")
    if float(gate.get("minimum_median_artifact_effect", 0.0)) <= 0:
        raise ValueError("replication minimum effect must be positive")
    if not 0 < float(gate.get("minimum_positive_artifact_fraction", 0.0)) <= 1:
        raise ValueError("positive artifact fraction must be in (0,1]")
    if float(ablation.get("minimum_effect_degradation", 0.0)) <= 0:
        raise ValueError("ablation degradation must be positive")
    return dict(payload)


def _ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1])


def _list_candidate_runs(repo: str, token: str, workflow_id: int, cutoff: int, maximum: int) -> list[dict]:
    encoded = urllib.parse.quote(str(workflow_id), safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}/runs?status=completed&per_page=100"
    payload = _request_json(url, token)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("workflow_runs"), list):
        raise RuntimeError("GitHub workflow run listing returned an invalid payload")
    runs = [
        dict(row)
        for row in payload["workflow_runs"]
        if isinstance(row, Mapping) and int(row.get("run_number", 10**9)) < cutoff
    ]
    runs.sort(key=lambda row: int(row.get("run_number", 0)), reverse=True)
    return runs[:maximum]


def _artifact_for_run(repo: str, token: str, run_id: int) -> dict | None:
    payload = _request_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts", token)
    if not isinstance(payload, Mapping):
        return None
    for artifact in payload.get("artifacts", []):
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("name") == ARTIFACT_NAME and artifact.get("expired") is not True:
            return dict(artifact)
    return None


def _artifact_digest_hex(artifact: Mapping) -> str:
    digest = str(artifact.get("digest") or "")
    return digest.split(":", 1)[1] if digest.startswith("sha256:") else digest


def select_independent_tapes(repo: str, token: str, prereg: Mapping) -> tuple[list[dict], list[dict]]:
    selection = prereg["artifact_selection"]
    workflow_id = int(selection["community_workflow_id"])
    cutoff = int(selection["maximum_run_number_exclusive"])
    desired = int(selection["desired_independent_artifacts"])
    maximum = int(selection["maximum_candidate_runs_to_scan"])
    min_ticks = int(selection["minimum_exact_ticks_per_artifact"])
    require_non_overlap = bool(selection.get("require_non_overlapping_time_ranges", True))

    candidates = _list_candidate_runs(repo, token, workflow_id, cutoff, maximum)
    accepted: list[dict] = []
    audit: list[dict] = []
    accepted_ranges: list[tuple[int, int]] = []

    with tempfile.TemporaryDirectory(prefix="ew-replication-v3-") as temp:
        root = Path(temp)
        for run in candidates:
            if len(accepted) >= desired:
                break
            run_id = int(run["id"])
            run_number = int(run["run_number"])
            audit_row = {"run_id": run_id, "run_number": run_number, "accepted": False}
            artifact = _artifact_for_run(repo, token, run_id)
            if artifact is None:
                audit_row["reason"] = "no_unexpired_community_artifact"
                audit.append(audit_row)
                continue
            artifact_id = int(artifact["id"])
            digest = _artifact_digest_hex(artifact)
            zip_path = root / f"run-{run_number}.zip"
            extract_root = root / f"run-{run_number}"
            try:
                _download_artifact(repo, artifact_id, zip_path)
                extract_root.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(extract_root)
                tape_raw = build_exact_tape(
                    extract_root,
                    min_ticks=min_ticks,
                    artifact_run_id=run_id,
                    artifact_sha256=digest,
                )
            except Exception as exc:
                audit_row["reason"] = f"exact_tape_rejected:{type(exc).__name__}:{exc}"
                audit.append(audit_row)
                continue

            start = int(tape_raw["metadata"]["time_step_start"])
            end = int(tape_raw["metadata"]["time_step_end"])
            time_range = (start, end)
            if require_non_overlap and any(_ranges_overlap(time_range, prior) for prior in accepted_ranges):
                audit_row["reason"] = "overlaps_previously_selected_exact_range"
                audit_row["time_step_start"] = start
                audit_row["time_step_end"] = end
                audit.append(audit_row)
                continue

            normalized = normalize_tape(tape_raw)
            accepted_ranges.append(time_range)
            manifest = {
                "run_id": run_id,
                "run_number": run_number,
                "artifact_id": artifact_id,
                "artifact_sha256": digest,
                "time_step_start": start,
                "time_step_end": end,
                "tick_count": int(tape_raw["metadata"]["tick_count"]),
            }
            audit_row.update({"accepted": True, **manifest})
            audit.append(audit_row)
            accepted.append({"manifest": manifest, "tape": normalized})

    return accepted, audit


def _recover_budget(budget: float, config: ReplayConfig) -> float:
    return min(float(config.budget_max), float(budget) + float(config.budget_recovery))


def _credit_capacity(budget: float, config: ReplayConfig, selected_count: int) -> int:
    affordable = int((float(budget) + 1e-12) // float(config.consolidation_cost))
    return max(0, min(int(selected_count), affordable))


def _selector_run(
    tape: dict,
    config: ReplayConfig,
    *,
    alpha: float,
    absence_decay: float,
    mode: str,
    shuffle_seed: int = 0,
) -> dict:
    expected: dict[str, float] = {}
    budget = float(config.budget_max)
    trace: list[dict] = []
    schedule: list[dict] = []

    for tick_index, tick in enumerate(tape["ticks"]):
        budget = _recover_budget(budget, config)
        budget_before = budget
        rows = list(tick["rows"])
        present_ids = {row["candidate"].candidate_id for row in rows}
        for candidate_id in list(expected):
            if candidate_id not in present_ids:
                expected[candidate_id] *= absence_decay
                if expected[candidate_id] < 0.001:
                    expected.pop(candidate_id, None)

        scored: list[dict] = []
        errors: list[float] = []
        for row in rows:
            candidate_id = row["candidate"].candidate_id
            current = float(row["retrieval_score"])
            predicted = float(expected.get(candidate_id, 0.0))
            error = max(0.0, current - predicted)
            errors.append(error)
            scored.append({**row, "selector_score": error})

        if mode == "shuffle_surprise_identity":
            shuffled = list(errors)
            random.Random(shuffle_seed + config.seed * 1009 + tick_index).shuffle(shuffled)
            for row, value in zip(scored, shuffled):
                row["selector_score"] = value
        elif mode == "retrieval_only":
            for row in scored:
                row["selector_score"] = float(row["retrieval_score"])
        elif mode != "prediction_error":
            raise ValueError(f"unknown selector mode: {mode}")

        scored.sort(
            key=lambda row: (
                -float(row["selector_score"]),
                -float(row["retrieval_score"]),
                row["candidate"].candidate_id,
            )
        )
        k = min(int(config.k), len(scored))
        selected = scored[:k]
        credit_count = _credit_capacity(budget, config, len(selected))
        credited_ids = [row["candidate"].candidate_id for row in selected[:credit_count]]
        budget = max(0.0, budget - credit_count * float(config.consolidation_cost))

        for row in rows:
            candidate_id = row["candidate"].candidate_id
            current = float(row["retrieval_score"])
            prior = float(expected.get(candidate_id, 0.0))
            expected[candidate_id] = (1.0 - alpha) * prior + alpha * current

        selected_ids = [row["candidate"].candidate_id for row in selected]
        trace.append(
            {
                "tick_index": tick_index,
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "consolidated_ids": credited_ids,
                "credit_count": credit_count,
                "budget_before": round(budget_before, 6),
                "budget_after": round(budget, 6),
            }
        )
        schedule.append(
            {
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "selection_count": len(selected_ids),
                "credit_count": credit_count,
                "budget_before": round(budget_before, 6),
                "budget_after": round(budget, 6),
            }
        )
    return {"trace": trace, "yoke_schedule": schedule}


def _scramble_tape(tape: dict, seed: int) -> dict:
    order = list(range(len(tape["ticks"])))
    random.Random(seed).shuffle(order)
    return {
        "schema_version": tape.get("schema_version", 1),
        "metadata": {**copy.deepcopy(tape.get("metadata", {})), "temporal_order_scrambled": True},
        "ticks": [tape["ticks"][index] for index in order],
    }


def _yoke_fallback_rate(run_c: dict) -> float:
    selected = sum(len(tick.get("selected_ids", [])) for tick in run_c["trace"])
    fallback = sum(int(tick.get("yoke_fallback_count", 0) or 0) for tick in run_c["trace"])
    return fallback / selected if selected else 1.0


def _evaluate_variant(tape: dict, prereg: Mapping, seed: int, variant: str) -> dict:
    config = ReplayConfig(k=int(prereg["k"]), seed=seed)
    alpha = float(prereg["prediction_alpha"])
    absence = float(prereg["prediction_absence_decay"])
    mode = "prediction_error"
    working_tape = tape
    ablation = prereg["ablation_gate"]

    if variant == "no_prediction_learning":
        alpha = 0.0
    elif variant == "shuffle_surprise_identity":
        mode = "shuffle_surprise_identity"
    elif variant == "scramble_temporal_order":
        working_tape = _scramble_tape(tape, int(ablation["temporal_shuffle_seed"]))
    elif variant == "absence_decay_zero":
        absence = 0.0
    elif variant == "absence_decay_one":
        absence = 1.0
    elif variant == "retrieval_only":
        mode = "retrieval_only"
    elif variant != "base":
        raise ValueError(f"unknown variant: {variant}")

    selector = _selector_run(
        working_tape,
        config,
        alpha=alpha,
        absence_decay=absence,
        mode=mode,
        shuffle_seed=int(ablation["shuffle_surprise_seed"]),
    )
    yoked = run_arm(working_tape, ARM_C, config, yoke_schedule=selector["yoke_schedule"])
    horizon = int(prereg["future_horizon_ticks"])
    discount = float(prereg["future_discount"])
    score = discounted_future_rank_score(selector, working_tape, horizon, discount)
    control = discounted_future_rank_score(yoked, working_tape, horizon, discount)
    if score["mean_discounted_future_rank_score"] is None or control["mean_discounted_future_rank_score"] is None:
        raise ValueError("variant produced no eligible consolidation credits")
    delta = float(score["mean_discounted_future_rank_score"]) - float(control["mean_discounted_future_rank_score"])
    capacity_matched = all(
        len(a.get("selected_ids", [])) == len(b.get("selected_ids", []))
        for a, b in zip(selector["trace"], yoked["trace"])
    )
    credits_matched = all(
        int(a.get("credit_count", 0)) == int(b.get("credit_count", 0))
        for a, b in zip(selector["trace"], yoked["trace"])
    )
    return {
        "delta": delta,
        "selector_score": float(score["mean_discounted_future_rank_score"]),
        "yoked_score": float(control["mean_discounted_future_rank_score"]),
        "yoke_fallback_rate": _yoke_fallback_rate(yoked),
        "capacity_matched": capacity_matched,
        "credits_matched": credits_matched,
    }


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else math.nan


def run_replication(repo: str, token: str, prereg_path: str | Path) -> dict:
    prereg = _load_prereg(prereg_path)
    selected, audit = select_independent_tapes(repo, token, prereg)
    manifest = [entry["manifest"] for entry in selected]
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    minimum_artifacts = int(prereg["artifact_selection"]["minimum_independent_artifacts"])
    if len(selected) < minimum_artifacts:
        return {
            "experiment": "endogenous_workspace_prediction_error_replication_ablation_v3",
            "produced_dialogue": False,
            "wrote_live_memory": False,
            "activated_live_workspace": False,
            "selection_manifest": manifest,
            "selection_manifest_sha256": manifest_sha,
            "selection_audit": audit,
            "results": {
                "status": "INSUFFICIENT_INDEPENDENT_ARTIFACTS",
                "selected_artifact_count": len(selected),
                "minimum_required": minimum_artifacts,
                "replication_supported": False,
                "mechanism_specificity_supported": False,
                "shadow_mode_permitted": False,
            },
        }

    variants = [
        "base",
        "no_prediction_learning",
        "shuffle_surprise_identity",
        "scramble_temporal_order",
        "absence_decay_zero",
        "absence_decay_one",
        "retrieval_only",
    ]
    artifact_results: list[dict] = []
    max_fallback = float(prereg["maximum_yoke_fallback_rate"])
    for entry in selected:
        tape = entry["tape"]
        variant_rows: dict[str, dict] = {}
        for variant in variants:
            seed_rows = []
            for raw_seed in prereg["seeds"]:
                outcome = _evaluate_variant(tape, prereg, int(raw_seed), variant)
                seed_rows.append({"seed": int(raw_seed), **outcome})
            variant_rows[variant] = {
                "median_delta": _median([float(row["delta"]) for row in seed_rows]),
                "median_selector_score": _median([float(row["selector_score"]) for row in seed_rows]),
                "median_yoked_score": _median([float(row["yoked_score"]) for row in seed_rows]),
                "max_yoke_fallback_rate": max(float(row["yoke_fallback_rate"]) for row in seed_rows),
                "structural_valid": all(
                    row["capacity_matched"] and row["credits_matched"] and float(row["yoke_fallback_rate"]) <= max_fallback
                    for row in seed_rows
                ),
                "seeds": seed_rows,
            }
        artifact_results.append({"manifest": entry["manifest"], "variants": variant_rows})

    base_effects = [float(row["variants"]["base"]["median_delta"]) for row in artifact_results]
    base_median = _median(base_effects)
    positive_fraction = sum(value > 0 for value in base_effects) / len(base_effects)
    structural_valid = all(
        variant["structural_valid"]
        for artifact in artifact_results
        for variant in artifact["variants"].values()
    )
    replication_gate = prereg["replication_gate"]
    replication_supported = (
        base_median >= float(replication_gate["minimum_median_artifact_effect"])
        and positive_fraction >= float(replication_gate["minimum_positive_artifact_fraction"])
        and structural_valid
    )

    aggregate_variant_medians = {
        variant: _median([float(row["variants"][variant]["median_delta"]) for row in artifact_results])
        for variant in variants
    }
    degradation = {
        variant: base_median - aggregate_variant_medians[variant]
        for variant in variants
        if variant != "base"
    }
    ablation_gate = prereg["ablation_gate"]
    threshold = float(ablation_gate["minimum_effect_degradation"])
    core = [str(name) for name in ablation_gate["core_ablations"]]
    core_pass = {name: degradation[name] >= threshold for name in core}
    core_pass_count = sum(core_pass.values())
    mechanism_supported = (
        core_pass_count >= int(ablation_gate["minimum_core_ablations_showing_degradation"])
        and structural_valid
    )
    shadow_permitted = replication_supported and mechanism_supported

    return {
        "experiment": "endogenous_workspace_prediction_error_replication_ablation_v3",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "preregistration": prereg,
        "selection_manifest": manifest,
        "selection_manifest_sha256": manifest_sha,
        "selection_audit": audit,
        "artifact_results": artifact_results,
        "aggregate": {
            "base_median_artifact_effect": round(base_median, 6),
            "positive_artifact_fraction": round(positive_fraction, 6),
            "variant_median_artifact_effects": {key: round(value, 6) for key, value in aggregate_variant_medians.items()},
            "ablation_degradation_from_base": {key: round(value, 6) for key, value in degradation.items()},
            "core_ablation_pass": core_pass,
            "core_ablation_pass_count": core_pass_count,
            "structural_valid": structural_valid,
        },
        "results": {
            "status": "SUPPORTED_FOR_SHADOW_MODE" if shadow_permitted else "DO_NOT_ENTER_SHADOW_MODE",
            "selected_artifact_count": len(selected),
            "replication_supported": replication_supported,
            "mechanism_specificity_supported": mechanism_supported,
            "shadow_mode_permitted": shadow_permitted,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked independent EW prediction-error replication and ablations.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-"))
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token:
        raise SystemExit("GITHUB_TOKEN or GH_TOKEN is required to retrieve pinned Community artifacts")
    result = run_replication(args.repository, token, args.prereg)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": result.get("aggregate"), "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
