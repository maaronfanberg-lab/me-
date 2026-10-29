#!/usr/bin/env python3
"""Provenance-specific hygiene: the model's control label must not be speech."""
from __future__ import annotations
import copy
import unittest
from room_research_architecture import autonomous_text_issue
from room_group_dynamics import model_context

class ControlLeakTests(unittest.TestCase):
    def test_live_20261028_private_role_label_is_not_public_speech(self):
        x={"id":"20261028T234126364-sarah-v5","speaker":"sarah",
           "text":"self_initiated_contribution"}
        self.assertEqual(autonomous_text_issue(x),"control_sentinel")
        self.assertIsNone(autonomous_text_issue({
            "speaker":"allen","text":"self_initiated_contribution"}))
        self.assertIsNone(autonomous_text_issue({
            "speaker":"sarah","text":"A self-initiated contribution could introduce a new idea."}))
    def test_exact_internal_floor_labels_not_learned(self):
        for code in ("self_initiated_contribution","open_floor_response_or_repair",
                     "respond_to_proposal","directed_response_or_repair"):
            with self.subTest(code=code):
                self.assertEqual(autonomous_text_issue({"speaker":"owen","text":code}),
                                 "control_sentinel")
    def test_invalid_persisted_quote_is_left_unchanged_but_not_prompted(self):
        bad={"id":"20261028T234126364-sarah-v5","speaker":"sarah",
             "target":"owen","text":"self_initiated_contribution","cycle":7}
        good={"id":"topic","speaker":"sarah","target":"owen",
              "text":"Ecological species can respond to a change in habitat.","cycle":8}
        minds={"entities":{"owen":{
            "people":{"sarah":{}},
            "group_dynamics":{"encounters":[bad,good]},
            "room_memories":[],"self_history":[]}}}
        before=copy.deepcopy(minds)
        context=[{"id":"live","speaker":"mara",
                  "text":"What about ecological species in this habitat?","cycle":9}]
        result=model_context(minds,"owen","sarah",context,
                             ("sarah","mara","owen","jules"),
                             {"group_dynamics":{"enabled":True}})
        self.assertNotIn(bad["id"],[x["source"] for x in result["encounters"]])
        self.assertIn(good["id"],[x["source"] for x in result["encounters"]])
        self.assertEqual(minds,before)

if __name__=="__main__":
    unittest.main()
