#!/usr/bin/env python3
"""Action-contingent floor opportunities, without novelty bans or quotas."""
from __future__ import annotations

import unittest

from room_conversational_floor import choose_next, checked_floor, last_participant_source_id, ORDER, NODE


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
        selected = choose_next([last], bus({"owen": {"action": "DEEPEN", "preferred_partner": "sarah"}}), config(["jules"]), {})
        self.assertNotEqual(selected["speaker"], "jules")
        self.assertEqual(selected["reason"], "open_floor_relevance")
        with self.assertRaises(ValueError):
            checked_floor({"speaker": "jules", "node": 11},
                          awake=["sarah", "mara", "owen"])

    def test_out_of_room_or_self_target_does_not_make_obligation(self):
        one = choose_next([msg("jules", "The moon looks strange.", "jules")],
                          bus({"sarah": {"action": "DEEPEN"}}), config(), {})
        self.assertEqual(one["reason"], "open_floor_relevance")
        two = choose_next([msg("allen", "Can anybody hear me?", "unknown")],
                          bus({"mara": {"action": "DEEPEN"}}), config(), {})
        self.assertEqual(two["reason"], "open_floor_relevance")

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

    def test_direct_natural_language_address_without_hidden_metadata(self):
        for text in ("Mara, can you explain?", "Mara what do you think?",
                     "@Mara please weigh in.", "Can you explain, Mara?"):
            event = msg("allen", text, target="", id="a-1")
            chosen = choose_next([event], bus(), config(), {})
            self.assertEqual(chosen["speaker"], "mara", text)
            self.assertEqual(chosen["reason"], "addressed_recipient", text)

    def test_contradictory_hidden_target_never_reassigns_audible_address(self):
        event = msg("sarah", "Mara, could you help me?", target="owen", id="s1")
        result = choose_next([event], bus({"mara": {"action": "REPAIR"}}), config(), {})
        self.assertNotEqual(result["reason"], "addressed_recipient")

    def test_system_metadata_at_end_does_not_change_last_public_contribution(self):
        public = msg("mara", "Sarah, are you listening?", "sarah", id="mara-22")
        metadata = {"id": "system-23", "speaker": "system",
                    "text": "runner heartbeat", "cognition": {"target": "sarah"}}
        self.assertEqual(last_participant_source_id([public, metadata]), "mara-22")
        selected = choose_next([public, metadata], bus(), config(), {})
        self.assertEqual(selected["speaker"], "sarah")
        self.assertEqual(selected["source_id"], "mara-22")
        # Once another public participant speaks, that source is obsolete.
        self.assertEqual(last_participant_source_id([public, metadata,
                             msg("owen", "I heard her.", id="owen-24")]), "owen-24")

    def test_missing_thoughts_not_speech_fabrication(self):
        with self.assertRaisesRegex(RuntimeError, "no credible deliberated reason"):
            choose_next([], {"recurrent": {}}, config(), {})
        # A directly addressed recipient can still recognize the social bid
        # without inventing a private action or claiming understanding.
        direct = choose_next([msg("mara", "Sarah, where did it go?", "sarah")],
                             {"recurrent": {}}, config(), {})
        self.assertEqual(direct["speaker"], "sarah")

    def test_completed_turn_gives_peers_real_conversational_opportunity(self):
        cfg = config()
        cfg["p"]["jules"]["traits"] = {
            "curiosity": .99, "extraversion": .91, "inhibition": .06}
        cfg["p"]["mara"]["traits"] = {
            "curiosity": .90, "extraversion": .96, "inhibition": .15}
        cfg["p"]["sarah"]["traits"] = {
            "curiosity": .99, "extraversion": .72, "inhibition": .30}
        cfg["p"]["owen"]["traits"] = {
            "curiosity": .93, "extraversion": .62, "inhibition": .38}
        deliberations = bus({e: {"action": "DEEPEN", "preferred_partner": "allen"} for e in ORDER})
        after_jules = choose_next([msg("jules", "I finished what I meant.", id="j")],
                                  deliberations, cfg, {})
        self.assertNotEqual(after_jules["speaker"], "jules")
        # This is a status-of-the-current-turn decision, not an across-beats
        # quota or a lexical repetition score.
        self.assertNotIn("quota", after_jules)

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
        selected = choose_next([same], bus({"sarah": {
            "action": "REPAIR", "unresolved_thread": "which particular oak?"
        }}), cfg, {})
        self.assertEqual(selected["speaker"], "sarah")
        self.assertNotIn("prohibit_repeating", selected)
        self.assertNotIn("forbidden_words", selected)


if __name__ == "__main__":
    unittest.main()
