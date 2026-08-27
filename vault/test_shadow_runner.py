import json
import math
import tempfile
import unittest
from pathlib import Path

from room_dynamics import ENTITIES, LATENT_BOUND
from shadow_runner import load_envelope, run_shadow, semantic_event_delta


class ShadowRunnerTests(unittest.TestCase):
    def sample_feed(self, count=2):
        base = [
            {"id": "m1", "speaker": "sarah", "text": "I wonder what changed?", "at": "2026-08-27T11:58:00Z"},
            {"id": "m2", "speaker": "owen", "text": "I'm not sure. Let's step back.", "at": "2026-08-27T11:59:00Z"},
        ]
        if count > 2:
            base = [
                {"id": f"m{i}", "speaker": ("sarah", "mara", "owen", "jules")[i % 4],
                 "text": "I wonder if this new change is strange, but maybe we should keep exploring together?",
                 "at": "2026-08-27T11:59:00Z"}
                for i in range(count)
            ]
        return {
            "generated_at": "2026-08-27T12:00:00Z",
            "state": {"cycle": 10},
            "brain": {"active": "llama3.2-1b"},
            "minds": {"entities": {e: {"genome": {"curiosity": 0.8}} for e in ENTITIES}},
            "conversation": base,
        }

    def test_semantics_not_cryptographic_noise(self):
        curious = semantic_event_delta("mara", "sarah", "I wonder how we explore something new?")
        tense = semantic_event_delta("mara", "sarah", "I'm angry and distrust this conflict")
        self.assertGreater(curious[0], tense[0])
        self.assertGreater(tense[1], curious[1])

    def test_word_boundaries_prevent_substring_false_hits(self):
        clean = semantic_event_delta("mara", "sarah", "show fright")
        direct = semantic_event_delta("mara", "sarah", "how right")
        self.assertGreater(direct[0], clean[0])
        self.assertGreater(direct[4], clean[4])

    def test_negated_certainty_is_not_high_confidence(self):
        unsure = semantic_event_delta("mara", "sarah", "I am not sure and don't know")
        sure = semantic_event_delta("mara", "sarah", "I know and I am sure")
        self.assertGreater(sure[4], unsure[4])

    def test_shadow_never_requests_speech(self):
        feed = self.sample_feed()
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        new_env, report = run_shadow(feed, env)
        self.assertFalse(report["production_write_enabled"])
        self.assertFalse(report["llm_enabled"])
        self.assertFalse(report["speech_requested"])
        self.assertFalse(report["candidate_selection_enabled"])
        self.assertEqual(report["processed_messages"], 2)
        for entity in ENTITIES:
            self.assertFalse(report["entities"][entity]["speech_requested"])
            self.assertFalse(report["candidates"][entity]["would_request_speech"])
            self.assertAlmostEqual(sum(new_env["entities"][entity]["regimes"]), 1.0, places=10)
            self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in new_env["entities"][entity]["latent"]))

    def test_cursor_prevents_replay(self):
        feed = self.sample_feed()
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, first = run_shadow(feed, env)
        env, second = run_shadow(feed, env)
        self.assertEqual(first["processed_messages"], 2)
        self.assertEqual(second["processed_messages"], 0)

    def test_duplicate_ids_are_processed_once(self):
        feed = self.sample_feed()
        feed["conversation"].append({"id": "m2", "speaker": "mara", "text": "replacement", "at": "2026-08-27T11:59:30Z"})
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        _, report = run_shadow(feed, env)
        self.assertEqual(report["processed_messages"], 2)
        self.assertEqual(report["health"]["anomalies"]["duplicate_ids"], 1)

    def test_missing_ids_receive_stable_synthetic_ids(self):
        feed = self.sample_feed()
        feed["conversation"][0].pop("id")
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, report = run_shadow(feed, env)
        self.assertEqual(report["health"]["anomalies"]["synthetic_ids"], 1)
        self.assertTrue(env["recent_message_ids"][0].startswith("synthetic-"))

    def test_missing_cursor_uses_recent_ids_instead_of_blind_replay(self):
        feed = self.sample_feed()
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, _ = run_shadow(feed, env)
        feed2 = self.sample_feed()
        feed2["conversation"] = [feed2["conversation"][1], {"id": "m3", "speaker": "jules", "text": "new", "at": "2026-08-27T12:00:00Z"}]
        env["last_message_id"] = "missing-from-window"
        _, report = run_shadow(feed2, env)
        self.assertTrue(report["health"]["anomalies"]["cursor_missing"])
        self.assertEqual(report["processed_messages"], 1)

    def test_corrupt_state_json_recovers(self):
        feed = self.sample_feed()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text("{broken")
            env = load_envelope(path, feed)
            self.assertEqual(env["version"], 4)
            self.assertEqual(env["recovery_reason"], "corrupt_state_json")
            self.assertEqual(set(env["entities"]), set(ENTITIES))

    def test_invalid_single_entity_is_repaired_without_discarding_others(self):
        feed = self.sample_feed()
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        original = list(env["entities"]["mara"]["latent"])
        env["entities"]["sarah"]["latent"] = [float("nan")] * 8
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text(json.dumps(env))
            repaired = load_envelope(path, feed)
            self.assertEqual(repaired["entities"]["mara"]["latent"], original)
            self.assertTrue(all(math.isfinite(v) for v in repaired["entities"]["sarah"]["latent"]))

    def test_extreme_genome_values_are_clamped(self):
        feed = self.sample_feed()
        feed["minds"]["entities"]["sarah"]["genome"] = {"curiosity": float("inf"), "inhibition": -999}
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        self.assertTrue(all(math.isfinite(v) for v in env["entities"]["sarah"]["latent"]))
        self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in env["entities"]["sarah"]["latent"]))

    def test_future_timestamp_is_quarantined(self):
        feed = self.sample_feed()
        feed["conversation"][0]["at"] = "2036-08-27T12:00:00Z"
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        _, report = run_shadow(feed, env)
        self.assertEqual(report["health"]["anomalies"]["future_timestamps"], 1)

    def test_cycle_regression_disables_candidate_selection(self):
        feed = self.sample_feed()
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, _ = run_shadow(feed, env)
        feed["state"]["cycle"] = 9
        feed["conversation"].append({"id": "m3", "speaker": "mara", "text": "angry conflict strange change", "at": "2026-08-27T12:00:00Z"})
        _, report = run_shadow(feed, env)
        self.assertTrue(report["health"]["anomalies"]["cycle_regressed"])
        self.assertFalse(report["candidate_selection_enabled"])
        self.assertFalse(any(d["would_request_speech"] for d in report["candidates"].values()))

    def test_bootstrap_does_not_saturate_latent_state(self):
        feed = self.sample_feed(40)
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, report = run_shadow(feed, env)
        self.assertEqual(report["processed_messages"], 40)
        for entity in ENTITIES:
            self.assertLess(max(abs(v) for v in env["entities"][entity]["latent"]), 2.5)
            self.assertGreaterEqual(report["entities"][entity]["regime_l1_change"], 0.0)


if __name__ == "__main__":
    unittest.main()
