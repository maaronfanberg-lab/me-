#!/usr/bin/env python3
import unittest
from room_social_memory import context_for, witnessed_history, retrieve, relationship_evidence


class SocialMemoryTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {"id": "a", "speaker": "mara", "text": "Sarah, look at the plant.",
             "at": "2026-11-15T00:00:00Z"},
            {"id": "b", "speaker": "owen", "text": "The notebook is wet.",
             "visibility": "private", "witnesses": ["owen", "jules"]},
            {"id": "c", "speaker": "sarah", "text": "Mara, the plant has new leaves."},
        ]

    def test_public_history_preserved(self):
        self.assertEqual([x.event_id for x in witnessed_history(self.events, "sarah")], ["a", "c"])

    def test_private_event_not_shared(self):
        self.assertEqual([x.event_id for x in witnessed_history(self.events, "jules")], ["a", "b", "c"])

    def test_relevance_retrieval(self):
        events = witnessed_history(self.events, "sarah")
        self.assertEqual(retrieve(events, "plant")[0].event_id, "c")

    def test_relationships_are_evidence_not_affinity(self):
        events = witnessed_history(self.events, "sarah")
        self.assertEqual(relationship_evidence(events, "sarah")["mara"], 2)
        self.assertNotIn("closeness", context_for("sarah", self.events, "plant"))

    def test_duplicate_event_not_replayed(self):
        events = self.events + [self.events[0]]
        self.assertEqual(len(witnessed_history(events, "sarah")), 2)


    def test_mentions_use_word_boundaries(self):
        events = [{"id": "m1", "speaker": "sarah", "text": "Samara visited the gallery."}]
        self.assertNotIn("mara", relationship_evidence(witnessed_history(events, "sarah"), "sarah"))
        events[0]["text"] = "Mara visited the gallery."
        self.assertEqual(relationship_evidence(witnessed_history(events, "sarah"), "sarah")["mara"], 1)

    def test_allen_addresses_are_counted_only_when_witnessed(self):
        events = [
            {"id": "a", "speaker": "allen", "text": "Sarah, look at this."},
            {"id": "b", "speaker": "allen", "text": "Sarah, a private thought.", "visibility": "private", "witnesses": ["allen"]},
        ]
        self.assertEqual(relationship_evidence(witnessed_history(events, "sarah"), "sarah")["allen"], 1)

    def test_unknown_person_is_rejected(self):
        with self.assertRaises(ValueError):
            witnessed_history(self.events, "stranger")



    def test_unknown_visibility_fails_closed(self):
        events = [
            {"id": "legacy", "speaker": "mara", "text": "Public legacy note."},
            {"id": "unknown", "speaker": "mara", "text": "Unclassified secret.", "visibility": "unclassified"},
            {"id": "empty", "speaker": "mara", "text": "Empty classification.", "visibility": ""},
            {"id": "private", "speaker": "mara", "text": "Private note.", "visibility": "private", "witnesses": ["mara"]},
        ]
        self.assertEqual([e.event_id for e in witnessed_history(events, "sarah")], ["legacy"])
        self.assertEqual([e.event_id for e in witnessed_history(events, "mara")],
                         ["legacy", "private"])

    def test_malformed_witnesses_cannot_grant_access(self):
        events = [{"id": "p", "speaker": "mara", "text": "Private note.",
                   "visibility": "private", "witnesses": "sarah"}]
        self.assertEqual(witnessed_history(events, "sarah"), [])
        self.assertEqual(len(witnessed_history(events, "mara")), 1)

    def test_duplicate_private_id_cannot_shadow_public_history(self):
        events = [
            {"id": "same", "speaker": "mara", "text": "Secret.", "visibility": "private", "witnesses": ["mara"]},
            {"id": "same", "speaker": "mara", "text": "Public note.", "visibility": "public"},
        ]
        self.assertEqual([e.text for e in witnessed_history(events, "sarah")], ["Public note."])


if __name__ == "__main__":
    unittest.main()
