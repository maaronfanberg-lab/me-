#!/usr/bin/env python3
"""Native Room calls back to source-linked speech only when publicly relevant."""
from __future__ import annotations
import copy
import os
import unittest

import room_chat_speech as chat


def turn(i, speaker, statement):
    return {"id": i,"speaker":speaker,"text":statement}


def base():
    prior=turn("current-voice","jules",
               "I think fungal mycelium networks might improve urban agriculture.")
    return {
        "entity":"owen",
        "profile":{"name":"Owen","psychology_v2":{
            "core_identity":"An independent thinker.",
            "motives":["Test real causes."]}},
        "event":prior,"context":[prior],"partner":"jules",
        "room_presence":{"present":["sarah","mara","jules","owen","allen"]},
        "group_context":{"encounters":[]},
        "private_self_state":{"secret":"NEVER PRINT SECRET"},
        "topic":{}
    }


def memory(i="past-1",speaker="mara",
           utterance="We studied fungal mycelium networks as a soil ecology example.",
           status="remembered_speech_not_verified_fact"):
    return {"source":i,"speaker":speaker,"text":utterance,"status":status}


class NativeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.old=os.environ.get("ROOM_CHAT_GROUNDED_MEMORY")
    def tearDown(self):
        if self.old is None:os.environ.pop("ROOM_CHAT_GROUNDED_MEMORY",None)
        else:os.environ["ROOM_CHAT_GROUNDED_MEMORY"]=self.old

    def test_default_off_is_exact_noop(self):
        inp=base()
        inp["group_context"]["encounters"]=[memory()]
        os.environ.pop("ROOM_CHAT_GROUNDED_MEMORY",None)
        before=chat.messages(inp,"owen")
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="0"
        self.assertEqual(before,chat.messages(inp,"owen"))
        self.assertNotIn("past-1",str(before))

    def test_two_source_terms_enable_one_provenance_tagged_public_quote(self):
        inp=base()
        inp["group_context"]["encounters"]=[
            memory(),memory("past-2","sarah","Urban agriculture could use fungal soil nutrients.")]
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        prompt=chat.messages(inp,"owen")
        rendered=str(prompt[-1]["content"])
        self.assertIn("Mara [source past-1]",rendered)
        self.assertIn("mycelium networks",rendered)
        self.assertIn("meaning and truth still open to question",rendered)
        self.assertNotIn("past-2",rendered)
        self.assertNotIn("NEVER PRINT SECRET",str(prompt))
        self.assertEqual(len(prompt),2)

    def test_partner_only_unrelated_old_message_is_not_recalled(self):
        inp=base()
        inp["group_context"]["encounters"]=[
            memory("random-probability","jules",
                   "I found P(X=0.1) in a random variable probability distribution.")]
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        self.assertEqual(chat.grounded_partner_recall(
            inp,"owen",chat.witnessed_context(inp,"owen")),"")

    def test_one_matching_term_or_no_verified_status_does_not_make_recall(self):
        inp=base()
        inp["group_context"]["encounters"]=[
            memory("one-match","mara","Fungal ponds have ducks."),
            memory("unsafe","sarah",
                   "We studied mycelium networks together.",
                   status="not_a_valid_recollection")]
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        self.assertNotIn("[source",str(chat.messages(inp,"owen")))

    def test_unwitnessed_status_missing_id_or_speaker_not_admitted(self):
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        for rec in (
            memory(i=""),memory(speaker="system"),
            memory(speaker="allen"),memory(speaker="stranger"),
            memory(status="unverified_hidden_notes"),
        ):
            inp=base()
            inp["group_context"]["encounters"]=[rec]
            with self.subTest(rec=rec):
                self.assertNotIn("[source",str(chat.messages(inp,"owen")))

    def test_sleeping_partner_and_current_turn_not_repeated_as_memory(self):
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        inp=base()
        inp["room_presence"]={"present":["sarah","jules","owen","allen"],
                              "absent":["mara"]}
        inp["group_context"]["encounters"]=[memory()]
        self.assertNotIn("[source",str(chat.messages(inp,"owen")))
        inp["room_presence"]={"present":["sarah","mara","jules","owen","allen"]}
        inp["group_context"]["encounters"]=[memory(
            "current-voice",speaker="mara")]
        self.assertNotIn("[source",str(chat.messages(inp,"owen")))

    def test_no_public_history_never_yields_background_memories(self):
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        inp=base()
        inp["event"]=None
        inp["context"]=[]
        inp["group_context"]["encounters"]=[memory()]
        self.assertNotIn("[source",str(chat.messages(inp,"owen")))

    def test_quote_is_sanitized_bounded_and_not_privileged(self):
        os.environ["ROOM_CHAT_GROUNDED_MEMORY"]="1"
        inp=base()
        text="Fungal mycelium networks behave\nlike a network. "+("X"*350)
        inp["group_context"]["encounters"]=[memory("public-55","sarah",text)]
        original=copy.deepcopy(inp)
        chat_text=chat.messages(inp,"owen")[-1]["content"]
        self.assertIn("Earlier",chat_text)
        self.assertIn("source public-55",chat_text)
        self.assertNotIn("\nlike a network",chat_text)
        self.assertNotIn("X"*200,chat_text)
        self.assertEqual(inp,original)


if __name__=="__main__":
    unittest.main()
