#!/usr/bin/env python3
"""Opt-in short public-reference test: context without memorizing others' wording."""
from __future__ import annotations
import os
import unittest
from room_conversation_project import expression_project

JULES={"name":"Jules","psychology_v2":{"motives":["Investigate unusual evolutionary mechanisms."]}}
SELF={"who_i_am":"I am an evolutionary biologist.","what_i_want":"I explore ecology."}


def project(text, speaker="mara", name="jules"):
    event={"id":"public-123","speaker":speaker,"text":text}
    return expression_project(entity=name,latest=event,context=[event],
                              profile=JULES,private_self_state=SELF)


class OptionalSourceCues(unittest.TestCase):
    def setUp(self):
        self.old=os.environ.get("ROOM_OPTIONAL_SOURCE_CUES")
        os.environ["ROOM_OPTIONAL_SOURCE_CUES"]="1"
    def tearDown(self):
        if self.old is None:os.environ.pop("ROOM_OPTIONAL_SOURCE_CUES",None)
        else:os.environ["ROOM_OPTIONAL_SOURCE_CUES"]=self.old

    def test_witnessed_long_statement_has_optional_cues_not_full_quote(self):
        statement=("I was wondering whether evolutionary adaptation in local forest "
                   "populations might respond differently after invasive species arrive.")
        out=project(statement)
        self.assertEqual(out["interaction_project"]["kind"],"self_initiated_contribution")
        self.assertIsNone(out["event"])
        self.assertEqual(out["context"],[])
        occasion=out["interaction_project"]["public_occasion"]
        self.assertEqual(occasion["source_id"],"public-123")
        self.assertEqual(occasion["prior_speaker"],"mara")
        self.assertEqual(occasion["role"],"optional_reference_not_an_obligation")
        self.assertNotIn(statement,str(out))
        self.assertGreaterEqual(len(occasion["cues"]),2)

    def test_short_scaffolds_do_not_reseed_the_old_topic(self):
        for statement in ("Experimental classification trees are good.",
                          "new", "sarah", "I agree.", "Nothing else needed.",
                          "Try something new."):
            with self.subTest(statement=statement):
                self.assertNotIn("public_occasion",project(statement)["interaction_project"])

    def test_cues_opt_out_is_exact_backward_compatibility(self):
        text=("I noticed communities of ocean organisms changed their migration "
              "patterns after major shifts in the climate system.")
        os.environ["ROOM_OPTIONAL_SOURCE_CUES"]="0"
        old=project(text)
        os.environ["ROOM_OPTIONAL_SOURCE_CUES"]="1"
        new=project(text)
        self.assertNotIn("public_occasion",old["interaction_project"])
        self.assertIn("public_occasion",new["interaction_project"])
        self.assertEqual(old["event"],new["event"])
        self.assertEqual(old["context"],new["context"])
        self.assertEqual(old["private_self_state"],new["private_self_state"])

    def test_direct_utterance_responses_preserve_exact_source(self):
        directed=project("Jules, can you explain why migration patterns changed?")
        self.assertEqual(directed["interaction_project"]["kind"],"respond_or_repair")
        self.assertIsNotNone(directed["event"])
        self.assertNotIn("public_occasion",directed["interaction_project"])

    def test_own_prior_statement_not_reused_as_other_speaker(self):
        text=("I would like to examine the relationship between forest diversity "
              "and how soil microbes respond to repeated fires.")
        self.assertNotIn("public_occasion",project(text,speaker="jules")["interaction_project"])

if __name__=="__main__":
    unittest.main()
