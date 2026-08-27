import math
import unittest

from decision import ENTITIES, MAX_L1_CHANGE, choose_candidates
from prompt_adapter import compact_state_text


class DecisionAdapterTests(unittest.TestCase):
    def diagnostics(self):
        base = {
            "regime_probabilities": [0.22, 0.30, 0.24, 0.24],
            "dominant_regime": "exploratory",
            "entropy": 0.997,
            "observables": [0.7, 0.4, 0.65, 0.55, 0.5, 0.48, 0.52, 0.58, 0.6, 0.63],
        }
        out = {}
        for entity, change in (("sarah", .08), ("mara", .05), ("owen", .13), ("jules", .07)):
            out[entity] = dict(base, regime_l1_change=change)
        return out

    def test_global_budget_allows_only_one_candidate(self):
        decisions, meta = choose_candidates(self.diagnostics(), 100, {}, 4)
        self.assertEqual(sum(bool(v["would_request_speech"]) for v in decisions.values()), 1)
        self.assertEqual(meta["global_candidate_budget"], 1)
        self.assertFalse(meta["actual_speech_enabled"])
        self.assertTrue(decisions["owen"]["would_request_speech"])

    def test_output_contains_only_known_entities(self):
        diagnostics = self.diagnostics(); diagnostics["intruder"] = dict(diagnostics["sarah"])
        decisions, _ = choose_candidates(diagnostics, 100, {}, 4)
        self.assertEqual(tuple(decisions), ENTITIES)

    def test_cooldown_blocks_repeat_candidate(self):
        _, meta = choose_candidates(self.diagnostics(), 100, {}, 4)
        second, _ = choose_candidates(self.diagnostics(), 101, meta, 4)
        self.assertFalse(second["owen"]["would_request_speech"])
        self.assertTrue(second["owen"]["cooldown_blocked"])

    def test_observation_cooldown_survives_missing_cycle(self):
        first, meta = choose_candidates(self.diagnostics(), None, {}, 4)
        self.assertTrue(first["owen"]["would_request_speech"])
        second, meta2 = choose_candidates(self.diagnostics(), None, meta, 4)
        self.assertFalse(second["owen"]["would_request_speech"])
        self.assertTrue(second["owen"]["cooldown_blocked"])
        third, _ = choose_candidates(self.diagnostics(), None, meta2, 4)
        self.assertTrue(third["owen"]["would_request_speech"])

    def test_no_messages_means_no_candidate(self):
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, 0)
        self.assertFalse(any(v["would_request_speech"] for v in decisions.values()))

    def test_negative_messages_are_treated_as_zero(self):
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, -99)
        self.assertFalse(any(v["would_request_speech"] for v in decisions.values()))

    def test_bootstrap_flag_suppresses_candidates(self):
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, 4, allow_candidates=False)
        self.assertFalse(any(v["would_request_speech"] for v in decisions.values()))
        self.assertTrue(all(v["reason"] == "bootstrap_suppressed" for v in decisions.values()))

    def test_nonfinite_values_do_not_poison_scores(self):
        diagnostics = self.diagnostics()
        diagnostics["owen"]["regime_l1_change"] = float("nan")
        diagnostics["owen"]["regime_probabilities"] = [0.2, 0.2, 0.2, float("inf")]
        decisions, _ = choose_candidates(diagnostics, "not-a-cycle", {}, 4)
        self.assertTrue(all(math.isfinite(v["score"]) for v in decisions.values()))
        self.assertFalse(decisions["owen"]["would_request_speech"])

    def test_absurd_change_is_clamped(self):
        diagnostics = self.diagnostics(); diagnostics["owen"]["regime_l1_change"] = 10**50
        decisions, _ = choose_candidates(diagnostics, 100, {}, 4)
        self.assertLessEqual(decisions["owen"]["score"], 2 * MAX_L1_CHANGE + 0.15)

    def test_missing_regime_probabilities_are_safe(self):
        diagnostics = self.diagnostics(); diagnostics["owen"].pop("regime_probabilities")
        decisions, _ = choose_candidates(diagnostics, 100, {}, 4)
        self.assertTrue(math.isfinite(decisions["owen"]["score"]))

    def test_equal_scores_have_stable_entity_tie_break(self):
        diagnostics = self.diagnostics()
        for diag in diagnostics.values():
            diag["regime_l1_change"] = 0.1; diag["regime_probabilities"] = [0.25] * 4
        decisions, _ = choose_candidates(diagnostics, 100, {}, 4)
        winners = [name for name, value in decisions.items() if value["would_request_speech"]]
        self.assertEqual(winners, ["jules"])

    def test_cycle_regression_is_explicit_and_suppressed(self):
        _, meta = choose_candidates(self.diagnostics(), 100, {}, 4)
        decisions, regressed = choose_candidates(self.diagnostics(), 99, meta, 4)
        self.assertTrue(regressed["cycle_regressed"])
        self.assertFalse(any(v["would_request_speech"] for v in decisions.values()))
        self.assertTrue(all(v["reason"] == "cycle_regression" for v in decisions.values()))

    def test_garbage_cooldown_keys_are_pruned(self):
        previous = {"last_candidate_cycle": {"owen": 10, "intruder": 9},
                    "last_candidate_observation": {"owen": 5, "intruder": 4}}
        _, meta = choose_candidates(self.diagnostics(), 20, previous, 4)
        self.assertNotIn("intruder", meta["last_candidate_cycle"])
        self.assertNotIn("intruder", meta["last_candidate_observation"])

    def test_huge_cycle_is_rejected_safely(self):
        decisions, meta = choose_candidates(self.diagnostics(), 10**30, {}, 4)
        self.assertIsNone(meta["last_source_cycle"])
        self.assertTrue(any(v["would_request_speech"] for v in decisions.values()))

    def test_semantic_summary_is_compact_and_directional(self):
        diag = self.diagnostics()["sarah"]
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, 4)
        text = compact_state_text("sarah", diag, decisions["sarah"])
        self.assertLessEqual(len(text), 480)
        self.assertIn("inner_state:", text)
        self.assertIn("regime_entropy=", text)
        self.assertIn("mode_separation=", text)
        self.assertTrue("high(" in text or "low(" in text)
        self.assertNotIn("[0.22", text)


if __name__ == "__main__":
    unittest.main()
