from __future__ import annotations

import math
import re

ENTITIES = {"sarah", "mara", "owen", "jules"}
OBSERVABLE_NAMES = (
    "curiosity", "tension", "novelty", "affiliation", "confidence",
    "memory", "uncertainty", "persistence", "social_salience", "initiative",
)
VALID_MODES = {"settled", "exploratory", "social", "transition"}
VALID_REASONS = {
    "highest_bounded_candidate", "meaningful_regime_change", "below_change_threshold",
    "no_new_messages", "cooldown", "bootstrap_suppressed", "cycle_regression",
}


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _bounded(value: object) -> float:
    return max(0.0, min(1.0, _finite(value, 0.5)))


def _safe_entity(entity: object) -> str:
    value = re.sub(r"[^a-z0-9_-]", "", str(entity or "").lower())[:32]
    return value if value in ENTITIES else "unknown"


def _normalized_probs(value: object) -> list[float]:
    raw = list(value)[:4] if isinstance(value, (list, tuple)) else []
    raw.extend([0.25] * (4 - len(raw)))
    probs = [_bounded(v) for v in raw[:4]]
    total = sum(probs)
    return [0.25] * 4 if total <= 0 else [v / total for v in probs]


def compact_state_summary(entity: str, diagnostic: dict, decision: dict | None = None) -> dict:
    diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
    raw_values = diagnostic.get("observables")
    values = list(raw_values)[: len(OBSERVABLE_NAMES)] if isinstance(raw_values, (list, tuple)) else []
    values.extend([0.5] * (len(OBSERVABLE_NAMES) - len(values)))
    values = [_bounded(v) for v in values]
    ranked = sorted(zip(OBSERVABLE_NAMES, values), key=lambda item: (-abs(item[1] - 0.5), item[0]))[:3]

    probs = _normalized_probs(diagnostic.get("regime_probabilities"))
    ordered = sorted(probs, reverse=True)
    separation = ordered[0] - ordered[1]
    mode = str(diagnostic.get("dominant_regime") or "unknown").lower()
    if mode not in VALID_MODES:
        mode = "unknown"

    summary = {
        "entity": _safe_entity(entity),
        "dominant_mode": mode,
        "mode_change": round(max(0.0, min(2.0, _finite(diagnostic.get("regime_l1_change"), 0.0))), 4),
        "regime_entropy": round(_bounded(diagnostic.get("entropy")), 4),
        "mode_separation": round(max(0.0, min(1.0, separation)), 4),
        "salient_signals": [
            {"name": name, "level": round(value, 3), "direction": "high" if value >= 0.5 else "low"}
            for name, value in ranked
        ],
    }
    if isinstance(decision, dict):
        summary["candidate"] = decision.get("would_request_speech") is True
        reason = str(decision.get("reason") or "none")
        summary["candidate_reason"] = reason if reason in VALID_REASONS else "other"
    return summary


def compact_state_text(entity: str, diagnostic: dict, decision: dict | None = None) -> str:
    state = compact_state_summary(entity, diagnostic, decision)
    signals = ", ".join(
        f"{item['name']}={item['direction']}({item['level']:.3f})" for item in state["salient_signals"]
    )
    action = "candidate" if state.get("candidate") else "observe"
    return (
        f"inner_state: entity={state['entity']}; mode={state['dominant_mode']}; "
        f"change={state['mode_change']:.4f}; regime_entropy={state['regime_entropy']:.4f}; "
        f"mode_separation={state['mode_separation']:.4f}; signals={signals}; "
        f"action={action}; reason={state.get('candidate_reason', 'none')}"
    )[:480]
