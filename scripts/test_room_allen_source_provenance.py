#!/usr/bin/env python3
"""Real Allen-injector regression: do not ascribe the archived topic to Allen."""
from __future__ import annotations

import os
import unittest
from room_participant import clean_terms, inject
from room_conversational_floor import last_participant_source_id, choose_next


class AllenProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = self.previous

    @staticmethod
    def state():
        return {"cycle": 100, "topic_episode": {
            "id": "topic-old", "root": "experimental category classification trees",
            "current_facet": "category trees", "status": "active"}}

    def test_real_injector_does_not_invent_topic_for_short_reply(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        history = []
        discourse = {}
        item = {"id": "allen-q-100", "text": "No.", "at": "2026-10-25T00:00:00Z"}
        self.assertEqual(inject(item, history, discourse, self.state()), item["id"])
        self.assertEqual(len(history), 1)
        message = history[0]
        self.assertEqual(message["text"], "No.")
        self.assertEqual(message["speaker"], "allen")
        self.assertEqual(message["cognition"]["topic_terms"], [])
        self.assertIsNone(message["cognition"]["topic_root"])
        self.assertIsNone(message["cognition"]["topic_facet"])
        self.assertEqual(last_participant_source_id(history), message["id"])
        self.assertEqual(discourse["nodes"][0]["topic_terms"], [])
        self.assertIsNone(discourse["nodes"][0]["topic_facet"])
        self.assertEqual(inject(item, history, discourse, self.state()), item["id"])
        self.assertEqual(len(history), 1)

    def test_legacy_keeps_its_existing_behavior(self):
        os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        self.assertEqual(clean_terms("No.", self.state()["topic_episode"]),
                         ["category trees", "experimental category classification trees"])
        h = []
        inject({"id": "old", "text": "No.", "at": "2026-10-25T00:00:00Z"},
               h, {}, self.state())
        self.assertEqual(h[0]["cognition"]["topic_root"],
                         "experimental category classification trees")

    def test_actual_address_and_source_survive_injection(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        h = []
        inject({"id": "allen-mara-1", "text": "Mara, can you explain?",
                "at": "2026-10-25T00:00:00Z"}, h, {}, self.state())
        self.assertEqual(h[0]["cognition"]["target"], "mara")
        self.assertNotIn("experimental category", " ".join(h[0]["cognition"]["topic_terms"]))
        cfg = {"p": {}, "sleeping_entities": []}
        chosen = choose_next(h, {"recurrent": {}}, cfg, {"entities": {}})
        self.assertEqual(chosen["speaker"], "mara")
        self.assertEqual(chosen["source_id"], h[0]["id"])
        self.assertEqual(chosen["reason"], "addressed_recipient")


if __name__ == "__main__":
    unittest.main()
