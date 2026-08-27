import unittest

from room_dynamics import ENTITIES, LATENT_BOUND
from shadow_runner import load_envelope, run_shadow, semantic_event_delta


class ShadowRunnerTests(unittest.TestCase):
    def sample_feed(self):
        return {
            "generated_at": "2026-08-27T12:00:00Z",
            "state": {"cycle": 10},
            "brain": {"active": "llama3.2-1b"},
            "minds": {"entities": {e: {"genome": {"curiosity": 0.8}} for e in ENTITIES}},
            "conversation": [
                {"id": "m1", "speaker": "sarah", "text": "I wonder what changed?", "at": "2026-08-27T11:58:00Z"},
                {"id": "m2", "speaker": "owen", "text": "I'm not sure. Let's step back.", "at": "2026-08-27T11:59:00Z"},
            ],
        }

    def test_semantics_not_cryptographic_noise(self):
        curious = semantic_event_delta("mara", "sarah", "I wonder how we explore something new?")
        tense = semantic_event_delta("mara", "sarah", "I'm angry and distrust this conflict")
        self.assertGreater(curious[0], tense[0])
        self.assertGreater(tense[1], curious[1])

    def test_shadow_never_requests_speech(self):
        feed = self.sample_feed()
        env = load_envelope(__import__('pathlib').Path('/definitely/not/a/file'), feed)
        new_env, report = run_shadow(feed, env)
        self.assertFalse(report["production_write_enabled"])
        self.assertFalse(report["llm_enabled"])
        self.assertFalse(report["speech_requested"])
        self.assertEqual(report["processed_messages"], 2)
        for entity in ENTITIES:
            self.assertFalse(report["entities"][entity]["speech_requested"])
            self.assertAlmostEqual(sum(new_env["entities"][entity]["regimes"]), 1.0, places=10)
            self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in new_env["entities"][entity]["latent"]))

    def test_cursor_prevents_replay(self):
        feed = self.sample_feed()
        env = load_envelope(__import__('pathlib').Path('/definitely/not/a/file'), feed)
        env, first = run_shadow(feed, env)
        env, second = run_shadow(feed, env)
        self.assertEqual(first["processed_messages"], 2)
        self.assertEqual(second["processed_messages"], 0)


if __name__ == "__main__":
    unittest.main()
