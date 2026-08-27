import json
import math
import unittest

from room_dynamics import (
    ENTITIES,
    LATENT_BOUND,
    MAX_ADVANCE_MINUTES,
    advance_latent,
    apply_event,
    initial_state,
    l1_change,
    normalized_entropy,
    project_observables,
    softmax,
    state_from_json,
    state_to_json,
    tick,
)


class RoomDynamicsTests(unittest.TestCase):
    def test_initial_state_is_deterministic(self):
        for entity in ENTITIES:
            self.assertEqual(state_to_json(initial_state(entity)), state_to_json(initial_state(entity)))

    def test_probabilities_are_normalized(self):
        for entity in ENTITIES:
            state = initial_state(entity)
            self.assertAlmostEqual(sum(state.regimes), 1.0, places=12)
            self.assertTrue(all(0.0 <= p <= 1.0 for p in state.regimes))
            self.assertTrue(0.0 <= state.entropy <= 1.0)

    def test_regimes_are_not_exactly_uniform(self):
        for entity in ENTITIES:
            state = initial_state(entity)
            self.assertGreater(max(state.regimes) - min(state.regimes), 0.001)

    def test_long_catchup_is_single_step_and_bounded(self):
        for entity in ENTITIES:
            state = initial_state(entity)
            advanced, diagnostics = tick(state, 60.0 * 24.0 * 30.0)
            self.assertEqual(diagnostics["dt_minutes"], 60.0 * 24.0 * 30.0)
            self.assertTrue(all(math.isfinite(v) for v in advanced.latent))
            self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in advanced.latent))
            self.assertAlmostEqual(sum(advanced.regimes), 1.0, places=12)

    def test_extreme_catchup_is_capped(self):
        state = initial_state("sarah", 0.0)
        out = advance_latent(state.latent, MAX_ADVANCE_MINUTES * 50, "sarah", 0.0)
        self.assertTrue(all(math.isfinite(v) for v in out))
        self.assertTrue(all(abs(v) <= LATENT_BOUND for v in out))

    def test_catchup_is_path_independent(self):
        for entity in ENTITIES:
            state = initial_state(entity, 1000.0)
            direct = advance_latent(state.latent, 180.0, entity, 1000.0)
            first = advance_latent(state.latent, 60.0, entity, 1000.0)
            second = advance_latent(first, 60.0, entity, 1060.0)
            stepped = advance_latent(second, 60.0, entity, 1120.0)
            for a, b in zip(direct, stepped):
                self.assertAlmostEqual(a, b, places=10)

    def test_state_moves_without_messages(self):
        for entity in ENTITIES:
            state = initial_state(entity, 1000.0)
            moved, _ = tick(state, 1060.0)
            self.assertNotEqual(state.latent, moved.latent)

    def test_backwards_clock_does_not_rewind_state(self):
        state = initial_state("mara", 1000.0)
        moved, diag = tick(state, 900.0)
        self.assertEqual(moved.minute, 1000.0)
        self.assertEqual(diag["dt_minutes"], 0.0)

    def test_event_is_deterministic_but_changes_state(self):
        state = initial_state("sarah")
        a, da = tick(state, 5.0, "A surprising new message arrives")
        b, db = tick(state, 5.0, "A surprising new message arrives")
        self.assertEqual(state_to_json(a), state_to_json(b))
        self.assertEqual(da, db)
        self.assertNotEqual(a.latent, state.latent)

    def test_empty_event_does_not_mark_interesting(self):
        state = initial_state("owen", 10.0)
        _, diag = tick(state, 10.0, "   ")
        self.assertFalse(diag["interesting"])

    def test_entities_diverge_on_same_event(self):
        states = []
        for entity in ENTITIES:
            state = initial_state(entity)
            advanced, _ = tick(state, 15.0, "same shared Room event")
            states.append(tuple(round(v, 12) for v in advanced.latent))
        self.assertEqual(len(set(states)), len(ENTITIES))

    def test_engine_never_requests_speech(self):
        for entity in ENTITIES:
            state = initial_state(entity)
            _, diagnostics = tick(state, 500.0, "highly salient event")
            self.assertFalse(diagnostics["speech_requested"])

    def test_round_trip_serialization(self):
        state = initial_state("jules")
        restored = state_from_json(state_to_json(state))
        self.assertEqual(state_to_json(state), state_to_json(restored))

    def test_nonfinite_initial_minute_rejected(self):
        with self.assertRaises(ValueError):
            initial_state("sarah", float("nan"))

    def test_nonfinite_tick_time_rejected(self):
        with self.assertRaises(ValueError):
            tick(initial_state("sarah"), float("inf"))

    def test_unknown_entity_rejected(self):
        with self.assertRaises(ValueError):
            initial_state("nobody")

    def test_wrong_latent_dimension_rejected(self):
        with self.assertRaises(ValueError):
            advance_latent([0.0] * 7, 1.0, "sarah")
        with self.assertRaises(ValueError):
            project_observables([0.0] * 9)
        with self.assertRaises(ValueError):
            apply_event([0.0] * 2, "sarah", "x")

    def test_nonfinite_latent_rejected(self):
        bad = [0.0] * 8
        bad[2] = float("nan")
        with self.assertRaises(ValueError):
            advance_latent(bad, 1.0, "sarah")

    def test_softmax_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            softmax([])

    def test_softmax_rejects_nonfinite_input(self):
        with self.assertRaises(ValueError):
            softmax([0.0, float("nan")])

    def test_softmax_stays_normalized_for_large_logits(self):
        p = softmax([10000.0, 9999.0, -10000.0, 0.0])
        self.assertAlmostEqual(sum(p), 1.0, places=12)
        self.assertTrue(all(math.isfinite(v) for v in p))

    def test_entropy_handles_empty_and_singleton(self):
        self.assertEqual(normalized_entropy([]), 0.0)
        self.assertEqual(normalized_entropy([1.0]), 0.0)

    def test_entropy_rejects_negative_probability(self):
        with self.assertRaises(ValueError):
            normalized_entropy([0.5, -0.1, 0.6])

    def test_l1_requires_equal_dimensions(self):
        with self.assertRaises(ValueError):
            l1_change([0.1], [0.1, 0.2])

    def test_serialization_rejects_wrong_entity(self):
        data = json.loads(state_to_json(initial_state("sarah")))
        data["entity"] = "bogus"
        with self.assertRaises(ValueError):
            state_from_json(json.dumps(data))

    def test_serialization_rejects_bad_entropy(self):
        data = json.loads(state_to_json(initial_state("sarah")))
        data["entropy"] = 2.0
        with self.assertRaises(ValueError):
            state_from_json(json.dumps(data))

    def test_serialization_rejects_bad_regime_sum(self):
        data = json.loads(state_to_json(initial_state("sarah")))
        data["regimes"] = [0.2, 0.2, 0.2, 0.2]
        with self.assertRaises(ValueError):
            state_from_json(json.dumps(data))

    def test_serialization_rejects_out_of_bounds_latent(self):
        data = json.loads(state_to_json(initial_state("sarah")))
        data["latent"][0] = LATENT_BOUND + 1.0
        with self.assertRaises(ValueError):
            state_from_json(json.dumps(data))


if __name__ == "__main__":
    unittest.main()
