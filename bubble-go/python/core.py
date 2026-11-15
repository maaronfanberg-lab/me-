"""Validated single-bubble core for the coupled GitHub bubble simulation.

The fast physics for one bubble stays monolithic in this process. Distributed
workers exchange only macrostep coupling pressure endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from scipy.integrate import solve_ivp


@dataclass(frozen=True)
class BubbleParams:
    rho: float = 997.0
    mu: float = 8.9e-4
    sigma: float = 0.072
    c: float = 1480.0
    p0: float = 101325.0
    pv: float = 2339.0
    R0: float = 10e-6
    kappa: float = 1.4
    drive_amplitude: float = 0.0
    drive_frequency: float = 20_000.0
    gas_pressure0: float | None = None

    def __post_init__(self) -> None:
        if self.rho <= 0 or self.c <= 0 or self.R0 <= 0:
            raise ValueError("rho, c and R0 must be positive")
        if self.mu < 0 or self.sigma < 0 or self.p0 < 0 or self.pv < 0:
            raise ValueError("material pressures/transport coefficients must be non-negative")
        if self.kappa <= 0 or self.drive_frequency < 0:
            raise ValueError("kappa must be positive and drive_frequency non-negative")

    @property
    def pg0(self) -> float:
        if self.gas_pressure0 is not None:
            return float(self.gas_pressure0)
        return self.p0 - self.pv + 2.0 * self.sigma / self.R0


@dataclass(frozen=True)
class CouplingRamp:
    """Coupling pressure over one macrostep in simulated time."""
    t_start: float
    t_end: float
    p_start: float = 0.0
    p_end: float = 0.0

    def pressure(self, t: float) -> float:
        if self.t_end <= self.t_start:
            return self.p_end
        a = (t - self.t_start) / (self.t_end - self.t_start)
        a = min(1.0, max(0.0, a))
        return self.p_start + a * (self.p_end - self.p_start)

    @property
    def slope(self) -> float:
        if self.t_end <= self.t_start:
            return 0.0
        return (self.p_end - self.p_start) / (self.t_end - self.t_start)


@dataclass
class SegmentResult:
    t_start: float
    t_end: float
    R: float
    U: float
    A: float
    min_R: float
    max_R: float
    max_abs_U: float
    max_wall_mach: float
    emitted_pressure_coeff: float
    solver: str
    nfev: int
    success: bool
    collapsed: bool
    message: str

    def state(self) -> list[float]:
        return [self.R, self.U]


def gas_pressure(R: float, p: BubbleParams) -> float:
    if R <= 0:
        raise ValueError("bubble radius must stay positive")
    return p.pg0 * (p.R0 / R) ** (3.0 * p.kappa)


def far_field_pressure(t: float, p: BubbleParams, coupling: CouplingRamp) -> float:
    return p.p0 + p.drive_amplitude * math.sin(2.0 * math.pi * p.drive_frequency * t) + coupling.pressure(t)


def far_field_pressure_rate(t: float, p: BubbleParams, coupling: CouplingRamp) -> float:
    return p.drive_amplitude * 2.0 * math.pi * p.drive_frequency * math.cos(2.0 * math.pi * p.drive_frequency * t) + coupling.slope


def acceleration(t: float, R: float, U: float, p: BubbleParams, model: str, coupling: CouplingRamp) -> float:
    if R <= 0:
        raise ValueError("bubble radius must stay positive")
    model = model.lower().replace("_", "-")
    pg = gas_pressure(R, p)
    pinf = far_field_pressure(t, p, coupling)
    q = pg + p.pv - 2.0 * p.sigma / R - 4.0 * p.mu * U / R - pinf
    if model in {"rp", "rayleigh-plesset"}:
        return q / (p.rho * R) - 1.5 * U * U / R
    if model not in {"km", "keller-miksis"}:
        raise ValueError(f"unknown radial model: {model}")
    dpg = -3.0 * p.kappa * pg * U / R
    dq_no_acc = dpg + 2.0 * p.sigma * U / (R * R) + 4.0 * p.mu * U * U / (R * R) - far_field_pressure_rate(t, p, coupling)
    denominator = (1.0 - U / p.c) * R + 4.0 * p.mu / (p.rho * p.c)
    if denominator <= 0:
        raise FloatingPointError("Keller-Miksis denominator became non-positive")
    rhs = (1.0 + U / p.c) * q / p.rho + R * dq_no_acc / (p.rho * p.c) - 1.5 * (1.0 - U / (3.0 * p.c)) * U * U
    return rhs / denominator


def emitted_pressure_coefficient(R: float, U: float, A: float, rho: float) -> float:
    return rho * (2.0 * R * U * U + R * R * A)


def integrate_segment(state: Iterable[float], p: BubbleParams, t_start: float, t_end: float, *, model: str = "km", coupling_start: float = 0.0, coupling_end: float = 0.0, rtol: float = 1e-8, atol: tuple[float, float] | None = None, primary_solver: str = "DOP853") -> SegmentResult:
    if t_end <= t_start:
        raise ValueError("t_end must be greater than t_start")
    y0 = np.asarray(list(state), dtype=float)
    if y0.shape != (2,) or not np.isfinite(y0).all() or y0[0] <= 0:
        raise ValueError("state must be finite [R, U] with R > 0")
    coupling = CouplingRamp(t_start, t_end, float(coupling_start), float(coupling_end))
    if atol is None:
        velocity_scale = max(1.0, 2.0 * math.pi * max(p.drive_frequency, 1.0) * p.R0)
        atol = (max(1e-18, p.R0 * 1e-11), velocity_scale * 1e-11)
    collapse_radius = max(1e-12, p.R0 * 1e-5)
    max_step = (t_end - t_start) / 25.0
    def rhs(t: float, y: np.ndarray):
        R, U = float(y[0]), float(y[1])
        return U, acceleration(t, R, U, p, model, coupling)
    def collapse_event(t: float, y: np.ndarray) -> float:
        return float(y[0]) - collapse_radius
    collapse_event.terminal = True
    collapse_event.direction = -1
    methods = [primary_solver]
    if primary_solver != "Radau": methods.append("Radau")
    sol = None; used = ""
    for method in methods:
        try:
            candidate = solve_ivp(rhs, (t_start, t_end), y0, method=method, rtol=rtol, atol=atol, max_step=max_step, events=collapse_event)
        except (FloatingPointError, ValueError):
            continue
        sol = candidate; used = method
        if candidate.success: break
    if sol is None:
        raise RuntimeError("all bubble integrators failed before producing a trajectory")
    Rvals = sol.y[0]; Uvals = sol.y[1]
    if not ((Rvals > 0) & np.isfinite(Rvals) & np.isfinite(Uvals)).all():
        raise FloatingPointError("non-physical state produced during bubble integration")
    t_final = float(sol.t[-1]); R_final = float(Rvals[-1]); U_final = float(Uvals[-1])
    A_final = acceleration(t_final, R_final, U_final, p, model, coupling)
    collapsed = bool(sol.t_events and len(sol.t_events[0]) > 0)
    reached_end = abs(t_final - t_end) <= 1e-12 * max(1.0, abs(t_end))
    return SegmentResult(t_start=t_start, t_end=t_final, R=R_final, U=U_final, A=A_final, min_R=float(np.min(Rvals)), max_R=float(np.max(Rvals)), max_abs_U=float(np.max(np.abs(Uvals))), max_wall_mach=float(np.max(np.abs(Uvals)) / p.c), emitted_pressure_coeff=emitted_pressure_coefficient(R_final, U_final, A_final, p.rho), solver=used, nfev=int(sol.nfev), success=bool(sol.success and (collapsed or reached_end)), collapsed=collapsed, message=str(sol.message))
