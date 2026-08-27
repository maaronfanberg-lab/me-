import unittest

from vault_talker import choose_speaker


class VaultTalkerTests(unittest.TestCase):
    def report(self, cycle=10, winner=None):
        candidates = {}
        scores = {"sarah": 0.2, "mara": 0.3, "owen": 0.4, "jules": 0.1}
        for entity, score in scores.items():
            candidates[entity] = {
                "score": score,
                "would_request_speech": entity == winner,
            }
        return {"source_cycle": cycle, "candidates": candidates}

    def test_latent_candidate_wins(self):
        entity, reason = choose_speaker(self.report(winner="mara"), [])
        self.assertEqual(entity, "mara")
        self.assertEqual(reason, "latent_candidate")

    def test_idle_turn_is_bounded(self):
        history = [{"source_cycle": 8, "speaker": "sarah", "text": "x"}]
        entity, reason = choose_speaker(self.report(cycle=10), history)
        self.assertIsNone(entity)
        self.assertEqual(reason, "idle_cooldown")

    def test_idle_turn_uses_highest_score(self):
        history = [{"source_cycle": 5, "speaker": "sarah", "text": "x"}]
        entity, reason = choose_speaker(self.report(cycle=10), history)
        self.assertEqual(entity, "owen")
        self.assertEqual(reason, "bounded_idle_turn")

    def test_missing_cycle_fails_closed(self):
        r = self.report()
        r["source_cycle"] = None
        entity, reason = choose_speaker(r, [])
        self.assertIsNone(entity)
        self.assertEqual(reason, "missing_cycle")


if __name__ == "__main__":
    unittest.main()
