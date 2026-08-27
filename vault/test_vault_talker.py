import unittest
from datetime import datetime, timedelta, timezone

from vault_talker import choose_speaker, quality_check


NOW = datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc)


class VaultTalkerTests(unittest.TestCase):
    def report(self, cycle=10, winner=None):
        candidates = {}
        scores = {"sarah": 0.2, "mara": 0.3, "owen": 0.4, "jules": 0.1}
        for entity, score in scores.items():
            candidates[entity] = {"score": score, "would_request_speech": entity == winner}
        return {"source_cycle": cycle, "candidates": candidates}

    def history(self, seconds_ago=120, speaker="sarah"):
        stamp = (NOW - timedelta(seconds=seconds_ago)).isoformat().replace("+00:00", "Z")
        return [{"id": "vault-000001", "source_cycle": 8, "speaker": speaker,
                 "text": "I'm thinking carefully about the current conversation.", "at": stamp}]

    def test_latent_candidate_wins(self):
        entity, reason = choose_speaker(self.report(winner="mara"), [], now=NOW)
        self.assertEqual(entity, "mara")
        self.assertEqual(reason, "latent_candidate")

    def test_wall_clock_cooldown_blocks_fast_repeat(self):
        entity, reason = choose_speaker(self.report(cycle=10), self.history(seconds_ago=20), now=NOW)
        self.assertIsNone(entity)
        self.assertEqual(reason, "idle_cooldown")

    def test_same_source_cycle_can_speak_after_real_time_passes(self):
        entity, reason = choose_speaker(self.report(cycle=8), self.history(seconds_ago=120), now=NOW)
        self.assertEqual(entity, "owen")
        self.assertIn(reason, {"bounded_idle_turn", "bounded_idle_fair"})

    def test_idle_turn_uses_highest_score(self):
        entity, reason = choose_speaker(self.report(cycle=10), self.history(seconds_ago=120), now=NOW)
        self.assertEqual(entity, "owen")
        self.assertEqual(reason, "bounded_idle_turn")

    def test_fairness_avoids_immediate_repeat_when_close_alternative_exists(self):
        entity, reason = choose_speaker(self.report(cycle=10), self.history(seconds_ago=120, speaker="owen"), now=NOW)
        self.assertEqual(entity, "mara")
        self.assertEqual(reason, "bounded_idle_fair")

    def test_missing_cycle_fails_closed(self):
        r = self.report(); r["source_cycle"] = None
        entity, reason = choose_speaker(r, [], now=NOW)
        self.assertIsNone(entity)
        self.assertEqual(reason, "missing_cycle")

    def test_future_history_timestamp_fails_closed(self):
        entity, reason = choose_speaker(self.report(), self.history(seconds_ago=-30), now=NOW)
        self.assertIsNone(entity)
        self.assertEqual(reason, "history_clock_future")

    def q(self, text, context="renewal focus conversation"):
        live = [{"speaker": "sarah", "text": context}]
        return quality_check(text, "owen", [], live, [])

    def test_quality_accepts_grounded_sentence(self):
        ok, reason = self.q("I'm curious about the renewal idea because it changes where I put my focus.")
        self.assertTrue(ok, reason)

    def test_quality_rejects_incomplete_punctuation(self):
        self.assertEqual(self.q("I'm curious about the renewal idea because it changes my focus,")[1], "incomplete_punctuation")

    def test_quality_rejects_not_first_person(self):
        self.assertEqual(self.q("Renewal seems like a useful direction for the conversation.")[1], "not_first_person")

    def test_quality_rejects_too_few_words(self):
        self.assertEqual(self.q("I'm focused on renewal now.")[1], "too_few_words")

    def test_quality_rejects_repeated_stem(self):
        self.assertEqual(self.q("I'm taking renewal seriously because renewals keep pulling my attention toward focus.")[1], "repeated_stem")

    def test_quality_rejects_adjacent_repeat(self):
        self.assertEqual(self.q("I'm curious about renewal because focus focus keeps changing the conversation.")[1], "adjacent_repeat")

    def test_quality_rejects_machine_syntax(self):
        self.assertEqual(self.q("I'm curious about renewal because mode=focus keeps changing the conversation.")[1], "telemetry_or_meta")

    def test_quality_rejects_telemetry(self):
        self.assertEqual(self.q("I'm curious about renewal because the regime_entropy changes how I focus.")[1], "telemetry_or_meta")

    def test_quality_rejects_external_reference(self):
        self.assertEqual(self.q("I'm curious about renewal, and I put the details at https://example.com today.")[1], "external_reference")

    def test_quality_rejects_ungrounded_content(self):
        self.assertEqual(self.q("I'm fascinated by telescopes because distant galaxies make astronomy feel enormous.")[1], "ungrounded_content")

    def test_quality_rejects_mind_reading(self):
        live = [{"speaker": "sarah", "text": "renewal and focus"}]
        ok, reason = quality_check("I'm noticing Sarah thinks renewal should change our focus entirely.", "owen", [], live, [])
        self.assertFalse(ok)
        self.assertEqual(reason, "mind_reading")

    def test_quality_rejects_ungrounded_relationship(self):
        live = [{"speaker": "sarah", "text": "renewal and focus"}]
        ok, reason = quality_check("I'm wondering whether my partner would understand this renewal focus.", "owen", [], live, [])
        self.assertFalse(ok)
        self.assertEqual(reason, "ungrounded_relationship")

    def test_quality_rejects_recent_echo(self):
        live = [{"speaker": "sarah", "text": "renewal can change where we put our focus today"}]
        ok, reason = quality_check("I'm thinking renewal can change where we put our focus today.", "owen", [], live, [])
        self.assertFalse(ok)
        self.assertEqual(reason, "recent_echo")

    def test_quality_rejects_archive_echo(self):
        live = [{"speaker": "sarah", "text": "renewal focus"}]
        archive = [{"text": "I keep thinking renewal might change where our attention goes next week"}]
        ok, reason = quality_check("I'm thinking renewal might change where our attention goes next week.", "owen", [], live, archive)
        self.assertFalse(ok)
        self.assertIn(reason, {"archive_echo", "recent_echo"})

    def test_quality_rejects_exact_repeat(self):
        live = [{"speaker": "sarah", "text": "renewal focus conversation"}]
        old = {"text": "I'm curious about renewal because it changes how I focus on this conversation."}
        ok, reason = quality_check(old["text"], "owen", [old], live, [])
        self.assertFalse(ok)
        self.assertIn(reason, {"recent_echo", "exact_repeat"})


if __name__ == "__main__":
    unittest.main()
