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

    def test_literal_present_action_starts_verified_work_without_instant_success(self):
        # Some live agent outputs contain an action and valid scheduler JSON
        # but no optional structured work. Only a direct action is actionable.
        step = [{"actions": {"Sarah":
                 'Sarah: I quietly organize my bookshelf.\n'
                 '{"mask":["chat.allen"],"timer":{"time":"15m"}}'}}]
        room_life.advance(self.world, self.cfg, 100, step)
        task = self.world["lives"]["sarah"]["task"]
        self.assertEqual((task["verb"], task["object"]), ("organize", "bookshelf"))
        self.assertEqual(self.world["objects"]["bookshelf"]["organized_sets"], 0)
        room_life.advance(self.world, self.cfg, 101, [])
        room_life.advance(self.world, self.cfg, 102, [])
        self.assertEqual(self.world["objects"]["bookshelf"]["organized_sets"], 1)
        self.assertEqual(self.world["lives"]["sarah"]["completed"], 1)
        self.assertEqual(
            [e["kind"] for e in self.world["events"]],
            ["work_started", "work_completed"],
        )

    def test_literal_action_bridge_does_not_turn_intentions_into_facts(self):
        disallowed = (
            "I will inspect the notebook.",
            "I'd like to inspect the notebook.",
            "I inspected the notebook.",
            "I might inspect the notebook.",
            "I wish I could inspect the notebook.",
            "I\u0027ll inspect the notebook and discover a secret.",
            "I inspect the notebook and discover a secret.",
            "Mara: I inspect the notebook.",
            "I inspect the window and test the samples.",
        )
        for action in disallowed:
            with self.subTest(action=action):
                self.assertIsNone(room_life._literal_work_from_action(action, "Sarah"))
        self.assertEqual(
            room_life._literal_work_from_action("I inspect the notebook.", "Sarah"),
            {"verb": "inspect", "object": "notebook"},
        )
        for commitment in (
            "I choose to inspect the notebook quietly.",
            "I decide to inspect the notebook quietly.",
            "I'll quietly inspect my notebook.",
            "I'm going to inspect the notebook quietly.",
        ):
            with self.subTest(commitment=commitment):
                self.assertEqual(
                    room_life._literal_work_from_action(commitment, "Sarah"),
                    {"verb": "inspect", "object": "notebook"},
                )
        self.assertEqual(
            room_life._literal_work_from_action("I'll quietly organize my bookshelf.", "Sarah"),
            {"verb": "organize", "object": "bookshelf"},
        )
        self.assertEqual(
            room_life._literal_work_from_action("I write in my notebook.", "Sarah"),
            {"verb": "write", "object": "notebook"},
        )

    def test_invalid_control_or_explicit_bad_work_cannot_use_literal_fallback(self):
        malformed = [{"actions": {"Mara":
                     'I inspect the notebook.\n{"mask":[]}'}}]
        room_life.advance(self.world, self.cfg, 100, malformed)
        self.assertIsNone(self.world["lives"]["mara"]["task"])
        self.assertFalse(self.world["events"])
        invalid = [{"actions": {"Mara":
                  'I inspect the notebook.\n{"mask":[],"timer":{"time":"15m"},'
                  '"work":{"verb":"invent","object":"outside"}}'}}]
        room_life.advance(self.world, self.cfg, 101, invalid)
        self.assertIsNone(self.world["lives"]["mara"]["task"])
        self.assertFalse(self.world["events"])

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

    def test_short_goal_is_not_mistaken_for_a_durable_project(self):
        old = self.world["lives"]["owen"]["goal"]
        room_life.advance(self.world, self.cfg, 100,
                          self.act("owen", "inspect", "bookshelf", "reorganize"))
        self.assertEqual(self.world["lives"]["owen"]["goal"], old)
        room_life.advance(self.world, self.cfg, 101,
                          self.act("owen", "prepare", "instruments",
                                   "Make the instruments ready for our test"))
        self.assertEqual(self.world["lives"]["owen"]["goal"], old)
        self.assertEqual(self.world["lives"]["owen"]["task"]["verb"], "inspect")

    def test_malformed_action_control_cannot_change_world(self):
        payload = [{"actions": {
            "Sarah": '\\n{"work":{"verb":"write","object":"notebook"}}'
        }}]
        room_life.advance(self.world, self.cfg, 100, payload)
        self.assertIsNone(self.world["lives"]["sarah"]["task"])
        self.assertEqual(self.world["events"], [])

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

    def test_migrates_old_copied_boilerplate_without_erasing_work(self):
        self.world["lives"]["sarah"].update(
            {"goal": "my own specific project", "goal_source": "agent_chosen",
             "completed": 7})
        self.world["lives"]["owen"].update(
            {"goal": "reorganize", "goal_source": "agent_chosen"})
        self.world["lives"]["jules"].update(
            {"goal": "Investigate a previously recorded adaptation in the specimens",
             "goal_source": "agent_chosen"})
        count = room_life.repair_profile_goals(self.world, self.cfg)
        self.assertEqual(count, 2)
        self.assertEqual(self.world["lives"]["sarah"]["goal"],
                         "Understand real causal mechanisms")
        self.assertEqual(self.world["lives"]["sarah"]["completed"], 7)
        self.assertEqual(self.world["lives"]["owen"]["goal"],
                         "Test a hypothesis")
        self.assertEqual(self.world["lives"]["jules"]["goal"],
                         "Investigate a previously recorded adaptation in the specimens")
        self.assertEqual(room_life.repair_profile_goals(self.world, self.cfg), 0)

    def test_different_characters_have_distinct_profile_sourced_goals(self):
        goals = [self.world["lives"][name]["goal"] for name in room_life.PEOPLE]
        self.assertEqual(len(set(goals)), len(room_life.PEOPLE))
        self.assertTrue(all(self.world["lives"][name]["goal_source"]
                            == "existing_character_profile" for name in room_life.PEOPLE))


if __name__ == "__main__":
    unittest.main()
