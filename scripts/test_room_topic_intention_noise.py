#!/usr/bin/env python3
"""Regression: native self-referential speech must not become a topic."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import room_topic_bounded as topic


class TopicIntentionNoiseTests(unittest.TestCase):
    def test_intentions_not_subjects(self):
        for phrase in ("I'll", "decide", "choose", "intending", "planned"):
            with self.subTest(phrase=phrase):
                self.assertFalse(topic._valid_term(phrase))

    def test_concrete_objects_still_valid(self):
        for phrase in ("notebook", "plant", "bookshelf", "instruments"):
            with self.subTest(phrase=phrase):
                self.assertTrue(topic._valid_term(phrase))

    def test_old_bad_root_is_not_retained(self):
        old = topic.topic_template(62222)
        old.update({"root": "i'll", "current_facet": "i'll"})
        result = topic._normalize(old, 62223)
        self.assertIsNone(result["root"])


if __name__ == "__main__":
    unittest.main()
