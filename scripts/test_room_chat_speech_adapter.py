#!/usr/bin/env python3
"""Native speech-first Room adapter preserves identity, floor and final safety."""
from __future__ import annotations
import json
import os
import unittest
from unittest.mock import patch

import room_chat_speech as chat
from room_conversational_candidate import validate_candidate
from room_conversational_floor import NODE


def source(speaker="jules", text="What if species didn't change into one shape in a lineage?"):
    return {"id":"public-123","speaker":speaker,"text":text}


def payload(entity="owen", previous=None):
    item=previous or source()
    return {"entity":entity,"profile":{
        "name":entity.capitalize(),
        "psychology_v2":{"core_identity":"An independent thinker.", "motives":["Understand natural patterns."]}},
        "event":item,"context":[item],"topic":{},"partner":item["speaker"],
        "private_self_state":{"who_i_am":"I am curious."},
        "room_presence":{"present":["sarah","mara","owen","jules","allen"],"absent":[]}
    }


class Fake:
    def __init__(self,text):
        self.text=text
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self):
        return json.dumps({"choices":[{"message":{"content":self.text}}]}).encode()


class ChatAdapterTests(unittest.TestCase):
    def setUp(self):
        self.old=os.environ.get("ROOM_MODEL_URL")
        self.old_cycle=os.environ.get("ROOM_CYCLE_KEY")
        os.environ["ROOM_MODEL_URL"]="http://127.0.0.1:18080/completion"
        os.environ["ROOM_CYCLE_KEY"]="chat-speech-tested-source-123"
    def tearDown(self):
        if self.old is None:os.environ.pop("ROOM_MODEL_URL",None)
        else:os.environ["ROOM_MODEL_URL"]=self.old
        if self.old_cycle is None:os.environ.pop("ROOM_CYCLE_KEY",None)
        else:os.environ["ROOM_CYCLE_KEY"]=self.old_cycle

    def test_local_only_endpoint(self):
        self.assertEqual(chat.chat_endpoint(os.environ["ROOM_MODEL_URL"]),
                         "http://127.0.0.1:18080/v1/chat/completions")
        for target in ("https://other.invalid/completion",
                       "http://evil.invalid:18080/completion","file:///tmp/model"):
            with self.subTest(target=target),self.assertRaises(ValueError):
                chat.chat_endpoint(target)

    def test_public_transcript_not_hidden_state_and_sleeping_excluded(self):
        inp=payload()
        inp["context"]=[
            source("sarah","I heard the scientist discuss the forest."),
            source("mara","I think forests are interesting."),
            source("jules","I want to investigate tree adaptation."),
        ]
        inp["event"]=source("owen","The model received a new public observation.")
        inp["room_presence"]={"present":["sarah","jules","owen","allen"],"absent":["mara"]}
        out=chat.messages(inp,"sarah")
        full=str(out)
        self.assertNotIn("Mara: I think forests",full)
        self.assertIn("Jules: I want",full)
        self.assertNotIn("I am curious.",full)
        self.assertNotIn("private_self_state",full)
        self.assertIn("latest",full.lower())

    def test_accepted_allen_public_turn_remains_verbatim_up_to_room_limit(self):
        said="Allen wants a specific discussion of the coastline. " + "x"*570
        inp=payload("sarah",source("allen",said))
        history=chat.witnessed_context(inp,"sarah")
        self.assertEqual(history[-1]["text"],said)
        self.assertIn(said,chat.messages(inp,"sarah")[-1]["content"])
        self.assertEqual(history[-1]["speaker"],"allen")

    def test_direct_request_stays_visible_and_prompt_requires_no_invented_task(self):
        item=source("mara","I need you to do something, but I haven't said what yet.")
        inp=payload("sarah",item)
        prompt=chat.messages(inp,"sarah")
        self.assertEqual(len(prompt),2)
        self.assertIn(item["text"],prompt[-1]["content"])
        self.assertIn("ask instead of inventing their request",prompt[0]["content"])
        self.assertIn("You may disagree, decline, or redirect",prompt[0]["content"])
        self.assertIn("final transcript line",prompt[-1]["content"])
        self.assertNotIn("private_self_state",str(prompt))

    def test_candidate_has_real_model_text_and_passes_final_preflight(self):
        inp=payload()
        said="The species could diverge because different environments favor different adaptations."
        with patch("room_chat_speech.urllib.request.urlopen",return_value=Fake(said)) as fake:
            result=chat.run(inp)
        self.assertEqual(result["utterance"],said)
        self.assertEqual(result["target"],"jules")
        self.assertEqual(result["decision"],"SPEAK")
        self.assertEqual(result["move"],"answer")
        self.assertTrue(result["semantic_terms"])
        self.assertEqual(fake.call_count,1)
        part={"node":NODE["owen"],"entity":"owen","role":"expression",
              "private":{"intent":{"readiness":.8},"expression":result}}
        self.assertEqual(validate_candidate(part,"owen",[inp["event"]],{}),said)

    def test_unclosed_model_quotation_is_not_published_as_finished_speech(self):
        broken='"Rethinking the ecology of a hypothetical predator that'
        complete="I would first ask which hypothesis you mean before assessing it."
        self.assertTrue(chat.unfinished_model_quotation(broken))
        self.assertFalse(chat.unfinished_model_quotation('"That hypothesis needs a test."'))
        with patch("room_chat_speech.urllib.request.urlopen",
                   side_effect=[Fake(broken),Fake(complete)]) as model:
            out=chat.run(payload("jules",source("owen",
                "My hypothesis was mistaken, but I haven't named its subject.")))
        self.assertEqual(model.call_count,2)
        self.assertEqual(out["utterance"],complete)

    def test_internal_role_label_is_retried_without_emitting_fake_speech(self):
        replies=[Fake("self_initiated_contribution"),
                 Fake("Jules, perhaps ecology changes as the habitat changes.")]
        with patch("room_chat_speech.urllib.request.urlopen",side_effect=replies) as mock:
            out=chat.run(payload())
        self.assertEqual(mock.call_count,2)
        self.assertIn("habitat changes",out["utterance"])
        with patch("room_chat_speech.urllib.request.urlopen",
                   return_value=Fake("self_initiated_contribution")):
            self.assertIsNone(chat.run(payload()))

    def test_internal_quality_gate_retries_self_address_and_long_run_on(self):
        wrong="That's an intriguing evolutionary explanation, Owen."
        correct="Different habitats can favor different evolutionary adaptations."
        with patch("room_chat_speech.urllib.request.urlopen",
                   side_effect=[Fake(wrong),Fake(correct)]) as model:
            out=chat.run(payload())
        self.assertEqual(model.call_count,2)
        self.assertEqual(out["utterance"],correct)
        very_long=("I am interested in examining ecological patterns and scientific "
                   "hypotheses about populations and environments, yet there are "
                   "many related implications that I could describe in a lengthy "
                   "and complicated statement while continuing to explore different "
                   "possible scenarios and historical details without a clear answer "
                   "to the actual question we are discussing right now, since "
                   "everything is possible and might be worth exploring in theory.")
        with patch("room_chat_speech.urllib.request.urlopen",
                   side_effect=[Fake(very_long),Fake(correct)]) as model:
            shortened=chat.run(payload())
        self.assertEqual(model.call_count,2)
        self.assertEqual(shortened["utterance"],correct)

    def test_model_must_not_ventriloquize_allen_or_another_agent(self):
        valid="The forest contains several independent evolutionary branches."
        for false_speaker in ("Allen","Mara","Sarah"):
            with self.subTest(false_speaker=false_speaker),patch(
                    "room_chat_speech.urllib.request.urlopen",
                    side_effect=[
                        Fake(false_speaker+": I think the idea is sound."),
                        Fake(valid)]) as fake_model:
                out=chat.run(payload("owen"))
                self.assertEqual(fake_model.call_count,2)
                self.assertEqual(out["utterance"],valid)
        with patch("room_chat_speech.urllib.request.urlopen",
                   return_value=Fake("Allen: I've already agreed.")) as fake_model:
            self.assertIsNone(chat.run(payload("owen")))
        self.assertEqual(fake_model.call_count,3)
        # A character labeling their *own* utterance is not impersonation.
        with patch("room_chat_speech.urllib.request.urlopen",
                   return_value=Fake("Owen: "+valid)):
            out=chat.run(payload("owen"))
        self.assertEqual(out["utterance"],valid)

    def test_only_complete_model_authored_prefix_may_be_preserved(self):
        first=("Different species can develop separate adaptations when their "
               "environments exert distinct pressures.")
        unfinished=(" A second and even more complicated explanation could "
                    "involve every possible kind of genetic effect, but it "
                    "might still be missing a conclusion because")
        raw=first+unfinished
        with patch("room_chat_speech.urllib.request.urlopen",
                   return_value=Fake(raw)) as model:
            out=chat.run(payload())
        self.assertEqual(model.call_count,1)
        self.assertEqual(out["utterance"],first)
        self.assertNotIn("second and even",out["utterance"])

    def test_does_not_cut_off_a_pending_contradiction(self):
        first="I think we should absolutely proceed with the experiment today."
        trailing=" However, I need to explain why we cannot"
        corrected="I'd prefer to collect one more observation before starting."
        with patch("room_chat_speech.urllib.request.urlopen",
                   side_effect=[Fake(first+trailing),Fake(corrected)]) as model:
            out=chat.run(payload())
        self.assertEqual(model.call_count,2)
        self.assertEqual(out["utterance"],corrected)
        self.assertEqual(chat.complete_model_prefix(first+trailing),"")

    def test_natural_vocative_controls_recipient_not_hidden_partner(self):
        x=payload("sarah",source("jules","I saw some migrating birds over the river."))
        x["partner"]="owen"
        result=chat.speech_metadata("Mara, I disagree because the river is frozen.",x,"sarah")
        self.assertEqual(result["target"],"mara")
        self.assertEqual(result["move"],"disagree")
        self.assertTrue(result["semantic_terms"])

    def test_legacy_floor_recovery_does_not_invoke_chat_adapter(self):
        import room_engine_v5 as engine
        import room_private_model_autonomy as autonomy
        prior={k:os.environ.get(k) for k in
               ("ROOM_CHAT_SPEECH_MODE","ROOM_CONVERSATIONAL_FLOOR","ROOM_NODE_PROMPT")}
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="0"
        os.environ["ROOM_NODE_PROMPT"]="Local model prompt available"
        dummy={"decision":"SPEAK","utterance":"A genuine model sentence.",
               "move":"deepen","target":"jules","semantic_terms":["genuine"]}
        try:
            with patch("room_chat_speech.run") as spy,patch.object(
                    autonomy,"run",return_value=dummy) as legacy:
                out=engine._llama_model_run("expression",payload(),timeout=30)
            self.assertEqual(out,dummy)
            spy.assert_not_called()
            legacy.assert_called_once()
        finally:
            for key,val in prior.items():
                if val is None:os.environ.pop(key,None)
                else:os.environ[key]=val

    def test_active_model_switch_is_the_only_adapter_activation(self):
        import room_engine_v5 as engine
        before=os.environ.get("ROOM_CHAT_SPEECH_MODE")
        before_node=os.environ.get("ROOM_NODE_PROMPT")
        before_floor=os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
        os.environ["ROOM_NODE_PROMPT"]="Local model prompt available"
        try:
            with patch("room_chat_speech.run",return_value={
                "decision":"SPEAK","utterance":"The forest contains several species.",
                "move":"deepen","target":"jules","semantic_terms":["forest"]
            }) as spy:
                response=engine._llama_model_run("expression",payload(),timeout=35)
            self.assertEqual(response["utterance"],"The forest contains several species.")
            self.assertEqual(spy.call_count,1)
        finally:
            if before is None:os.environ.pop("ROOM_CHAT_SPEECH_MODE",None)
            else:os.environ["ROOM_CHAT_SPEECH_MODE"]=before
            if before_node is None:os.environ.pop("ROOM_NODE_PROMPT",None)
            else:os.environ["ROOM_NODE_PROMPT"]=before_node
            if before_floor is None:os.environ.pop("ROOM_CONVERSATIONAL_FLOOR",None)
            else:os.environ["ROOM_CONVERSATIONAL_FLOOR"]=before_floor


    def test_stalled_scene_uses_grounded_four_voice_history_not_eight_turn_imitation(self):
        turns = [{"id":f"loop-{n}","speaker":who,
                  "text":f"The projector question number {n} remains open."}
                 for n,who in enumerate(
                     ["sarah","mara","jules","owen",
                      "sarah","mara","jules","owen",
                      "sarah","mara","jules","owen"])]
        reduced=chat.grounded_stall_history(turns)
        self.assertEqual([t["id"] for t in reduced],
                         ["loop-8","loop-9","loop-10","loop-11"])
        self.assertEqual({t["speaker"] for t in reduced},
                         {"sarah","mara","jules","owen"})
        self.assertEqual(reduced[-1],turns[-1])
        inp=payload("sarah",turns[-1])
        inp["context"]=turns
        inp["room_cycle"]=36621
        def fake_file(path, *args, **kwargs):
            return (json.dumps({"cycle":36620}) if path.name=="state.json"
                    else json.dumps({"conversation":turns}))
        with patch.dict(os.environ,{"ROOM_CAUSAL_WORLD_EXPERIMENT":"1"}), \
             patch("room_chat_speech.Path.read_text",autospec=True,side_effect=fake_file), \
             patch("room_causal_world.stalled_scene",return_value=True), \
             patch("room_causal_world.production_cue",return_value=""):
            prompt=chat.messages(inp,"sarah")
        self.assertIn("no completed test or firsthand finding",prompt[0]["content"])
        self.assertIn("Owen: The projector question number 11",prompt[1]["content"])
        self.assertNotIn("question number 7",prompt[1]["content"])
        self.assertIn("Jules: The projector question number 10",prompt[1]["content"])

if __name__=="__main__":
    unittest.main()
