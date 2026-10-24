#!/usr/bin/env python3
"""Review sampling tests: ground provenance, deterministic windows and no mindreading."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from room_offline_replay import (
    public_events, read_public_feed, observer_view, review_windows,
)


def corpus():
    return {
        "conversation": [
            {"id": "q1", "speaker": "mara", "text": "Sarah, where was it?",
             "cognition": {"target": "sarah", "move_type": "deepen", "private_thought": "DO_NOT_COPY"},
             "private": {"secret": "SECRET"}, "at": "2026-10-20T00:00:01Z"},
            {"id": "a1", "speaker": "sarah", "text": "I found it by the garden.",
             "cognition": {"target": "mara", "move_type": "answer"}},
            {"id": "q2", "speaker": "jules", "text": "Can we look closer?",
             "cognition": {"target": "owen"}},
            {"id": "s1", "speaker": "owen", "text": "I remember the narrow gate."},
            {"id": "q3", "speaker": "mara", "text": "Could you explain that?",
             "cognition": {"target": "owen"}},
            {"id": "q4", "speaker": "owen", "text": "Do you mean the old tree?",
             "cognition": {"target": "mara"}},
            {"id": "s2", "speaker": "sarah", "text": "The same oak is still there."},
            {"id": "s3", "speaker": "jules", "text": "I left a note on the bench."},
        ]
    }


class ReplayTests(unittest.TestCase):
    def test_read_only_public_projection_excludes_private_thoughts(self):
        original = corpus()
        events = public_events(original)
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0]["reported_target"], "sarah")
        self.assertNotIn("DO_NOT_COPY", json.dumps(events))
        self.assertNotIn("SECRET", json.dumps(events))
        self.assertEqual(original["conversation"][0]["private"], {"secret": "SECRET"})

    def test_read_uses_existing_file_without_modification(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "feed.json"
            p.write_text(json.dumps(corpus()), encoding="utf-8")
            before = p.read_bytes()
            events = read_public_feed(p)
            self.assertEqual(len(events), 8)
            self.assertEqual(before, p.read_bytes())

    def test_replay_never_infers_sleeping_observers(self):
        events = public_events(corpus())
        witness = {"sarah": ["q1", "a1"], "jules": ["q2", "s3"]}
        self.assertEqual([x["source_id"] for x in observer_view(events, witness, "jules")],
                         ["q2", "s3"])
        self.assertEqual(observer_view(events, witness, "owen"), ())

    def test_duplicate_event_id_fails_closed(self):
        feed = corpus()
        feed["conversation"][1]["id"] = "q1"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            public_events(feed)

    def test_sampling_reproducible_preserves_context_and_negative_controls(self):
        events = public_events(corpus())
        first = review_windows(events, sample_count=4, seed="annotator-v1")
        second = review_windows(events, sample_count=4, seed="annotator-v1")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertTrue(any(w["sampling_cue"] == "unfiltered_turn" for w in first),
                        "must keep negative controls, not only question marks")
        self.assertTrue(any(w["sampling_cue"] != "unfiltered_turn" for w in first))
        for w in first:
            self.assertIn(w["anchor_id"], [e["source_id"] for e in w["public_context"]])
            self.assertIsNone(w["human_action_label"])

    def test_invalid_sampling_requests_rejected(self):
        events = public_events(corpus())
        for sample, seed in ((-1, "valid"), (2, "")):
            with self.assertRaises(ValueError):
                review_windows(events, sample_count=sample, seed=seed)


if __name__ == "__main__":
    unittest.main()
