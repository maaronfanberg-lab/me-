#!/usr/bin/env python3
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from endogenous_workspace import (
    Candidate,
    MAX_SLOW_TRACES,
    STATE_KEY,
    feature_enabled,
    memory_candidate,
    observation_candidate,
    pulse_agent,
    run_pulse,
)


class EndogenousWorkspaceTests(unittest.TestCase):
    def test_feature_is_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(feature_enabled())
        self.assertTrue(feature_enabled("ON"))
        self.assertFalse(feature_enabled("0"))

    def test_repeated_candidate_builds_slow_trace_and_can_ignite(self):
        candidate = observation_candidate("Olivia mentioned the same unfinished sketch again.")
        self.assertIsNotNone(candidate)
        state = None
        ignitions = []
        slow_strengths = []
        for step in range(1, 9):
            state, _broadcast, diagnostics = run_pulse([candidate], state, step)
            ignitions.append(diagnostics["ignited"])
            slow_strengths.append(state["slow"][candidate.candidate_id]["strength"])
        self.assertFalse(ignitions[0])
        self.assertTrue(any(ignitions[2:]))
        self.assertGreater(slow_strengths[-1], slow_strengths[0])

    def test_broadcast_contains_only_existing_candidate_text(self):
        candidate = Candidate(
            candidate_id="a",
            source="memory:reflection",
            text="Emily remembers that Olivia preferred to revisit the unfinished sketch.",
            importance=1.0,
            recency=1.0,
        )
        _state, broadcast, diagnostics = run_pulse([candidate], None, 10)
        self.assertTrue(diagnostics["ignited"])
        self.assertIn(candidate.text, broadcast)
        self.assertNotIn("reasoning", broadcast.casefold())

    def test_persistent_state_stores_no_representation_text(self):
        text = "A private fact that should not be duplicated into workspace state."
        candidate = Candidate("secret-id", "memory:event", text, 1.0, 1.0)
        state, _broadcast, _diagnostics = run_pulse([candidate], None, 1)
        self.assertNotIn(text, repr(state))
        self.assertIn("secret-id", state["slow"])

    def test_slow_state_is_bounded(self):
        candidates = [
            Candidate(f"id-{i}", "memory:event", f"memory {i}", 1.0, 1.0)
            for i in range(MAX_SLOW_TRACES + 20)
        ]
        state = None
        for start in range(0, len(candidates), 16):
            state, _, _ = run_pulse(candidates[start:start + 16], state, start + 1)
        self.assertLessEqual(len(state["slow"]), MAX_SLOW_TRACES)

    def test_memory_candidate_uses_importance_and_recency_without_generation(self):
        node = SimpleNamespace(
            content="Olivia brought up the ceramic bowl.",
            importance=80,
            created=18,
            node_type="event",
        )
        candidate = memory_candidate(node, time_step=20)
        self.assertIsNotNone(candidate)
        self.assertAlmostEqual(candidate.importance, 0.8)
        self.assertGreater(candidate.recency, 0.7)

    def test_disabled_pulse_does_not_touch_memory_or_scratch(self):
        class Brain:
            scratch = {}

            def update_scratch(self, payload):
                raise AssertionError("disabled pulse should not update scratch")

            class MemoryStream:
                def retrieve(self, *args, **kwargs):
                    raise AssertionError("disabled pulse should not retrieve")

            memory_stream = MemoryStream()

        agent = SimpleNamespace(name="Emily", brain=Brain())
        with patch.dict(os.environ, {"COMMUNITY_ENDOGENOUS_WORKSPACE": "0"}, clear=True):
            result = pulse_agent(agent, "Olivia", 1)
        self.assertFalse(result.enabled)
        self.assertEqual(result.broadcast_context, "")

    def test_enabled_pulse_persists_numeric_trace_in_scratch(self):
        node = SimpleNamespace(
            content="Olivia mentioned the same unfinished sketch again.",
            importance=95,
            created=1,
            node_type="event",
        )

        class MemoryStream:
            def retrieve(self, queries, time_step, n_count):
                return {queries[0]: [node]}

        class Brain:
            def __init__(self):
                self.scratch = {}
                self.memory_stream = MemoryStream()

            def update_scratch(self, payload):
                self.scratch.update(payload)

        agent = SimpleNamespace(name="Emily", brain=Brain())
        with patch.dict(os.environ, {"COMMUNITY_ENDOGENOUS_WORKSPACE": "1"}, clear=True):
            result = pulse_agent(agent, "Olivia", 2)
        self.assertTrue(result.enabled)
        self.assertIn(STATE_KEY, agent.brain.scratch)
        self.assertNotIn(node.content, repr(agent.brain.scratch[STATE_KEY]))


if __name__ == "__main__":
    unittest.main()
