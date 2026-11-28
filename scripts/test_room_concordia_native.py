#!/usr/bin/env python3
"""Real-upstream integration tests. No imitation or monkeypatched Concordia."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import room_concordia_native as native


class NativeConcordiaTests(unittest.TestCase):
    def test_lossless_checkpoint_compression_and_legacy_read(self):
        original = {"schema": 1, "entities": {"Sarah": {"memory": ["past event"] * 5000}}, "game_master": {"timer": "15m"}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "checkpoint.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            self.assertEqual(native.read_checkpoint(path), original)
            with patch.object(native, "CHECKPOINT_COMPRESS_BYTES", 100):
                native.write_checkpoint(path, original)
            self.assertEqual(json.loads(path.read_text())["checkpoint_encoding"], "gzip+base64-v1")
            self.assertEqual(native.read_checkpoint(path), original)
            self.assertLess(path.stat().st_size, 2000)

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

    def test_llama_choice_uses_raw_numeric_response(self):
        model = native.LocalLlama("http://127.0.0.1:18080/v1/chat/completions", "local")
        # A bare index is valid for Concordia choice prompts, even though it
        # is deliberately invalid as a scheduler action control block.
        with patch.object(model, "_sample_raw_text", return_value="1") as call:
            index, selected, metadata = model.sample_choice(
                "Choose the next entity", ["Sarah", "Mara", "Jules"]
            )
        self.assertEqual((index, selected, metadata), (1, "Mara", {}))
        call.assert_called_once()

    def test_llama_action_still_requires_scheduler_json(self):
        model = native.LocalLlama("http://127.0.0.1:18080/v1/chat/completions", "local")
        with patch.object(model, "_sample_raw_text", return_value="1"):
            self.assertEqual(
                model.sample_text("What does Mara independently choose to do next?"),
                chr(10) + '{"mask": [], "timer": {"time": "15m", "reason": "reflect quietly"}}',
            )

    def test_llama_adapter_refuses_remote_upload_of_room_prompts(self):
        with self.assertRaises(ValueError):
            native.LocalLlama("https://example.com/v1/chat/completions", "example")
        with self.assertRaises(ValueError):
            native.LocalLlama("http://127.0.0.1:18080/completion", "example")
        native.LocalLlama("http://127.0.0.1:18080/v1/chat/completions", "local")


if __name__ == "__main__":
    unittest.main()
