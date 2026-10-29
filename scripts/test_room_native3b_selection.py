#!/usr/bin/env python3
"""Native 3B canary select/fallback with unmodified public speech integrity."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

import room_chat_speech as chat


class Fake:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):
        return json.dumps({"choices":[{"message":{"content":
            "Distinct habitats can favor distinct species adaptations."}}]}).encode()


def payload():
    source={"id":"source-public-1","speaker":"jules",
            "text":"Could a species split into two different lineages?"}
    return {
        "entity":"owen","profile":{
            "name":"Owen","psychology_v2":{
                "core_identity":"An independent naturalist.",
                "motives":["Investigate mechanisms."]}},
        "context":[source],"event":source,"partner":"jules","topic":{},
        "room_presence":{"present":["sarah","mara","owen","jules","allen"]},
    }


class Native3BSelectionTests(unittest.TestCase):
    def setUp(self):
        self.keys=("ROOM_MODEL_URL","ROOM_CYCLE_KEY","ROOM_CHAT_MODEL_ID",
                   "ROOM_CHAT_SPEECH_MODE","ROOM_CONVERSATIONAL_FLOOR")
        self.saved={k:os.environ.get(k) for k in self.keys}
        os.environ["ROOM_MODEL_URL"]="http://127.0.0.1:18080/completion"
        os.environ["ROOM_CYCLE_KEY"]="canary-test-3b-model-identity"
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"

    def tearDown(self):
        for k,value in self.saved.items():
            if value is None:os.environ.pop(k,None)
            else:os.environ[k]=value

    def test_chat_request_uses_selected_verified_3b_alias(self):
        recorded=[]
        def model_call(request,*args,**kwargs):
            recorded.append(json.loads(request.data))
            return Fake()
        os.environ["ROOM_CHAT_MODEL_ID"]="Llama-3.2-3B-Instruct"
        with patch("room_chat_speech.urllib.request.urlopen",side_effect=model_call):
            out=chat.run(payload())
        self.assertEqual(out["utterance"],
                         "Distinct habitats can favor distinct species adaptations.")
        self.assertEqual([r["model"] for r in recorded],
                         ["Llama-3.2-3B-Instruct"])
        self.assertEqual(out["target"],"jules")

    def test_no_model_override_preserves_exact_1b_default(self):
        os.environ.pop("ROOM_CHAT_MODEL_ID",None)
        recorded=[]
        def model_call(request,*args,**kwargs):
            recorded.append(json.loads(request.data))
            return Fake()
        with patch("room_chat_speech.urllib.request.urlopen",side_effect=model_call):
            out=chat.run(payload())
        self.assertTrue(out)
        self.assertEqual(recorded[0]["model"],"Llama-3.2-1B-Instruct")

    def test_guarded_live_workflow_has_pinned_3b_and_1b_fallback(self):
        source=(Path(__file__).resolve().parents[1]/
                ".github/workflows/sarah-society.yml").read_text()
        self.assertIn("ROOM_NATIVE_3B_DISABLE",source)
        self.assertIn("ROOM_CHAT_SPEECH_MODE",source)
        self.assertIn("native_brain_probe()",source)
        self.assertIn("sha256sum -c -",source)
        self.assertIn(
            "6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff",source)
        self.assertLess(
            source.index("start_model 'llama3.2-3b'"),
            source.index("start_model 'llama3.2-1b'"))
        self.assertIn('if [ "$llama_ready" -ne 1 ]; then',source)
        self.assertIn("start_model 'qwen2.5-0.5b-fallback'",source)

    def test_full_production_beat_script_has_valid_bash_syntax(self):
        # Validate the real embedded runner shell, including its new native
        # 3B startup branch and heredoc. This only PARSES; it cannot start
        # downloads, publish speech or alter any Room state.
        source=(Path(__file__).resolve().parents[1]/
                ".github/workflows/sarah-society.yml").read_text()
        suffix=source.split(
            "      - name: Keep all 12 cognitive nodes hot and publish every beat",
            1)[1]
        script=suffix.split("        run: |",1)[1]
        unindented="\n".join(
            line[10:] if line.startswith("          ") else line
            for line in script.splitlines()
        )
        checked=subprocess.run(["bash","-n"],input=unindented,
                               text=True,capture_output=True,check=False)
        self.assertEqual(checked.returncode,0,checked.stderr)

    def test_no_untrusted_model_url_and_no_fabricated_utterance(self):
        for path in ("https://untrusted.example/v1/chat/completions",
                     "file:///tmp/brain"):
            with self.subTest(path=path),self.assertRaises(ValueError):
                chat.chat_endpoint(path)
        class WrongSpeaker:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):
                return json.dumps({"choices":[{"message":{
                    "content":"Allen: I approved this science experiment."}}]}).encode()
        with patch("room_chat_speech.urllib.request.urlopen",
                   return_value=WrongSpeaker()) as model:
            self.assertIsNone(chat.run(payload()))
        self.assertEqual(model.call_count,3)


if __name__=="__main__":
    unittest.main()
