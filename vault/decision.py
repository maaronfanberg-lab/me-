from __future__ import annotations

from dataclasses import dataclass, asdict

CANDIDATE_CHANGE_THRESHOLD = 0.06
COOLDOWN_CYCLES = 2
GLOBAL_CANDIDATE_BUDGET = 1


@dataclass(frozen=True)
class CandidateDecision:
    entity: str
    would_request_speech: bool
    score: float
    reason: str
    cooldown_blocked: bool


def _score(diag: dict) -> float:
    change = float(diag.get("regime_l1_change", 0.0) or 0.0)
    probs = list(diag.get("regime_probabilities") or [0.25] * 4)
    transition = float(probs[3]) if len(probs) >= 4 else 0.25
    # Change does the real work. Transition probability is only a small tie-breaker.
    return 2.0 * change + 0.15 * transition


def choose_candidates(diagnostics: dict[str, dict], source_cycle: int | None,
                      previous: dict | None = None, processed_messages: int = 0) -> tuple[dict, dict]:
    previous = previous if isinstance(previous, dict) else {}
    last_cycle = previous.get("last_candidate_cycle") if isinstance(previous.get("last_candidate_cycle"), dict) else {}
    cycle = int(source_cycle or 0)
    ranked = []
    decisions: dict[str, CandidateDecision] = {}

    for entity, diag in diagnostics.items():
        change = float(diag.get("regime_l1_change", 0.0) or 0.0)
        prior = last_cycle.get(entity)
        blocked = prior is not None and cycle > 0 and cycle - int(prior) < COOLDOWN_CYCLES
        eligible = processed_messages > 0 and change >= CANDIDATE_CHANGE_THRESHOLD and not blocked
        score = _score(diag)
        if eligible:
            ranked.append((score, entity))
        reason = "below_change_threshold"
        if processed_messages <= 0:
            reason = "no_new_messages"
        elif blocked:
            reason = "cooldown"
        elif eligible:
            reason = "meaningful_regime_change"
        decisions[entity] = CandidateDecision(entity, False, score, reason, blocked)

    ranked.sort(reverse=True)
    winners = {entity for _, entity in ranked[:GLOBAL_CANDIDATE_BUDGET]}
    next_last = dict(last_cycle)
    for entity in winners:
        old = decisions[entity]
        decisions[entity] = CandidateDecision(entity, True, old.score, "highest_bounded_candidate", False)
        if cycle:
            next_last[entity] = cycle

    output = {entity: asdict(decision) for entity, decision in decisions.items()}
    meta = {
        "last_candidate_cycle": next_last,
        "global_candidate_budget": GLOBAL_CANDIDATE_BUDGET,
        "actual_speech_enabled": False,
    }
    return output, meta
