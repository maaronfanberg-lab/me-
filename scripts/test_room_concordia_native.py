#!/usr/bin/env python3
"""Real-upstream integration tests. No imitation or monkeypatched Concordia."""
from pathlib import Path
import json
import unittest

import room_concordia_native as native


class NativeConcordiaTests(unittest.TestCase):
    def test_upstream_engine_and_referee_are_really_running(self):
        result = native.run(mode="scripted", steps=1)
        self.assertEqual(result["framework"], "google-deepmind/concordia")
        self.assertEqual(result["engine_class"],
                         "concordia.environment.engines.simultaneous.Simultaneous")
        self.assertIn("concordia.", result["game_master_class"])
        self.assertIn("concordia.", result["scheduler_class"])
        self.assertEqual(set(result["players"]), {"Sarah", "Mara", "Owen", "Jules"})

    def test_busy_characters_not_forced_to_speak(self):
        result = native.run(mode="scripted", steps=1)
        self.assertEqual(len(result["steps"]), 1)
        first = set(result["steps"][0]["acting"])
        self.assertEqual(first, {"Mara", "Jules"})
        self.assertNotIn("Sarah", first)
        self.assertNotIn("Owen", first)

    def test_time_and_events_continue_after_initial_attention(self):
        result = native.run(mode="scripted", steps=5)
        self.assertGreaterEqual(len(result["steps"]), 2)
        self.assertTrue(result["simulated_time"])
        self.assertEqual(result["steps"][0]["step"], 1)
        self.assertTrue(all("actions" in step for step in result["steps"]))

    def test_keeps_real_room_character_definitions(self):
        config = json.loads((native.ROOT / "room" / "config.json").read_text())
        for person in native.PARTICIPANTS:
            identity = native.identity_text(person, config)
            self.assertIn(config["p"][person]["psychology_v2"]["core_identity"], identity)

    def test_llama_adapter_refuses_remote_upload_of_room_prompts(self):
        with self.assertRaises(ValueError):
            native.LocalLlama("https://example.com/v1/chat/completions", "example")
        with self.assertRaises(ValueError):
            native.LocalLlama("http://127.0.0.1:18080/completion", "example")
        native.LocalLlama("http://127.0.0.1:18080/v1/chat/completions", "local")


if __name__ == "__main__":
    unittest.main()
