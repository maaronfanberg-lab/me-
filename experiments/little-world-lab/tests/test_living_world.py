import json
import tempfile
import unittest
from pathlib import Path

from living_world import StubBackend, WorldEngine, load_config


HERE = Path(__file__).resolve().parents[1]
CONFIG = HERE / "world.json"


class FixedBackend:
    def __init__(self, proposal):
        self.proposal = proposal

    def choose_action(self, **kwargs):
        return dict(self.proposal)


class TalkBackend:
    def choose_action(self, *, agent, observation, tick):
        others = observation["co_located_agents"]
        if others:
            return {"type": "talk", "target": others[0], "utterance": f"message-{agent.name}-{tick}"}
        return {"type": "observe"}


class LittleWorldTests(unittest.TestCase):
    def engine(self, output, backend=None, **kwargs):
        return WorldEngine(
            load_config(CONFIG),
            backend or StubBackend(),
            Path(output),
            seed=kwargs.get("seed", 7),
            actors_per_tick=kwargs.get("actors_per_tick", 2),
            checkpoint_every=kwargs.get("checkpoint_every", 2),
        )

    def test_stub_run_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            e1 = self.engine(a)
            e2 = self.engine(b)
            m1 = e1.run(10)
            m2 = e2.run(10)
            self.assertEqual(m1, m2)
            self.assertEqual(
                (Path(a) / "events.jsonl").read_text(),
                (Path(b) / "events.jsonl").read_text(),
            )

    def test_invalid_move_cannot_mutate_location(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d, FixedBackend({"type": "move", "location": "clinic"}), actors_per_tick=8)
            before = {name: agent.location for name, agent in e.agents.items()}
            e.step()
            self.assertEqual(e.agents["Theo"].location, before["Theo"])
            rejected = [json.loads(x) for x in (Path(d) / "events.jsonl").read_text().splitlines()]
            self.assertTrue(any(x["kind"] == "proposal_rejected" for x in rejected))

    def test_talk_requires_colocation(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d, FixedBackend({"type": "talk", "target": "Arden", "utterance": "hello"}), actors_per_tick=8)
            e.step()
            actions = [json.loads(x) for x in (Path(d) / "events.jsonl").read_text().splitlines()]
            mira_action = next(x for x in actions if x.get("kind") == "action" and x.get("actor") == "Mira")
            self.assertEqual(mira_action["action"]["type"], "observe")

    def test_private_memory_not_exposed_to_other_agent(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d)
            e._remember("Mira", "private orchid note", importance=9)
            mira = e.observation_for("Mira")
            theo = e.observation_for("Theo")
            self.assertIn("private orchid note", [m["text"] for m in mira["relevant_private_memories"]])
            self.assertNotIn("private orchid note", [m["text"] for m in theo["relevant_private_memories"]])

    def test_incident_is_observed_only_at_location(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d, FixedBackend({"type": "observe"}), actors_per_tick=1)
            e.run(3)
            self.assertTrue(any("Strong wind" in m.text for m in e.agents["Mira"].memories))
            self.assertFalse(any("Strong wind" in m.text for m in e.agents["Theo"].memories))

    def test_valid_talk_is_observed_but_does_not_move_relationship_state(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d, TalkBackend(), actors_per_tick=8)
            e.step()
            talk_events = []
            for line in (Path(d) / "events.jsonl").read_text().splitlines():
                item = json.loads(line)
                if item.get("kind") == "action" and item.get("action", {}).get("type") == "talk":
                    talk_events.append(item)
            self.assertTrue(talk_events)
            event = talk_events[0]
            actor = event["actor"]
            target = event["action"]["target"]
            self.assertNotIn(target, e.agents[actor].relationships)
            self.assertTrue(any(actor in m.text for m in e.agents[target].memories))

    def test_checkpoint_roundtrip_preserves_state(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as resumed:
            e = self.engine(d)
            e.run(6)
            restored = WorldEngine.from_checkpoint(Path(d) / "checkpoint.json", StubBackend(), Path(resumed))
            self.assertEqual(restored.tick, e.tick)
            self.assertEqual(restored.locations, e.locations)
            self.assertEqual(
                {k: v.location for k, v in restored.agents.items()},
                {k: v.location for k, v in e.agents.items()},
            )
            self.assertEqual(
                {k: len(v.memories) for k, v in restored.agents.items()},
                {k: len(v.memories) for k, v in e.agents.items()},
            )

    def test_repeated_utterance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.engine(d, FixedBackend({"type": "talk", "target": "Ivo", "utterance": "same"}), actors_per_tick=8)
            e.step()
            e.step()
            rows = [json.loads(x) for x in (Path(d) / "events.jsonl").read_text().splitlines()]
            self.assertTrue(any(x.get("kind") == "proposal_rejected" and x.get("reason") == "repeated_utterance" for x in rows))


if __name__ == "__main__":
    unittest.main()
