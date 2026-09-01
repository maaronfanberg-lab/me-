#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from endogenous_workspace_tape import build_tape, read_replay_turns


class FakeNode:
    def __init__(self, content, importance, created, node_type="event"):
        self.content = content
        self.importance = importance
        self.created = created
        self.node_type = node_type


class FakeAgent:
    def __init__(self, name, nodes):
        self.name = name
        self.brain = SimpleNamespace(memory_stream=SimpleNamespace(seq_nodes=nodes))


class EndogenousWorkspaceTapeTests(unittest.TestCase):
    def test_build_tape_recovers_memory_metadata_without_writes(self):
        memory = "Emily observes a message from Olivia: hello"
        agent = FakeAgent("Emily", [FakeNode(memory, 80, 4)])
        turns = [
            {
                "agent": "Emily",
                "time_step": 5,
                "observation": {"inbox": [{"content": "hello"}]},
                "retrieved_memories": [memory],
            }
        ]
        tape = build_tape(turns, [agent], source="fixture.json")
        self.assertEqual(tape["metadata"]["tick_count"], 1)
        candidate = tape["ticks"][0]["candidates"][0]
        self.assertTrue(candidate["metadata_recovered"])
        self.assertAlmostEqual(candidate["importance"], 0.8)
        self.assertEqual(candidate["retrieval_score"], 1.0)
        self.assertEqual(tape["ticks"][0]["observation"], "hello")

    def test_unmatched_replay_memory_is_marked_not_fabricated(self):
        agent = FakeAgent("Olivia", [])
        turns = [
            {
                "agent": "Olivia",
                "time_step": 9,
                "observation": {"inbox": [{"content": "hi"}]},
                "retrieved_memories": ["old retrieved text"],
            }
        ]
        tape = build_tape(turns, [agent])
        candidate = tape["ticks"][0]["candidates"][0]
        self.assertFalse(candidate["metadata_recovered"])
        self.assertEqual(candidate["importance"], 0.0)
        self.assertEqual(tape["metadata"]["unmatched_memory_count"], 1)

    def test_jsonl_reader_extracts_only_turn_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replay.jsonl"
            path.write_text(
                '{"type":"session_start","opening_turn":null}\n'
                '{"type":"turn","turn":{"agent":"Emily","time_step":2}}\n'
                '{"type":"session_end","summary":{}}\n'
            )
            turns = read_replay_turns(path)
        self.assertEqual(turns, [{"agent": "Emily", "time_step": 2}])


if __name__ == "__main__":
    unittest.main()
