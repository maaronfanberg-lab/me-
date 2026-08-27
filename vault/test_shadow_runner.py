import json
import math
import tempfile
import unittest
from pathlib import Path

from room_dynamics import ENTITIES, LATENT_BOUND
from shadow_runner import STATE_VERSION, load_envelope, run_shadow, semantic_event_delta


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
                 "at": f"2026-08-27T11:{min(59, i):02d}:00Z"}
                for i in range(count)
            ]
        return {
            "generated_at": "2026-08-27T12:00:00Z",
            "production_generated_at": "2026-08-27T11:59:30Z",
            "state": {"cycle": 10},
            "brain": {"active": "llama3.2-1b"},
            "minds": {"entities": {e: {"genome": {"curiosity": 0.8}} for e in ENTITIES}},
            "conversation": base,
        }

    def test_semantics_not_cryptographic_noise(self):
        curious = semantic_event_delta("mara", "sarah", "I wonder how we explore something new?")
        tense = semantic_event_delta("mara", "sarah", "I'm angry and distrust this conflict")
        self.assertGreater(curious[0], tense[0]); self.assertGreater(tense[1], curious[1])

    def test_word_boundaries_prevent_substring_false_hits(self):
        clean = semantic_event_delta("mara", "sarah", "show fright")
        direct = semantic_event_delta("mara", "sarah", "how right")
        self.assertGreater(direct[0], clean[0]); self.assertGreater(direct[4], clean[4])

    def test_negated_certainty_is_not_high_confidence(self):
        unsure = semantic_event_delta("mara", "sarah", "I am not sure and don't know")
        sure = semantic_event_delta("mara", "sarah", "I know and I am sure")
        self.assertGreater(sure[4], unsure[4])

    def test_shadow_never_requests_direct_speech(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        new_env, report = run_shadow(feed, env)
        self.assertFalse(report["production_write_enabled"]); self.assertFalse(report["llm_enabled"])
        self.assertFalse(report["speech_requested"]); self.assertFalse(report["candidate_selection_enabled"])
        self.assertEqual(report["processed_messages"], 2)
        self.assertEqual(report["production_generated_at"], feed["production_generated_at"])
        for entity in ENTITIES:
            self.assertFalse(report["entities"][entity]["speech_requested"])
            self.assertFalse(report["candidates"][entity]["would_request_speech"])
            self.assertAlmostEqual(sum(new_env["entities"][entity]["regimes"]), 1.0, places=10)
            self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in new_env["entities"][entity]["latent"]))

    def test_seen_ids_prevent_replay(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, first = run_shadow(feed, env); env, second = run_shadow(feed, env)
        self.assertEqual(first["processed_messages"], 2); self.assertEqual(second["processed_messages"], 0)

    def test_new_out_of_order_id_is_not_missed(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, _ = run_shadow(feed, env)
        feed2 = self.sample_feed()
        feed2["generated_at"] = "2026-08-27T12:01:00Z"
        feed2["conversation"].insert(1, {"id": "room2-new", "speaker": "mara",
            "text": "I'm curious about this new direction.", "at": "2026-08-27T11:58:30Z"})
        env2, report = run_shadow(feed2, env)
        self.assertEqual(report["processed_messages"], 1)
        self.assertIn("room2-new", env2["recent_message_ids"])
        env3, report2 = run_shadow(feed2, env2)
        self.assertEqual(report2["processed_messages"], 0)
        self.assertEqual(env3["recent_message_ids"].count("room2-new"), 1)

    def test_recent_ids_cover_whole_visible_window(self):
        feed = self.sample_feed(80); env = load_envelope(Path('/definitely/not/a/file'), feed)
        env, report = run_shadow(feed, env)
        self.assertEqual(report["processed_messages"], 40)
        self.assertEqual(len(env["recent_message_ids"]), 80)
        _, report2 = run_shadow(feed, env)
        self.assertEqual(report2["processed_messages"], 0)

    def test_duplicate_ids_are_processed_once(self):
        feed = self.sample_feed(); feed["conversation"].append(
            {"id": "m2", "speaker": "mara", "text": "replacement", "at": "2026-08-27T11:59:30Z"})
        env = load_envelope(Path('/definitely/not/a/file'), feed); _, report = run_shadow(feed, env)
        self.assertEqual(report["processed_messages"], 2); self.assertEqual(report["health"]["anomalies"]["duplicate_ids"], 1)
        self.assertEqual(report["health"]["status"], "degraded")

    def test_empty_text_is_rejected(self):
        feed = self.sample_feed(); feed["conversation"].append({"id": "empty", "speaker": "mara", "text": "   ", "at": "x"})
        env = load_envelope(Path('/definitely/not/a/file'), feed); _, report = run_shadow(feed, env)
        self.assertEqual(report["health"]["anomalies"]["invalid_messages"], 1)
        self.assertEqual(report["processed_messages"], 2)

    def test_missing_ids_receive_stable_synthetic_ids(self):
        feed = self.sample_feed(); feed["conversation"][0].pop("id")
        env = load_envelope(Path('/definitely/not/a/file'), feed); env, report = run_shadow(feed, env)
        self.assertEqual(report["health"]["anomalies"]["synthetic_ids"], 1)
        self.assertTrue(any(x.startswith("synthetic-") for x in env["recent_message_ids"]))

    def test_missing_cursor_does_not_cause_replay(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed); env, _ = run_shadow(feed, env)
        env["last_message_id"] = "missing-from-window"
        feed2 = self.sample_feed(); feed2["conversation"].append(
            {"id": "m3", "speaker": "jules", "text": "A genuinely new message.", "at": "2026-08-27T12:00:00Z"})
        _, report = run_shadow(feed2, env)
        self.assertTrue(report["health"]["anomalies"]["cursor_missing"])
        self.assertEqual(report["processed_messages"], 1)

    def test_corrupt_state_json_recovers(self):
        feed = self.sample_feed()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"; path.write_text("{broken")
            env = load_envelope(path, feed)
            self.assertEqual(env["version"], STATE_VERSION); self.assertEqual(env["recovery_reason"], "corrupt_state_json")
            self.assertEqual(set(env["entities"]), set(ENTITIES))

    def test_v4_state_migrates_without_discarding_latent(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        env["version"] = 4; old_latent = list(env["entities"]["mara"]["latent"])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"; path.write_text(json.dumps(env))
            migrated = load_envelope(path, feed)
            self.assertEqual(migrated["version"], STATE_VERSION)
            self.assertEqual(migrated["entities"]["mara"]["latent"], old_latent)
            self.assertEqual(migrated["recovery_reason"], "migrated_state_v5")

    def test_invalid_single_entity_is_repaired_without_discarding_others(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        original = list(env["entities"]["mara"]["latent"]); env["entities"]["sarah"]["latent"] = [float("nan")] * 8
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"; path.write_text(json.dumps(env))
            repaired = load_envelope(path, feed)
            self.assertEqual(repaired["entities"]["mara"]["latent"], original)
            self.assertTrue(all(math.isfinite(v) for v in repaired["entities"]["sarah"]["latent"]))

    def test_extra_entity_state_fields_do_not_crash_restore(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed)
        env["entities"]["sarah"]["junk"] = {"anything": True}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"; path.write_text(json.dumps(env))
            repaired = load_envelope(path, feed)
            self.assertNotIn("junk", repaired["entities"]["sarah"])

    def test_extreme_genome_values_are_clamped(self):
        feed = self.sample_feed(); feed["minds"]["entities"]["sarah"]["genome"] = {"curiosity": float("inf"), "inhibition": -999}
        env = load_envelope(Path('/definitely/not/a/file'), feed)
        self.assertTrue(all(math.isfinite(v) and -LATENT_BOUND <= v <= LATENT_BOUND for v in env["entities"]["sarah"]["latent"]))

    def test_future_timestamp_is_quarantined(self):
        feed = self.sample_feed(); feed["conversation"][0]["at"] = "2036-08-27T12:00:00Z"
        env = load_envelope(Path('/definitely/not/a/file'), feed); _, report = run_shadow(feed, env)
        self.assertEqual(report["health"]["anomalies"]["future_timestamps"], 1)

    def test_cycle_regression_disables_candidate_selection(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed); env, _ = run_shadow(feed, env)
        feed["state"]["cycle"] = 9; feed["conversation"].append(
            {"id": "m3", "speaker": "mara", "text": "angry conflict strange change", "at": "2026-08-27T12:00:00Z"})
        _, report = run_shadow(feed, env)
        self.assertTrue(report["health"]["anomalies"]["cycle_regressed"])
        self.assertFalse(report["candidate_selection_enabled"])
        self.assertFalse(any(d["would_request_speech"] for d in report["candidates"].values()))

    def test_bootstrap_does_not_saturate_latent_state(self):
        feed = self.sample_feed(40); env = load_envelope(Path('/definitely/not/a/file'), feed); env, report = run_shadow(feed, env)
        self.assertEqual(report["processed_messages"], 40)
        for entity in ENTITIES:
            self.assertLess(max(abs(v) for v in env["entities"][entity]["latent"]), 2.5)
            self.assertGreaterEqual(report["entities"][entity]["regime_l1_change"], 0.0)

    def test_self_speech_is_damped_relative_to_other_speech(self):
        feed = self.sample_feed(); env = load_envelope(Path('/definitely/not/a/file'), feed); env, _ = run_shadow(feed, env)
        base_sarah = list(env["entities"]["sarah"]["latent"])
        own = self.sample_feed(); own["generated_at"] = "2026-08-27T12:01:00Z"; own["conversation"].append(
            {"id": "r1", "speaker": "sarah", "text": "I wonder about this strange new change?", "at": "2026-08-27T12:00:30Z"})
        other = self.sample_feed(); other["generated_at"] = "2026-08-27T12:01:00Z"; other["conversation"].append(
            {"id": "r1", "speaker": "mara", "text": "I wonder about this strange new change?", "at": "2026-08-27T12:00:30Z"})
        own_env, _ = run_shadow(own, json.loads(json.dumps(env)))
        other_env, _ = run_shadow(other, json.loads(json.dumps(env)))
        own_shift = sum(abs(a-b) for a,b in zip(base_sarah, own_env["entities"]["sarah"]["latent"]))
        other_shift = sum(abs(a-b) for a,b in zip(base_sarah, other_env["entities"]["sarah"]["latent"]))
        self.assertLess(own_shift, other_shift)


if __name__ == "__main__":
    unittest.main()
