#!/usr/bin/env python3
import unittest

import numpy as np

from bubble.core import BubbleParams
from bubble.coupled import (
    CoupledConfig,
    acoustic_coupling_pressures,
    pairwise_distances,
    ring_positions,
    simulate_coupled_world,
)


class CoupledBubbleTests(unittest.TestCase):
    def test_ring_geometry_is_symmetric(self):
        spacing = 1.0e-3
        positions = ring_positions(12, spacing)
        distances = pairwise_distances(positions)
        self.assertTrue(np.allclose(distances, distances.T))
        finite = distances[np.isfinite(distances)]
        self.assertAlmostEqual(float(np.min(finite)), spacing, places=12)

    def test_identical_sources_give_identical_pressure_on_ring(self):
        positions = ring_positions(8, 2.0e-3)
        distances = pairwise_distances(positions)
        coupling = acoustic_coupling_pressures(np.full(8, 1.0e-5), distances)
        self.assertLess(float(np.ptp(coupling)), 1.0e-14)

    def test_equilibrium_world_stays_stationary(self):
        p = BubbleParams(drive_amplitude=0.0)
        config = CoupledConfig(
            node_count=4,
            radius_spread_fraction=0.0,
            end_time=5.0e-6,
            macro_dt=2.5e-6,
            min_macro_dt=3.125e-7,
            max_corrections=3,
            rtol=1e-9,
        )
        result = simulate_coupled_world(p, config)
        self.assertEqual(result["status"], "complete")
        for state in result["final_states"]:
            self.assertAlmostEqual(state["R"] / p.R0, 1.0, places=9)
            self.assertAlmostEqual(state["U"], 0.0, places=9)
            self.assertAlmostEqual(state["coupling_pressure_pa"], 0.0, places=9)

    def test_driven_world_completes_with_shared_feedback(self):
        p = BubbleParams(R0=10e-6, drive_amplitude=500.0, drive_frequency=20_000.0)
        config = CoupledConfig(
            node_count=4,
            radius_spread_fraction=0.01,
            nearest_spacing_m=1.0e-3,
            end_time=1.0e-5,
            macro_dt=2.5e-6,
            min_macro_dt=1.5625e-7,
            max_corrections=4,
            coupling_abs_tol_pa=0.5,
            coupling_rel_tol=1e-3,
            rtol=1e-8,
        )
        result = simulate_coupled_world(p, config)
        self.assertEqual(result["status"], "complete")
        self.assertGreater(len(result["history"]), 0)
        self.assertTrue(any(abs(x) > 0.0 for step in result["history"] for x in step["coupling_pressure_pa"]))
        self.assertTrue(all(step["normalized_coupling_residual"] <= 1.0 for step in result["history"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
