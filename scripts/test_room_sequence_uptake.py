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

    def test_no_arbitrary_topic_or_repeated_word_ban(self):
        previous = turn("m-1", "mara", "Trees? That oak has the best view.")
        for reply in (
            "Trees? That oak has the best view.",
            "I agree, that oak has the best view.",
            "No. I'm thinking of the other oak.",
        ):
            validate_uptake(history=[previous], speaker="sarah",
                            utterance=reply, move="support")

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
