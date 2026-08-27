from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict
from typing import Iterable

ENTITIES = ("sarah", "mara", "owen", "jules")
LATENT_DIM = 8
OBS_DIM = 10
REGIME_DIM = 4
LATENT_BOUND = 3.0

OMEGA = (0.071, 0.103, 0.149, 0.211, 0.293, 0.379, 0.487, 0.613)
DECAY_PER_MINUTE = (0.004, 0.006, 0.005, 0.008, 0.007, 0.004, 0.009, 0.006)
INTRINSIC_AMPLITUDE = 0.22

OBS_WEIGHTS = (
    (0.55, -0.10, 0.20, 0.05, 0.15, 0.10, -0.05, 0.15),
    (-0.05, 0.60, -0.10, 0.20, -0.15, 0.10, 0.15, 0.05),
    (0.30, 0.10, 0.55, -0.05, 0.10, 0.05, 0.15, -0.10),
    (0.10, -0.15, 0.05, 0.60, 0.10, 0.20, -0.05, 0.05),
    (0.10, -0.25, 0.05, 0.15, 0.55, 0.05, -0.15, 0.10),
    (0.05, 0.10, 0.10, 0.15, 0.10, 0.60, 0.05, 0.15),
    (-0.10, 0.25, 0.15, -0.05, -0.20, 0.05, 0.55, 0.05),
    (0.05, 0.05, -0.10, 0.10, 0.10, 0.15, 0.05, 0.65),
    (0.15, 0.20, 0.05, 0.35, 0.05, 0.10, 0.10, 0.15),
    (0.25, 0.05, 0.20, 0.10, 0.20, 0.00, -0.10, 0.30),
)

REGIME_NAMES = ("settled", "exploratory", "social", "transition")
REGIME_WEIGHTS = (
    (0.10, -0.35, -0.10, 0.20, 0.35, 0.15, -0.30, 0.25, 0.05, -0.05),
    (0.45, -0.05, 0.50, 0.05, 0.00, 0.15, 0.10, 0.10, 0.00, 0.30),
    (0.05, 0.05, 0.05, 0.45, 0.10, 0.10, 0.05, 0.05, 0.50, 0.15),
    (0.10, 0.35, 0.20, -0.05, -0.20, 0.05, 0.50, -0.10, 0.10, 0.15),
)


@dataclass
class EntityState:
    version: int
    entity: str
    minute: float
    latent: list[float]
    regimes: list[float]
    entropy: float
    last_event_hash: str | None = None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _seed_unit(entity: str, i: int) -> float:
    raw = hashlib.sha256(f"room-vault:{entity}:{i}".encode()).digest()
    n = int.from_bytes(raw[:8], "big") / float(2**64 - 1)
    return 2.0 * n - 1.0


def _phase(entity: str, i: int) -> float:
    return math.pi * (_seed_unit(entity, i + 200) + 1.0)


def initial_state(entity: str, minute: float = 0.0) -> EntityState:
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    latent = [0.35 * _seed_unit(entity, i) for i in range(LATENT_DIM)]
    observables = project_observables(latent)
    regimes = softmax(regime_logits(observables))
    return EntityState(1, entity, float(minute), latent, regimes, normalized_entropy(regimes))


def advance_latent(latent: Iterable[float], dt_minutes: float, entity: str,
                   start_minute: float = 0.0) -> list[float]:
    """Exact transition of a damped sinusoidally forced state over any interval.

    This has the semigroup property: advancing A→B→C matches A→C (apart from
    floating-point roundoff), so missed scheduler ticks do not alter the physics.
    """
    dt = max(0.0, float(dt_minutes))
    t0 = float(start_minute)
    t1 = t0 + dt
    out: list[float] = []
    for i, x in enumerate(latent):
        lam = DECAY_PER_MINUTE[i]
        omega = OMEGA[i]
        phase = _phase(entity, i)
        decay = math.exp(-lam * dt)
        # Choose forcing magnitude so the steady-state sinusoid has the desired amplitude.
        forcing = INTRINSIC_AMPLITUDE * math.sqrt(lam * lam + omega * omega) * _seed_unit(entity, i + 100)
        denom = lam * lam + omega * omega

        def primitive(t: float) -> float:
            angle = omega * t + phase
            return (lam * math.sin(angle) - omega * math.cos(angle)) / denom

        value = float(x) * decay + forcing * (primitive(t1) - decay * primitive(t0))
        out.append(_clamp(value, -LATENT_BOUND, LATENT_BOUND))
    return out


def event_vector(entity: str, event: str) -> list[float]:
    text = str(event or "").strip()
    if not text:
        return [0.0] * LATENT_DIM
    digest = hashlib.sha256(f"{entity}|{text}".encode()).digest()
    return [((digest[i] / 255.0) * 2.0 - 1.0) * 0.28 for i in range(LATENT_DIM)]


def apply_event(latent: Iterable[float], entity: str, event: str) -> list[float]:
    delta = event_vector(entity, event)
    return [_clamp(float(x) + delta[i], -LATENT_BOUND, LATENT_BOUND) for i, x in enumerate(latent)]


def project_observables(latent: Iterable[float]) -> list[float]:
    x = list(latent)
    if len(x) != LATENT_DIM:
        raise ValueError(f"latent must have {LATENT_DIM} values")
    return [0.5 + 0.5 * math.tanh(sum(w * v for w, v in zip(row, x))) for row in OBS_WEIGHTS]


def regime_logits(observables: Iterable[float]) -> list[float]:
    o = list(observables)
    if len(o) != OBS_DIM:
        raise ValueError(f"observables must have {OBS_DIM} values")
    centered = [v - 0.5 for v in o]
    return [sum(w * v for w, v in zip(row, centered)) for row in REGIME_WEIGHTS]


def softmax(logits: Iterable[float]) -> list[float]:
    vals = [float(v) for v in logits]
    m = max(vals)
    exps = [math.exp(v - m) for v in vals]
    total = sum(exps)
    return [v / total for v in exps]


def normalized_entropy(probabilities: Iterable[float]) -> float:
    p = [max(0.0, float(v)) for v in probabilities]
    total = sum(p)
    if total <= 0.0:
        return 0.0
    p = [v / total for v in p]
    h = -sum(v * math.log(v) for v in p if v > 0.0)
    return _clamp(h / math.log(len(p)), 0.0, 1.0)


def l1_change(a: Iterable[float], b: Iterable[float]) -> float:
    return sum(abs(float(x) - float(y)) for x, y in zip(a, b))


def tick(state: EntityState, now_minute: float, event: str | None = None) -> tuple[EntityState, dict]:
    if state.entity not in ENTITIES:
        raise ValueError(f"unknown entity: {state.entity}")
    dt = max(0.0, float(now_minute) - float(state.minute))
    latent = advance_latent(state.latent, dt, state.entity, state.minute)

    event_hash = state.last_event_hash
    if event is not None and str(event).strip():
        latent = apply_event(latent, state.entity, str(event))
        event_hash = hashlib.sha256(str(event).encode()).hexdigest()[:16]

    observables = project_observables(latent)
    regimes = softmax(regime_logits(observables))
    entropy = normalized_entropy(regimes)
    change = l1_change(state.regimes, regimes)

    # Diagnostic only. Candidate speech policy lives in decision.py.
    interesting = bool(event is not None or change >= 0.18 or dt >= 180.0)
    new_state = EntityState(1, state.entity, float(now_minute), latent, regimes, entropy, event_hash)
    diagnostics = {
        "entity": state.entity,
        "dt_minutes": dt,
        "observables": observables,
        "regime_names": REGIME_NAMES,
        "regime_probabilities": regimes,
        "entropy": entropy,
        "regime_l1_change": change,
        "interesting": interesting,
        "speech_requested": False,
    }
    return new_state, diagnostics


def state_to_json(state: EntityState) -> str:
    return json.dumps(asdict(state), sort_keys=True, separators=(",", ":"))


def state_from_json(text: str) -> EntityState:
    data = json.loads(text)
    state = EntityState(**data)
    if len(state.latent) != LATENT_DIM or len(state.regimes) != REGIME_DIM:
        raise ValueError("invalid state dimensions")
    if not all(math.isfinite(float(v)) for v in state.latent + state.regimes):
        raise ValueError("state contains non-finite values")
    return state
