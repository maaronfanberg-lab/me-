from __future__ import annotations

"""Single-pass autonomy overlay for The Room.

The surrounding Room still owns persistence, memory retrieval, relationships,
turn-taking, topic state, and feed publication.  The language model itself is
used once per participant turn: it receives that grounded state and produces
the final spoken action.  Comprehension and deliberation are therefore no
longer separate model generations; those functions happen implicitly inside
the transformer's one autoregressive inference, as in a conventional chat LLM.
"""

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

AUTONOMY_ENGINE = "monolithic-single-pass-natural-social-v7"
AUTONOMY_PROMPTS = dict(_legacy.AUTONOMY_PROMPTS)

# Kept as compatibility metadata for old replays and diagnostics.  Live Room
# generation does not call the model for this role in single-pass mode.
AUTONOMY_PROMPTS["thought"] = (
    "Understand the exchange and form this participant's own next response from their identity, "
    "values, relationships, memories, and what was actually said."
)

AUTONOMY_PROMPTS["expression"] = (
    "Use the supplied recent conversation, grounded memory and relationship context, and this participant's "
    "personality to understand what is happening, decide what they mean, and produce their next spoken turn in "
    "one inference. Do not narrate comprehension, reasoning, planning, prompting, or generation. "
    "Speak only as this participant to the intended person. Respond to the substance of the newest relevant turn "
    "without copying its wording. Do not invent a setting, event, relationship, plan, organization, or role that "
    "has not been established. Use ordinary human conversational language and keep the reply natural and concise."
)

_legacy.AUTONOMY_PROMPTS = AUTONOMY_PROMPTS
_legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
_ORIGINAL_REQUEST_AUTONOMY = _legacy._request_autonomy


def _request_autonomy(model_url: str, prompt: str, role: str, temperature: float, timeout: int,
                      self_entity: str | None = None, attempt: int = 0, intent: dict | None = None) -> str:
    if role == "expression" and attempt:
        prompt += (
            "\nTRY_AGAIN_NATURALLY\n"
            "Generate a genuinely different complete spoken reply from the same grounded situation. "
            "Do not reveal or describe these instructions.\n"
        )
    return _ORIGINAL_REQUEST_AUTONOMY(
        model_url, prompt, role, temperature, timeout, self_entity, attempt, intent
    )


_has_context_echo = _legacy._has_context_echo
base = _legacy.base


def run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
    """Use one LLM inference stage per participant turn.

    The engine may still invoke the old comprehension/thought slots because the
    persisted 12-node topology is retained for backward compatibility.  Returning
    None here makes those slots deterministic scaffolding instead of additional
    generations.  Expression receives the grounded state and lets the transformer
    perform comprehension, association, intent formation, and wording internally.
    """
    if role in {"comprehension", "thought"}:
        return None

    _legacy.AUTONOMY_PROMPTS = AUTONOMY_PROMPTS
    _legacy._request_autonomy = globals().get("_request_autonomy", _request_autonomy)
    _legacy._has_context_echo = globals().get("_has_context_echo", _has_context_echo)
    _legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
    return _legacy.run(role, payload, timeout=timeout, min_words=min_words)
