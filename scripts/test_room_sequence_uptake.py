#!/usr/bin/env python3
"""Conversational sequence tests, including actual October 25 question-echo failure."""
from __future__ import annotations

import os
import unittest

from room_sequence_uptake import question_sequence, validate_uptake
from room_conversation_project import expression_project
from room_conversational_candidate import validate_candidate


def turn(id, speaker, text):
    return {"id": id, "speaker": speaker, "text": text}


class UptakeTests(unittest.TestCase):
    def test_question_is_not_answered_by_copying_the_question(self):
        latest = turn("mara-1", "mara", "Who do you think you are?")
        with self.assertRaisesRegex(ValueError, "question_not_answered"):
            validate_uptake(history=[latest], speaker="jules",
                            utterance="Who do you think you are?", move="answer")
        # The same words in a longer actual explanation are not prohibited.
        validate_uptake(history=[latest], speaker="jules",
                        utterance="Who do you think you are? I'm Jules, and I disagree.",
                        move="disagree")
        validate_uptake(history=[latest], speaker="jules",
                        utterance="I don't want to answer that.", move="disagree")

    def test_first_genuine_repair_may_quote_the_source_exactly(self):
        history = [turn("q1", "mara", "Who do you think you are?")]
        validate_uptake(history=history, speaker="jules",
                        utterance="Who do you think you are?", move="repair")

    def test_repeated_unresolved_repair_must_advance_conversation(self):
        history = [
            turn("q1", "mara", "Who do you think you are?"),
            turn("q2", "jules", "Who do you think you are?"),
        ]
        project = question_sequence(history, history[-1])
        self.assertEqual(project["kind"], "unanswered_question_echo")
        self.assertEqual(project["first_source_id"], "q1")
        with self.assertRaisesRegex(ValueError, "repair_sequence_not_advanced"):
            validate_uptake(history=history, speaker="mara",
                            utterance="Who do you think you are?", move="repair")
        validate_uptake(history=history, speaker="mara",
                        utterance="I meant what sort of person you hope to become.",
                        move="repair")

    def test_intervening_response_resets_question_echo_evidence(self):
        history = [
            turn("q1", "mara", "Who do you think you are?"),
            turn("a1", "jules", "I'm Jules. I want to understand you."),
            turn("q2", "mara", "Who do you think you are?"),
        ]
        project = question_sequence(history, history[-1])
        self.assertEqual(project["kind"], "question_open")
        self.assertEqual(project["echoes"], 0)
        self.assertEqual(project["first_source_id"], "q2")
        # An exact repetition after a real intervening contribution is not
        # automatically a repeated unresolved repair.
        validate_uptake(history=history, speaker="sarah",
                        utterance="Who do you think you are?", move="repair")

    def test_contiguous_question_echo_still_rejected(self):
        history = [
            turn("q1", "mara", "Who do you think you are?"),
            turn("q2", "jules", "Who do you think you are?"),
        ]
        self.assertEqual(question_sequence(history, history[-1])["echoes"], 1)
        with self.assertRaisesRegex(ValueError, "repair_sequence_not_advanced"):
            validate_uptake(history=history, speaker="sarah",
                            utterance="Who do you think you are?", move="repair")

    def test_live_prefaced_question_echo_is_not_a_new_answer(self):
        source = turn("20261028T114814385-sarah-v5", "sarah",
            "You want to be coherent and mutual understanding. "
            "Can you help me achieve that by being helpful and supportive?")
        echoed = turn("20261028T114932241-jules-v5", "jules",
            "can you help me achieve that by being helpful and supportive?")
        project = question_sequence([source, echoed], echoed)
        self.assertEqual(project["kind"], "unanswered_question_echo")
        self.assertEqual(project["echoes"], 1)
        self.assertEqual(project["first_source_id"], source["id"])
        with self.assertRaisesRegex(ValueError, "question_not_answered"):
            validate_uptake(history=[source], speaker="jules",
                utterance=echoed["text"], move="support")
        # A first repair may repeat the trouble source, but a third does not.
        validate_uptake(history=[source], speaker="jules",
            utterance=echoed["text"], move="repair")
        with self.assertRaisesRegex(ValueError, "repair_sequence_not_advanced"):
            validate_uptake(history=[source, echoed], speaker="mara",
                utterance=echoed["text"], move="repair")

    def test_real_answer_and_new_question_remain_allowed(self):
        source = turn("s1", "sarah",
            "I could use help. Can you help me by being supportive?")
        validate_uptake(history=[source], speaker="jules",
            utterance="Yes, I can help by listening first.", move="answer")
        validate_uptake(history=[source], speaker="jules",
            utterance="What kind of support would actually help?", move="repair")
        validate_uptake(history=[source], speaker="jules",
            utterance="Can you help me by being supportive? I mean: what specifically?",
            move="repair")
        self.assertEqual(question_sequence([source], source)["echoes"], 0)

    def test_no_arbitrary_topic_or_repeated_word_ban(self):
        previous = turn("m-1", "mara", "Trees? That oak has the best view.")
        for reply in (
            "Trees? That oak has the best view.",
            "I agree, that oak has the best view.",
            "No. I'm thinking of the other oak.",
        ):
            validate_uptake(history=[previous], speaker="sarah",
                            utterance=reply, move="support")

    def test_long_unchanged_statement_is_not_a_responsive_action(self):
        source = turn("mara-source", "mara",
            "I can tell that our conversation needs to address that awkwardness "
            "in our past. Let's try to have a grown-up conversation about "
            "the elephant in the room.")
        for action in ("answer", "support", "repair"):
            with self.subTest(action=action), self.assertRaisesRegex(
                    ValueError, "unchanged_full_turn_echo"):
                validate_uptake(history=[source], speaker="sarah",
                    utterance=source["text"], move=action)
        # Sharing the subject or quotation AND giving an independent meaning
        # remains legal. This is conversational action, not lexical censorship.
        validate_uptake(history=[source], speaker="sarah",
            utterance="The awkwardness matters, Mara, but I don't agree that "
                      "we have a shared past in the way you suggest.", move="disagree")
        validate_uptake(history=[source], speaker="sarah",
            utterance=source["text"] + " What particular incident do you mean?",
            move="repair")

    def test_long_statement_copy_fails_selected_candidate_preflight(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        source = turn("mara-old", "mara",
            "I think we should try new ideas, especially since we have "
            "several different perspectives and we could test one concrete "
            "hypothesis before committing to a joint project.")
        part = {"node": 2, "entity": "sarah", "role": "expression",
                "private": {"intent": {"readiness": .7}, "expression": {
                    "decision": "SPEAK", "utterance": source["text"],
                    "move": "answer", "target": "mara",
                    "semantic_terms": ["hypothesis"]
                }}}
        with self.assertRaisesRegex(ValueError, "unchanged_full_turn_echo"):
            validate_candidate(part, "sarah", [source], {"root": "river"})

    def test_generation_boundary_retries_whole_source_action_not_short_echo(self):
        from room_private_model_autonomy_legacy import _unchanged_source_action
        long_source = ("I can tell that our conversation needs to address that "
                       "awkwardness in our past. Let's try to have a grown-up "
                       "conversation about the elephant in the room.")
        compact = {"event": {"speaker": "mara", "text": long_source}}
        self.assertTrue(_unchanged_source_action(long_source, compact))
        self.assertFalse(_unchanged_source_action(
            "Mara, what particular awkwardness do you mean?", compact))
        self.assertFalse(_unchanged_source_action(
            long_source + " Could you name an example?", compact))
        self.assertFalse(_unchanged_source_action(
            "Trees? That oak has the best view.",
            {"event": {"speaker": "mara",
                       "text": "Trees? That oak has the best view."}}))
        self.assertFalse(_unchanged_source_action(
            long_source, {"event": {"speaker": "mara",
                                   "text": "What do you mean by this?"}}))

    def test_live_long_multisentence_question_echo_is_not_a_repair(self):
        source = turn("live-owen", "owen",
            "That's a fascinating question. Can you tell me more about "
            "what you think this is? What makes you think species might not "
            "change into one shape in a single species lineage?")
        echo = ("That's a fascinating question. Can you tell me more about "
                "what you think this is. What makes you think species might not "
                "change into one shape in a single species lineage?")
        for action in ("answer", "support", "repair", "clarify"):
            with self.subTest(action=action), self.assertRaisesRegex(
                    ValueError, "unchanged_full_turn_echo"):
                validate_uptake(history=[source], speaker="jules",
                                utterance=echo, move=action)
        # A real repair points to one unclear aspect, not the entire source.
        validate_uptake(history=[source], speaker="jules",
            utterance="Owen, what do you mean by one shape within a lineage?",
            move="repair")
        # Short exact questions can still be purposefully repeated as repair.
        validate_uptake(history=[turn("short-q", "mara", "Where did it go?")],
            speaker="jules", utterance="Where did it go?", move="repair")

    def test_source_identity_survives_mixed_public_conversation(self):
        history = [
            turn("q1", "mara", "Who do you think you are?"),
            {"id": "status", "speaker": "system", "text": "heartbeat"},
            turn("q2", "jules", "Who do you think you are?"),
        ]
        project = expression_project(
            entity="sarah", latest=history[-1], context=history,
            profile={"psychology_v2": {"values": ["curiosity"]}},
            private_self_state={},
        )
        self.assertEqual(project["interaction_project"]["observed_source_id"], "q2")
        self.assertEqual(project["interaction_project"]["sequence"]["first_source_id"], "q1")
        self.assertEqual(project["interaction_project"]["sequence"]["echoes"], 1)
        self.assertEqual(project["interaction_project"]["kind"], "respond_or_repair")

    def test_real_candidate_preflight_checks_action(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        data = {"node": 11, "entity": "jules", "role": "expression",
                "private": {"intent": {"readiness": 0.8}, "expression": {
                    "decision": "SPEAK", "utterance": "Who do you think you are?",
                    "move": "answer", "target": "mara", "semantic_terms": ["think"]
                }}}
        history = [turn("q1", "mara", "Who do you think you are?")]
        with self.assertRaisesRegex(ValueError, "question_not_answered"):
            validate_candidate(data, "jules", history, {"root": "experiment"})
        data["private"]["expression"]["move"] = "repair"
        validate_candidate(data, "jules", history, {"root": "experiment"})
        history.append(turn("q2", "jules", "Who do you think you are?"))
        data["entity"] = "mara"
        data["node"] = 5
        with self.assertRaisesRegex(ValueError, "repair_sequence_not_advanced"):
            validate_candidate(data, "mara", history, {"root": "experiment"})


if __name__ == "__main__":
    unittest.main()
