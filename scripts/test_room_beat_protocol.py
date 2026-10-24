#!/usr/bin/env python3
"""Tests for offline-only health semantics, including 900s watchdog contrast."""
from __future__ import annotations

import unittest

from room_beat_protocol import (
    BeatOutcome, advance_health, classify_beat, watchdog_status,
)

STAGES = {"perception": True, "observation": True, "floor_selection": True}


def quiet(key):
    return classify_beat(
        key, completed_stages=STAGES, selected_speaker=None,
        expression_attempted=False,
    )


def failed(key):
    return classify_beat(
        key, completed_stages=STAGES, selected_speaker="sarah",
        expression_attempted=True, expression_valid=False,
    )


class BeatProtocolTests(unittest.TestCase):
    def test_silence_does_not_require_expression_generation(self):
        b = quiet("d-1")
        self.assertEqual(b.kind, "chosen_silence")
        self.assertTrue(b.healthy)
        self.assertIsNone(b.selected_speaker)
        self.assertFalse(b.published_message_ids)

    def test_invalid_generation_is_not_silence(self):
        b = failed("d-1")
        self.assertEqual(b.kind, "validation_failed")
        self.assertFalse(b.healthy)
        self.assertIsNone(b.selected_speaker)
        self.assertEqual(
            classify_beat("d", completed_stages=STAGES, selected_speaker="mara",
                          expression_attempted=False).kind,
            "generation_failed",
        )
        self.assertEqual(
            classify_beat("d", completed_stages=STAGES, selected_speaker=None,
                          expression_attempted=False,
                          failure="model_unavailable").kind,
            "model_unavailable",
        )

    def test_missing_stage_does_not_pass_as_social_decision(self):
        incomplete = dict(STAGES, observation=False)
        self.assertEqual(
            classify_beat("d", completed_stages=incomplete, selected_speaker=None,
                          expression_attempted=False).kind,
            "stage_failed",
        )

    def test_mismatched_outcome_rejected(self):
        with self.assertRaises(ValueError):
            BeatOutcome("chosen_silence", "d", published_message_ids=("m1",))
        with self.assertRaises(ValueError):
            BeatOutcome("spoken", "d")
        with self.assertRaises(ValueError):
            BeatOutcome("model_unavailable", "d", published_message_ids=("m1",))

    def test_healthy_silence_survives_over_900s_without_word_output(self):
        for seed in range(20):
            state, commits = {}, 0
            for beat in range(1001):
                state, persist = advance_health(state, quiet(f"{seed}-{beat}"), beat)
                commits += int(persist)
                if beat >= 900:
                    self.assertEqual(watchdog_status(state, beat), "healthy")
            self.assertTrue(state["silence_review"])
            self.assertEqual(state["last_public_message_at"], None)
            self.assertLessEqual(commits, 6, "silent beats must not cause a Git commit storm")

    def test_failure_ratio_cannot_be_hidden_by_occasional_silence(self):
        state = {}
        for beat in range(40):
            result = quiet(str(beat)) if beat % 10 == 0 else failed(str(beat))
            state, _ = advance_health(state, result, beat)
        self.assertTrue(state["degraded"])
        self.assertEqual(state["failure_count_window"], 18)
        self.assertEqual(watchdog_status(state, 40), "unhealthy")

    def test_chosen_silence_does_not_reset_failure_window(self):
        state = {}
        for i in range(10):
            state, _ = advance_health(state, failed(str(i)), i)
        self.assertTrue(state["degraded"])
        state, _ = advance_health(state, quiet("s"), 11)
        self.assertTrue(state["degraded"])

    def test_silence_monitor_is_diagnostic_not_speech_filter(self):
        state = {}
        for i in range(100):
            state, _ = advance_health(state, quiet(str(i)), i, silence_review_streak=20)
        self.assertEqual(state["last_outcome"], "chosen_silence")
        self.assertTrue(state["silence_review"])
        self.assertEqual(state["failure_count_window"], 0)

    def test_clock_regression_fails_closed(self):
        state, _ = advance_health({}, quiet("d1"), 100)
        with self.assertRaisesRegex(ValueError, "clock moved backwards"):
            advance_health(state, quiet("d2"), 99)

    def test_real_speech_and_no_speech_differ(self):
        spoken = classify_beat(
            "id2", completed_stages=STAGES, selected_speaker="owen",
            expression_attempted=True, expression_valid=True,
            published_message_ids=("owen-1",)
        )
        state, persist = advance_health({}, spoken, 1000)
        self.assertTrue(persist)
        self.assertEqual(state["last_public_message_at"], 1000)
        state, _ = advance_health(state, quiet("id3"), 1001)
        self.assertEqual(state["last_public_message_at"], 1000)

    def test_bad_heartbeat_interval_rejected(self):
        with self.assertRaises(ValueError):
            advance_health({}, quiet("id"), 100, heartbeat_seconds=900)


if __name__ == "__main__":
    unittest.main()
