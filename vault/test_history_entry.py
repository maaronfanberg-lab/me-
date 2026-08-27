import json
import tempfile
import unittest
from pathlib import Path

import history_sanitizer
import room2_talker_entry


class Room2HistoryEntryTests(unittest.TestCase):
    def test_unsupported_hostility_is_quarantined(self):
        value = [
            {"id": "a", "speaker": "sarah", "text": "I'm not going to give in to your demands.", "at": "2026-08-27T14:00:00Z"},
            {"id": "b", "speaker": "jules", "text": "I'm curious about how this conversation might change next.", "at": "2026-08-27T14:01:00Z"},
        ]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(stats["removed"], 1)
        self.assertEqual([x["id"] for x in clean], ["b"])

    def test_meta_state_is_quarantined(self):
        value = [{"id": "a", "speaker": "mara", "text": "I'm watching regime_entropy while this state keeps changing today.", "at": "2026-08-27T14:00:00Z"}]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(clean, [])
        self.assertEqual(stats["removed"], 1)

    def test_duplicate_id_is_removed(self):
        good = {"id": "a", "speaker": "owen", "text": "I'm curious about where this conversation might go from here.", "at": "2026-08-27T14:00:00Z"}
        clean, stats = history_sanitizer.sanitize_history([good, dict(good)])
        self.assertEqual(len(clean), 1)
        self.assertEqual(stats["removed"], 1)

    def test_generic_boilerplate_is_quarantined(self):
        value = [{"id": "a", "speaker": "mara", "text": "I'm grateful for the opportunity to share my perspective today.", "at": "2026-08-27T14:00:00Z"}]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(clean, [])
        self.assertEqual(stats["removed"], 1)

    def test_generic_connection_filler_is_quarantined(self):
        value = [{"id": "a", "speaker": "sarah", "text": "I'm grateful for these moments of connection.", "at": "2026-08-27T14:00:00Z"}]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(clean, [])
        self.assertEqual(stats["removed"], 1)

    def test_telegraphic_word_salad_is_quarantined(self):
        value = [{"id": "a", "speaker": "owen", "text": "I appreciate deeply, care nature, conversation means.", "at": "2026-08-27T14:00:00Z"}]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(clean, [])
        self.assertEqual(stats["removed"], 1)
        self.assertTrue(room2_talker_entry._looks_telegraphic(value[0]["text"]))

    def test_stitched_multiple_sentences_are_quarantined(self):
        value = [{"id": "a", "speaker": "mara", "text": "I'm considering that idea carefully. That's great, Owen!", "at": "2026-08-27T14:00:00Z"}]
        clean, stats = history_sanitizer.sanitize_history(value)
        self.assertEqual(clean, [])
        self.assertEqual(stats["removed"], 1)

    def test_compact_text_keeps_concepts_not_sentence(self):
        cue = room2_talker_entry._compact_text("I'm curious because renewal can change where our attention goes next week.")
        self.assertEqual(cue, "curious because renewal change attention goes")
        self.assertNotIn("where our attention goes next week", cue)

    def test_sarah_abandonment_phase_is_rare_and_state_dependent(self):
        observables = [0.5] * 10
        observables[1] = 0.70
        observables[3] = 0.70
        observables[6] = 0.70
        observables[8] = 0.70
        active_report = {"source_cycle": 8, "entities": {"sarah": {"observables": observables, "dominant_regime": "transition"}}}
        quiet_report = {"source_cycle": 1, "entities": {"sarah": {"observables": observables, "dominant_regime": "transition"}}}
        active, intensity = room2_talker_entry._sarah_abandonment_pressure(active_report)
        quiet, _ = room2_talker_entry._sarah_abandonment_pressure(quiet_report)
        self.assertTrue(active)
        self.assertGreater(intensity, 0.5)
        self.assertFalse(quiet)
        style = room2_talker_entry._room2_attention_style(active_report, "sarah")
        self.assertIn("hiss", style.lower())
        self.assertIn("fear of being left", style.lower())
        self.assertIn("anger", style.lower())

    def test_balanced_guard_allows_six_word_overlap(self):
        text = "I'm curious because renewal can change our focus today."
        source = [{"text": "renewal can change our focus today very quickly"}]
        self.assertFalse(room2_talker_entry._balanced_echo_guard(text, source, n=5))

    def test_balanced_guard_blocks_seven_word_overlap(self):
        text = "I'm curious because renewal can change where our focus goes today."
        source = [{"text": "renewal can change where our focus goes today quickly"}]
        self.assertTrue(room2_talker_entry._balanced_echo_guard(text, source, n=5))

    def test_archive_guard_allows_eight_word_overlap(self):
        text = "I'm thinking renewal can change where attention goes next week."
        source = [{"text": "renewal can change where attention goes next week quickly"}]
        self.assertFalse(room2_talker_entry._balanced_echo_guard(text, source, n=7))

    def test_archive_guard_blocks_nine_word_overlap(self):
        text = "I'm thinking renewal can change where our attention goes next week."
        source = [{"text": "renewal can change where our attention goes next week quickly"}]
        self.assertTrue(room2_talker_entry._balanced_echo_guard(text, source, n=7))

    def test_entry_sanitizes_history_argument(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            path.write_text(json.dumps([
                {"id": "bad", "speaker": "sarah", "text": "I'm not going to give in to your demands.", "at": "2026-08-27T14:00:00Z"},
                {"id": "ok", "speaker": "mara", "text": "I'm curious about where this conversation might go from here.", "at": "2026-08-27T14:01:00Z"},
            ]))
            stats = room2_talker_entry.sanitize_history_argument(["entry", "feed", "report", str(path)])
            saved = json.loads(path.read_text())
            self.assertEqual(stats["removed"], 1)
            self.assertEqual([x["id"] for x in saved], ["ok"])


if __name__ == "__main__":
    unittest.main()
