#!/usr/bin/env python3
"""Deterministic record/replay harness for Endogenous Workspace experiments.

This module exists specifically to keep the experimental workspace OUT of the
live Emily + Olivia conversation until its causal claims are falsifiable.

It implements Claude's adversarial-review requirements as an offline harness:

* frozen candidate tapes;
* capacity-matched A/B/C arms with exactly K read slots per tick;
* B: workspace-ranked scarcity consolidation;
* C: yoked shuffle using B's exact selection/consolidation schedule while
  changing which content wins, matched as closely as possible on importance,
  recency, and retrieval score;
* full numeric state/provenance traces with no representation text;
* deterministic seeded replay;
* a preregistration gate for non-pilot runs.

The harness never sends dialogue, never calls an LLM, never writes Stanford
memory, and never touches The Room. It is an experimental instrument, not a
consciousness claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from endogenous_workspace import Candidate, score_candidate

TAPE_SCHEMA_VERSION = 1
HARNESS_VERSION = 1
ARM_A = "A_capacity_off"
ARM_B = "B_scarcity_workspace"
ARM_C = "C_yoked_shuffle"
PRIMARY_METRIC = "final_bc_survivor_jaccard_distance"


@dataclass(frozen=True)
class ReplayConfig:
    k: int = 4
    seed: int = 0
    slow_decay: float = 0.94
    consolidation_boost: float = 0.22
    strong_memory_threshold: float = 0.35
    budget_max: float = 1.0
    budget_recovery: float = 0.20
    consolidation_cost: float = 0.25
    refractory_decay: float = 0.72
    refractory_penalty: float = 0.18

    def validate(self) -> None:
        if not 1 <= self.k <= 12:
            raise ValueError("k must be between 1 and 12")
        for name in (
            "slow_decay",
            "consolidation_boost",
            "strong_memory_threshold",
            "budget_max",
            "budget_recovery",
            "consolidation_cost",
            "refractory_decay",
            "refractory_penalty",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.budget_max <= 0 or self.consolidation_cost <= 0:
            raise ValueError("budget_max and consolidation_cost must be positive")


def _clamp01(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _stable_id(source: str, text: str) -> str:
    payload = f"{source}\n{text.strip()}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:20]


def _candidate_from_dict(raw: Mapping) -> Candidate:
    text = str(raw.get("text") or "").strip()
    if not text:
        raise ValueError("candidate text is required in the frozen input tape")
    source = str(raw.get("source") or "memory:event").strip() or "memory:event"
    candidate_id = str(raw.get("id") or raw.get("candidate_id") or "").strip()
    if not candidate_id:
        candidate_id = _stable_id(source, text)
    return Candidate(
        candidate_id=candidate_id,
        source=source,
        text=text,
        importance=_clamp01(raw.get("importance", 0.0)),
        recency=_clamp01(raw.get("recency", 0.0)),
    )


def _retrieval_score(raw: Mapping, candidate: Candidate) -> float:
    if "retrieval_score" in raw:
        return _clamp01(raw.get("retrieval_score"))
    # Deterministic fallback for synthetic/pilot tapes only. Real recordings
    # should store the Stanford retrieval score explicitly.
    return _clamp01(0.60 * candidate.importance + 0.40 * candidate.recency)


def normalize_tape(tape: Mapping) -> dict:
    if not isinstance(tape, Mapping):
        raise ValueError("tape must be a JSON object")
    schema = int(tape.get("schema_version", TAPE_SCHEMA_VERSION))
    if schema != TAPE_SCHEMA_VERSION:
        raise ValueError(f"unsupported tape schema_version: {schema}")
    raw_ticks = tape.get("ticks")
    if not isinstance(raw_ticks, list) or not raw_ticks:
        raise ValueError("tape.ticks must be a non-empty list")

    ticks: list[dict] = []
    for index, raw_tick in enumerate(raw_ticks):
        if not isinstance(raw_tick, Mapping):
            raise ValueError(f"tick {index} must be an object")
        time_step = int(raw_tick.get("time_step", index + 1))
        raw_candidates = raw_tick.get("candidates")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ValueError(f"tick {index} candidates must be non-empty")
        rows = []
        seen_ids: set[str] = set()
        for raw in raw_candidates:
            if not isinstance(raw, Mapping):
                continue
            candidate = _candidate_from_dict(raw)
            if candidate.candidate_id in seen_ids:
                continue
            seen_ids.add(candidate.candidate_id)
            rows.append(
                {
                    "candidate": candidate,
                    "retrieval_score": _retrieval_score(raw, candidate),
                }
            )
        if not rows:
            raise ValueError(f"tick {index} has no valid candidates")
        ticks.append({"time_step": time_step, "rows": rows})

    metadata = copy.deepcopy(tape.get("metadata") if isinstance(tape.get("metadata"), Mapping) else {})
    return {"schema_version": schema, "metadata": metadata, "ticks": ticks}


def load_tape(path: str | Path) -> dict:
    return normalize_tape(json.loads(Path(path).read_text()))


def _empty_state(config: ReplayConfig) -> dict:
    return {
        "version": HARNESS_VERSION,
        "pulse": 0,
        "budget": float(config.budget_max),
        "slow": {},
        "refractory": {},
    }


def _decay_state(state: dict, config: ReplayConfig) -> None:
    state["budget"] = min(
        config.budget_max,
        float(state.get("budget", 0.0)) + config.budget_recovery,
    )
    slow = {}
    for candidate_id, value in dict(state.get("slow", {})).items():
        new_value = _clamp01(float(value) * config.slow_decay)
        if new_value >= 0.005:
            slow[candidate_id] = new_value
    state["slow"] = slow

    refractory = {}
    for candidate_id, value in dict(state.get("refractory", {})).items():
        new_value = _clamp01(float(value) * config.refractory_decay)
        if new_value >= 0.005:
            refractory[candidate_id] = new_value
    state["refractory"] = refractory


def _rank_a(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (-float(row["retrieval_score"]), row["candidate"].candidate_id),
    )


def _rank_b(rows: list[dict], state: dict, config: ReplayConfig) -> list[dict]:
    ranked = []
    for row in rows:
        candidate = row["candidate"]
        slow = _clamp01(state["slow"].get(candidate.candidate_id, 0.0))
        refractory = _clamp01(state["refractory"].get(candidate.candidate_id, 0.0))
        base = score_candidate(candidate, slow)
        effective = _clamp01(base - config.refractory_penalty * refractory)
        ranked.append(
            {
                **row,
                "workspace_score": base,
                "effective_score": effective,
                "slow_before": slow,
                "refractory_before": refractory,
            }
        )
    return sorted(
        ranked,
        key=lambda row: (-float(row["effective_score"]), row["candidate"].candidate_id),
    )


def _credit_capacity(budget: float, config: ReplayConfig, selected_count: int) -> int:
    affordable = int((float(budget) + 1e-12) // config.consolidation_cost)
    return max(0, min(selected_count, affordable))


def _apply_consolidation(
    state: dict,
    selected: list[dict],
    credit_count: int,
    config: ReplayConfig,
) -> list[str]:
    credited: list[str] = []
    for row in selected[:credit_count]:
        candidate_id = row["candidate"].candidate_id
        before = _clamp01(state["slow"].get(candidate_id, 0.0))
        state["slow"][candidate_id] = _clamp01(before + config.consolidation_boost)
        state["refractory"][candidate_id] = 1.0
        credited.append(candidate_id)
        state["budget"] = max(0.0, float(state["budget"]) - config.consolidation_cost)
    return credited


def _distribution_distance(a: dict, b: dict) -> float:
    ca = a["candidate"]
    cb = b["candidate"]
    return (
        abs(float(ca.importance) - float(cb.importance))
        + abs(float(ca.recency) - float(cb.recency))
        + abs(float(a["retrieval_score"]) - float(b["retrieval_score"]))
    )


def _yoked_selection(
    rows: list[dict],
    b_selected_ids: list[str],
    k: int,
    rng: random.Random,
) -> tuple[list[dict], int]:
    by_id = {row["candidate"].candidate_id: row for row in rows}
    targets = [by_id[candidate_id] for candidate_id in b_selected_ids if candidate_id in by_id]
    remaining = list(rows)
    chosen: list[dict] = []
    fallback_count = 0

    for target in targets[:k]:
        alternatives = [
            row
            for row in remaining
            if row["candidate"].candidate_id not in b_selected_ids
        ]
        if not alternatives:
            alternatives = list(remaining)
            fallback_count += 1
        if not alternatives:
            break
        decorated = [
            (_distribution_distance(target, row), rng.random(), row["candidate"].candidate_id, row)
            for row in alternatives
        ]
        decorated.sort(key=lambda item: (item[0], item[1], item[2]))
        selected = decorated[0][3]
        chosen.append(selected)
        remaining = [
            row for row in remaining
            if row["candidate"].candidate_id != selected["candidate"].candidate_id
        ]

    if len(chosen) < k:
        extras = sorted(
            remaining,
            key=lambda row: (-float(row["retrieval_score"]), row["candidate"].candidate_id),
        )
        chosen.extend(extras[: max(0, k - len(chosen))])

    return chosen[:k], fallback_count


def _row_trace(row: dict, rank: int) -> dict:
    candidate = row["candidate"]
    out = {
        "id": candidate.candidate_id,
        "source": candidate.source,
        "rank": rank,
        "importance": round(float(candidate.importance), 6),
        "recency": round(float(candidate.recency), 6),
        "retrieval_score": round(float(row["retrieval_score"]), 6),
    }
    if "workspace_score" in row:
        out["workspace_score"] = round(float(row["workspace_score"]), 6)
        out["effective_score"] = round(float(row["effective_score"]), 6)
        out["slow_before"] = round(float(row["slow_before"]), 6)
        out["refractory_before"] = round(float(row["refractory_before"]), 6)
    return out


def _state_snapshot(state: dict) -> dict:
    return {
        "pulse": int(state["pulse"]),
        "budget": round(float(state["budget"]), 6),
        "slow": {key: round(float(value), 6) for key, value in sorted(state["slow"].items())},
        "refractory": {
            key: round(float(value), 6)
            for key, value in sorted(state["refractory"].items())
        },
    }


def run_arm(
    tape: dict,
    arm: str,
    config: ReplayConfig,
    yoke_schedule: list[dict] | None = None,
) -> dict:
    config.validate()
    if arm not in {ARM_A, ARM_B, ARM_C}:
        raise ValueError(f"unknown arm: {arm}")
    if arm == ARM_C and not yoke_schedule:
        raise ValueError("arm C requires B's yoke schedule")

    state = _empty_state(config)
    rng = random.Random(config.seed)
    trace: list[dict] = []
    schedule: list[dict] = []

    for tick_index, tick in enumerate(tape["ticks"]):
        state["pulse"] += 1
        _decay_state(state, config)
        rows = list(tick["rows"])
        k = min(config.k, len(rows))
        budget_before = float(state["budget"])
        fallback_count = 0

        if arm == ARM_A:
            ranked = _rank_a(rows)
            selected = ranked[:k]
            credit_count = 0
            credited_ids: list[str] = []
        elif arm == ARM_B:
            ranked = _rank_b(rows, state, config)
            selected = ranked[:k]
            credit_count = _credit_capacity(state["budget"], config, len(selected))
            credited_ids = _apply_consolidation(state, selected, credit_count, config)
        else:
            yoke = yoke_schedule[tick_index]
            b_selected_ids = list(yoke.get("selected_ids", []))
            selected, fallback_count = _yoked_selection(rows, b_selected_ids, k, rng)
            ranked = selected + [
                row for row in _rank_a(rows)
                if row["candidate"].candidate_id not in {x["candidate"].candidate_id for x in selected}
            ]
            credit_count = min(int(yoke.get("credit_count", 0)), len(selected))
            # Yoke the global scarcity schedule exactly to B. C changes content,
            # not perturbation count/timing or total budget history.
            state["budget"] = float(yoke.get("budget_before", state["budget"]))
            credited_ids = _apply_consolidation(state, selected, credit_count, config)
            state["budget"] = float(yoke.get("budget_after", state["budget"]))

        selected_ids = [row["candidate"].candidate_id for row in selected]
        rank_map = {row["candidate"].candidate_id: i + 1 for i, row in enumerate(ranked)}
        candidate_trace = [
            _row_trace(row, rank_map[row["candidate"].candidate_id])
            for row in ranked
        ]
        record = {
            "tick_index": tick_index,
            "time_step": int(tick["time_step"]),
            "arm": arm,
            "k": k,
            "budget_before": round(budget_before, 6),
            "budget_after": round(float(state["budget"]), 6),
            "selected_ids": selected_ids,
            "consolidated_ids": credited_ids,
            "credit_count": credit_count,
            "yoke_fallback_count": fallback_count,
            "provenance": {
                "read_slot_ids": selected_ids,
                "write_credit_ids": credited_ids,
            },
            "candidates": candidate_trace,
            "state_after": _state_snapshot(state),
        }
        trace.append(record)
        schedule.append(
            {
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "selection_count": len(selected_ids),
                "credit_count": credit_count,
                "budget_before": round(budget_before, 6),
                "budget_after": round(float(state["budget"]), 6),
            }
        )

    return {
        "arm": arm,
        "config": config.__dict__,
        "metadata": copy.deepcopy(tape.get("metadata", {})),
        "trace": trace,
        "yoke_schedule": schedule,
        "final_state": _state_snapshot(state),
    }


def _survivors(run: dict, threshold: float) -> set[str]:
    return {
        candidate_id
        for candidate_id, strength in run["final_state"]["slow"].items()
        if float(strength) >= threshold
    }


def jaccard_distance(a: Iterable[str], b: Iterable[str]) -> float:
    set_a, set_b = set(a), set(b)
    union = set_a | set_b
    if not union:
        return 0.0
    return 1.0 - len(set_a & set_b) / len(union)


def _ignition_retrieval_rank_correlation(run_b: dict) -> float | None:
    xs: list[float] = []
    ys: list[float] = []
    for tick in run_b["trace"]:
        retrieval_sorted = sorted(
            tick["candidates"],
            key=lambda row: (-float(row["retrieval_score"]), row["id"]),
        )
        retrieval_rank = {row["id"]: i + 1 for i, row in enumerate(retrieval_sorted)}
        for workspace_rank, candidate_id in enumerate(tick["selected_ids"], start=1):
            if candidate_id in retrieval_rank:
                xs.append(float(retrieval_rank[candidate_id]))
                ys.append(float(workspace_rank))
    if len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return numerator / (denom_x * denom_y)


def run_experiment(tape: dict, config: ReplayConfig) -> dict:
    normalized = normalize_tape(tape) if "rows" not in tape.get("ticks", [{}])[0] else tape
    run_a = run_arm(normalized, ARM_A, config)
    run_b = run_arm(normalized, ARM_B, config)
    run_c = run_arm(normalized, ARM_C, config, yoke_schedule=run_b["yoke_schedule"])

    threshold = config.strong_memory_threshold
    survivors_a = _survivors(run_a, threshold)
    survivors_b = _survivors(run_b, threshold)
    survivors_c = _survivors(run_c, threshold)
    metrics = {
        "strong_memory_threshold": threshold,
        "final_survivor_counts": {
            "A": len(survivors_a),
            "B": len(survivors_b),
            "C": len(survivors_c),
        },
        "final_ab_survivor_jaccard_distance": round(jaccard_distance(survivors_a, survivors_b), 6),
        "final_ac_survivor_jaccard_distance": round(jaccard_distance(survivors_a, survivors_c), 6),
        "final_bc_survivor_jaccard_distance": round(jaccard_distance(survivors_b, survivors_c), 6),
        "ignition_vs_retrieval_rank_correlation": _ignition_retrieval_rank_correlation(run_b),
        "b_equals_c_selected_all_ticks": all(
            b["selected_ids"] == c["selected_ids"]
            for b, c in zip(run_b["trace"], run_c["trace"])
        ),
        "capacity_matched": all(
            len(a["selected_ids"]) == len(b["selected_ids"]) == len(c["selected_ids"])
            for a, b, c in zip(run_a["trace"], run_b["trace"], run_c["trace"])
        ),
        "yoked_credit_counts": all(
            b["credit_count"] == c["credit_count"]
            for b, c in zip(run_b["trace"], run_c["trace"])
        ),
    }
    corr = metrics["ignition_vs_retrieval_rank_correlation"]
    metrics["early_stop_retrieval_relabel_warning"] = bool(corr is not None and corr > 0.90)

    return {
        "experiment": "endogenous_workspace_scarcity_consolidation_replay",
        "harness_version": HARNESS_VERSION,
        "produced_dialogue": False,
        "wrote_live_memory": False,
        "primary_metric": PRIMARY_METRIC,
        "metrics": metrics,
        "runs": {"A": run_a, "B": run_b, "C": run_c},
    }


def require_preregistration(primary_metric: str | None, min_effect: float | None, pilot: bool) -> None:
    if pilot:
        return
    if primary_metric != PRIMARY_METRIC:
        raise ValueError(
            f"non-pilot runs must preregister primary_metric={PRIMARY_METRIC!r}"
        )
    if min_effect is None or not math.isfinite(float(min_effect)) or float(min_effect) <= 0:
        raise ValueError("non-pilot runs require a positive --min-effect chosen before execution")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline A/B/C replay harness for Endogenous Workspace.")
    parser.add_argument("--tape", required=True, help="Frozen JSON candidate tape")
    parser.add_argument("--out", required=True, help="Output JSON trace")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pilot", action="store_true", help="Permit exploratory runs without a preregistered effect threshold")
    parser.add_argument("--primary-metric", default=None)
    parser.add_argument("--min-effect", type=float, default=None)
    args = parser.parse_args()

    require_preregistration(args.primary_metric, args.min_effect, args.pilot)
    config = ReplayConfig(k=args.k, seed=args.seed)
    result = run_experiment(load_tape(args.tape), config)
    result["preregistration"] = {
        "pilot": bool(args.pilot),
        "primary_metric": args.primary_metric or (PRIMARY_METRIC if args.pilot else None),
        "minimum_effect_size": args.min_effect,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": args.out, "metrics": result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
