#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from endogenous_workspace_replay import (
    ARM_A,
    ARM_B,
    ARM_C,
    PRIMARY_METRIC,
    ReplayConfig,
    jaccard_distance,
    normalize_tape,
    require_preregistration,
    run_arm,
    run_experiment,
)


def synthetic_tape():
    ticks = []
    for step in range(1, 7):
        candidates = []
        for index in range(7):
            candidates.append(
                {
                    "id": f"m{index}",
                    "source": "memory:event",
                    "text": f"existing memory {index}",
                    "importance": round(0.2 + 0.1 * index, 3),
                    "recency": round(max(0.1, 1.0 - 0.08 * abs(index - step)), 3),
                    "retrieval_score": round(max(0.05, 0.92 - 0.09 * ((index + step) % 7)), 3),
                }
            )
        ticks.append({"time_step": step, "candidates": candidates})
    return {
        "schema_version": 1,
        "metadata": {"llm_seed": 17, "temperature": 0.0, "frozen": True},
        "ticks": ticks,
    }


class EndogenousWorkspaceReplayTests(unittest.TestCase):
    def test_normalize_tape_requires_frozen_candidates(self):
        normalized = normalize_tape(synthetic_tape())
        self.assertEqual(len(normalized["ticks"]), 6)
        self.assertEqual(len(normalized["ticks"][0]["rows"]), 7)

    def test_all_arms_are_capacity_matched(self):
        tape = normalize_tape(synthetic_tape())
        config = ReplayConfig(k=4, seed=11)
        run_a = run_arm(tape, ARM_A, config)
        run_b = run_arm(tape, ARM_B, config)
        run_c = run_arm(tape, ARM_C, config, run_b["yoke_schedule"])
        for a, b, c in zip(run_a["trace"], run_b["trace"], run_c["trace"]):
            self.assertEqual(len(a["selected_ids"]), 4)
            self.assertEqual(len(b["selected_ids"]), 4)
            self.assertEqual(len(c["selected_ids"]), 4)

    def test_yoked_shuffle_preserves_credit_count_and_budget_schedule(self):
        tape = normalize_tape(synthetic_tape())
        config = ReplayConfig(k=3, seed=23)
        run_b = run_arm(tape, ARM_B, config)
        run_c = run_arm(tape, ARM_C, config, run_b["yoke_schedule"])
        for b, c in zip(run_b["trace"], run_c["trace"]):
            self.assertEqual(b["credit_count"], c["credit_count"])
            self.assertEqual(b["budget_before"], c["budget_before"])
            self.assertEqual(b["budget_after"], c["budget_after"])

    def test_yoked_shuffle_changes_content_when_alternatives_exist(self):
        result = run_experiment(synthetic_tape(), ReplayConfig(k=3, seed=9))
        b = result["runs"]["B"]["trace"]
        c = result["runs"]["C"]["trace"]
        self.assertTrue(any(x["selected_ids"] != y["selected_ids"] for x, y in zip(b, c)))
        self.assertFalse(result["metrics"]["b_equals_c_selected_all_ticks"])

    def test_trace_and_state_do_not_persist_candidate_text(self):
        result = run_experiment(synthetic_tape(), ReplayConfig(k=3, seed=4))
        rendered = json.dumps(result)
        self.assertNotIn("existing memory 0", rendered)
        self.assertIn("m0", rendered)

    def test_same_seed_is_deterministic(self):
        first = run_experiment(synthetic_tape(), ReplayConfig(k=3, seed=123))
        second = run_experiment(synthetic_tape(), ReplayConfig(k=3, seed=123))
        self.assertEqual(first, second)

    def test_preregistration_is_required_for_non_pilot(self):
        with self.assertRaises(ValueError):
            require_preregistration(None, None, pilot=False)
        with self.assertRaises(ValueError):
            require_preregistration(PRIMARY_METRIC, None, pilot=False)
        require_preregistration(PRIMARY_METRIC, 0.1, pilot=False)
        require_preregistration(None, None, pilot=True)

    def test_primary_metric_is_nonlinguistic_memory_store_distance(self):
        result = run_experiment(synthetic_tape(), ReplayConfig(k=3, seed=5))
        self.assertEqual(result["primary_metric"], PRIMARY_METRIC)
        self.assertIn(PRIMARY_METRIC, result["metrics"])
        self.assertGreaterEqual(result["metrics"][PRIMARY_METRIC], 0.0)
        self.assertLessEqual(result["metrics"][PRIMARY_METRIC], 1.0)

    def test_jaccard_distance(self):
        self.assertEqual(jaccard_distance(set(), set()), 0.0)
        self.assertEqual(jaccard_distance({"a"}, {"a"}), 0.0)
        self.assertEqual(jaccard_distance({"a"}, {"b"}), 1.0)


if __name__ == "__main__":
    unittest.main()
