import math
import unittest

from room_dynamics import (
    ENTITIES,
    LATENT_BOUND,
    initial_state,
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

    def test_long_catchup_is_single_step_and_bounded(self):
        for entity in ENTITIES:
            state = initial_state(entity)
            advanced, diagnostics = tick(state, 60.0 * 24.0 * 30.0)
            self.assertEqual(diagnostics["dt_minutes"], 60.0 * 24.0 * 30.0)
            self.assertTrue(all(math.isfinite(v) for v in advanced.latent))
            self.assertTrue(all(-LATENT_BOUND <= v <= LATENT_BOUND for v in advanced.latent))
            self.assertAlmostEqual(sum(advanced.regimes), 1.0, places=12)

    def test_event_is_deterministic_but_changes_state(self):
        state = initial_state("sarah")
        a, da = tick(state, 5.0, "A surprising new message arrives")
        b, db = tick(state, 5.0, "A surprising new message arrives")
        self.assertEqual(state_to_json(a), state_to_json(b))
        self.assertEqual(da, db)
        self.assertNotEqual(a.latent, state.latent)

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


if __name__ == "__main__":
    unittest.main()
