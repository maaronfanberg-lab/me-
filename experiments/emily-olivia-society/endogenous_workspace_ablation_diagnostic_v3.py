#!/usr/bin/env python3
"""Diagnostic-only v3 ablations when independent replication is incomplete.

Uses the exact locked v3 selection and ablation definitions, but never upgrades
an underpowered sample into replication support. Its only purpose is to learn
whether the one available independent artifact already falsifies the proposed
prediction-error mechanism while we improve prospective evidence capture.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from endogenous_workspace_replication_v3 import (
    _evaluate_variant,
    _load_prereg,
    _median,
    select_independent_tapes,
)

VARIANTS = [
    "base",
    "no_prediction_learning",
    "shuffle_surprise_identity",
    "scramble_temporal_order",
    "absence_decay_zero",
    "absence_decay_one",
    "retrieval_only",
]


def run_diagnostic(repository: str, token: str, prereg_path: str | Path) -> dict:
    prereg = _load_prereg(prereg_path)
    selected, audit = select_independent_tapes(repository, token, prereg)
    if not selected:
        return {
            "experiment": "prediction_error_ablation_diagnostic_v3",
            "produced_dialogue": False,
            "wrote_live_memory": False,
            "activated_live_workspace": False,
            "results": {
                "status": "NO_INDEPENDENT_ARTIFACT_AVAILABLE",
                "shadow_mode_permitted": False,
            },
            "selection_audit": audit,
        }

    artifact_results = []
    for entry in selected:
        variants = {}
        for variant in VARIANTS:
            rows = [
                {"seed": int(seed), **_evaluate_variant(entry["tape"], prereg, int(seed), variant)}
                for seed in prereg["seeds"]
            ]
            variants[variant] = {
                "median_delta": _median([float(row["delta"]) for row in rows]),
                "seeds": rows,
            }
        artifact_results.append({"manifest": entry["manifest"], "variants": variants})

    base = _median([float(row["variants"]["base"]["median_delta"]) for row in artifact_results])
    variant_medians = {
        variant: _median([float(row["variants"][variant]["median_delta"]) for row in artifact_results])
        for variant in VARIANTS
    }
    degradation = {
        variant: base - value for variant, value in variant_medians.items() if variant != "base"
    }
    gate = prereg["ablation_gate"]
    threshold = float(gate["minimum_effect_degradation"])
    core_pass = {
        name: degradation[str(name)] >= threshold for name in gate["core_ablations"]
    }
    core_pass_count = sum(core_pass.values())
    diagnostic_specificity = core_pass_count >= int(gate["minimum_core_ablations_showing_degradation"])

    return {
        "experiment": "prediction_error_ablation_diagnostic_v3",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "selection_manifest": [entry["manifest"] for entry in selected],
        "selection_audit": audit,
        "artifact_results": artifact_results,
        "aggregate": {
            "base_median_effect": round(base, 6),
            "variant_median_effects": {key: round(value, 6) for key, value in variant_medians.items()},
            "degradation_from_base": {key: round(value, 6) for key, value in degradation.items()},
            "core_ablation_pass": core_pass,
            "core_ablation_pass_count": core_pass_count,
            "mechanism_specificity_diagnostic": diagnostic_specificity,
        },
        "results": {
            "status": "ABLATION_DIAGNOSTIC_ONLY_REPLICATION_INCOMPLETE",
            "selected_artifact_count": len(selected),
            "minimum_replication_artifacts_required": int(prereg["artifact_selection"]["minimum_independent_artifacts"]),
            "mechanism_specificity_diagnostic": diagnostic_specificity,
            "shadow_mode_permitted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run diagnostic v3 ablations without relaxing replication gates.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-"))
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token:
        raise SystemExit("GITHUB_TOKEN or GH_TOKEN is required")
    result = run_diagnostic(args.repository, token, args.prereg)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": result.get("aggregate"), "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
