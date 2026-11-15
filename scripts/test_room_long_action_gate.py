#!/usr/bin/env python3
"""Witnessed Room long-question echo regression, not a topic or lexical ban."""
from __future__ import annotations
import json
import os
import unittest

from room_sequence_uptake import validate_uptake
from room_conversational_candidate import validate_candidate
import room_private_model_autonomy_legacy as model

LONG_QUESTION = (
    "That's a fascinating question. Can you tell me more about what you "
    "think this is? What makes you think species might not change into "
    "one shape in a single species lineage?"
)
SOURCE = {"id":"owen-live-evolution-q", "speaker":"owen", "text":LONG_QUESTION}


class LongActionGate(unittest.TestCase):
    def test_no_full_multisentence_question_copy_as_answer_or_repair(self):
        altered_punctuation = LONG_QUESTION.replace("this is?", "this is.")
        for move in ("answer","repair","support","clarify"):
            with self.subTest(move=move), self.assertRaisesRegex(
                    ValueError,"unchanged_full_turn_echo"):
                validate_uptake(history=[SOURCE],speaker="jules",
                                utterance=altered_punctuation,move=move)
        validate_uptake(history=[SOURCE],speaker="jules",
                        utterance="Owen, what do you mean by one shape?",
                        move="repair")
        validate_uptake(
            history=[{"id":"short","speaker":"owen","text":"Where did it go?"}],
            speaker="jules",utterance="Where did it go?",move="repair")

    def test_nonquestion_copy_requires_own_contribution(self):
        prior={"id":"mara-previous","speaker":"mara",
            "text":"I think the river's water level changed rapidly because "
                   "the rainstorms altered the runoff around the watershed."}
        with self.assertRaisesRegex(ValueError,"unchanged_full_turn_echo"):
            validate_uptake(history=[prior],speaker="sarah",
                            utterance=prior["text"],move="answer")
        validate_uptake(history=[prior],speaker="sarah",
                        utterance=prior["text"] +
                        " Did you compare measurements upstream?",
                        move="repair")
        validate_uptake(history=[prior],speaker="sarah",
                        utterance="Mara, do you have the upstream measurements?",
                        move="repair")

    def test_generator_uses_bounded_retry_instead_of_publishing_copied_action(self):
        before = model._request_autonomy
        old_url=os.environ.get("ROOM_MODEL_URL")
        old_floor=os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
        os.environ["ROOM_MODEL_URL"]="http://127.0.0.1:9/unused-test-model"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
        attempts=[]
        def mocked(_url,prompt,_role,_temp,_timeout,_speaker,attempt,_intent):
            attempts.append((attempt,prompt))
            spoken=(LONG_QUESTION if attempt==0
                    else "Owen, evolutionary lineages branch. What kind of pattern "
                         "would show that your hypothetical species diverged?")
            return json.dumps({"decision":"SPEAK","target":"owen",
                               "move":"repair","utterance":spoken,
                               "semantic_terms":["species"]})
        model._request_autonomy=mocked
        try:
            result=model.run("expression",{
                "entity":"jules","profile":{"name":"Jules"},
                "event":SOURCE,"context":[SOURCE],"topic":{},
                "private_self_state":{},"partner":"owen",
            })
        finally:
            model._request_autonomy=before
            if old_url is None:os.environ.pop("ROOM_MODEL_URL",None)
            else:os.environ["ROOM_MODEL_URL"]=old_url
            if old_floor is None:os.environ.pop("ROOM_CONVERSATIONAL_FLOOR",None)
            else:os.environ["ROOM_CONVERSATIONAL_FLOOR"]=old_floor
        self.assertEqual([i for i,_ in attempts],[0,1])
        self.assertIn("copied",attempts[1][1])
        self.assertIn("lineages branch",result["utterance"])

    def test_real_candidate_preflight_hard_rejects_long_copy(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
        part={"node":11,"entity":"jules","role":"expression",
              "private":{"intent":{"readiness":.7},"expression":{
                  "decision":"SPEAK","target":"owen","move":"answer",
                  "utterance":LONG_QUESTION,"semantic_terms":["species"]}}}
        with self.assertRaisesRegex(ValueError,"unchanged_full_turn_echo"):
            validate_candidate(part,"jules",[SOURCE],{"root":"species"})


if __name__=="__main__":
    unittest.main()
