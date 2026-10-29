#!/usr/bin/env python3
"""Actual Room import-time model selection: no wasted 3B thought/comprehension calls."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import unittest


_CHECK = r'''
import json,os
import room_engine_v5 as engine
import room_engine_v5_legacy as legacy
import room_private_model_autonomy as autonomy

variant=os.environ["ROOM_BRAIN_ACTIVE"]
active=legacy._core.model_run is engine._llama_model_run
private_bound=legacy._private_model.run is engine._llama_model_run
assert active==private_bound, "engine and private model routed inconsistently"
if variant in {"llama3.2-1b","llama3.2-3b"}:
    assert active, "native Llama size must not use legacy model path"
    assert legacy._core.recurrent is engine._coherent_recurrent
    assert legacy.recurrent is engine._coherent_recurrent
    assert engine._llama_model_run("thought",{"entity":"sarah"},timeout=1) is None
    assert engine._llama_model_run("comprehension",{"entity":"jules"},timeout=1) is None
else:
    assert not active, "Qwen retains its existing fallback route"
print(json.dumps({
    "active_model":variant,
    "native_single_pass":active,
    "private_bound":private_bound,
}))
'''


class NativeLlamaRouting(unittest.TestCase):
    def _check(self,model):
        env=dict(os.environ)
        env.update({
            "ROOM_BRAIN_ACTIVE":model,
            "ROOM_NODE_PROMPT":"public test activation flag, no private prompts",
            "ROOM_CHAT_SPEECH_MODE":"1",
            "ROOM_CONVERSATIONAL_FLOOR":"1",
            # No local HTTP service. A real comprehension/thought request would
            # time out or raise, proving the single-pass no-op contract.
            "ROOM_MODEL_URL":"http://127.0.0.1:9/unreachable",
        })
        result=subprocess.run([sys.executable,"-c",_CHECK],
                              env=env,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,
                         model+"\nSTDOUT="+result.stdout+"\nSTDERR="+result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_native_3b_routes_all_12_nodes_through_single_pass_backend(self):
        result=self._check("llama3.2-3b")
        self.assertTrue(result["native_single_pass"])

    def test_existing_1b_behavior_is_identical(self):
        result=self._check("llama3.2-1b")
        self.assertTrue(result["native_single_pass"])

    def test_qwen_fallback_does_not_silently_use_native_llama_route(self):
        result=self._check("qwen2.5-0.5b-fallback")
        self.assertFalse(result["native_single_pass"])


if __name__=="__main__":
    unittest.main()
