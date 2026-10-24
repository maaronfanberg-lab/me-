#!/usr/bin/env python3
"""Tests for offline-only health semantics, including 900s watchdog contrast."""
from __future__ import annotations

import unittest

from room_beat_protocol import (
    BeatOutcome, advance_health, classify_beat, mark_durable, watchdog_status,
)

STAGES = {"perception": True, "observation": True, "floor_selection": True}
ELIGIBLE = ("sarah", "mara", "owen", "jules")


def quiet(key):
    return classify_beat(
        key, completed_stages=STAGES, eligible_speakers=ELIGIBLE,
        selected_speaker=None, silence_chosen=True, expression_attempted=False,
    )


def failed(key):
    return classify_beat(
        key, completed_stages=STAGES, eligible_speakers=ELIGIBLE,
        selected_speaker="sarah", silence_chosen=False,
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
            classify_beat("d", completed_stages=STAGES, eligible_speakers=ELIGIBLE,
                          selected_speaker="mara", silence_chosen=False,
                          expression_attempted=False).kind,
            "generation_failed",
        )
        self.assertEqual(
            classify_beat("d", completed_stages=STAGES, eligible_speakers=ELIGIBLE,
                          selected_speaker=None, silence_chosen=False,
                          expression_attempted=False, failure="model_unavailable").kind,
            "model_unavailable",
        )

    def test_missing_stage_does_not_pass_as_social_decision(self):
        incomplete = dict(STAGES, observation=False)
        self.assertEqual(
            classify_beat("d", completed_stages=incomplete, eligible_speakers=ELIGIBLE,
                          selected_speaker=None, silence_chosen=True,
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
                if persist:
                    state = mark_durable(state, beat)
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
            "id2", completed_stages=STAGES, eligible_speakers=ELIGIBLE,
            selected_speaker="owen", silence_chosen=False,
            expression_attempted=True, expression_valid=True,
            published_message_ids=("owen-1",)
        )
        state, persist = advance_health({}, spoken, 1000)
        self.assertTrue(persist)
        state = mark_durable(state, 1000)
        self.assertEqual(state["last_public_message_at"], 1000)
        state, _ = advance_health(state, quiet("id3"), 1001)
        self.assertEqual(state["last_public_message_at"], 1000)

    def test_failed_model_is_never_a_healthy_heartbeat(self):
        state, persist = advance_health({}, quiet("quiet"), 0)
        self.assertTrue(persist)
        state = mark_durable(state, 0)
        state, persist = advance_health(state, failed("broken"), 1)
        self.assertEqual(watchdog_status(state, 2), "unhealthy")
        self.assertEqual(state["last_durable_healthy_at"], 0)

    def test_no_eligible_agent_is_not_silence(self):
        result = classify_beat(
            "unavailable", completed_stages=STAGES, eligible_speakers=(),
            selected_speaker=None, silence_chosen=False, expression_attempted=False,
        )
        self.assertEqual(result.kind, "invalid_no_eligible_person")
        result = classify_beat(
            "missing-decision", completed_stages=STAGES, eligible_speakers=ELIGIBLE,
            selected_speaker=None, silence_chosen=False, expression_attempted=False,
        )
        self.assertEqual(result.kind, "infrastructure_failure")

    def test_1000_failed_beats_do_not_create_a_commit_storm(self):
        state, commits = {}, 0
        for i in range(1000):
            state, persist = advance_health(state, failed(str(i)), i)
            commits += persist
            if persist:
                state = mark_durable(state, i)
        self.assertLessEqual(commits, 7)
        self.assertEqual(watchdog_status(state, 1000), "unhealthy")

    def test_failed_git_push_does_not_count_as_durable(self):
        state, persist = advance_health({}, quiet("first"), 0)
        self.assertTrue(persist)
        # Deliberately do not call mark_durable; the push failed.
        state, retry = advance_health(state, quiet("second"), 1)
        self.assertTrue(retry)
        self.assertNotIn("last_durable_write_at", state)
        state = mark_durable(state, 1)
        self.assertEqual(state["last_durable_healthy_at"], 1)

    def test_invalid_state_and_nonboolean_generation_are_rejected(self):
        with self.assertRaises(ValueError):
            advance_health({"recent_outcomes": ["corrupted"]}, failed("x"), 1)
        with self.assertRaises(ValueError):
            advance_health({}, failed("x"), float("nan"))
        with self.assertRaises(ValueError):
            classify_beat("x", completed_stages=STAGES, eligible_speakers=ELIGIBLE,
                          selected_speaker=None, silence_chosen=True, expression_attempted="no")
        with self.assertRaises(ValueError):
            BeatOutcome("spoken", "x", selected_speaker="sarah",
                        published_message_ids=("same", "same"))

    def test_bad_heartbeat_interval_rejected(self):
        with self.assertRaises(ValueError):
            advance_health({}, quiet("id"), 100, heartbeat_seconds=900)


if __name__ == "__main__":
    unittest.main()
