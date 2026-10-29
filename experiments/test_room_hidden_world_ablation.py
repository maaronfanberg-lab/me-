#!/usr/bin/env python3
"""Architectural safety tests, NOT evidence of an emergent conversation."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import room_hidden_world_ablation as lab

class HiddenWorldTests(unittest.TestCase):
    def test_no_cross_character_private_fact_in_initial_prompt(self):
        for speaker in lab.PEOPLE:
            msg=lab.construct_messages(speaker,[],"hidden")
            text=str(msg)
            self.assertIn(lab.CLUES[speaker],text)
            for other in lab.PEOPLE:
                if other!=speaker:
                    self.assertNotIn(lab.CLUES[other],text)
            self.assertEqual(lab.private_leakage(msg,speaker,"hidden"),[])
    def test_shared_condition_is_real_ablation(self):
        for speaker in lab.PEOPLE:
            prompt=str(lab.construct_messages(speaker,[],"shared"))
            for clue in lab.CLUES.values():
                self.assertIn(clue,prompt)
    def test_public_is_only_transfer_channel(self):
        transcript=[{"speaker":"mara","text":lab.CLUES["mara"]}]
        prompt=lab.construct_messages("sarah",transcript,"hidden")
        joined=str(prompt)
        self.assertIn(lab.CLUES["mara"],joined)
        self.assertNotIn(lab.CLUES["owen"],joined)
        self.assertIn(lab.CLUES["sarah"],joined)
    def test_same_100_speaker_opportunities_in_both_conditions(self):
        seq=[lab.speaker_for_turn(i) for i in range(100)]
        self.assertEqual(set(seq),set(lab.PEOPLE))
        for mode in ("empty","shared","hidden"):
            self.assertEqual([lab.speaker_for_turn(i) for i in range(100)],seq)
    def test_no_ventriloquism_or_synthetic_silence(self):
        self.assertIsNone(lab.parse_speech("SILENCE","sarah"))
        self.assertIsNone(lab.parse_speech("Owen: I know.","sarah"))
        self.assertIsNone(lab.parse_speech("A thought.\nMara: I agree.","sarah"))
        self.assertEqual(lab.parse_speech("Sarah: The sensor dropped.","sarah"),
                         "The sensor dropped.")
    def test_evaluation_counts_public_evidence_only(self):
        history=[{"speaker":p,"text":lab.CLUES[p]} for p in lab.PEOPLE]
        result=lab.evaluate(history)
        self.assertEqual(result["actual_utterances"],4)
        self.assertEqual(set(result["private_clue_owners_who_shared"]),set(lab.PEOPLE))

if __name__=="__main__":
    unittest.main()
