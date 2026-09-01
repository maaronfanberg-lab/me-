#!/usr/bin/env python3
"""Offline prediction-error challenger for Endogenous Workspace experiments.

Instead of ranking memories by static salience weights, this arm asks a simpler
question: which currently retrieved memories are more salient than the agent's
own recent retrieval history predicted? Positive prediction error is computed
entirely from the frozen retrieval tape. No LLM, prose generation, dialogue,
Stanford write, or live feature activation occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from endogenous_workspace_replay import ReplayConfig

ARM_PE = "PE_prediction_error"


@dataclass(frozen=True)
class PredictionConfig:
    alpha: float = 0.35
    absence_decay: float = 0.90

    def validate(self) -> None:
        if not 0.0 < float(self.alpha) <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        if not 0.0 <= float(self.absence_decay) <= 1.0:
            raise ValueError("absence_decay must be in [0, 1]")


def _recover_budget(budget: float, config: ReplayConfig) -> float:
    return min(float(config.budget_max), float(budget) + float(config.budget_recovery))


def _credit_capacity(budget: float, config: ReplayConfig, selected_count: int) -> int:
    affordable = int((float(budget) + 1e-12) // float(config.consolidation_cost))
    return max(0, min(int(selected_count), affordable))


def run_prediction_error_arm(
    tape: Mapping,
    config: ReplayConfig,
    prediction: PredictionConfig | None = None,
) -> dict:
    config.validate()
    prediction = prediction or PredictionConfig()
    prediction.validate()

    expected: dict[str, float] = {}
    seen_count: dict[str, int] = {}
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
                expected[candidate_id] *= prediction.absence_decay
                if expected[candidate_id] < 0.001:
                    expected.pop(candidate_id, None)
                    seen_count.pop(candidate_id, None)

        scored: list[dict] = []
        for row in rows:
            candidate = row["candidate"]
            candidate_id = candidate.candidate_id
            current = float(row["retrieval_score"])
            predicted = float(expected.get(candidate_id, 0.0))
            positive_error = max(0.0, current - predicted)
            scored.append(
                {
                    **row,
                    "predicted_retrieval_score": predicted,
                    "positive_prediction_error": positive_error,
                    "seen_before": int(seen_count.get(candidate_id, 0)),
                }
            )

        scored.sort(
            key=lambda row: (
                -float(row["positive_prediction_error"]),
                -float(row["retrieval_score"]),
                row["candidate"].candidate_id,
            )
        )
        k = min(int(config.k), len(scored))
        selected = scored[:k]
        credit_count = _credit_capacity(budget, config, len(selected))
        credited_ids = [row["candidate"].candidate_id for row in selected[:credit_count]]
        budget = max(0.0, budget - credit_count * float(config.consolidation_cost))

        # Update the predictor only after scoring so the current retrieval cannot
        # help predict itself.
        for row in rows:
            candidate_id = row["candidate"].candidate_id
            current = float(row["retrieval_score"])
            prior = float(expected.get(candidate_id, 0.0))
            expected[candidate_id] = (1.0 - prediction.alpha) * prior + prediction.alpha * current
            seen_count[candidate_id] = int(seen_count.get(candidate_id, 0)) + 1

        selected_rows = []
        for rank, row in enumerate(selected, start=1):
            selected_rows.append(
                {
                    "id": row["candidate"].candidate_id,
                    "rank": rank,
                    "retrieval_score": round(float(row["retrieval_score"]), 6),
                    "predicted_retrieval_score": round(float(row["predicted_retrieval_score"]), 6),
                    "positive_prediction_error": round(float(row["positive_prediction_error"]), 6),
                    "seen_before": int(row["seen_before"]),
                }
            )

        selected_ids = [row["candidate"].candidate_id for row in selected]
        record = {
            "tick_index": tick_index,
            "time_step": int(tick["time_step"]),
            "arm": ARM_PE,
            "k": k,
            "budget_before": round(float(budget_before), 6),
            "budget_after": round(float(budget), 6),
            "selected_ids": selected_ids,
            "consolidated_ids": credited_ids,
            "credit_count": credit_count,
            "selected": selected_rows,
            "predictor_state_size": len(expected),
        }
        trace.append(record)
        schedule.append(
            {
                "time_step": int(tick["time_step"]),
                "selected_ids": selected_ids,
                "selection_count": len(selected_ids),
                "credit_count": credit_count,
                "budget_before": round(float(budget_before), 6),
                "budget_after": round(float(budget), 6),
            }
        )

    return {
        "arm": ARM_PE,
        "config": config.__dict__,
        "prediction_config": prediction.__dict__,
        "trace": trace,
        "yoke_schedule": schedule,
        "final_predictor": {
            key: round(float(value), 6) for key, value in sorted(expected.items())
        },
    }
