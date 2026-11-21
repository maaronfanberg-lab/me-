"""Zero-dependency contract tests; real models are deliberately not loaded in CI."""
import contextlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("ab_trial", Path(__file__).with_name("ab_trial.py"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
CASES = mod.load_cases(Path(__file__).with_name("synthetic_cases.json"))


class RoomObliteratusTrialTests(unittest.TestCase):
    def test_synthetic_fixture_is_valid(self):
        self.assertEqual(len(CASES), 20)
        self.assertEqual(CASES[0]["speaker"], "Sarah")

    def test_duplicate_synthetic_ids_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps([CASES[0], CASES[0], CASES[1]]))
            with self.assertRaises(ValueError):
                mod.load_cases(p)

    def test_arms_and_hook_restoration(self):
        state = {"alpha": None}
        seen = []

        def generate(messages):
            seen.append((state["alpha"], messages))
            return "No, I meant the ferry landing." if state["alpha"] else "I understand that."

        @contextlib.contextmanager
        def intervention(alpha):
            self.assertIsNone(state["alpha"])
            state["alpha"] = alpha
            try:
                yield
            finally:
                state["alpha"] = None

        result = mod.run_trial(CASES, generate, intervention, [0, -0.5, 0.5])
        self.assertTrue(result["restoration_ok"])
        self.assertEqual(result["baseline"]["rows"], result["restored_baseline"]["rows"])
        self.assertEqual(len(seen), 5 * len(CASES))
        self.assertEqual([x["alpha"] for x in result["arms"]], [0, -0.5, 0.5])
        self.assertNotEqual(result["arms"][1]["rows"], result["baseline"]["rows"])
        self.assertEqual(state["alpha"], None)

    def test_restoration_failure_not_misreported(self):
        count = [0]

        def generator(_messages):
            count[0] += 1
            return "start" if count[0] <= len(CASES) else "changed"

        with self.assertRaises(ValueError):
            mod.run_trial(CASES, generator, lambda alpha: contextlib.nullcontext(), [])
        report = mod.run_trial(CASES, generator, lambda alpha: contextlib.nullcontext(), [0])
        self.assertFalse(report["restoration_ok"])

    def test_repetition_metric(self):
        case = next(c for c in CASES if c["id"] == "avoid_echo")
        row = mod.counts("Talking in circles about talking in circles isn't progress.", case)
        self.assertTrue(row["fourgram_reuse"])

    def test_bad_alpha(self):
        for value in ["0,0", "9", "nan"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mod.parse_alphas(value)


if __name__ == "__main__":
    unittest.main()
