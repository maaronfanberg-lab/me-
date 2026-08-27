from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Iterable

ENTITIES = ("sarah", "mara", "owen", "jules")
LATENT_DIM = 8
OBS_DIM = 10
REGIME_DIM = 4
LATENT_BOUND = 3.0
MAX_ADVANCE_MINUTES = 525600.0
REGIME_GAIN = 5.0

OMEGA = (0.071, 0.103, 0.149, 0.211, 0.293, 0.379, 0.487, 0.613)
DECAY_PER_MINUTE = (0.004, 0.006, 0.005, 0.008, 0.007, 0.004, 0.009, 0.006)
INTRINSIC_AMPLITUDE = 0.30

# Each entity has its own deterministic tempo. These are deliberately not
# harmonic multiples, so their internal motion drifts in and out of phase.
ENTITY_TEMPO = {
    "sarah": 0.82,
    "mara": 1.07,
    "owen": 0.94,
    "jules": 1.19,
}
ENTITY_PULSE_AMPLITUDE = {
    "sarah": 0.48,
    "mara": 0.58,
    "owen": 0.53,
    "jules": 0.65,
}
REGIME_PULSE_OMEGA = (0.031, 0.043, 0.057, 0.071)

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


def _finite(value: object, name: str = "value") -> float:
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(n):
        raise ValueError(f"{name} must be finite")
    return n


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _seed_unit(entity: str, i: int) -> float:
    raw = hashlib.sha256(f"room-vault:{entity}:{i}".encode()).digest()
    n = int.from_bytes(raw[:8], "big") / float(2**64 - 1)
    return 2.0 * n - 1.0


def _phase(entity: str, i: int) -> float:
    return math.pi * (_seed_unit(entity, i + 200) + 1.0)


def _reduced_angle(value: float) -> float:
    return math.remainder(value, math.tau)


def rhythmic_regime_pulse(entity: str, minute: float) -> list[float]:
    """Zero-mean deterministic rhythmic pressure on the four regimes."""
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    t = _finite(minute, "minute")
    tempo = ENTITY_TEMPO[entity]
    amplitude = ENTITY_PULSE_AMPLITUDE[entity]
    raw = [
        amplitude * math.sin(
            _reduced_angle(REGIME_PULSE_OMEGA[i] * tempo * t + _phase(entity, i + 500))
        )
        for i in range(REGIME_DIM)
    ]
    mean = sum(raw) / REGIME_DIM
    return [v - mean for v in raw]


def regime_probabilities(observables: Iterable[float], entity: str, minute: float) -> list[float]:
    base = regime_logits(observables)
    pulse = rhythmic_regime_pulse(entity, minute)
    return softmax([a + b for a, b in zip(base, pulse)])


def initial_state(entity: str, minute: float = 0.0) -> EntityState:
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    minute_f = _finite(minute, "minute")
    latent = [0.35 * _seed_unit(entity, i) for i in range(LATENT_DIM)]
    observables = project_observables(latent)
    regimes = regime_probabilities(observables, entity, minute_f)
    return EntityState(1, entity, minute_f, latent, regimes, normalized_entropy(regimes))


def advance_latent(latent: Iterable[float], dt_minutes: float, entity: str,
                   start_minute: float = 0.0) -> list[float]:
    """Exact bounded transition of a damped sinusoidally forced state."""
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    xs = list(latent)
    if len(xs) != LATENT_DIM:
        raise ValueError(f"latent must have {LATENT_DIM} values")
    xs = [_finite(v, f"latent[{i}]") for i, v in enumerate(xs)]
    dt = _finite(dt_minutes, "dt_minutes")
    if dt < 0.0:
        dt = 0.0
    dt = min(dt, MAX_ADVANCE_MINUTES)
    t0 = _finite(start_minute, "start_minute")
    t1 = t0 + dt
    tempo = ENTITY_TEMPO[entity]
    out: list[float] = []
    for i, x in enumerate(xs):
        lam = DECAY_PER_MINUTE[i]
        omega = OMEGA[i] * tempo
        phase = _phase(entity, i)
        decay = math.exp(-lam * dt)
        forcing = INTRINSIC_AMPLITUDE * math.sqrt(lam * lam + omega * omega) * _seed_unit(entity, i + 100)
        denom = lam * lam + omega * omega

        def primitive(t: float) -> float:
            angle = _reduced_angle(omega * t + phase)
            return (lam * math.sin(angle) - omega * math.cos(angle)) / denom

        value = x * decay + forcing * (primitive(t1) - decay * primitive(t0))
        if not math.isfinite(value):
            raise ValueError("latent transition became non-finite")
        out.append(_clamp(value, -LATENT_BOUND, LATENT_BOUND))
    return out


def event_vector(entity: str, event: str) -> list[float]:
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    text = str(event or "").strip()[:4096]
    if not text:
        return [0.0] * LATENT_DIM
    digest = hashlib.sha256(f"{entity}|{text}".encode()).digest()
    return [((digest[i] / 255.0) * 2.0 - 1.0) * 0.28 for i in range(LATENT_DIM)]


def apply_event(latent: Iterable[float], entity: str, event: str) -> list[float]:
    xs = list(latent)
    if len(xs) != LATENT_DIM:
        raise ValueError(f"latent must have {LATENT_DIM} values")
    xs = [_finite(v, f"latent[{i}]") for i, v in enumerate(xs)]
    delta = event_vector(entity, event)
    return [_clamp(x + delta[i], -LATENT_BOUND, LATENT_BOUND) for i, x in enumerate(xs)]


def project_observables(latent: Iterable[float]) -> list[float]:
    x = list(latent)
    if len(x) != LATENT_DIM:
        raise ValueError(f"latent must have {LATENT_DIM} values")
    x = [_finite(v, f"latent[{i}]") for i, v in enumerate(x)]
    out = [0.5 + 0.5 * math.tanh(sum(w * v for w, v in zip(row, x))) for row in OBS_WEIGHTS]
    if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in out):
        raise ValueError("observable projection left [0,1]")
    return out


def regime_logits(observables: Iterable[float]) -> list[float]:
    o = list(observables)
    if len(o) != OBS_DIM:
        raise ValueError(f"observables must have {OBS_DIM} values")
    o = [_finite(v, f"observable[{i}]") for i, v in enumerate(o)]
    centered = [v - 0.5 for v in o]
    return [REGIME_GAIN * sum(w * v for w, v in zip(row, centered)) for row in REGIME_WEIGHTS]


def softmax(logits: Iterable[float]) -> list[float]:
    vals = list(logits)
    if not vals:
        raise ValueError("softmax requires at least one value")
    vals = [_finite(v, f"logit[{i}]") for i, v in enumerate(vals)]
    m = max(vals)
    exps = [math.exp(v - m) for v in vals]
    total = sum(exps)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("invalid softmax normalization")
    out = [v / total for v in exps]
    if not all(math.isfinite(v) for v in out):
        raise ValueError("softmax produced non-finite probability")
    return out


def normalized_entropy(probabilities: Iterable[float]) -> float:
    p = list(probabilities)
    if not p:
        return 0.0
    p = [_finite(v, f"probability[{i}]") for i, v in enumerate(p)]
    if any(v < 0.0 for v in p):
        raise ValueError("probabilities must be non-negative")
    total = sum(p)
    if total <= 0.0:
        return 0.0
    p = [v / total for v in p]
    if len(p) == 1:
        return 0.0
    h = -sum(v * math.log(v) for v in p if v > 0.0)
    return _clamp(h / math.log(len(p)), 0.0, 1.0)


def l1_change(a: Iterable[float], b: Iterable[float]) -> float:
    aa, bb = list(a), list(b)
    if len(aa) != len(bb):
        raise ValueError("l1 vectors must have equal dimensions")
    return sum(abs(_finite(x, "l1 lhs") - _finite(y, "l1 rhs")) for x, y in zip(aa, bb))


def tick(state: EntityState, now_minute: float, event: str | None = None) -> tuple[EntityState, dict]:
    if state.entity not in ENTITIES:
        raise ValueError(f"unknown entity: {state.entity}")
    state_minute = _finite(state.minute, "state.minute")
    requested_now = _finite(now_minute, "now_minute")
    effective_now = max(state_minute, requested_now)
    dt = effective_now - state_minute
    latent = advance_latent(state.latent, dt, state.entity, state_minute)
    has_event = bool(str(event or "").strip())
    event_hash = state.last_event_hash
    if has_event:
        latent = apply_event(latent, state.entity, str(event))
        event_hash = hashlib.sha256(str(event).encode()).hexdigest()[:16]
    observables = project_observables(latent)
    regimes = regime_probabilities(observables, state.entity, effective_now)
    entropy = normalized_entropy(regimes)
    change = l1_change(state.regimes, regimes)
    interesting = bool(has_event or change >= 0.18 or dt >= 180.0)
    new_state = EntityState(1, state.entity, effective_now, latent, regimes, entropy, event_hash)
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
    state_from_json(json.dumps(asdict(state)))
    return json.dumps(asdict(state), sort_keys=True, separators=(",", ":"))


def state_from_json(text: str) -> EntityState:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("state must be an object")
    state = EntityState(**data)
    if state.entity not in ENTITIES:
        raise ValueError("invalid entity")
    state.minute = _finite(state.minute, "state.minute")
    state.entropy = _finite(state.entropy, "state.entropy")
    if not 0.0 <= state.entropy <= 1.0:
        raise ValueError("entropy outside [0,1]")
    if len(state.latent) != LATENT_DIM or len(state.regimes) != REGIME_DIM:
        raise ValueError("invalid state dimensions")
    state.latent = [_finite(v, f"latent[{i}]") for i, v in enumerate(state.latent)]
    if any(abs(v) > LATENT_BOUND + 1e-9 for v in state.latent):
        raise ValueError("latent outside bounds")
    state.regimes = [_finite(v, f"regime[{i}]") for i, v in enumerate(state.regimes)]
    if any(v < 0.0 or v > 1.0 for v in state.regimes):
        raise ValueError("regime probability outside [0,1]")
    if abs(sum(state.regimes) - 1.0) > 1e-6:
        raise ValueError("regime probabilities must sum to 1")
    return state
