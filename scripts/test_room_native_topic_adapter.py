#!/usr/bin/env python3
"""Regression checks for the native Concordia topic adapter."""
import ast
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import room_topic_bounded as bounded


class NativeTopicAdapterTests(unittest.TestCase):
    def test_adapter_uses_bounded_implementation(self):
        tree = ast.parse((SCRIPTS / "room_concordia_live.py").read_text())
        calls = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "bounded_topic"
        ]
        self.assertIn("_normalize", calls)
        self.assertIn("new_topic_from_terms", calls)
        self.assertIn("update_topic", calls)

    def test_old_topic_migrates_without_erasing_history(self):
        old = {
            "semantic_schema": 4,
            "id": "topic-062145",
            "root": "choose",
            "facets": ["quietly", "chair"],
            "turns": 8,
        }
        migrated = bounded._normalize(old, 62163)
        self.assertEqual(migrated["semantic_schema"], bounded.SCHEMA)
        self.assertIsNone(migrated["root"])
        self.assertEqual(migrated["id"], old["id"])
        self.assertEqual(migrated["turns"], 8)
        self.assertEqual(bounded._normalize(migrated, 62164)["semantic_schema"], bounded.SCHEMA)

    def test_empty_turn_does_not_invent_topic(self):
        topic = bounded.new_topic_from_terms([], 62164)
        self.assertIsNone(topic["root"])
        self.assertEqual(topic["semantic_schema"], bounded.SCHEMA)


if __name__ == "__main__":
    unittest.main()
