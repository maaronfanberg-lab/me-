from __future__ import annotations

"""Behavior-shaped autonomy overlay for The Room."""

import room_private_model_autonomy_legacy as _legacy

PROCESS_TERMS = {
    "ground", "grounded", "grounding",
    "clarify", "clarifies", "clarified", "clarifying", "clarification", "clarifications", "clarity",
    "utterance", "utterances", "turn", "turns", "contribution", "contributions",
}

try:
    import room_topic_bounded as _bounded_topic
    _bounded_topic._TOPIC_NOISE.update(PROCESS_TERMS)
except Exception:
    pass

try:
    import room_engine_v5 as _engine
    _engine._CUE_STOPWORDS.update(PROCESS_TERMS)
    _engine._TOPIC_FILLER.update(PROCESS_TERMS)
except Exception:
    pass

for _name, _value in vars(_legacy).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

AUTONOMY_ENGINE = "structural-base-selective-context-natural-social-v6"
AUTONOMY_PROMPTS = dict(_legacy.AUTONOMY_PROMPTS)
AUTONOMY_PROMPTS["thought"] = (
    "Decide what this participant personally wants to say or do next. "
    "Use their own identity, values, motives, attention, relationships, and what was actually said. "
    "Form their own view rather than guessing a group consensus. "
    "Prefer something that genuinely moves the exchange forward: a reason, inference, distinction, disagreement, connection, change of mind, question, consequence, or personal reaction. "
    "Do not copy another speaker or agree automatically. If the same idea keeps repeating, respond to what is underneath it instead of repeating the wording. "
    "Do not invent a setting, event, relationship, plan, or role that the conversation has not established. "
    "A reported claim may be questioned, believed weakly, or left unresolved; it is not a witnessed event merely because someone said it. "
    "Choose among ANSWER, DEEPEN, DISCLOSE, COMPARE, DISAGREE, REPAIR, SUPPORT, CALLBACK, BRIDGE, or CLOSE. "
    "No move is preferred. If this participant has nothing worth adding, CLOSE is better than filler. "
    "Choose another Room participant as the intended partner."
)
AUTONOMY_PROMPTS["expression"] = (
    "Speak naturally as this participant in the ongoing exchange. "
    "Say what they actually mean to the intended person in their own voice. "
    "Respond to the substance of what was said rather than copying its wording. "
    "Use ordinary human conversational language, not analytical or procedural commentary about the exchange itself. "
    "Do not invent a setting, event, relationship, plan, organization, or role that has not been established. "
    "Use only details supported by what was actually said. Keep the reply natural and concise."
)

_legacy.AUTONOMY_PROMPTS = AUTONOMY_PROMPTS
_legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
_ORIGINAL_REQUEST_AUTONOMY = _legacy._request_autonomy


def _request_autonomy(model_url: str, prompt: str, role: str, temperature: float, timeout: int,
                      self_entity: str | None = None, attempt: int = 0, intent: dict | None = None) -> str:
    if role in {"thought", "expression"} and attempt:
        prompt += (
            "\nTRY_AGAIN_NATURALLY\n"
            "Keep the same purpose, but use a genuinely different idea or sentence rather than a cosmetic rewording.\n"
        )
    return _ORIGINAL_REQUEST_AUTONOMY(
        model_url, prompt, role, temperature, timeout, self_entity, attempt, intent
    )

_has_context_echo = _legacy._has_context_echo
base = _legacy.base


def run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
    _legacy.AUTONOMY_PROMPTS = AUTONOMY_PROMPTS
    _legacy._request_autonomy = globals().get("_request_autonomy", _request_autonomy)
    _legacy._has_context_echo = globals().get("_has_context_echo", _has_context_echo)
    _legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
    return _legacy.run(role, payload, timeout=timeout, min_words=min_words)
