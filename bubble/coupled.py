"""In-memory multi-bubble coupling engine.

Each virtual node owns a complete radial bubble model. Nodes communicate only
through the shared acoustic pressure field at macrostep boundaries. The fast
ODE physics never depends on wall-clock timing or network latency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from typing import Sequence

import numpy as np

from .core import BubbleParams, SegmentResult, integrate_segment


@dataclass(frozen=True)
class CoupledConfig:
    node_count: int = 12
    model: str = "km"
    nearest_spacing_m: float = 1.0e-3
    radius_spread_fraction: float = 0.02
    end_time: float = 5.0e-5
    macro_dt: float = 2.5e-6
    min_macro_dt: float = 7.8125e-8
    max_corrections: int = 4
    coupling_rel_tol: float = 1.0e-3
    coupling_abs_tol_pa: float = 0.5
    under_relaxation: float = 0.65
    rtol: float = 1.0e-8

    def __post_init__(self) -> None:
        if self.node_count < 2:
            raise ValueError("node_count must be at least 2")
        if self.nearest_spacing_m <= 0:
            raise ValueError("nearest_spacing_m must be positive")
        if not 0 <= self.radius_spread_fraction < 1:
            raise ValueError("radius_spread_fraction must be in [0, 1)")
        if self.end_time <= 0 or self.macro_dt <= 0 or self.min_macro_dt <= 0:
            raise ValueError("simulation times must be positive")
        if self.min_macro_dt > self.macro_dt:
            raise ValueError("min_macro_dt cannot exceed macro_dt")
        if self.max_corrections < 1:
            raise ValueError("max_corrections must be positive")
        if self.coupling_rel_tol < 0 or self.coupling_abs_tol_pa <= 0:
            raise ValueError("coupling tolerances must be non-negative/positive")
        if not 0 < self.under_relaxation <= 1:
            raise ValueError("under_relaxation must be in (0, 1]")
        if self.rtol <= 0:
            raise ValueError("rtol must be positive")


def ring_positions(node_count: int, nearest_spacing_m: float) -> np.ndarray:
    """Place nodes evenly on a ring with the requested nearest-neighbor chord."""
    if node_count < 2 or nearest_spacing_m <= 0:
        raise ValueError("invalid ring geometry")
    radius = nearest_spacing_m / (2.0 * math.sin(math.pi / node_count))
    theta = 2.0 * math.pi * np.arange(node_count, dtype=float) / node_count
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta), np.zeros(node_count)))


def pairwise_distances(positions: np.ndarray) -> np.ndarray:
    positions = np.asarray(positions, dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("positions must have shape (N, 3)")
    delta = positions[:, None, :] - positions[None, :, :]
    distances = np.linalg.norm(delta, axis=2)
    np.fill_diagonal(distances, np.inf)
    return distances


def acoustic_coupling_pressures(emitted_coefficients: Sequence[float], distances: np.ndarray) -> np.ndarray:
    """Leading monopole pressure from every other virtual node at one instant.

    ``emitted_coefficients[j]`` is K_j in p_ij = K_j / r_ij. Self-coupling is
    excluded by the infinite diagonal in ``distances``.
    """
    coeff = np.asarray(emitted_coefficients, dtype=float)
    distances = np.asarray(distances, dtype=float)
    if distances.shape != (coeff.size, coeff.size):
        raise ValueError("distance matrix shape does not match coefficient count")
    if not np.isfinite(coeff).all():
        raise ValueError("emitted coefficients must be finite")
    return np.sum(coeff[None, :] / distances, axis=1)


def _node_parameters(base: BubbleParams, config: CoupledConfig) -> list[BubbleParams]:
    params: list[BubbleParams] = []
    for i in range(config.node_count):
        phase = 2.0 * math.pi * i / config.node_count
        scale = 1.0 + config.radius_spread_fraction * math.sin(phase)
        params.append(replace(base, R0=base.R0 * scale, gas_pressure0=None))
    return params


def _normalized_residual(target: np.ndarray, guess: np.ndarray, config: CoupledConfig) -> tuple[float, float]:
    difference = np.abs(target - guess)
    scale = config.coupling_abs_tol_pa + config.coupling_rel_tol * np.maximum(np.abs(target), np.abs(guess))
    return float(np.max(difference / scale)), float(np.max(difference))


def _terminal_result(
    *,
    status: str,
    t: float,
    config: CoupledConfig,
    base: BubbleParams,
    params: Sequence[BubbleParams],
    states: Sequence[Sequence[float]],
    coupling: np.ndarray,
    positions: np.ndarray,
    history: list[dict],
    rollbacks: int,
    message: str,
    collapsed_nodes: Sequence[int] = (),
) -> dict:
    return {
        "schema": "coupled-bubble-world-v1",
        "status": status,
        "message": message,
        "simulation_time": float(t),
        "completed_fraction": float(min(1.0, t / config.end_time)),
        "rollbacks": int(rollbacks),
        "collapsed_nodes": [int(i) for i in collapsed_nodes],
        "config": asdict(config),
        "base_params": asdict(base),
        "node_params": [asdict(p) for p in params],
        "positions_m": np.asarray(positions).tolist(),
        "final_states": [
            {
                "node": i,
                "R": float(state[0]),
                "U": float(state[1]),
                "coupling_pressure_pa": float(coupling[i]),
            }
            for i, state in enumerate(states)
        ],
        "history": history,
    }


def simulate_coupled_world(base: BubbleParams, config: CoupledConfig) -> dict:
    """Run a rollback-safe predictor/corrector world of communicating bubbles.

    A macrostep is accepted only after the pressure field produced by the node
    predictions is self-consistent with the pressure field used to integrate
    those predictions. Failure to converge halves the simulated macrostep and
    retries from the last authoritative checkpoint.
    """
    params = _node_parameters(base, config)
    positions = ring_positions(config.node_count, config.nearest_spacing_m)
    distances = pairwise_distances(positions)
    states: list[list[float]] = [[p.R0, 0.0] for p in params]
    coupling_start = np.zeros(config.node_count, dtype=float)

    t = 0.0
    dt = config.macro_dt
    rollbacks = 0
    history: list[dict] = []
    accepted_steps = 0

    while t < config.end_time - 1.0e-18:
        step_dt = min(dt, config.end_time - t)
        checkpoint = [list(state) for state in states]
        guess_end = coupling_start.copy()
        accepted_results: list[SegmentResult] | None = None
        accepted_coupling: np.ndarray | None = None
        last_norm = math.inf
        last_abs = math.inf
        corrections_used = 0

        for correction in range(config.max_corrections):
            corrections_used = correction + 1
            results: list[SegmentResult] = []
            for i in range(config.node_count):
                results.append(
                    integrate_segment(
                        checkpoint[i],
                        params[i],
                        t,
                        t + step_dt,
                        model=config.model,
                        coupling_start=float(coupling_start[i]),
                        coupling_end=float(guess_end[i]),
                        rtol=config.rtol,
                    )
                )

            collapsed = [i for i, result in enumerate(results) if result.collapsed]
            if collapsed:
                terminal_t = min(results[i].t_end for i in collapsed)
                terminal_states = [result.state() for result in results]
                return _terminal_result(
                    status="collapsed",
                    t=terminal_t,
                    config=config,
                    base=base,
                    params=params,
                    states=terminal_states,
                    coupling=coupling_start,
                    positions=positions,
                    history=history,
                    rollbacks=rollbacks,
                    message="one or more virtual bubbles reached the configured collapse radius",
                    collapsed_nodes=collapsed,
                )

            if not all(result.success for result in results):
                break

            emitted = np.asarray([result.emitted_pressure_coeff for result in results], dtype=float)
            target_end = acoustic_coupling_pressures(emitted, distances)
            last_norm, last_abs = _normalized_residual(target_end, guess_end, config)

            if last_norm <= 1.0:
                accepted_results = results
                accepted_coupling = target_end
                break

            guess_end = guess_end + config.under_relaxation * (target_end - guess_end)

        if accepted_results is None or accepted_coupling is None:
            next_dt = step_dt * 0.5
            rollbacks += 1
            if next_dt < config.min_macro_dt * (1.0 - 1.0e-12):
                return _terminal_result(
                    status="failed",
                    t=t,
                    config=config,
                    base=base,
                    params=params,
                    states=states,
                    coupling=coupling_start,
                    positions=positions,
                    history=history,
                    rollbacks=rollbacks,
                    message=(
                        "coupling iteration failed to converge before reaching min_macro_dt; "
                        f"last normalized residual={last_norm:.6g}"
                    ),
                )
            dt = max(config.min_macro_dt, next_dt)
            continue

        states = [result.state() for result in accepted_results]
        coupling_start = accepted_coupling
        t += step_dt
        accepted_steps += 1

        radii = np.asarray([state[0] for state in states])
        velocities = np.asarray([state[1] for state in states])
        mach = np.asarray([result.max_wall_mach for result in accepted_results])
        history.append(
            {
                "step": accepted_steps,
                "t": float(t),
                "dt": float(step_dt),
                "corrections": corrections_used,
                "normalized_coupling_residual": float(last_norm),
                "max_abs_coupling_residual_pa": float(last_abs),
                "radii_m": radii.tolist(),
                "velocities_m_s": velocities.tolist(),
                "coupling_pressure_pa": coupling_start.tolist(),
                "max_wall_mach": float(np.max(mach)),
                "solver_nfev": int(sum(result.nfev for result in accepted_results)),
            }
        )

        # After a rollback, cautiously restore the requested macrostep size.
        if step_dt < config.macro_dt and corrections_used <= 2:
            dt = min(config.macro_dt, 2.0 * step_dt)
        else:
            dt = step_dt

    return _terminal_result(
        status="complete",
        t=t,
        config=config,
        base=base,
        params=params,
        states=states,
        coupling=coupling_start,
        positions=positions,
        history=history,
        rollbacks=rollbacks,
        message="coupled bubble world reached the requested simulation end time",
    )
