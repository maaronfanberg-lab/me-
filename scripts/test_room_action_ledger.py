#!/usr/bin/env python3
"""Test evidence projection without assigning semantic understanding."""
import json
import unittest

from room_action_ledger import directed_question_evidence


def msg(id, speaker, text, target=None):
    return {"id": id, "speaker": speaker, "text": text,
            "cognition": {"target": target} if target else {}}


class LedgerTests(unittest.TestCase):
    def test_live_mismatch_creates_sarah_record_not_mara(self):
        source = msg("20261028T120004873-jules-v5", "jules",
            "Hey Sarah, can you tell me about the new exercise idea you want to explore?",
            "mara")
        sarah = directed_question_evidence([source], "sarah")
        self.assertEqual(len(sarah), 1)
        self.assertEqual(sarah[0]["source_id"], source["id"])
        self.assertEqual(sarah[0]["recipient"], "sarah")
        self.assertEqual(sarah[0]["semantic_resolution"], "not_assessed")
        self.assertEqual(directed_question_evidence([source], "mara"), [])

    def test_bystander_speech_does_not_count_as_recipient_uptake(self):
        history = [
            msg("q", "jules", "Mara, what happened?"),
            msg("b", "owen", "I might have an idea."),
            msg("s", "sarah", "I heard Jules."),
        ]
        record = directed_question_evidence(history, "mara")[0]
        self.assertEqual(record["subsequent_recipient_turn_ids"], [])
        history.append(msg("r", "mara", "I will have to think about that."))
        record = directed_question_evidence(history, "mara")[0]
        self.assertEqual(record["subsequent_recipient_turn_ids"], ["r"])
        self.assertEqual(record["semantic_resolution"], "not_assessed")

    def test_no_unearned_answer_status(self):
        history = [
            msg("q", "jules", "Mara, why do whales sing?"),
            msg("r", "mara", "Actually I was thinking about bicycles."),
        ]
        record = directed_question_evidence(history, "mara")[0]
        self.assertEqual(record["subsequent_recipient_turn_ids"], ["r"])
        self.assertNotIn("answered", json.dumps(record))
        self.assertEqual(record["semantic_resolution"], "not_assessed")

    def test_ambiguous_two_names_is_not_exclusive_debt(self):
        turn = msg("q", "jules",
            "Sarah, I thought of you. What do you think, Mara?", "mara")
        self.assertEqual(directed_question_evidence([turn], "sarah"), [])
        self.assertEqual(directed_question_evidence([turn], "mara"), [])

    def test_third_person_mention_and_hidden_target_are_not_address(self):
        history = [
            msg("q1", "jules", "What did Sarah say about the garden?", "sarah"),
            msg("q2", "owen", "Can you send that to Sarah?", "sarah"),
            msg("q3", "mara", "Is Sarah an evolutionary biologist?", "sarah"),
        ]
        self.assertEqual(directed_question_evidence(history, "sarah"), [])

    def test_allen_and_quoted_system_events(self):
        history = [
            msg("sys", "system", "Mara, did you get the message?"),
            msg("q", "allen", "Mara, did you get the message?"),
            msg("q", "allen", "Mara, did you get the message?"),
            msg("r", "mara", "Yes."),
        ]
        rows = directed_question_evidence(history, "mara")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_speaker"], "allen")
        self.assertEqual(rows[0]["subsequent_recipient_turn_ids"], ["r"])

    def test_bounds_and_truncation(self):
        history = [msg("q0", "allen", "Mara, did you hear?")]
        history += [msg("o%d" % i, "owen", "Just a note.") for i in range(10)]
        self.assertEqual(directed_question_evidence(history, "mara", window=8), [])
        self.assertEqual(len(directed_question_evidence(history, "mara", window=12)), 1)
        with self.assertRaises(ValueError):
            directed_question_evidence(history, "mara", window=0)
        with self.assertRaises(ValueError):
            directed_question_evidence(history, "mara", maximum=0)
        self.assertEqual(directed_question_evidence(history, "allen"), [])

    def test_hundred_conflicting_private_targets(self):
        order = ("sarah", "mara", "owen", "jules")
        for i in range(100):
            recipient = order[i % 4]
            speaker = order[(i + 1) % 4]
            wrong = order[(i + 2) % 4]
            history = [msg("source-%03d" % i, speaker,
                "Hey %s, can you explain this?" % recipient.capitalize(),
                wrong)]
            with self.subTest(i=i):
                row = directed_question_evidence(history, recipient)
                self.assertEqual(len(row), 1)
                self.assertEqual(row[0]["source_id"], "source-%03d" % i)
                self.assertEqual(directed_question_evidence(history, wrong), [])

    def test_only_public_provenance_is_exposed(self):
        event = msg("q", "jules", "Sarah, are you there?")
        event["private"] = {"unshared_thought": "secret belief"}
        row = directed_question_evidence([event], "sarah")[0]
        self.assertEqual(set(row), {
            "kind", "source_id", "source_speaker", "recipient", "source_text",
            "subsequent_recipient_turn_ids", "semantic_resolution", "provenance"})
        self.assertNotIn("secret belief", json.dumps(row))


if __name__ == "__main__":
    unittest.main()
