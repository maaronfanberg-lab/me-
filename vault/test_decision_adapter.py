import unittest

from decision import choose_candidates
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

    def test_cooldown_blocks_repeat_candidate(self):
        first, meta = choose_candidates(self.diagnostics(), 100, {}, 4)
        second, _ = choose_candidates(self.diagnostics(), 101, meta, 4)
        self.assertFalse(second["owen"]["would_request_speech"])
        self.assertTrue(second["owen"]["cooldown_blocked"])

    def test_no_messages_means_no_candidate(self):
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, 0)
        self.assertFalse(any(v["would_request_speech"] for v in decisions.values()))

    def test_semantic_summary_is_compact(self):
        diag = self.diagnostics()["sarah"]
        decisions, _ = choose_candidates(self.diagnostics(), 100, {}, 4)
        text = compact_state_text("sarah", diag, decisions["sarah"])
        self.assertLess(len(text), 500)
        self.assertIn("inner_state:", text)
        self.assertNotIn("[0.22", text)


if __name__ == "__main__":
    unittest.main()
