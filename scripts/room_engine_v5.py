#!/usr/bin/env python3
from __future__ import annotations

"""Select the lean autonomy-v2 model path only for the Llama Room brain.

The complete pre-Llama production wrapper is preserved in
room_engine_v5_legacy.py. Qwen fallback uses that code unchanged. When the
workflow has positively identified Llama 3.2 as the active brain, only the
language-model call boundary is replaced with the autonomy-v2 adapter; the
Room engine, Allen routing, state transitions, and commit behavior remain the
preserved production implementation.
"""

import json
import os
import re

import room_engine_v5_legacy as _legacy

# The production workflow verifies the known-good legacy retry budget before
# starting a warm runner. The real loop remains in room_engine_v5_legacy.py.
LEGACY_RETRY_POLICY = 'attempts = 9 if role == "expression" else 2'

_CUE_STOPWORDS = {
    "about", "after", "again", "also", "because", "been", "before", "being", "between",
    "could", "does", "doing", "each", "from", "have", "here", "into", "just", "more",
    "most", "much", "only", "other", "ourselves", "should", "some", "still", "than", "that",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "very",
    "want", "what", "when", "where", "whether", "which", "while", "with", "without", "would",
    "your", "yourselves",
}


def _semantic_cues(value: object, limit: int = 6) -> list[str]:
    cues: list[str] = []
    for word in re.findall(r"[a-z0-9']+", str(value or "").lower()):
        if len(word) < 4 or word in _CUE_STOPWORDS or word in cues:
            continue
        cues.append(word)
        if len(cues) >= limit:
            break
    return cues


def _rewrite_prompt_data(prompt: str, transform) -> str:
    marker = "\nSITUATION_DATA\n"
    end_marker = "\nRETURN_STRUCTURED_DATA_ONLY\n"
    if marker not in prompt or end_marker not in prompt:
        return prompt
    before, rest = prompt.split(marker, 1)
    raw, after = rest.split(end_marker, 1)
    try:
        data = json.loads(raw)
    except Exception:
        return prompt
    if not isinstance(data, dict):
        return prompt
    transformed = transform(data)
    return before + marker + json.dumps(transformed, ensure_ascii=False, separators=(",", ":")) + end_marker + after


def _mask_thought_transcript(prompt: str) -> str:
    """Compact older transcript text for Llama thought only.

    The latest event remains verbatim and the structured social observation is
    preserved. Only older context messages are reduced to speaker/target plus
    sparse semantic cues, removing redundant tokens before two concurrent
    deliberation calls reach the 1B model.
    """
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            compact = []
            for item in context:
                if isinstance(item, dict):
                    compact.append({
                        "speaker": item.get("speaker"),
                        "target": item.get("target"),
                        "cues": _semantic_cues(item.get("text"), limit=5),
                    })
                else:
                    compact.append({"speaker": None, "target": None, "cues": _semantic_cues(item, limit=5)})
            data["context"] = compact
        return data

    return _rewrite_prompt_data(prompt, transform)


def _mask_expression_transcript(prompt: str) -> str:
    """Hide copyable sentence text from expression generation only.

    Validation still receives the original compact payload, so anti-copy checks
    compare generated speech with the exact transcript. Thought and
    comprehension still receive the real conversation. Expression keeps
    speaker/target information, sparse semantic cues, its own intent, topic,
    identity, and relationship context.
    """
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            masked = []
            for item in context:
                if isinstance(item, dict):
                    masked.append({
                        "speaker": item.get("speaker"),
                        "target": item.get("target"),
                        "cues": _semantic_cues(item.get("text")),
                    })
                else:
                    masked.append({"speaker": None, "target": None, "cues": _semantic_cues(item)})
            data["context"] = masked

        event = data.get("event")
        if isinstance(event, dict):
            data["event"] = {
                "speaker": event.get("speaker"),
                "target": event.get("target"),
                "cues": _semantic_cues(event.get("text")),
            }
        elif event:
            data["event"] = {"speaker": None, "target": None, "cues": _semantic_cues(event)}
        return data

    return _rewrite_prompt_data(prompt, transform)


def _remember_rejected(autonomy, utterance: object) -> None:
    text = str(utterance or "").strip()
    rejected = getattr(autonomy, "_production_rejected_wordings", [])
    if text and text not in rejected:
        rejected.append(text)
    autonomy._production_rejected_wordings = rejected[-3:]


def _llama_model_run(role: str, payload: dict, timeout: int = 30):
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    import room_private_model_autonomy as autonomy

    autonomy._production_rejected_wordings = []

    if not hasattr(autonomy, "_production_original_request_autonomy"):
        autonomy._production_original_request_autonomy = autonomy._request_autonomy

        def _production_request_autonomy(model_url, prompt, request_role, temperature, request_timeout,
                                         self_entity=None, attempt=0, intent=None):
            if request_role == "thought":
                prompt = _mask_thought_transcript(prompt)
            elif request_role == "expression":
                prompt = _mask_expression_transcript(prompt)
            rejected = [
                str(item or "").strip()
                for item in getattr(autonomy, "_production_rejected_wordings", [])
                if str(item or "").strip()
            ]
            if request_role == "expression" and attempt > 0 and rejected:
                prompt += (
                    "\nREJECTED_WORDING\n"
                    "Previous attempts copied recent speech too closely. Rewrite from scratch while preserving "
                    "the same internal intent. Do not repeat, lightly edit, or closely paraphrase any rejected "
                    "sentence below. Use a different sentence structure and different phrasing.\n"
                    + "\n".join(f"- {item}" for item in rejected[-3:])
                    + "\nEND_REJECTED_WORDING\n"
                )
            return autonomy._production_original_request_autonomy(
                model_url, prompt, request_role, temperature, request_timeout,
                self_entity, attempt, intent
            )

        autonomy._request_autonomy = _production_request_autonomy

    if not hasattr(autonomy, "_production_original_context_echo"):
        autonomy._production_original_context_echo = autonomy._has_context_echo

        def _production_context_echo(utterance, compact, n=5):
            matched = autonomy._production_original_context_echo(utterance, compact, n=max(8, int(n)))
            if matched:
                _remember_rejected(autonomy, utterance)
            return matched

        autonomy._has_context_echo = _production_context_echo

    if not hasattr(autonomy.base, "_production_original_too_similar"):
        autonomy.base._production_original_too_similar = autonomy.base._too_similar_to_context

        def _production_too_similar(utterance, compact):
            matched = autonomy.base._production_original_too_similar(utterance, compact)
            if matched:
                _remember_rejected(autonomy, utterance)
            return matched

        autonomy.base._too_similar_to_context = _production_too_similar

    return autonomy.run(role, payload, timeout=timeout)


if os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":
    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run


for _name in dir(_legacy):
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = getattr(_legacy, _name)


def main():
    if "commit" in globals():
        _legacy.commit = globals()["commit"]
    return _legacy.main()


if __name__ == "__main__":
    main()
