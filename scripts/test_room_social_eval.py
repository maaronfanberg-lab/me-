#!/usr/bin/env python3
import unittest
from room_social_eval import audit


class SocialEvalTests(unittest.TestCase):
    def test_lexical_proxies_and_echo(self):
        trace = [
            {"speaker": "mara", "text": "I will quietly inspect the same red tree and its damaged leaves."},
            {"speaker": "jules", "text": "Mara, what did you find?"},
            {"speaker": "mara", "text": "I will quietly inspect the same red tree and its damaged leaves."},
        ]
        result = audit(trace)
        self.assertEqual(result["turns"], 3)
        self.assertEqual(result["same_speaker_near_duplicates"], 1)
        self.assertEqual(result["explicitly_addressed_turns"], 1)
        self.assertEqual(result["question_mark_turns"], 1)
        self.assertEqual(result["intention_phrase_turns"], 2)

    def test_empty_trace(self):
        result = audit([])
        self.assertEqual(result["turns"], 0)
        self.assertEqual(result["same_speaker_near_duplicates"], 0)

    def test_does_not_label_intentions_as_verified_actions(self):
        result = audit([{"speaker": "owen", "text": "I will measure the glass today."}])
        self.assertEqual(result["intention_phrase_turns"], 1)
        self.assertNotIn("verified_actions", result)


if __name__ == "__main__":
    unittest.main()
