#!/usr/bin/env python3
"""Real expression-generation boundary: quarantine bad self perspective before publication."""
from __future__ import annotations
import json
import os
import unittest
import room_private_model_autonomy_legacy as legacy


class SelfVoiceRetryTests(unittest.TestCase):
    def test_retry_bad_self_perspective_with_fresh_model_answer(self):
        original = legacy._request_autonomy
        old_url = os.environ.get("ROOM_MODEL_URL")
        old_floor = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
        os.environ["ROOM_MODEL_URL"] = "http://127.0.0.1:1/dummy-not-requested"
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        sent = []
        def fake_request(_url, prompt, _role, _temp, _timeout, _speaker, attempt, _intent):
            sent.append((attempt, prompt))
            text = ("I, Sarah, would like to talk about the pond." if attempt == 0
                    else "Mara, I saw two dragonflies over the pond yesterday.")
            return json.dumps({
                "decision": "SPEAK", "target": "mara", "move": "deepen",
                "utterance": text, "semantic_terms": ["pond"]
            })
        legacy._request_autonomy = fake_request
        try:
            result = legacy.run("expression", {
                "entity": "sarah", "profile": {"name": "Sarah"},
                "event": {"id": "q-1", "speaker": "mara",
                          "text": "I saw a dragonfly over the pond."},
                "context": [{"id": "q-1", "speaker": "mara",
                             "text": "I saw a dragonfly over the pond."}],
                "topic": {}, "private_self_state": {},
            })
        finally:
            legacy._request_autonomy = original
            if old_url is None:
                os.environ.pop("ROOM_MODEL_URL", None)
            else:
                os.environ["ROOM_MODEL_URL"] = old_url
            if old_floor is None:
                os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
            else:
                os.environ["ROOM_CONVERSATIONAL_FLOOR"] = old_floor
        self.assertEqual(len(sent), 2)
        self.assertEqual([a for a,_ in sent], [0,1])
        self.assertIn("self", sent[1][1].casefold())
        self.assertEqual(result["utterance"],
                         "Mara, I saw two dragonflies over the pond yesterday.")

    def test_valid_first_person_and_real_name_mention_not_rejected(self):
        from room_research_architecture import autonomous_text_issue
        self.assertEqual(
            autonomous_text_issue({"speaker":"sarah",
                "text":"I, Sarah, have a proposal."}), "self_perspective_leak")
        self.assertIsNone(autonomous_text_issue({
            "speaker":"sarah", "text":"I think Mara has a good point."}))
        self.assertIsNone(autonomous_text_issue({
            "speaker":"sarah", "text":"Sarah is a common name in my family."}))


if __name__ == "__main__":
    unittest.main()
