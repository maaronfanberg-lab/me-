#!/usr/bin/env python3
import math
import unittest

from bubble.core import BubbleParams, integrate_segment, linear_natural_frequency, rayleigh_collapse_time


class BubbleCoreTests(unittest.TestCase):
    def test_equilibrium_is_stationary(self):
        p = BubbleParams()
        out = integrate_segment([p.R0, 0.0], p, 0.0, 1.0e-5, model="rp", rtol=1e-10)
        self.assertTrue(out.success)
        self.assertAlmostEqual(out.R / p.R0, 1.0, places=10)
        self.assertAlmostEqual(out.U, 0.0, places=10)

    def test_linear_period_returns_small_perturbation(self):
        p = BubbleParams()
        period = 2.0 * math.pi / linear_natural_frequency(p)
        initial_R = 1.0001 * p.R0
        out = integrate_segment([initial_R, 0.0], p, 0.0, period, model="rp", rtol=1e-10)
        self.assertTrue(out.success)
        self.assertLess(abs(out.R - initial_R) / p.R0, 2.0e-5)
        self.assertLess(abs(out.U), 2.0e-5)

    def test_rayleigh_empty_cavity_collapse_time(self):
        p = BubbleParams(
            rho=997.0,
            mu=0.0,
            sigma=0.0,
            c=1480.0,
            p0=101325.0,
            pv=0.0,
            R0=1.0e-3,
            gas_pressure0=0.0,
        )
        expected = rayleigh_collapse_time(p.R0, p.rho, p.p0)
        out = integrate_segment([p.R0, 0.0], p, 0.0, 1.2 * expected, model="rp", rtol=1e-9)
        self.assertTrue(out.collapsed)
        self.assertLess(abs(out.t_end - expected) / expected, 2.0e-5)

    def test_rp_and_km_agree_at_low_wall_mach(self):
        p = BubbleParams(R0=30.0e-6, drive_amplitude=1000.0, drive_frequency=10_000.0)
        period = 1.0 / p.drive_frequency
        rp = integrate_segment([p.R0, 0.0], p, 0.0, period, model="rp", rtol=1e-9)
        km = integrate_segment([p.R0, 0.0], p, 0.0, period, model="km", rtol=1e-9)
        self.assertTrue(rp.success and km.success)
        self.assertLess(max(rp.max_wall_mach, km.max_wall_mach), 1.0e-3)
        self.assertLess(abs(rp.R - km.R) / p.R0, 1.0e-3)

    def test_solver_tolerance_converges(self):
        p = BubbleParams(R0=20.0e-6, drive_amplitude=5000.0, drive_frequency=25_000.0)
        period = 1.0 / p.drive_frequency
        loose = integrate_segment([p.R0, 0.0], p, 0.0, period, model="km", rtol=1e-6)
        tight = integrate_segment([p.R0, 0.0], p, 0.0, period, model="km", rtol=1e-9)
        self.assertTrue(loose.success and tight.success)
        self.assertLess(abs(loose.R - tight.R) / p.R0, 2.0e-4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
