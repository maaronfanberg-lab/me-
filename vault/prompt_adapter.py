from __future__ import annotations

OBSERVABLE_NAMES = (
    "curiosity", "tension", "novelty", "affiliation", "confidence",
    "memory", "uncertainty", "persistence", "social_salience", "initiative",
)


def compact_state_summary(entity: str, diagnostic: dict, decision: dict | None = None) -> dict:
    values = list(diagnostic.get("observables") or [])
    ranked = sorted(zip(OBSERVABLE_NAMES, values), key=lambda item: abs(float(item[1]) - 0.5), reverse=True)[:3]
    summary = {
        "entity": entity,
        "dominant_mode": diagnostic.get("dominant_regime"),
        "mode_change": round(float(diagnostic.get("regime_l1_change", 0.0) or 0.0), 4),
        "uncertainty": round(float(diagnostic.get("entropy", 0.0) or 0.0), 4),
        "salient_signals": [
            {"name": name, "level": round(float(value), 3)} for name, value in ranked
        ],
    }
    if isinstance(decision, dict):
        summary["candidate"] = bool(decision.get("would_request_speech"))
        summary["candidate_reason"] = decision.get("reason")
    return summary


def compact_state_text(entity: str, diagnostic: dict, decision: dict | None = None) -> str:
    s = compact_state_summary(entity, diagnostic, decision)
    signals = ", ".join(f"{x['name']}={x['level']:.3f}" for x in s["salient_signals"])
    candidate = "candidate" if s.get("candidate") else "observe"
    return (
        f"inner_state: entity={s['entity']}; mode={s['dominant_mode']}; "
        f"change={s['mode_change']:.4f}; uncertainty={s['uncertainty']:.4f}; "
        f"signals={signals}; action={candidate}; reason={s.get('candidate_reason','none')}"
    )
