#!/usr/bin/env python3
"""Actual Llama 1B public output is spoken grammar, not token-run-on."""
from __future__ import annotations
import os
import unittest
import room_expression_quality_legacy as quality

WITNESSED=(
    "The fossil record would then reveal a vast, sprawling tapestry of "
    "divergent paths, a fractal landscape where seemingly identical organisms "
    "have evolved into radically different forms, defying the notion that "
    "evolution is a linear, one-way process."
)


def issue(spoken, speaker="jules"):
    return quality.quality_issue(spoken,{"context":[],"event":None},
                                 speaker,lambda a,b:0.)


class SpeechLengthTests(unittest.TestCase):
    def setUp(self):
        self.old={k:os.environ.get(k) for k in (
            "ROOM_CONVERSATIONAL_FLOOR","ROOM_CHAT_SPEECH_MODE")}
        os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
    def tearDown(self):
        for k,v in self.old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

    def test_actual_complete_37_word_jules_expression_not_false_run_on(self):
        self.assertEqual(len(quality._tokens(WITNESSED)),37)
        os.environ["ROOM_CHAT_SPEECH_MODE"]="0"
        self.assertEqual(issue(WITNESSED),"run_on_expression")
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        self.assertIsNone(issue(WITNESSED))

    def test_legacy_and_extreme_repetition_still_quarantined(self):
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        long=" ".join(["evolutionary","ecosystems","provide","interesting","possibilities"]*12)+"."
        self.assertEqual(issue(long),"wordy_expression")
        os.environ["ROOM_CHAT_SPEECH_MODE"]="0"
        self.assertEqual(issue(WITNESSED),"run_on_expression")

    def test_speech_first_limit_is_bounded_and_self_name_still_invalid(self):
        os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
        overlong=("Scientific explanations can require a careful account of "
                  "multiple interlocking processes and changing ecological "
                  "circumstances which we could explore with small experiments "
                  "but this discussion has now become very long and difficult "
                  "to follow because it includes so many speculative ideas "
                  "without a specific example to anchor our conversation "
                  "in something we can observe today.")
        self.assertGreater(len(quality._tokens(overlong)),48)
        self.assertEqual(issue(overlong),"wordy_expression")
        self.assertEqual(issue("Jules, that is the problem.",speaker="jules"),
                         "self_perspective_leak")

if __name__=="__main__":
    unittest.main()
