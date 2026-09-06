from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cedar_live_session import build_live_state, write_live_state
from living_world import StubBackend, WorldEngine, load_config


class CedarLiveSessionTests(unittest.TestCase):
    def test_snapshot_is_read_only_world_state_after_tick(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            config = load_config(Path(__file__).resolve().parents[1] / "world.json")
            engine = WorldEngine(
                config,
                backend=StubBackend(),
                output_dir=output,
                seed=7,
                actors_per_tick=2,
                checkpoint_every=1,
            )
            engine.step()
            state = build_live_state(
                engine,
                status="live",
                session_id="unit-session",
                model="stub",
                temperature=0.1,
            )

            self.assertEqual(state["version"], 1)
            self.assertEqual(state["status"], "live")
            self.assertEqual(state["tick"], 1)
            self.assertEqual(state["session_id"], "unit-session")
            self.assertEqual(set(state["agents"]), set(engine.agents))
            self.assertEqual(set(state["locations"]), set(engine.locations))
            self.assertTrue(any(event.get("kind") == "decision" for event in state["recent_events"]))
            self.assertIn("observational", state["read_only_note"].lower())

    def test_write_live_state_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            config = load_config(Path(__file__).resolve().parents[1] / "world.json")
            engine = WorldEngine(
                config,
                backend=StubBackend(),
                output_dir=output,
                seed=19,
                actors_per_tick=1,
                checkpoint_every=1,
            )
            state_path = output / "public.json"
            write_live_state(
                engine,
                state_path,
                status="starting",
                session_id="unit-start",
                model="stub",
                temperature=0.1,
            )
            parsed = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["status"], "starting")
            self.assertEqual(parsed["tick"], 0)


if __name__ == "__main__":
    unittest.main()
