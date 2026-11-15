#!/usr/bin/env python3
"""Offline meaningful-pair refractory selection for Emily + Olivia.

The mechanism reuses the repository's existing generic dialogue-attractor
representation: rooted content tokens and adjacent meaningful word-pairs.
Selected phrase-pairs receive short-lived inhibition, so a different memory
node that recycles the same phrasing can be penalized even when its node ID is
new. No LLM, embedding model, topic rule, or generated text is involved.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Mapping

from dialogue_attractor import content_tokens
from endogenous_workspace_artifact_tape import build_exact_tape
from endogenous_workspace_replay import normalize_tape
from endogenous_refractory_selection_v5 import future_rank_utility, mean_immediate_utility

SCHEMA_VERSION = 6
_MESSAGE_RE = re.compile(
    r"\bobserves\s+a\s+message\s+from\s+(?:Emily|Olivia)\s*:\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def load_prereg(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("preregistration must be an object")
    if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported semantic refractory preregistration schema")
    if payload.get("status") != "locked_before_semantic_refractory_execution":
        raise ValueError("semantic refractory preregistration is not locked")
    params = payload.get("parameters")
    gates = payload.get("co_primary_gates")
    if not isinstance(params, Mapping) or not isinstance(gates, Mapping):
        raise ValueError("parameters and co-primary gates are required")
    if payload.get("representation_source") != "dialogue_attractor.content_tokens plus adjacent meaningful rooted token pairs":
        raise ValueError("unexpected semantic representation source")
    for key in ("refractory_decay", "refractory_penalty", "future_discount"):
        value = float(params[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and non-negative")
    return dict(payload)


def _semantic_text(text: str) -> str:
    text = str(text or "").strip()
    match = _MESSAGE_RE.search(text)
    return match.group(1).strip() if match else text


def meaningful_pairs(text: str) -> frozenset[tuple[str, str]]:
    tokens = content_tokens(_semantic_text(text))
    return frozenset(
        (tokens[index], tokens[index + 1])
        for index in range(len(tokens) - 1)
        if tokens[index] != tokens[index + 1]
    )


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def run_selector(tape: dict, *, k: int, decay: float, penalty: float) -> dict:
    refractory: dict[tuple[str, str], float] = {}
    trace: list[dict] = []
    for tick in tape["ticks"]:
        next_refractory = {}
        for pair, value in refractory.items():
            decayed = float(value) * float(decay)
            if decayed >= 0.001:
                next_refractory[pair] = decayed
        refractory = next_refractory

        ranked = []
        for row in tick["rows"]:
            pairs = meaningful_pairs(row["candidate"].text)
            inhibition = max((float(refractory.get(pair, 0.0)) for pair in pairs), default=0.0)
            effective = float(row["retrieval_score"]) - float(penalty) * inhibition
            ranked.append(
                {
                    **row,
                    "meaningful_pairs": pairs,
                    "semantic_inhibition": inhibition,
                    "effective_score": effective,
                }
            )
        ranked.sort(
            key=lambda row: (
                -float(row["effective_score"]),
                -float(row["retrieval_score"]),
                row["candidate"].candidate_id,
            )
        )
        selected = ranked[: min(int(k), len(ranked))]
        selected_ids = [row["candidate"].candidate_id for row in selected]
        pair_union: set[tuple[str, str]] = set()
        for row in selected:
            for pair in row["meaningful_pairs"]:
                refractory[pair] = 1.0
                pair_union.add(pair)
        trace.append(
            {
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "selected_retrieval_scores": [float(row["retrieval_score"]) for row in selected],
                # Keep result evidence content-free. The actual phrase pairs are
                # used only in-memory during the offline calculation.
                "selected_meaningful_pair_count": len(pair_union),
                "_pair_union": pair_union,
            }
        )
    return {"trace": trace}


def mean_consecutive_pair_overlap(run: dict) -> float:
    values = []
    for previous, current in zip(run["trace"], run["trace"][1:]):
        values.append(_jaccard(set(previous["_pair_union"]), set(current["_pair_union"])))
    return sum(values) / len(values) if values else 0.0


def _strip_private_pairs(run: dict) -> dict:
    return {
        "trace": [
            {key: value for key, value in tick.items() if key != "_pair_union"}
            for tick in run["trace"]
        ]
    }


def evaluate_tape(tape: dict, prereg: Mapping) -> dict:
    params = prereg["parameters"]
    gates = prereg["co_primary_gates"]
    k = int(params["k"])
    decay = float(params["refractory_decay"])
    penalty = float(params["refractory_penalty"])
    horizon = int(params["future_horizon_ticks"])
    discount = float(params["future_discount"])

    baseline = run_selector(tape, k=k, decay=decay, penalty=0.0)
    semantic = run_selector(tape, k=k, decay=decay, penalty=penalty)
    sanity = run_selector(tape, k=k, decay=decay, penalty=0.0)

    baseline_overlap = mean_consecutive_pair_overlap(baseline)
    semantic_overlap = mean_consecutive_pair_overlap(semantic)
    overlap_reduction = baseline_overlap - semantic_overlap
    baseline_immediate = mean_immediate_utility(baseline)
    semantic_immediate = mean_immediate_utility(semantic)
    immediate_ratio = semantic_immediate / baseline_immediate if baseline_immediate else 0.0
    baseline_future = future_rank_utility(baseline, tape, horizon=horizon, discount=discount)
    semantic_future = future_rank_utility(semantic, tape, horizon=horizon, discount=discount)
    future_ratio = semantic_future / baseline_future if baseline_future else 0.0
    sanity_exact = all(
        a["selected_ids"] == b["selected_ids"]
        for a, b in zip(baseline["trace"], sanity["trace"])
    )

    passes = {
        "meaningful_pair_overlap_reduction": overlap_reduction >= float(gates["minimum_consecutive_meaningful_pair_overlap_reduction"]),
        "immediate_utility": immediate_ratio >= float(gates["minimum_immediate_retrieval_utility_ratio"]),
        "future_utility": future_ratio >= float(gates["minimum_future_rank_utility_ratio"]),
        "sanity_zero_penalty": sanity_exact,
    }
    return {
        "baseline_consecutive_meaningful_pair_overlap": round(baseline_overlap, 6),
        "semantic_refractory_consecutive_meaningful_pair_overlap": round(semantic_overlap, 6),
        "consecutive_meaningful_pair_overlap_reduction": round(overlap_reduction, 6),
        "baseline_immediate_retrieval_utility": round(baseline_immediate, 6),
        "semantic_refractory_immediate_retrieval_utility": round(semantic_immediate, 6),
        "immediate_retrieval_utility_ratio": round(immediate_ratio, 6),
        "baseline_future_rank_utility": round(baseline_future, 6),
        "semantic_refractory_future_rank_utility": round(semantic_future, 6),
        "future_rank_utility_ratio": round(future_ratio, 6),
        "sanity_zero_penalty_matches_retrieval": sanity_exact,
        "gate_pass": passes,
        "all_gates_pass": all(passes.values()),
        "baseline_trace": _strip_private_pairs(baseline)["trace"],
        "semantic_trace": _strip_private_pairs(semantic)["trace"],
    }


def run_experiment(prereg_path: str | Path, artifact_roots: Mapping[str, str | Path]) -> dict:
    prereg = load_prereg(prereg_path)
    blocks = []
    for evidence in prereg["frozen_evidence"]:
        label = str(evidence["label"])
        raw = build_exact_tape(
            artifact_roots[label],
            min_ticks=12,
            artifact_run_id=int(evidence["community_run_id"]),
            artifact_sha256=str(evidence["artifact_sha256"]),
        )
        expected_start, expected_end = [int(x) for x in evidence["expected_exact_range"]]
        if (int(raw["metadata"]["time_step_start"]), int(raw["metadata"]["time_step_end"])) != (expected_start, expected_end):
            raise ValueError(f"{label} exact range changed")
        blocks.append(
            {
                "label": label,
                "source_run_id": int(evidence["community_run_id"]),
                "source_artifact_id": int(evidence["artifact_id"]),
                "tape_metadata": raw["metadata"],
                "metrics": evaluate_tape(normalize_tape(raw), prereg),
            }
        )

    supported = all(block["metrics"]["all_gates_pass"] for block in blocks)
    return {
        "experiment": "endogenous_semantic_refractory_v6",
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "activated_live_workspace": False,
        "activated_shadow_mode": False,
        "preregistration": prereg,
        "blocks": blocks,
        "results": {
            "status": "SUPPORTED_FOR_PROSPECTIVE_REPLICATION" if supported else "NOT_SUPPORTED_BY_FROZEN_BLOCKS",
            "all_required_blocks_pass": supported,
            "shadow_mode_permitted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked semantic refractory test on frozen artifacts.")
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
    print(json.dumps({"blocks": [{"label": b["label"], "metrics": {k:v for k,v in b["metrics"].items() if not k.endswith('_trace')}} for b in result["blocks"]], "results": result["results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
