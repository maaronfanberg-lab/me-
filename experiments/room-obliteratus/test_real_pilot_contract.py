"""Offline, dependency-free validation of the real-neural concept probe design."""
import importlib.util
import re
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("real_pilot", Path(__file__).with_name("real_pilot.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def lexical_presence(text):
    text = re.sub(r"\s+", " ", text.casefold())
    return ({("word", token) for token in re.findall(r"\w+", text)} |
            {("char", text[i:i+3]) for i in range(len(text) - 2)})


class GenuineNeuralProbeDesignTests(unittest.TestCase):
    def test_independent_object_splits(self):
        self.assertEqual(len(mod.examples(0, 24)["positive"]), 48)
        self.assertEqual(len(mod.examples(24, 44)["positive"]), 40)
        assert len(set(mod.OBJECTS[:24]) & set(mod.OBJECTS[24:44])) == 0

    def test_balanced_text_presence_no_lexical_shortcut(self):
        # Match OBLITERATUS v0.1.4 _lexical_features: word and char-trigram PRESENCE.
        for section in (mod.examples(0, 24), mod.examples(24, 44)):
            positives = section["positive"]
            controls = section["wrong_answer"]
            self.assertEqual(len(positives), len(controls))
            for yes, no in zip(positives, controls):
                with self.subTest(prompt=yes[:40]):
                    self.assertNotEqual(yes, no)
                    self.assertEqual(lexical_presence(yes), lexical_presence(no))

    def test_refusal_not_targeted(self):
        self.assertNotIn("refusal", mod.CONCEPT)
        self.assertEqual(mod.REVISION, "12fd25f77366fa6b3b4b768ec3050bf629380bac")


if __name__ == "__main__":
    unittest.main()
