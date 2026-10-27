"""Depth geometry of a network, measured from the error signals backprop delivers to each layer.

Definitions (all quantities are computed from arrays you pass in, so any framework can supply them):

    delta_l       the gradient of the loss with respect to layer l's pre-activation, one row per example.
                  This is the signal layer l's weights actually learn from: dL/dW_l = delta_l^T x_l.
    lapse  N_l    RMS_examples ||delta_l||  /  RMS_examples ||delta_out||
                  How loudly layer l hears the error, relative to the output layer.
    tilt   T      ln N_first : the total log-gain of the error signal from the output down to the
                  first hidden layer. T > 0 means the signal swells toward the input, T < 0 that it fades.
    slope  kappa  least-squares slope of ln N_l against layer index l (index increases toward the output).
                  For a steady exponential profile the depth spacetime ds^2 = -N^2 dtau^2 + dl^2 has
                  constant curvature R = -2 kappa^2.
    R_l           -2 N''_l / N_l by second differences, the local curvature (needs 3+ layers).
    horizons      hidden layers whose lapse is below a threshold (default 1e-2).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np

__all__ = ["lapse_profile", "Geometry", "geometry", "slope", "local_curvature"]


def _rms_norm(d: np.ndarray) -> float:
    d = np.asarray(d, dtype=np.float64)
    if d.ndim == 1:
        d = d[None, :]
    d = d.reshape(d.shape[0], -1)
    return float(np.sqrt(np.mean(np.sum(d * d, axis=1))))


def lapse_profile(deltas, output_delta=None) -> np.ndarray:
    """Lapse N_l for each hidden layer.

    deltas: sequence of arrays, one per layer, ordered input side -> output side. If output_delta is
    None, the LAST entry is taken to be the output layer and is excluded from the returned profile.
    Each array has shape (examples, units...) and holds dL/d(pre-activation) for that layer.
    """
    deltas = list(deltas)
    if output_delta is None:
        if len(deltas) < 2:
            raise ValueError("need at least one hidden layer plus the output layer")
        output_delta = deltas[-1]
        deltas = deltas[:-1]
    out = _rms_norm(output_delta)
    if not out > 0:
        return np.full(len(deltas), np.nan)
    return np.array([_rms_norm(d) / out for d in deltas])


def slope(N) -> float | None:
    """Least-squares slope of ln N against layer index. None if fewer than 3 layers or any N <= 0."""
    N = np.asarray(N, dtype=np.float64)
    if N.size < 3 or not np.all(np.isfinite(N)) or np.any(N <= 0):
        return None
    l = np.arange(N.size, dtype=np.float64)
    y = np.log(N)
    lc = l - l.mean()
    return float(np.sum(lc * (y - y.mean())) / np.sum(lc * lc))


def local_curvature(N) -> np.ndarray:
    """R_l = -2 N''/N at interior layers by second differences (length len(N)-2)."""
    N = np.asarray(N, dtype=np.float64)
    if N.size < 3:
        return np.array([])
    return -2.0 * (N[2:] - 2 * N[1:-1] + N[:-2]) / N[1:-1]


@dataclass
class Geometry:
    lapse: np.ndarray
    tilt: float            # ln N_first
    kappa: float | None    # slope of ln N per layer
    curvature: float | None  # -2 kappa^2 for the fitted exponential
    local_R: np.ndarray
    horizons: list = field(default_factory=list)

    def summary(self) -> str:
        k = "n/a" if self.kappa is None else f"{self.kappa:+.4f}"
        hz = ", ".join(str(h) for h in self.horizons) if self.horizons else "none"
        return (f"layers {len(self.lapse)} | first layer hears x{math.exp(self.tilt):.3g} "
                f"(tilt {self.tilt:+.3f}) | kappa {k} | horizons: {hz}")


def geometry(deltas, output_delta=None, horizon=1e-2) -> Geometry:
    N = lapse_profile(deltas, output_delta)
    k = slope(N)
    tilt = float(np.log(N[0])) if N.size and N[0] > 0 else float("nan")
    return Geometry(lapse=N, tilt=tilt, kappa=k,
                    curvature=None if k is None else -2 * k * k,
                    local_R=local_curvature(N),
                    horizons=[i for i, v in enumerate(N) if not (v >= horizon)])
