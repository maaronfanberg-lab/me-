#!/usr/bin/env python3
"""Real-upstream integration tests. No imitation or monkeypatched Concordia."""
from pathlib import Path
import json
import unittest

import room_concordia_native as native


class NativeConcordiaTests(unittest.TestCase):
    def test_terminal_all_silent_checkpoint_rearms_without_erasing_memory(self):
        root = native.ROOT
        # The live outage checkpoint had masks [''] for all four people,
        # no remaining timers, and an empty future event queue.
        exhausted = {
            "masks": {name: [""] for name in ("Sarah", "Mara", "Owen", "Jules")},
            "timers": {name: None for name in ("Sarah", "Mara", "Owen", "Jules")},
            "event_queue": [],
            "pending": {"Sarah": [{"tag": "timer.expired.Owen"}]},
        }
        self.assertTrue(native.scheduler_is_exhausted(exhausted))
        exhausted["timers"]["Sarah"] = {"time": "15m"}
        self.assertFalse(native.scheduler_is_exhausted(exhausted))
        exhausted["timers"]["Sarah"] = None
        exhausted["event_queue"] = [{"tag": "action.", "timestamp": "tomorrow"}]
        self.assertFalse(native.scheduler_is_exhausted(exhausted))

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

    def test_real_concordia_scheduler_receives_verified_world_interrupts(self):
        event = {"id": "life-0000123-owen-work_completed-0001",
                 "actor": "owen", "kind": "work_completed",
                 "description": "Owen finished an inspection of the bookshelf."}
        result = native.run(mode="scripted", steps=1, world_events=[
            event,
            {"id": "fake", "actor": "owen", "kind": "work_completed",
             "description": "unverifiable text"},
        ])
        self.assertEqual(result["injected_world_events"], [event["id"]])
        self.assertIn("concordia.", result["scheduler_class"])

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
