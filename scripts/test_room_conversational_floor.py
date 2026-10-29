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
    def test_hey_mara_invitation_has_one_audible_addressee(self):
        history = [msg("jules",
            "Hey Mara, could we collaborate on a project together?",
            target="", id="jules-offer-1")]
        decision = choose_next(history, bus(), config(), {})
        self.assertEqual(decision["speaker"], "mara")
        self.assertEqual(decision["reason"], "addressed_recipient")
        self.assertEqual(decision["source_id"], "jules-offer-1")

    def test_live_mid_utterance_vocative_selects_actual_recipient(self):
        from room_conversational_floor import is_directed, audible_addressee
        observed = msg(
            "owen",
            "That's an interesting observation - I didn't notice anything about the microphone cable, so I'm curious, Mara, did you notice anything unusual when you moved the cable?",
            "sarah", id="20261029-choir-owen")
        self.assertTrue(is_directed(observed, "mara"))
        self.assertFalse(is_directed(observed, "sarah"))
        self.assertEqual(audible_addressee("owen", observed["text"]), "mara")
        decision = choose_next([observed], bus(), config(), {})
        self.assertEqual((decision["speaker"], decision["reason"]),
                         ("mara", "addressed_recipient"))
        # A name mentioned in a third-person claim is not an invitation.
        self.assertIsNone(audible_addressee(
            "owen", "I think Sarah, Mara, and Jules all remember it differently."))
        self.assertIsNone(audible_addressee(
            "owen", "I spoke to Mara, did you hear what she said?"))
        # The same speaker cannot address themselves through this mechanism.
        self.assertFalse(is_directed(msg("mara", "I'm curious, Mara, did you see?"), "mara"))

    def test_live_vocative_overrides_hidden_partner(self):
        from room_conversational_floor import is_directed
        source = msg("jules",
                     "Hey Sarah, can you tell me about the new exercise idea you want to explore?",
                     "mara", id="20261028T120004873-jules-v5")
        self.assertTrue(is_directed(source, "sarah"))
        self.assertFalse(is_directed(source, "mara"))
        selected = choose_next([source], bus(), config(), {})
        self.assertEqual(selected["speaker"], "sarah")
        self.assertEqual(selected["reason"], "addressed_recipient")

    def test_hidden_partner_is_not_an_audible_invitation(self):
        from room_conversational_floor import is_directed
        source = msg("jules", "An owl flew past the window.", "mara")
        self.assertFalse(is_directed(source, "mara"))
        self.assertFalse(is_directed(source, "sarah"))

    def test_audible_addressee_controls_public_target(self):
        from room_conversational_floor import audible_addressee
        self.assertEqual(audible_addressee("jules",
            "Hey Sarah, can you explain your proposal?"), "sarah")
        self.assertIsNone(audible_addressee("jules",
            "I think Sarah made an interesting point about Mara."))
        self.assertIsNone(audible_addressee("sarah",
            "Hey Sarah, can you explain?"))
        self.assertIsNone(audible_addressee("jules",
            "Hey Sarah, can you explain?", ("mara", "owen")))
        self.assertEqual(audible_addressee("jules",
            "Mara, I am interested in your example."), "mara")

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

    def test_vocative_is_not_confused_with_a_person_being_discussed(self):
        from room_conversational_floor import is_directed
        question = msg("allen", "Mara, why did you disagree with Sarah?",
                       target="", id="allen-question")
        self.assertTrue(is_directed(question, "mara"))
        self.assertFalse(is_directed(question, "sarah"))
        decision = choose_next([question], bus(), config(), {})
        self.assertEqual(decision["speaker"], "mara")
        self.assertEqual(decision["reason"], "addressed_recipient")
        self.assertEqual(decision["source_id"], "allen-question")
        # Mentioned third parties do not acquire a compulsory turn.
        about = msg("allen", "What did Mara say about Sarah?", id="allen-about")
        self.assertFalse(is_directed(about, "mara"))
        self.assertFalse(is_directed(about, "sarah"))

    def test_direct_natural_language_address_without_hidden_metadata(self):
        for text in ("Mara, can you explain?", "Mara what do you think?",
                     "@Mara please weigh in.", "Can you explain, Mara?"):
            event = msg("allen", text, target="", id="a-1")
            chosen = choose_next([event], bus(), config(), {})
            self.assertEqual(chosen["speaker"], "mara", text)
            self.assertEqual(chosen["reason"], "addressed_recipient", text)

    def test_contradictory_hidden_target_preserves_audible_address(self):
        event = msg("sarah", "Mara, could you help me?", target="owen", id="s1")
        result = choose_next([event], bus({"mara": {"action": "REPAIR"}}), config(), {})
        self.assertEqual(result["speaker"], "mara")
        self.assertEqual(result["reason"], "addressed_recipient")

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
        with self.assertRaisesRegex(RuntimeError, "no observed utterance or deliberated social bid"):
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

    def test_single_pass_model_without_thought_objects_can_select_real_uptake(self):
        # Actual production autonomy intentionally returns None for all
        # separate thought roles. This was the exact live failure condition
        # on 2026-10-25, not an artificial prompt-quality problem.
        history = [
            msg("jules", "Could somebody explain what happened?", id="j1"),
            msg("mara", "I saw it differently.", id="m2"),
        ]
        selected = choose_next(history, bus(), config(), {})
        self.assertEqual(selected["speaker"], "jules")
        self.assertEqual(selected["reason"], "open_floor_uptake")
        self.assertEqual(selected["source_id"], "m2")
        self.assertNotIn("invented_intent", selected)
        self.assertNotIn("topic_reset", selected)

    def test_unclaimed_floor_does_not_crown_static_most_extraverted_voice(self):
        # In live single-pass mode there are NO separate deliberated bids.
        # Strong fixed personality numbers are not observable floor bids;
        # they must not select the same speaker in every neutral exchange.
        cfg = config()
        cfg["p"]["jules"]["traits"] = {
            "curiosity": 1.0, "extraversion": 1.0, "inhibition": 0.0}
        for name in ("sarah", "owen", "mara"):
            cfg["p"][name]["traits"] = {
                "curiosity": .15, "extraversion": .15, "inhibition": .9}
        picks = [
            choose_next([msg("mara", "The light changed in the forest.",
                             id=f"open-floor-neutral-{i}")],
                        bus(), cfg, {})["speaker"]
            for i in range(96)
        ]
        self.assertGreaterEqual(len(set(picks)), 3, picks[:12])
        # These are source-grounded independent opportunities, not quotas.
        sample = choose_next([msg("mara", "The light changed in the forest.",
                                  id="repeat-stable")], bus(), cfg, {})
        self.assertEqual(sample, choose_next(
            [msg("mara", "The light changed in the forest.",
                 id="repeat-stable")], bus(), cfg, {}))

    def test_monolithic_autonomy_explicitly_skips_thought_generation(self):
        import room_private_model_autonomy as one_pass
        self.assertIsNone(one_pass.run("thought", {"entity": "mara"}))
        self.assertIsNone(one_pass.run("comprehension", {"entity": "mara"}))

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



    def test_private_scene_fact_relevance_selects_question_answerer_not_quota(self):
        import os
        from unittest.mock import patch
        from room_conversational_floor import _fact_opportunity
        source = msg("mara", "Has anyone checked the warm breaker panel?", id="lantern-panel")
        with patch.dict(os.environ, {"ROOM_SCENE_RELEVANCE_FLOOR":"1"}):
            chosen = choose_next([source], bus(), config(), {}, cycle=35233)
            self.assertEqual(chosen["speaker"], "owen", chosen)
            self.assertGreater(_fact_opportunity("owen", source, [source], 35233), 0)
            self.assertEqual(_fact_opportunity("owen", source, [source], 35211), 0)
            self.assertNotEqual(
                choose_next([source],bus(),config(["owen"]),{},cycle=35233)["speaker"],
                "owen")
            addressed = msg("mara", "Jules, did you see the breaker panel?", id="explicit")
            directed = choose_next([addressed], bus(), config(), {}, cycle=35233)
            self.assertEqual(directed["speaker"], "jules")
            voiced = msg("owen", "I noticed the warm breaker panel.", id="owen-observed")
            self.assertEqual(
                _fact_opportunity("owen", source, [voiced,source], 35233),0)
            assert "quota" not in chosen
        with patch.dict(os.environ, {"ROOM_SCENE_RELEVANCE_FLOOR":"0"}):
            no_opt_in = choose_next([source],bus(),config(),{},cycle=35233)
            self.assertEqual(no_opt_in,choose_next([source],bus(),config(),{},cycle=None))


    def test_unshared_eyewitness_fact_can_answer_open_group_question(self):
        import os
        from unittest.mock import patch
        earlier = [
            msg("mara", "The generator fuel was checked at noon.", id="m1"),
            msg("sarah", "The lanterns flickered and one row went dark.", id="s2"),
        ]
        open_question = msg("sarah", "Does anyone have another clue about the outage?", id="s3")
        with patch.dict(os.environ, {"ROOM_SCENE_RELEVANCE_FLOOR":"1"}):
            from room_conversational_floor import _fact_opportunity
            assert _fact_opportunity("mara", open_question, earlier+[open_question], 35245) == 0
            assert _fact_opportunity("owen", open_question, earlier+[open_question], 35245) > 0
            assert _fact_opportunity("jules", open_question, earlier+[open_question], 35245) > 0
            selected = choose_next(earlier+[open_question], bus(), config(), {},cycle=35245)
            self.assertIn(selected["speaker"], ("owen","jules"))
            addressed = msg("sarah","Mara, can you tell me more?", id="s4")
            self.assertEqual(
                choose_next(earlier+[addressed],bus(),config(),{},cycle=35233)["speaker"],
                "mara")

    def test_causal_trial_unshared_private_fact_gets_relevant_open_floor(self):
        import os
        from unittest.mock import patch
        from room_conversational_floor import _fact_opportunity
        question = msg("mara",
                       "What did the folded cardboard cover on the rear grille?",
                       id="planetarium-open-question")
        question["beat_id"] = "beat-test-036558"
        with patch.dict(os.environ, {"ROOM_SCENE_RELEVANCE_FLOOR":"1",
                                     "ROOM_CAUSAL_WORLD_EXPERIMENT":"1"}):
            self.assertGreater(_fact_opportunity(
                "jules", question, [question], 36559), .70)
            chosen = choose_next([question], bus(), config(), {}, cycle=36559)
            self.assertEqual(chosen["speaker"], "jules", chosen)
            self.assertNotIn("required_action", chosen)
            # Publicly speaking the clue consumes its information advantage;
            # the referee never pretends that a mere plan disclosed it.
            witnessed = msg("jules",
                "I noticed folded cardboard partly covering the projector rear ventilation grille.",
                id="jules-disclosed")
            witnessed["beat_id"] = "beat-test-036557"
            self.assertEqual(_fact_opportunity(
                "jules", question, [witnessed, question], 36559), 0)
            after = choose_next(
                [witnessed, question], bus(), config(), {}, cycle=36559)
            self.assertNotEqual(after["speaker"], "jules")
            # Allen's actual question must not be redirected to the
            # fictional scene, even when it shares a distinctive noun.
            visitor = msg("allen", "What about the folded cardboard?",
                          id="allen-question")
            with patch("room_conversational_floor._fact_opportunity",
                       side_effect=AssertionError("visitor was displaced")):
                choose_next([visitor], bus(), config(), {}, cycle=36559)


if __name__ == "__main__":
    unittest.main()
