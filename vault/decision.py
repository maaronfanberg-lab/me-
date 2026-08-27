from __future__ import annotations

import math
from dataclasses import asdict, dataclass

CANDIDATE_CHANGE_THRESHOLD = 0.06
COOLDOWN_CYCLES = 2
COOLDOWN_OBSERVATIONS = 2
GLOBAL_CANDIDATE_BUDGET = 1


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
    except (TypeError, ValueError):
        return None
    return cycle if cycle >= 0 else None


def _score(diag: dict) -> float:
    change = max(0.0, _finite(diag.get("regime_l1_change"), 0.0))
    probs = list(diag.get("regime_probabilities") or [])
    transition = _finite(probs[3], 0.25) if len(probs) >= 4 else 0.25
    transition = max(0.0, min(1.0, transition))
    # Change does the real work. Transition probability is only a small tie-breaker.
    return 2.0 * change + 0.15 * transition


def choose_candidates(
    diagnostics: dict[str, dict],
    source_cycle: int | None,
    previous: dict | None = None,
    processed_messages: int = 0,
    allow_candidates: bool = True,
) -> tuple[dict, dict]:
    previous = previous if isinstance(previous, dict) else {}
    last_cycle = previous.get("last_candidate_cycle") if isinstance(previous.get("last_candidate_cycle"), dict) else {}
    last_observation = previous.get("last_candidate_observation") if isinstance(previous.get("last_candidate_observation"), dict) else {}
    observation = max(0, int(_finite(previous.get("observation_index"), 0.0))) + 1
    cycle = _safe_cycle(source_cycle)
    previous_cycle = _safe_cycle(previous.get("last_source_cycle"))
    cycle_regressed = cycle is not None and previous_cycle is not None and cycle < previous_cycle

    ranked: list[tuple[float, str]] = []
    decisions: dict[str, CandidateDecision] = {}

    for entity in sorted(diagnostics):
        diag = diagnostics.get(entity) if isinstance(diagnostics.get(entity), dict) else {}
        change = max(0.0, _finite(diag.get("regime_l1_change"), 0.0))
        prior_cycle = _safe_cycle(last_cycle.get(entity))
        prior_observation = _safe_cycle(last_observation.get(entity))

        blocked_by_cycle = (
            cycle is not None
            and prior_cycle is not None
            and not cycle_regressed
            and cycle >= prior_cycle
            and cycle - prior_cycle < COOLDOWN_CYCLES
        )
        blocked_by_observation = (
            prior_observation is not None
            and observation >= prior_observation
            and observation - prior_observation < COOLDOWN_OBSERVATIONS
        )
        blocked = blocked_by_cycle or blocked_by_observation
        eligible = (
            allow_candidates
            and processed_messages > 0
            and change >= CANDIDATE_CHANGE_THRESHOLD
            and not blocked
        )
        score = _score(diag)
        if eligible:
            # Explicit entity tie-break makes identical scores reproducible across runtimes.
            ranked.append((-score, entity))

        if not allow_candidates:
            reason = "bootstrap_suppressed"
        elif processed_messages <= 0:
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

    output = {entity: asdict(decisions[entity]) for entity in sorted(decisions)}
    meta = {
        "last_candidate_cycle": next_last_cycle,
        "last_candidate_observation": next_last_observation,
        "observation_index": observation,
        "last_source_cycle": cycle if cycle is not None else previous_cycle,
        "cycle_regressed": cycle_regressed,
        "global_candidate_budget": GLOBAL_CANDIDATE_BUDGET,
        "actual_speech_enabled": False,
    }
    return output, meta
