#!/usr/bin/env python3
import unittest
from room_social_eval import audit, proposed_work_signature


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

    def test_recurrent_work_promises_are_not_missed_as_identical_text(self):
        # Distinct sentences, same unverified proposal. No need for a ban.
        trace = [
            {"speaker": "mara", "text": "I decide to inspect the notebook."},
            {"speaker": "jules", "text": "I will test the instruments."},
            {"speaker": "mara", "text": "I'll quietly inspect the notebook for another clue."},
        ]
        result = audit(trace)
        self.assertEqual(result["same_speaker_near_duplicates"], 0)
        self.assertEqual(result["repeated_intended_work_turns_within_80"], 1)
        self.assertEqual(result["distinct_intended_work_signatures"], 2)
        self.assertEqual(result["repeated_intended_work_examples"][0]["speaker"], "mara")

    def test_work_proposal_is_not_verified_work_and_requires_affordance(self):
        self.assertEqual(proposed_work_signature("I'll inspect the notebook."), ("inspect", "notebook"))
        self.assertEqual(proposed_work_signature("I decide to write(board, notebook)"), ("write", "board"))
        self.assertIsNone(proposed_work_signature("The plant might need inspecting."))
        self.assertIsNone(proposed_work_signature("I'll write on the plant."))
        self.assertEqual(audit([{"speaker": "sarah", "text": "I'll inspect the notebook."}])["repeated_intended_work_turns_within_80"], 0)

    def test_does_not_label_intentions_as_verified_actions(self):
        result = audit([{"speaker": "owen", "text": "I will measure the glass today."}])
        self.assertEqual(result["intention_phrase_turns"], 1)
        self.assertNotIn("verified_actions", result)


if __name__ == "__main__":
    unittest.main()
