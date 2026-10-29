#!/usr/bin/env python3
"""Opt-in next-action grounding: heard source, no forced answer or word ban."""
from __future__ import annotations
import os
import unittest
import room_chat_speech as chat


def turn(identifier, speaker, text):
    return {"id": identifier, "speaker": speaker, "text": text}


def payload(entity="owen", history=None):
    history = history if history is not None else [
        turn("m-1", "mara", "I have been studying mycelial networks."),
        turn("j-1", "jules", "Could a fungal network improve urban agriculture?"),
    ]
    return {
        "entity": entity, "profile":{"name":entity.capitalize(),
           "psychology_v2":{"core_identity":"An independent naturalist.",
                             "motives":["Understand ecology."]}},
        "context": history, "event": history[-1] if history else None,
        "partner": history[-1]["speaker"] if history else "sarah",
        "room_presence":{"present":["sarah","mara","jules","owen","allen"]},
    }


class SpecificUptakeTests(unittest.TestCase):
    def setUp(self):
        self.prior=os.environ.get("ROOM_CHAT_ACTION_FOCUS")
    def tearDown(self):
        if self.prior is None: os.environ.pop("ROOM_CHAT_ACTION_FOCUS",None)
        else: os.environ["ROOM_CHAT_ACTION_FOCUS"]=self.prior

    def test_opt_in_keeps_baseline_unmodified(self):
        inp=payload()
        os.environ.pop("ROOM_CHAT_ACTION_FOCUS",None)
        existing=chat.messages(inp,"owen")
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="0"
        self.assertEqual(existing,chat.messages(inp,"owen"))
        self.assertEqual(len(existing),2)

    def test_question_prompts_relevant_action_without_mandatory_reply(self):
        inp=payload()
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="1"
        rendered=chat.messages(inp,"owen")
        spoken=rendered[-1]["content"]
        self.assertIn("Could a fungal network improve urban agriculture?",spoken)
        self.assertIn("has asked a question",spoken)
        self.assertIn("decline",spoken)
        self.assertIn("specific missing detail",spoken)
        self.assertNotIn("private_self_state",str(rendered))
        self.assertEqual(len(rendered),2)

    def test_statement_asks_for_specific_meaning_but_allows_short_acknowledgement(self):
        inp=payload(history=[
            turn("s1","sarah","I measured tree roots at the river."),
            turn("m2","mara","The flood appears to have exposed the fungal connections."),
        ])
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="1"
        text=chat.messages(inp,"jules")[-1]["content"]
        self.assertIn("statement, observation, or proposal",text)
        self.assertIn("brief acknowledgment",text)
        self.assertIn("natural topic change",text)
        self.assertIn("flood appears to have exposed",text)

    def test_no_context_stays_free_of_invented_source_action(self):
        inp=payload(history=[])
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="1"
        result=chat.messages(inp,"sarah")
        self.assertNotIn("latest person has",result[-1]["content"].lower())
        self.assertNotIn("asked a question",result[-1]["content"].lower())

    def test_sleeping_source_excluded_from_action_cue(self):
        inp=payload(history=[
            turn("old","mara","I have an ongoing fungal argument."),
            turn("awake","jules","Can we discuss the water measurements?"),
        ])
        inp["room_presence"]={"present":["sarah","owen","jules","allen"],
                              "absent":["mara"]}
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="1"
        result=chat.messages(inp,"owen")
        self.assertNotIn("I have an ongoing fungal argument",str(result))
        self.assertIn("water measurements",str(result))

    def test_partner_identity_not_mistaken_for_question_source(self):
        inp=payload(history=[turn("j1","jules",
          "One pond supported many mushroom species without extra water.")])
        inp["partner"]="sarah"
        os.environ["ROOM_CHAT_ACTION_FOCUS"]="1"
        result=chat.messages(inp,"owen")
        self.assertIn("latest person has made a statement",
                      result[-1]["content"].lower())
        self.assertNotIn("has asked a question",result[-1]["content"])

    def test_rephrasing_and_short_conceptual_alignment_remain_allowed(self):
        prior=turn("a","mara","I think the tree may be dying.")
        for utterance in ("I agree.","No.","What changed about the leaves?",
                          "It could be lack of water rather than disease."):
            p=payload(history=[prior])
            response=chat.speech_metadata(utterance,p,"owen")
            self.assertEqual(response["decision"],"SPEAK")
            self.assertNotIn("scripted",response)


if __name__=="__main__":
    unittest.main()
