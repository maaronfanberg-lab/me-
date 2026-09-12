from __future__ import annotations

"""Behavior-shaped autonomy overlay for The Room."""

import room_private_model_autonomy_legacy as _legacy

PROCESS_TERMS = {
    "ground", "grounded", "grounding",
    "clarify", "clarifies", "clarified", "clarifying", "clarification", "clarifications", "clarity",
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

AUTONOMY_ENGINE = "structural-base-selective-context-behavior-shaped-v5"
AUTONOMY_PROMPTS = dict(_legacy.AUTONOMY_PROMPTS)
AUTONOMY_PROMPTS["thought"] = (
    "Decide what this participant personally wants to do next in the conversation. "
    "Use their own identity, values, motives, attention, relationship state, evidence_context, and what was actually said. "
    "Form this participant's own position rather than inferring a group consensus. "
    "Before choosing a move, identify what this turn would add. Prefer a contribution that changes the informational state: "
    "derive an implication, distinguish possibilities, notice a contradiction, connect separate facts, challenge an assumption with a reason, "
    "revise a belief, identify missing evidence, make a supported prediction, or recognize an important human consequence. "
    "Paraphrase, automatic agreement, repeated process language, and unnecessary process questions add little and should not drive the next move. "
    "When a phrase or concept is already dominating the conversation, look underneath it for the unresolved cause, assumption, evidence, disagreement, or consequence instead of repeating it. "
    "Novelty alone is not valuable; the contribution must remain relevant and supported. "
    "A reported claim may be questioned, believed weakly, or left unresolved; it is not a witnessed event merely because someone said it. "
    "Choose among ANSWER, DEEPEN, DISCLOSE, COMPARE, DISAGREE, REPAIR, SUPPORT, CALLBACK, BRIDGE, or CLOSE. "
    "No move is preferred. SUPPORT is appropriate only when this participant actually wants to reinforce or affiliate. "
    "If this participant has nothing meaningful to add, CLOSE is better than filler. "
    "Choose another Room participant as the intended partner. Choose for yourself what matters next."
)
AUTONOMY_PROMPTS["expression"] = (
    "Speak as this participant in the ongoing conversation. "
    "Realize the internally generated intent supplied in the situation: keep its move, focus, and intended partner. "
    "Respond to the meaning of recent speech rather than copying its wording or conversational structure. "
    "A strong turn stays coherent with the conversation while transforming information: it adds an inference, distinction, reason, revision, connection, prediction, or human consequence. "
    "Reuse another speaker's terminology only when it is needed for precision. Do not merely paraphrase, echo agreement, or keep a repeated concept alive because it is salient. "
    "When the conversation is looping, address the unresolved assumption, evidence, disagreement, cause, or consequence underneath the repeated language. "
    "Demonstrate understanding through the substance of the reply rather than announcing that you understand, are listening, or are coherent. "
    "Novel wording without new meaning is not an improvement. Keep the reply relevant, defensible, natural, and concise. "
    "Use evidence_context to distinguish what was observed from what was merely claimed. "
    "Use only details supported by the conversation and choose your own wording."
)

_legacy.AUTONOMY_PROMPTS = AUTONOMY_PROMPTS
_legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
_ORIGINAL_REQUEST_AUTONOMY = _legacy._request_autonomy


def _request_autonomy(model_url: str, prompt: str, role: str, temperature: float, timeout: int,
                      self_entity: str | None = None, attempt: int = 0, intent: dict | None = None) -> str:
    if role in {"thought", "expression"}:
        prompt += (
            "\nBEHAVIORAL_CONTINGENCY\n"
            "High-value behavior: make one evidence-linked contribution that changes what the conversation knows, distinguishes, predicts, revises, connects, or recognizes. "
            "Low-value behavior: repeat, lightly paraphrase, automatically agree, recycle process words, or ask unnecessary process questions. "
            "If recent speakers are converging on the same wording, respond to the underlying meaning and take a different reasoning step. "
            "Do not manufacture novelty; relevance and evidence still control.\n"
        )
        if attempt:
            prompt += (
                "SHAPING_RETRY\n"
                "The prior attempt did not satisfy the active quality boundary. Preserve the intended conversational goal, but choose a more substantive reasoning step rather than merely changing phrasing.\n"
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
