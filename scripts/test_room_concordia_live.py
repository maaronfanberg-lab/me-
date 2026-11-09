#!/usr/bin/env python3
"""End-to-end Room publication tests using the unmodified DeepMind engine."""
import json
from pathlib import Path
import tempfile
import unittest

import room_concordia_native as native
import room_concordia_live as bridge
import room_engine_v5 as core


class LiveRoomTests(unittest.TestCase):

    def make_root(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        (root / "room").mkdir()
        (root / "society").mkdir()
        (root / "room" / "config.json").write_text(
            (native.ROOT / "room" / "config.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "room" / "state.json").write_text(
            json.dumps(core.fresh_state()), encoding="utf-8",
        )
        (root / "room" / "cognitive_state.json").write_text(
            json.dumps(core.fresh_minds()), encoding="utf-8",
        )
        (root / "room" / "discourse.json").write_text(
            json.dumps({"nodes": [], "roots": []}), encoding="utf-8",
        )
        (root / "room" / "conversation.json").write_text("[]", encoding="utf-8")
        return root

    def test_native_events_visible_in_existing_room_feed_schema(self):
        root = self.make_root()
        ack_path = root / "ack.json"
        ack_path.write_text('{"ids":[]}', encoding="utf-8")
        result = bridge.beat(root, mode="scripted", ack_path=ack_path)
        self.assertEqual(result["engine"],
                         "concordia.environment.engines.simultaneous.Simultaneous")
        self.assertEqual(set(result["spoke"]), {"mara", "jules"})
        viewer = json.loads((root / "room" / "live.json").read_text())
        self.assertEqual(viewer["architecture_version"], "room-native-concordia-v1")
        self.assertTrue(viewer["network"]["native_concordia"])
        self.assertTrue(all(
            item["cognition"]["native_concordia"]
            for item in viewer["conversation"] if item["speaker"] != "allen"
        ))
        self.assertTrue(all("{\"mask\"" not in item["text"]
                            for item in viewer["conversation"]))
        state = json.loads((root / "room" / "state.json").read_text())
        self.assertEqual(state["cycle"], 1)
        self.assertEqual(state["messages"], 2)
        self.assertEqual(state["conversational_floor"],
                         "native_concordia_interrupt_driven")
        self.assertTrue((root / "room" / bridge.CHECKPOINT).exists())

    def test_concordia_checkpoint_survives_real_runner_restart(self):
        root = self.make_root()
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        first = bridge.beat(root, mode="scripted", ack_path=ack)
        original = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        second = bridge.beat(root, mode="scripted", ack_path=ack)
        restored = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        self.assertEqual(first["cycle"], 1)
        self.assertEqual(second["cycle"], 2)
        self.assertIn("game_master", restored)
        self.assertIn("entities", restored)
        self.assertGreaterEqual(
            restored["game_master"]["context_components"]["entity_scheduler"]["tick_count"],
            original["game_master"]["context_components"]["entity_scheduler"]["tick_count"],
        )

    def test_invalid_model_scaffolding_not_published(self):
        history = [{"text": "Hi there"}]
        self.assertEqual(
            bridge._message_from_concordia(
                'Sarah: Hi there\n{"mask":[],"timer":{"time":"5m"}}',
                "Sarah", history,
            ), "",
        )
        self.assertEqual(
            bridge._message_from_concordia(
                "Sarah: someone's hidden prompt is here", "Sarah", history,
            ), "",
        )


if __name__ == "__main__":
    unittest.main()
