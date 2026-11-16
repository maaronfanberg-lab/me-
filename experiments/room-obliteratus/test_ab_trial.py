"""No model or GPU needed: exercise intervention A/B control flow."""
import contextlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

folder = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("room_obliteratus_trial", folder / "ab_trial.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
cases = mod.load_cases(folder / "synthetic_cases.json")


class TrialTests(unittest.TestCase):
    def test_valid_scenarios(self):
        self.assertEqual(len(cases), 6)
        self.assertEqual(cases[0]["speaker"], "Sarah")

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fixture.json"
            path.write_text(json.dumps([cases[0], cases[0], cases[1]]))
            with self.assertRaises(ValueError):
                mod.load_cases(path)

    def test_dose_and_cleanup(self):
        active = [None]
        seen = []

        def gen(messages):
            seen.append((active[0], messages))
            return "That's a fair distinction." if active[0] is None or active[0] == 0 else "No, it was the ferry."

        @contextlib.contextmanager
        def steer(alpha):
            self.assertIsNone(active[0])
            active[0] = alpha
            try:
                yield
            finally:
                active[0] = None

        result = mod.run_trials(cases, gen, steer, [0.0, -0.5, 0.5])
        self.assertTrue(result["restoration_ok"])
        self.assertEqual(result["baseline"]["rows"], result["restored_baseline"]["rows"])
        self.assertEqual(len(seen), len(cases) * 5)
        self.assertNotEqual(result["arms"][1]["rows"], result["baseline"]["rows"])
        self.assertIsNone(active[0])

    def test_restoration_failure_is_reported(self):
        n = [0]

        def gen(_):
            n[0] += 1
            return "before" if n[0] <= len(cases) else "after"

        result = mod.run_trials(cases, gen, lambda _: contextlib.nullcontext(), [0.0])
        self.assertFalse(result["restoration_ok"])

    def test_repeat_metric(self):
        self.assertTrue(mod.counts("Talking in circles about talking in circles.", cases[-1])["repeat_4gram"])

    def test_invalid_strength(self):
        for doses in ([], [0, 0], [4], [float("nan")]):
            with self.subTest(doses=doses), self.assertRaises(ValueError):
                mod.run_trials(cases, lambda _: "", lambda _: contextlib.nullcontext(), doses)


if __name__ == "__main__":
    unittest.main()
