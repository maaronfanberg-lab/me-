#!/usr/bin/env python3
"""Structural metrics remain observational, never a word ban."""
from __future__ import annotations

import unittest

from room_conversation_evidence import analyze, extract, key


def turn(i: int, who: str, text: str) -> dict:
    return {"id": str(i), "speaker": who, "text": text}


class EvidenceTests(unittest.TestCase):
    def test_filters_status_but_keeps_accepted_allen(self):
        feed = {"conversation": [
            turn(1, "system", "Heartbeat"),
            turn(2, "allen", "Sarah, where did it go?"),
            turn(3, "sarah", "I saw it nearby."),
        ]}
        self.assertEqual([x["id"] for x in extract(feed)], ["2", "3"])

    def test_counts_repeats_and_questions_without_auto_rejection(self):
        sample = [
            turn(1, "jules", "Can we try an experiment?"),
            turn(2, "owen", "Can we try an experiment?"),
            turn(3, "mara", "Can we try an experiment?"),
            turn(4, "sarah", "No."),
            turn(5, "jules", "Try."),
        ]
        result = analyze(sample)
        self.assertEqual(result["exact_adjacent_repeats"], 2)
        self.assertEqual(result["contiguous_question_echoes"], 2)
        self.assertEqual(result["longest_identical_action_run"], 3)
        self.assertEqual(result["short_autonomous_1to3_word_turns"], 2)
        self.assertEqual(result["autonomous_turns"], 5)
        self.assertEqual(len(result["repeat_evidence"]), 2)
        self.assertIn("Structural diagnostics", result["limitations"])

    def test_short_valid_reply_is_not_labeled_bad(self):
        result = analyze([turn(1, "mara", "Will you come?"),
                          turn(2, "sarah", "Yes.")])
        self.assertEqual(result["short_autonomous_1to3_word_turns"], 1)
        self.assertNotIn("invalid", result)
        self.assertNotIn("reject", result)

    def test_missing_or_wrong_feed_fails_closed(self):
        for bad in (None, {}, {"conversation": None}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                extract(bad)

    def test_normalization_preserves_action_identity_without_rules(self):
        self.assertEqual(key("What, next?!"), key("what next"))
        self.assertNotEqual(key("What next?"), key("I know what comes next."))

    def test_all_speakers_and_empty_sample(self):
        self.assertEqual(analyze([])["short_autonomous_rate"], None)
        self.assertEqual(analyze([turn(1, "allen", "Hi.")])["autonomous_turns"], 0)

    def test_respects_positive_window(self):
        feed = {"conversation": [turn(i, "sarah", str(i)) for i in range(20)]}
        self.assertEqual([x["id"] for x in extract(feed, 2)], ["18", "19"])
        with self.assertRaises(ValueError):
            extract(feed, 0)


if __name__ == "__main__":
    unittest.main()
