#!/usr/bin/env python3
"""Action-contingent floor opportunities, without novelty bans or quotas."""
from __future__ import annotations

import unittest

from room_conversational_floor import choose_next, checked_floor, ORDER, NODE


def msg(speaker, text, target="", id="m1", move="deepen"):
    return {"id": id, "speaker": speaker, "text": text,
            "cognition": {"target": target, "move_type": move}}


def config(sleep=()):
    return {"p": {
        person: {"traits": {"curiosity": .5, "extraversion": .5, "inhibition": .5}}
        for person in ORDER}, "sleeping_entities": list(sleep)}


def bus(choices=None):
    choices = choices or {}
    return {"recurrent": {person: {"thought": {"private": {"deliberation": choices.get(person, {})}}}
                          for person in ORDER}}


class FloorTests(unittest.TestCase):
    def test_direct_question_selects_recipient_not_everyone(self):
        last = msg("mara", "Sarah, where did the moths go?", "sarah")
        selected = choose_next([last], bus(), config(), {})
        self.assertEqual((selected["speaker"], selected["node"]), ("sarah", NODE["sarah"]))
        self.assertEqual(selected["reason"], "addressed_recipient")
        self.assertEqual(selected["source_id"], last["id"])

    def test_direct_refusal_or_repair_can_come_next_without_forced_agreement(self):
        last = msg("jules", "Mara, will you join the experiment?", "mara")
        selected = choose_next([last], bus({"mara": {"action": "DISAGREE"}}), config(), {})
        self.assertEqual(selected["speaker"], "mara")
        self.assertNotIn("required_action", selected)

    def test_addressed_sleeping_participant_does_not_speak(self):
        last = msg("owen", "Jules, are you awake?", "jules")
        selected = choose_next([last], bus(), config(["jules"]), {})
        self.assertNotEqual(selected["speaker"], "jules")
        self.assertEqual(selected["reason"], "open_floor_relevance")
        with self.assertRaises(ValueError):
            checked_floor({"speaker": "jules", "node": 11},
                          awake=["sarah", "mara", "owen"])

    def test_out_of_room_or_self_target_does_not_make_obligation(self):
        one = choose_next([msg("jules", "The moon looks strange.", "jules")],
                          bus(), config(), {})
        self.assertEqual(one["reason"], "voluntary_relevance")
        two = choose_next([msg("allen", "Can anybody hear me?", "unknown")],
                          bus(), config(), {})
        self.assertEqual(two["reason"], "voluntary_relevance")

    def test_hidden_generated_target_is_not_evidence_of_audible_address(self):
        # Live expression JSON always supplies a target, including for
        # statements that never address that person in public speech.
        last = msg("mara", "Category trees are curious.", "sarah")
        initiative = bus({"owen": {
            "preferred_partner": "mara", "action": "REPAIR",
            "unresolved_thread": "Did Mara mean the oak?"
        }})
        picked = choose_next([last], initiative, config(), {})
        self.assertEqual(picked["reason"], "open_floor_relevance")
        self.assertEqual(picked["speaker"], "owen")

    def test_self_initiative_matters_without_rotation_or_topic_change(self):
        personal = bus({"owen": {
            "preferred_partner": "mara", "action": "REPAIR",
            "unresolved_thread": "Did she mean the tall oak?"
        }})
        one = choose_next([msg("mara", "I meant the other tree.")],
                          personal, config(), {})
        self.assertEqual(one["speaker"], "owen")
        two = choose_next([msg("mara", "I meant the other tree.")],
                          personal, config(), {})
        self.assertEqual(one, two)
        self.assertNotIn("new_topic", one)
        self.assertNotIn("repetition_score", one)

    def test_missing_thoughts_not_speech_fabrication(self):
        out = choose_next([], {"recurrent": {}}, config(), {})
        self.assertIn(out["speaker"], ORDER)
        self.assertEqual(out["reason"], "voluntary_relevance")
        self.assertNotIn("utterance", out)

    def test_technical_fallback_selects_second_distinct_opportunity(self):
        latest = msg("mara", "Sarah, what happened to the moths?", "sarah")
        first = choose_next([latest], bus(), config(), {}, rank=0)
        second = choose_next([latest], bus(), config(), {}, rank=1)
        self.assertEqual(first["speaker"], "sarah")
        self.assertNotEqual(first["speaker"], second["speaker"])
        self.assertEqual(second["reason"], "technical_fallback_opportunity")
        self.assertEqual(first["candidate_speakers"], second["candidate_speakers"])
        self.assertEqual(second["source_id"], latest["id"])
        with self.assertRaises(ValueError):
            choose_next([latest], bus(), config(), {}, rank=5)

    def test_invalid_decision_and_nobody_awake_are_fatal(self):
        with self.assertRaises(RuntimeError):
            choose_next([], bus(), config(ORDER), {})
        with self.assertRaises(ValueError):
            checked_floor({"speaker": "sarah", "node": 5}, awake=ORDER, required=True)
        with self.assertRaises(ValueError):
            checked_floor({}, awake=ORDER, required=True)

    def test_allows_consecutive_speaker_and_productive_repetition(self):
        cfg = config(("mara", "owen", "jules"))
        same = msg("sarah", "Trees? That oak tree?", "mara")
        selected = choose_next([same], bus(), cfg, {})
        self.assertEqual(selected["speaker"], "sarah")
        self.assertNotIn("prohibit_repeating", selected)
        self.assertNotIn("forbidden_words", selected)


if __name__ == "__main__":
    unittest.main()
