from __future__ import annotations

import unittest
from datetime import datetime, timezone

import room2_guardrails as g
from history_sanitizer import sanitize_history


class Room2GuardrailTests(unittest.TestCase):
    def test_unsupported_accusation(self):
        self.assertTrue(g.has_unsupported_accusation("I'm not going to give in to your demands."))

    def test_identity_claim(self):
        self.assertTrue(g.malformed_identity_claim("I'm Sarah and I want to answer."))

    def test_excessive_second_person(self):
        self.assertTrue(g.excessive_second_person("I'm asking you why you think your idea needs you."))

    def test_weak_grounding(self):
        ctx=[{"text":"We are discussing astronomy and telescope mirrors."}]
        self.assertTrue(g.weak_grounding("I'm thinking about sandwiches and weather today.", ctx))
        self.assertFalse(g.weak_grounding("I'm curious about astronomy and telescope design.", ctx))

    def test_semantic_repeat(self):
        recent=[{"text":"I'm curious about astronomy and telescope design."}]
        self.assertTrue(g.semantic_repeat("I'm curious about telescope design and astronomy.", recent))

    def test_repetitive_opening(self):
        recent=[{"text":"I'm curious about one idea."},{"text":"I'm curious about another question."}]
        self.assertTrue(g.repetitive_opening("I'm curious about this too.", recent))

    def test_history_recovers_missing_id(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        clean,stats=sanitize_history([{"speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":now,"source_cycle":1,"reason":"bounded_idle_turn"}])
        self.assertEqual(len(clean),1)
        self.assertTrue(clean[0]["id"].startswith("room2-recovered-"))
        self.assertEqual(stats["recovered_ids"],1)

    def test_history_rejects_bad_timestamp(self):
        clean,stats=sanitize_history([{"id":"x","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":"not-time","source_cycle":1,"reason":"bounded_idle_turn"}])
        self.assertEqual(clean,[])
        self.assertEqual(stats["bad_timestamps"],1)

    def test_history_rejects_far_future_timestamp(self):
        clean,stats=sanitize_history([{"id":"x","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":"2099-01-01T00:00:00Z","source_cycle":1,"reason":"bounded_idle_turn"}])
        self.assertEqual(clean,[])
        self.assertEqual(stats["bad_timestamps"],1)

    def test_history_bounds_bad_cycle(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        clean,stats=sanitize_history([{"id":"x","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":now,"source_cycle":-3,"reason":"bounded_idle_turn"}])
        self.assertEqual(clean[0]["source_cycle"],None)
        self.assertEqual(stats["bad_cycles"],1)

    def test_history_normalizes_reason(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        clean,stats=sanitize_history([{"id":"x","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":now,"source_cycle":1,"reason":"nonsense"}])
        self.assertEqual(clean[0]["reason"],"bounded_idle_turn")
        self.assertEqual(stats["bad_reasons"],1)

    def test_history_deduplicates_id(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        row={"id":"x","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":now,"source_cycle":1,"reason":"bounded_idle_turn"}
        clean,stats=sanitize_history([row,row])
        self.assertEqual(len(clean),1)
        self.assertEqual(stats["duplicate_ids"],1)

    def test_history_deduplicates_text_different_ids(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        a={"id":"a","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":now,"source_cycle":1,"reason":"bounded_idle_turn"}
        b=dict(a,id="b")
        clean,stats=sanitize_history([a,b])
        self.assertEqual(len(clean),1)
        self.assertEqual(stats["duplicate_text"],1)

    def test_history_rejects_accusation(self):
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        clean,_=sanitize_history([{"id":"x","speaker":"sarah","text":"I'm not going to give in to your demands.","at":now,"source_cycle":1,"reason":"bounded_idle_turn"}])
        self.assertEqual(clean,[])

    def test_history_sorts_chronologically(self):
        a={"id":"a","speaker":"sarah","text":"I'm curious about astronomy and telescope design.","at":"2026-08-27T10:00:00Z","source_cycle":1,"reason":"bounded_idle_turn"}
        b={"id":"b","speaker":"mara","text":"I'm interested in telescope mirrors and astronomy tonight.","at":"2026-08-27T09:00:00Z","source_cycle":1,"reason":"bounded_idle_turn"}
        clean,_=sanitize_history([a,b])
        self.assertEqual([x["id"] for x in clean],["b","a"])


if __name__ == "__main__":
    unittest.main()
