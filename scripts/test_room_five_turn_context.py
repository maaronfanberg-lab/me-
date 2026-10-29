#!/usr/bin/env python3
"""Exact witnessed full-cycle window tests without memory or speaker mutation."""
from __future__ import annotations
import os
import unittest
import room_chat_speech as chat
import room_engine_v5_core as core

NAMES=("sarah","mara","owen","jules")

def turn(i,speaker,text):
    return {"id":f"public-{i}","speaker":speaker,"text":text}

def data(history):
    return {
        "entity":"sarah",
        "context":history,
        "event":history[-1] if history else None,
        "profile":{"name":"Sarah","psychology_v2":{
            "core_identity":"An independent person.",
            "motives":["Understand what people say."]}},
        "room_presence":{"present":["sarah","mara","owen","jules","allen"],
                         "absent":[]},
        "partner":"jules",
    }

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.keys=("ROOM_CHAT_SPEECH_MODE","ROOM_CONVERSATIONAL_FLOOR",
                   "ROOM_CHAT_CONTEXT_WINDOW")
        self.old={key:os.environ.get(key) for key in self.keys}
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
    def tearDown(self):
        for key,value in self.old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value

    def source_history(self):
        return [
            turn(1,"mara","I found a fungal colony in the garden."),
            turn(2,"owen","How did you identify the colony?"),
            turn(3,"jules","Maybe we can compare the spores."),
            turn(4,"sarah","I have a microscope."),
            turn(5,"mara","Would a microscope reveal the spores?"),
            turn(6,"owen","We could try a slide of the soil."),
        ]

    def test_baseline_three_stays_the_default(self):
        os.environ.pop("ROOM_CHAT_CONTEXT_WINDOW",None)
        history=self.source_history()
        self.assertEqual(core.selected_floor_public_window(),3)
        self.assertEqual([x["id"] for x in chat.witnessed_context(data(history),"sarah")],
                         ["public-4","public-5","public-6"])
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="0"
        self.assertEqual(core.selected_floor_public_window(),3)

    def test_opt_in_retains_previous_question_and_full_group_cycle(self):
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5"
        history=self.source_history()
        self.assertEqual(core.selected_floor_public_window(),5)
        observed=chat.witnessed_context(data(history),"sarah")
        self.assertEqual([x["id"] for x in observed],
                         ["public-2","public-3","public-4","public-5","public-6"])
        rendered=chat.messages(data(history),"sarah")[-1]["content"]
        self.assertIn("Owen: How did you identify the colony?",rendered)
        self.assertIn("Mara: Would a microscope reveal the spores?",rendered)
        self.assertNotIn("I found a fungal colony in the garden.",rendered)

    def test_private_and_sleeping_speech_do_not_enter_wider_window(self):
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5"
        history=self.source_history()
        history.insert(3,turn(7,"system","PRIVATE CONTROL TOKEN"))
        inp=data(history)
        inp["room_presence"]={"present":["sarah","owen","jules","allen"],
                              "absent":["mara"]}
        observed=chat.witnessed_context(inp,"sarah")
        self.assertFalse(any(x["speaker"]=="mara" for x in observed))
        self.assertNotIn("PRIVATE CONTROL TOKEN",str(observed))
        self.assertTrue(all(x["speaker"] in NAMES for x in observed))

    def test_allen_accepted_public_words_retained_with_original_limit(self):
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5"
        accepted="Allen asked about a specific garden experiment. "+"x"*570
        inp=data(self.source_history()+[turn(9,"allen",accepted)])
        recent=chat.witnessed_context(inp,"sarah")
        self.assertEqual(recent[-1]["text"],accepted)
        self.assertEqual(recent[-1]["speaker"],"allen")

    def test_legacy_and_floor_disabled_do_not_take_new_history(self):
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5"
        for key in ("ROOM_CHAT_SPEECH_MODE","ROOM_CONVERSATIONAL_FLOOR"):
            with self.subTest(flag=key):
                prior=os.environ.pop(key,None)
                try:
                    self.assertEqual(core.selected_floor_public_window(),3)
                    self.assertEqual(len(chat.witnessed_context(
                        data(self.source_history()),"sarah")),3)
                finally:
                    if prior is not None:os.environ[key]=prior

    def test_no_memory_or_unwitnessed_facts_are_inserted(self):
        os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5"
        inp=data(self.source_history())
        inp["private_self_state"]={"secret":"Never published"}
        inp["topic"]={"root":"unverified_memory"}
        rendered=chat.messages(inp,"sarah")
        self.assertNotIn("Never published",str(rendered))
        self.assertNotIn("unverified_memory",str(rendered))
        self.assertEqual(len(rendered),2)


if __name__=="__main__":
    unittest.main()
