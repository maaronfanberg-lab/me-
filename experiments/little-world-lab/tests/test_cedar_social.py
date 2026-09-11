from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cedar_world import CedarWorldEngine
from living_world import StubBackend, load_config


class CedarSocialTests(unittest.TestCase):
    def make_engine(self, output: Path) -> CedarWorldEngine:
        config = load_config(Path(__file__).resolve().parents[1] / "world.json")
        return CedarWorldEngine(
            config,
            backend=StubBackend(),
            output_dir=output,
            seed=7,
            actors_per_tick=2,
            checkpoint_every=1,
        )

    def test_meaningful_talk_builds_connection_and_reciprocity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = self.make_engine(Path(temp))
            lena = engine.agents["Lena"]
            sol = engine.agents["Sol"]
            lena.location = sol.location = "kitchen"

            before_connection = engine.social_state["Lena"]["connection"]
            before_energy = lena.energy
            engine.tick = 1
            engine._resolve(
                lena,
                {
                    "type": "talk",
                    "target": "Sol",
                    "utterance": "Sol, can we coordinate food so the kitchen wastes less?",
                },
                None,
            )

            self.assertGreater(engine.social_state["Lena"]["connection"], before_connection)
            self.assertGreater(lena.energy, before_energy - 1.0)
            self.assertTrue(engine.social_state["Lena"]["recent_social"][-1]["meaningful"])

            engine.tick = 2
            engine._resolve(
                sol,
                {
                    "type": "talk",
                    "target": "Lena",
                    "utterance": "Lena, yes, let's coordinate food and reduce waste together.",
                },
                None,
            )
            self.assertTrue(engine.social_state["Sol"]["recent_social"][-1]["reciprocal"])

    def test_needed_help_conserves_helper_energy_and_tracks_mutuality(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = self.make_engine(Path(temp))
            lena = engine.agents["Lena"]
            sol = engine.agents["Sol"]
            lena.location = sol.location = "kitchen"
            lena.energy = 50.0
            sol.energy = 10.0

            engine.tick = 1
            engine._resolve(lena, {"type": "help", "target": "Sol"}, None)
            self.assertGreater(lena.energy, 47.0)
            self.assertGreater(sol.energy, 10.0)
            self.assertTrue(engine.social_state["Lena"]["recent_social"][-1]["meaningful"])

            sol.energy = 50.0
            lena.energy = 20.0
            engine.tick = 2
            engine._resolve(sol, {"type": "help", "target": "Lena"}, None)
            self.assertTrue(engine.social_state["Sol"]["recent_social"][-1]["reciprocal"])

    def test_zero_energy_resident_cannot_walk_and_recovers_by_resting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = self.make_engine(Path(temp))
            lena = engine.agents["Lena"]
            lena.location = "kitchen"
            lena.energy = 0.0
            action, note = engine._validate(
                lena, {"type": "move", "location": "square"}
            )
            self.assertEqual(action, {"type": "rest"})
            self.assertEqual(note, "insufficient_energy_for_move")

    def test_social_state_survives_checkpoint_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine = self.make_engine(output)
            engine.social_state["Jun"]["connection"] = 73.5
            engine.social_state["Jun"]["loneliness"] = 11.0
            engine.save_checkpoint()

            restored = CedarWorldEngine.from_checkpoint(
                output / "checkpoint.json",
                backend=StubBackend(),
                output_dir=output,
            )
            self.assertEqual(restored.social_state["Jun"]["connection"], 73.5)
            self.assertEqual(restored.social_state["Jun"]["loneliness"], 11.0)


if __name__ == "__main__":
    unittest.main()
