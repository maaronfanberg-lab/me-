from __future__ import annotations

import math
from dataclasses import asdict, dataclass

ENTITIES = ("sarah", "mara", "owen", "jules")
CANDIDATE_CHANGE_THRESHOLD = 0.06
COOLDOWN_CYCLES = 2
COOLDOWN_OBSERVATIONS = 2
GLOBAL_CANDIDATE_BUDGET = 1
MAX_L1_CHANGE = 2.0


@dataclass(frozen=True)
class CandidateDecision:
    entity: str
    would_request_speech: bool
    score: float
    reason: str
    cooldown_blocked: bool


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _safe_cycle(value: object) -> int | None:
    try:
        cycle = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return cycle if 0 <= cycle <= 10**12 else None


def _safe_nonnegative_int(value: object, default: int = 0, cap: int = 10**9) -> int:
    n = _finite(value, float(default))
    if n < 0:
        return default
    return min(cap, int(n))


def _safe_change(value: object) -> float:
    return max(0.0, min(MAX_L1_CHANGE, _finite(value, 0.0)))


def _safe_transition(diag: dict) -> float:
    probs = diag.get("regime_probabilities")
    if not isinstance(probs, (list, tuple)) or len(probs) < 4:
        return 0.25
    return max(0.0, min(1.0, _finite(probs[3], 0.25)))


def _score(diag: dict) -> float:
    change = _safe_change(diag.get("regime_l1_change"))
    transition = _safe_transition(diag)
    return 2.0 * change + 0.15 * transition


def _clean_history_map(value: object) -> dict[str, int]:
    raw = value if isinstance(value, dict) else {}
    out: dict[str, int] = {}
    for entity in ENTITIES:
        n = _safe_cycle(raw.get(entity))
        if n is not None:
            out[entity] = n
    return out


def choose_candidates(
    diagnostics: dict[str, dict],
    source_cycle: int | None,
    previous: dict | None = None,
    processed_messages: int = 0,
    allow_candidates: bool = True,
) -> tuple[dict, dict]:
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    last_cycle = _clean_history_map(previous.get("last_candidate_cycle"))
    last_observation = _clean_history_map(previous.get("last_candidate_observation"))
    observation = _safe_nonnegative_int(previous.get("observation_index"), 0) + 1
    cycle = _safe_cycle(source_cycle)
    previous_cycle = _safe_cycle(previous.get("last_source_cycle"))
    cycle_regressed = cycle is not None and previous_cycle is not None and cycle < previous_cycle
    processed = _safe_nonnegative_int(processed_messages, 0, cap=100000)
    enabled = bool(allow_candidates) and not cycle_regressed

    ranked: list[tuple[float, str]] = []
    decisions: dict[str, CandidateDecision] = {}

    for entity in ENTITIES:
        diag = diagnostics.get(entity) if isinstance(diagnostics.get(entity), dict) else {}
        change = _safe_change(diag.get("regime_l1_change"))
        prior_cycle = _safe_cycle(last_cycle.get(entity))
        prior_observation = _safe_cycle(last_observation.get(entity))
        blocked_by_cycle = (
            cycle is not None and prior_cycle is not None and not cycle_regressed
            and cycle >= prior_cycle and cycle - prior_cycle < COOLDOWN_CYCLES
        )
        blocked_by_observation = (
            prior_observation is not None and observation >= prior_observation
            and observation - prior_observation < COOLDOWN_OBSERVATIONS
        )
        blocked = blocked_by_cycle or blocked_by_observation
        eligible = enabled and processed > 0 and change >= CANDIDATE_CHANGE_THRESHOLD and not blocked
        score = _score(diag)
        if eligible:
            ranked.append((-score, entity))

        if cycle_regressed:
            reason = "cycle_regression"
        elif not bool(allow_candidates):
            reason = "bootstrap_suppressed"
        elif processed <= 0:
            reason = "no_new_messages"
        elif blocked:
            reason = "cooldown"
        elif change < CANDIDATE_CHANGE_THRESHOLD:
            reason = "below_change_threshold"
        else:
            reason = "meaningful_regime_change"
        decisions[entity] = CandidateDecision(entity, False, score, reason, blocked)

    ranked.sort()
    winners = {entity for _, entity in ranked[:GLOBAL_CANDIDATE_BUDGET]}
    next_last_cycle = dict(last_cycle)
    next_last_observation = dict(last_observation)
    for entity in winners:
        old = decisions[entity]
        decisions[entity] = CandidateDecision(entity, True, old.score, "highest_bounded_candidate", False)
        if cycle is not None:
            next_last_cycle[entity] = cycle
        next_last_observation[entity] = observation

    output = {entity: asdict(decisions[entity]) for entity in ENTITIES}
    meta = {
        "last_candidate_cycle": next_last_cycle,
        "last_candidate_observation": next_last_observation,
        "observation_index": observation,
        "last_source_cycle": cycle if cycle is not None else previous_cycle,
        "cycle_regressed": cycle_regressed,
        "global_candidate_budget": GLOBAL_CANDIDATE_BUDGET,
        "direct_speech_enabled": False,
        "actual_speech_enabled": False,
    }
    return output, meta
