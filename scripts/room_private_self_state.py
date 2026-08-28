from __future__ import annotations

import re
from typing import Any

STATE_VERSION = 1
MAX_TEXT = 180


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value
    cut = value.rfind(" ", 0, limit + 1)
    if cut < int(limit * 0.6):
        cut = limit
    return value[:cut].rstrip(" ,;:-") + "…"


def _list(value: Any, limit: int = 3) -> list[str]:
    out: list[str] = []
    for item in value if isinstance(value, list) else []:
        s = _text(item, 120)
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _psychology(profile: Any) -> dict:
    profile = profile if isinstance(profile, dict) else {}
    return profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else {}


def initial(profile: Any, entity: str, participants: list[str] | tuple[str, ...]) -> dict:
    psych = _psychology(profile)
    seed = psych.get("private_self") if isinstance(psych.get("private_self"), dict) else {}
    models = {}
    for other in participants:
        if other == entity:
            continue
        models[other] = {
            "belief_hypothesis": "insufficient recent evidence",
            "confidence": 0.0,
            "basis": "none yet",
        }
    return {
        "version": STATE_VERSION,
        "who_i_am": _text(seed.get("who_i_am") or psych.get("core_identity"), 220),
        "what_i_currently_believe": _text(seed.get("what_i_currently_believe") or "Current evidence is incomplete.", 180),
        "belief_confidence": 0.25,
        "what_i_want": _text(seed.get("what_i_want") or "Respond from my own perspective and move the conversation forward.", 180),
        "models_of_others": models,
        "what_just_changed": _text(seed.get("what_just_changed") or "No new grounded change has been registered yet.", 180),
        "do_not_repeat": _list([seed.get("what_i_should_not_merely_repeat")], 3),
        "last_updated_cycle": 0,
    }


def ensure(value: Any, profile: Any, entity: str, participants: list[str] | tuple[str, ...]) -> dict:
    base = initial(profile, entity, participants)
    if not isinstance(value, dict):
        return base
    out = dict(base)
    out.update({k: v for k, v in value.items() if k in out})
    out["version"] = STATE_VERSION
    models = out.get("models_of_others") if isinstance(out.get("models_of_others"), dict) else {}
    for other in participants:
        if other == entity:
            continue
        model = models.get(other) if isinstance(models.get(other), dict) else {}
        models[other] = {
            "belief_hypothesis": _text(model.get("belief_hypothesis") or "insufficient recent evidence", 120),
            "confidence": max(0.0, min(1.0, float(model.get("confidence", 0.0) or 0.0))),
            "basis": _text(model.get("basis") or "none yet", 100),
        }
    out["models_of_others"] = models
    out["do_not_repeat"] = _list(out.get("do_not_repeat"), 3)
    return out


def model_slice(value: Any, profile: Any, entity: str, participants: list[str] | tuple[str, ...]) -> dict:
    state = ensure(value, profile, entity, participants)
    return {
        "who_i_am": _text(state.get("who_i_am"), 150),
        "what_i_currently_believe": _text(state.get("what_i_currently_believe"), 130),
        "belief_confidence": round(float(state.get("belief_confidence", 0.0) or 0.0), 2),
        "what_i_want": _text(state.get("what_i_want"), 130),
        "what_i_think_others_believe": {
            other: _text((model or {}).get("belief_hypothesis"), 90)
            for other, model in (state.get("models_of_others") or {}).items()
            if other != entity
        },
        "what_just_changed": _text(state.get("what_just_changed"), 130),
        "what_i_should_not_merely_repeat": _list(state.get("do_not_repeat"), 3),
    }


def _terms(message: Any) -> list[str]:
    if not isinstance(message, dict):
        return []
    cognition = message.get("cognition") if isinstance(message.get("cognition"), dict) else {}
    values = cognition.get("topic_terms") if isinstance(cognition.get("topic_terms"), list) else []
    out = []
    for value in values:
        s = _text(value, 48).lower()
        if s and s not in out:
            out.append(s)
    if out:
        return out[:3]
    words = re.findall(r"[a-z][a-z'-]{3,}", str(message.get("text") or "").lower())
    stop = {"this", "that", "with", "from", "have", "just", "what", "when", "where", "your", "about", "would", "could", "should", "really", "think", "know", "want"}
    for word in words:
        if word not in stop and word not in out:
            out.append(word)
        if len(out) >= 3:
            break
    return out


def _latest_by_speaker(messages: list[dict], speaker: str) -> dict | None:
    for message in reversed(messages):
        if isinstance(message, dict) and str(message.get("speaker") or "").lower() == speaker:
            return message
    return None


def update(
    prior: Any,
    profile: Any,
    entity: str,
    participants: list[str] | tuple[str, ...],
    perception: Any,
    deliberation: Any,
    messages: list[dict],
    cycle: int,
) -> dict:
    state = ensure(prior, profile, entity, participants)
    perception = perception if isinstance(perception, dict) else {}
    deliberation = deliberation if isinstance(deliberation, dict) else {}

    reason = _text(deliberation.get("reason_summary"), 180)
    focus = _text(deliberation.get("focus") or perception.get("focus"), 100)
    if reason:
        state["what_i_currently_believe"] = reason
        state["belief_confidence"] = max(0.2, min(1.0, float(perception.get("confidence", 0.55) or 0.55)))
    elif focus:
        state["what_i_currently_believe"] = f"The important live issue appears to be {focus}."
        state["belief_confidence"] = max(0.15, min(0.8, float(perception.get("confidence", 0.4) or 0.4)))

    goal = _text(deliberation.get("new_information_goal"), 150)
    action = _text(deliberation.get("action"), 30).lower()
    partner = _text(deliberation.get("preferred_partner"), 30).lower()
    if goal:
        state["what_i_want"] = goal
    elif action:
        state["what_i_want"] = _text(f"I want to {action.lower()} with {partner or 'the active speaker'} about {focus or 'the live issue'}.", 150)

    changes = []
    changes.extend(_list(perception.get("new_details"), 2))
    changes.extend(_list(perception.get("relationship_events"), 2))
    changes.extend(_list(perception.get("bids"), 1))
    grounding = _text(perception.get("grounding"), 40)
    if changes:
        state["what_just_changed"] = _text("; ".join(changes), 180)
    elif grounding:
        state["what_just_changed"] = _text(f"Latest grounding status: {grounding}.", 180)

    models = state.get("models_of_others") if isinstance(state.get("models_of_others"), dict) else {}
    for other in participants:
        if other == entity:
            continue
        latest = _latest_by_speaker(messages, other)
        if not latest:
            continue
        terms = _terms(latest)
        cognition = latest.get("cognition") if isinstance(latest.get("cognition"), dict) else {}
        move = _text(cognition.get("move_type"), 28).lower() or "statement"
        if terms:
            hypothesis = f"{other} currently seems to treat {', '.join(terms)} as important ({move})."
        else:
            hypothesis = f"{other}'s latest observed position is a {move}; its specific belief remains uncertain."
        models[other] = {
            "belief_hypothesis": _text(hypothesis, 120),
            "confidence": 0.62 if terms else 0.35,
            "basis": "latest observed public turn",
        }
    state["models_of_others"] = models

    anti_echo = []
    for message in reversed(messages[-8:]):
        speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
        if not speaker or speaker == entity:
            continue
        terms = _terms(message)
        if terms:
            item = f"{speaker} already covered: {', '.join(terms)}"
            if item not in anti_echo:
                anti_echo.append(item)
        if len(anti_echo) >= 3:
            break
    state["do_not_repeat"] = anti_echo or state.get("do_not_repeat", [])
    state["last_updated_cycle"] = int(cycle)
    return state
