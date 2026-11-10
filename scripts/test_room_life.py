#!/usr/bin/env python3
"""Unit/causal tests for verifiable agent lives used by real Concordia."""
import json
import unittest
import room_life


class RoomLifeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"p": {
            "sarah": {"psychology_v2": {"motives": ["Understand real causal mechanisms"]}},
            "mara": {"psychology_v2": {"motives": ["Notice changing relationships"]}},
            "owen": {"psychology_v2": {"motives": ["Test a hypothesis"]}},
            "jules": {"psychology_v2": {"motives": ["Investigate unexpected details"]}},
        }}
        self.world = room_life.initial(self.cfg, 100)

    @staticmethod
    def act(person, verb="write", object_name="notebook", goal="Keep a grounded record"):
        return [{"actions": {
            person.capitalize(): ('\n{"mask":[],"timer":{"time":"15m"},'
                                  '"work":{"verb":"' + verb + '","object":"' +
                                  object_name + '","goal":"' + goal + '"}}'),
        }}]

    def test_no_public_chatter_is_needed_for_progress(self):
        self.world = room_life.advance(self.world, self.cfg, 100,
                                       self.act("sarah"))
        self.assertEqual(self.world["lives"]["sarah"]["task"]["progress"], 0)
        self.world = room_life.advance(self.world, self.cfg, 101, [])
        self.assertEqual(self.world["lives"]["sarah"]["task"]["progress"], 1)
        self.world = room_life.advance(self.world, self.cfg, 102, [])
        self.assertEqual(self.world["objects"]["notebook"]["written_pages"], 1)
        self.assertEqual(self.world["lives"]["sarah"]["completed"], 1)
        self.assertIsNone(self.world["lives"]["sarah"]["task"])
        self.assertTrue(any(e["kind"] == "work_completed" for e in self.world["events"]))
        self.assertFalse(any("speech" in e for e in self.world["events"]))

    def test_no_instant_fabricated_completion_and_no_double_commit(self):
        w = room_life.advance(self.world, self.cfg, 100, self.act("jules", "test", "instruments"))
        self.assertEqual(w["objects"]["instruments"]["tests"], 0)
        old = json.dumps(w, sort_keys=True)
        self.assertIs(room_life.advance(w, self.cfg, 100, self.act("jules", "test", "instruments")), w)
        self.assertEqual(json.dumps(w, sort_keys=True), old)
        for tick in [101, 102]:
            room_life.advance(w, self.cfg, tick, [])
            self.assertEqual(w["objects"]["instruments"]["tests"], 0)
        room_life.advance(w, self.cfg, 103, [])
        self.assertEqual(w["objects"]["instruments"]["tests"], 1)

    def test_invalid_affordances_do_not_change_world(self):
        room_life.advance(self.world, self.cfg, 100,
                          self.act("mara", "invent facts", "outside world"))
        self.assertEqual(self.world["lives"]["mara"]["completed"], 0)
        self.assertIsNone(self.world["lives"]["mara"]["task"])
        self.assertEqual(self.world["events"], [])

    def test_a_commitment_cannot_be_overwritten_by_new_prompt(self):
        room_life.advance(self.world, self.cfg, 100, self.act("owen", "measure", "window"))
        room_life.advance(self.world, self.cfg, 101, self.act("owen", "write", "board"))
        self.assertEqual(self.world["lives"]["owen"]["task"]["verb"], "measure")
        self.assertEqual(self.world["objects"]["board"]["written_pages"], 0)

    def test_reflections_are_private_tentative_and_require_real_evidence(self):
        room_life.advance(self.world, self.cfg, 100, self.act("sarah"))
        fake = [{"actions": {"Sarah": '\n{"mask":[],"timer":{"time":"5m"},'
                 '"reflection":{"text":"An unseen event has definitely happened.",'
                 '"evidence":["fiction-99"]}}'}}]
        room_life.advance(self.world, self.cfg, 101, fake)
        self.assertEqual(self.world["lives"]["sarah"]["reflections"], [])
        event_id = self.world["events"][0]["id"]
        grounded = [{"actions": {"Sarah": '\n{"mask":[],"timer":{"time":"5m"},'
                    '"reflection":{"text":"This may be worth following up.",'
                    '"evidence":["' + event_id + '"]}}'}}]
        room_life.advance(self.world, self.cfg, 102, grounded)
        self.assertEqual(self.world["lives"]["sarah"]["reflections"][0]["status"], "tentative")
        self.assertEqual(self.world["lives"]["sarah"]["reflections"][0]["evidence"], [event_id])
        self.assertNotIn("reflections", room_life.public_snapshot(self.world)["activities"]["sarah"])

    def test_memory_retrieval_uses_witnessed_evidence_and_retains_source(self):
        room_life.advance(self.world, self.cfg, 100, self.act("jules", "inspect", "plant"))
        room_life.advance(self.world, self.cfg, 101, [])
        room_life.advance(self.world, self.cfg, 102, [])
        found = room_life.retrieve(self.world, "owen", "plant observations", limit=3)
        self.assertTrue(found)
        self.assertTrue(all(v["id"].startswith("life-") for v in found))
        ctx = room_life.context(self.world, "jules")
        self.assertIn("Your current goal", ctx)
        self.assertIn("plant", ctx)
        self.assertIn("verified", ctx.lower())
        self.assertNotIn("I have discovered", ctx)

    def test_illegal_cycle_gap_fails_instead_of_erasing_history(self):
        room_life.advance(self.world, self.cfg, 100, [])
        with self.assertRaises(ValueError):
            room_life.advance(self.world, self.cfg, 102, [])
        with self.assertRaises(ValueError):
            room_life.advance(self.world, self.cfg, 99, [])

    def test_different_characters_have_distinct_profile_sourced_goals(self):
        goals = [self.world["lives"][name]["goal"] for name in room_life.PEOPLE]
        self.assertEqual(len(set(goals)), len(room_life.PEOPLE))
        self.assertTrue(all(self.world["lives"][name]["goal_source"]
                            == "existing_character_profile" for name in room_life.PEOPLE))


if __name__ == "__main__":
    unittest.main()
