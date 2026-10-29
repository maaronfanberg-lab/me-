#!/usr/bin/env python3
"""Exercised world-actions never fabricate a speaker's completed operation."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import room_causal_world_ablation as lab

class CausalWorldTests(unittest.TestCase):
    def test_suggestion_is_not_an_executed_action(self):
        w=lab.World()
        for speech in ("Let's check the breaker.","We should check the breaker.",
                       "Maybe someone could close the door.",
                       "Don't check the thermometer."):
            self.assertIsNone(w.enact("owen",speech),speech)
        self.assertFalse(w.record)
    def test_personal_committed_check_produces_verified_observation(self):
        w=lab.World()
        e=w.enact("owen","I'll check the heater breaker now.")
        self.assertIsNotNone(e)
        self.assertEqual(e["action"],"inspect")
        self.assertEqual(e["target"],"breaker")
        self.assertIn("tripped",e["detail"])
        self.assertIn("breaker",w.observe("sarah"))
    def test_world_operations_are_causal_and_persist(self):
        w=lab.World()
        blocked=w.enact("mara","I will close the door.")
        self.assertEqual(blocked["action"],"repair")
        self.assertIn("before an inspection",blocked["detail"])
        self.assertFalse(w.repaired)
        w.enact("mara","I will inspect the east door.")
        applied=w.enact("mara","I will close the door.")
        self.assertIn("airflow",applied["detail"])
        self.assertEqual(w.repaired,{"door"})
        repeat=w.enact("mara","I will close the door.")
        self.assertIn("already",repeat["detail"])
    def test_speaker_observations_are_private_but_public_results_are_shared(self):
        w=lab.World()
        self.assertNotIn(lab.WITNESSED["owen"],w.observe("sarah"))
        self.assertIn(lab.WITNESSED["sarah"],w.observe("sarah"))
        w.enact("owen","I will inspect the breaker.")
        self.assertIn("tripped",w.observe("sarah"))
    def test_no_published_fake_speech_from_world(self):
        w=lab.World()
        self.assertFalse(lab.evaluate([],w)["utterances"])
        w.enact("jules","I'll check the soil.")
        self.assertEqual(lab.evaluate([],w)["utterances"],0)
        self.assertEqual(lab.evaluate([],w)["world_actions"],1)
    def test_regular_and_causal_conditions_keep_same_persona(self):
        for who in lab.PEOPLE:
            a=lab.prompt(who,[],None)
            b=lab.prompt(who,[],lab.World())
            self.assertEqual(a[0]["content"],b[0]["content"])
            self.assertIn(lab.WITNESSED[who],str(a))
            self.assertIn(lab.WITNESSED[who],str(b))

if __name__=="__main__":
    unittest.main()
