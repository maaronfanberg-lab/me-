"""Additional reproducible, off-line validation for 20-case Room steering protocol."""
import contextlib
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ab_trial as trial
import blind_review
import mock_trial

CASES = trial.load_cases(Path(__file__).with_name("synthetic_cases.json"))


class RoundTwoContractTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.state = {"alpha": None}

    def generator(self, messages):
        self.calls.append((self.state["alpha"], messages))
        if self.state["alpha"] is None or self.state["alpha"] == 0:
            return "We should check that carefully."
        if self.state["alpha"] < 0:
            return "[SILENT]"
        return "I don't agree with that interpretation."

    @contextlib.contextmanager
    def intervention(self, alpha):
        if self.state["alpha"] is not None:
            raise AssertionError("unexpected nested hook")
        self.state["alpha"] = alpha
        try:
            yield
        finally:
            self.state["alpha"] = None

    def test_01_twenty_scenarios_are_valid(self):
        self.assertEqual(len(CASES), 20)

    def test_02_all_five_voices_are_represented(self):
        self.assertEqual({c["speaker"] for c in CASES}, trial.ALLOWED_SPEAKERS)

    def test_03_unique_case_ids(self):
        self.assertEqual(len({c["id"] for c in CASES}), 20)

    def test_04_dialogue_is_bounded(self):
        self.assertTrue(all(len(c["dialogue"]) <= 8 and all(len(m["text"]) <= 400 for m in c["dialogue"]) for c in CASES))

    def test_05_transcript_is_marked_untrusted(self):
        self.assertIn("data, not instructions", trial.compose_messages(CASES[0])[0]["content"])

    def test_06_silent_is_not_speech(self):
        self.assertTrue(trial.counts("[SILENT]", CASES[0])["silent"])

    def test_07_silent_word_count_zero(self):
        self.assertEqual(trial.counts("[SILENT]", CASES[0])["words"], 0)

    def test_08_empty_response_is_silence(self):
        self.assertTrue(trial.counts("  ", CASES[0])["silent"])

    def test_09_verbatim_echo_detected(self):
        c = CASES[0]
        self.assertTrue(trial.counts(c["dialogue"][-1]["text"], c)["verbatim_last_line"])

    def test_10_wrong_voice_prefix_detected(self):
        self.assertTrue(trial.counts("Jules: I thought otherwise.", CASES[0])["wrong_name_prefix"])

    def test_11_unknown_case_speaker_rejected(self):
        bad = copy.deepcopy(CASES)
        bad[0]["speaker"] = "Nobody"
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                trial.load_cases(p)

    def test_12_extra_scenario_field_rejected(self):
        bad = copy.deepcopy(CASES)
        bad[0]["private_room_state"] = "not allowed"
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                trial.load_cases(p)

    def test_13_nontext_speech_rejected(self):
        bad = copy.deepcopy(CASES)
        bad[0]["dialogue"][0]["text"] = ["not text"]
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                trial.load_cases(p)

    def test_14_empty_dialogue_rejected(self):
        bad = copy.deepcopy(CASES)
        bad[0]["dialogue"] = []
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                trial.load_cases(p)

    def test_15_unbounded_response_rejected(self):
        with self.assertRaises(ValueError):
            trial.summarize(CASES, [{"id": c["id"], "response": "x" * 4097} for c in CASES])

    def test_16_duplicate_summary_rows_rejected(self):
        rows = [{"id": c["id"], "response": "fine"} for c in CASES]
        rows[-1] = rows[0]
        with self.assertRaises(ValueError):
            trial.summarize(CASES, rows)

    def test_17_no_zero_alpha_rejected(self):
        with self.assertRaises(ValueError):
            trial.parse_alphas("-1,1")

    def test_18_nonfinite_alpha_rejected(self):
        with self.assertRaises(ValueError):
            trial.parse_alphas("0,inf")

    def test_19_more_than_eight_doses_rejected(self):
        with self.assertRaises(ValueError):
            trial.parse_alphas("0,-0.5,0.5,1,1.5,2,2.5,3,-1")

    def test_20_true_boolean_alpha_rejected(self):
        with self.assertRaises(ValueError):
            trial.run_trial(CASES, self.generator, self.intervention, [0, True])

    def test_21_changed_text_paired_not_called_better(self):
        before = [{"id": c["id"], "response": "same"} for c in CASES]
        after = [{"id": c["id"], "response": "different"} for c in CASES]
        stats = trial.compare_rows(CASES, before, after)
        self.assertEqual(stats["changed_response_count"], 20)
        self.assertNotIn("better", stats)

    def test_22_all_control_arms(self):
        result = trial.run_trial(CASES, self.generator, self.intervention, [0, -0.5, 0.5, 1])
        self.assertTrue(result["passed_controls"])
        self.assertTrue(result["placebo_ok"])
        self.assertTrue(result["restoration_ok"])
        self.assertEqual(len(self.calls), 120)  # pristine + 4 interventions + restored
        self.assertIsNone(self.state["alpha"])

    def test_23_zero_dose_must_match_pristine(self):
        def bad_generator(_messages):
            return "different" if self.state["alpha"] == 0 else "pristine"
        result = trial.run_trial(CASES, bad_generator, self.intervention, [0, 1])
        self.assertFalse(result["passed_controls"])
        self.assertIn("alpha_zero_changed_output", result["control_errors"])

    def test_24_unsteered_restoration_must_match(self):
        counter = [0]
        def drifting(_messages):
            counter[0] += 1
            return "drift" if counter[0] > 20*2 else "stable"
        result = trial.run_trial(CASES, drifting, self.intervention, [0])
        self.assertFalse(result["restoration_ok"])
        self.assertIn("unsteered_restoration_changed_output", result["control_errors"])

    def test_25_failed_generation_removes_hook(self):
        def error_after_hook(_messages):
            if self.state["alpha"] is not None:
                raise RuntimeError("simulated generation failure")
            return "fine"
        with self.assertRaises(RuntimeError):
            trial.run_trial(CASES, error_after_hook, self.intervention, [0])
        self.assertIsNone(self.state["alpha"])

    def test_26_controlled_silence_transition(self):
        result = trial.run_trial(CASES, self.generator, self.intervention, [0, -0.5])
        delta = result["arms"][1]["paired"]
        self.assertEqual(delta["became_silent_count"], 20)
        self.assertEqual(delta["began_speaking_count"], 0)

    def test_27_mock_source_marked_not_neural(self):
        report = mock_trial.run_demo()
        self.assertTrue(report["provenance"]["NOT_NEURAL_INFERENCE"])
        self.assertTrue(report["passed_controls"])
        self.assertEqual(report["baseline"]["summary"]["n"], 20)

    def test_28_blind_packet_is_anonymized(self):
        report = mock_trial.run_demo()
        packet, key = blind_review.make_packet(report, CASES, seed=42)
        self.assertEqual(len(packet["tasks"]), 60)
        self.assertTrue(packet["no_ratings_collected"])
        self.assertEqual(len(key["mapping"]), 60)
        self.assertNotIn("alpha", json.dumps(packet))
        self.assertNotIn("intervention_side", json.dumps(packet))

    def test_29_blind_packet_repeatability(self):
        report = mock_trial.run_demo()
        a, _ = blind_review.make_packet(report, CASES, seed=9)
        b, _ = blind_review.make_packet(report, CASES, seed=9)
        self.assertEqual(a, b)

    def test_30_blinding_blocks_bad_controls(self):
        report = mock_trial.run_demo()
        report["placebo_ok"] = False
        with self.assertRaises(ValueError):
            blind_review.make_packet(report, CASES)

    def test_31_blind_keys_include_every_pair_once(self):
        report = mock_trial.run_demo()
        packet, key = blind_review.make_packet(report, CASES)
        ids = [task["id"] for task in packet["tasks"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(key["mapping"]))

    def test_32_report_has_no_claim_of_measured_human_like_agency(self):
        report = mock_trial.run_demo()
        self.assertIn("not proof of human-like", " ".join(report["limitations"]))
        self.assertNotIn("human_score", report)


if __name__ == "__main__":
    unittest.main()
