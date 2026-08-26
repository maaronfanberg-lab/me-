#!/usr/bin/env python3
from __future__ import annotations

"""Select the lean autonomy-v2 model path only for the Llama Room brain.

The complete pre-Llama production wrapper is preserved in
room_engine_v5_legacy.py. Qwen fallback uses that code unchanged. When the
workflow has positively identified Llama 3.2 as the active brain, only the
language-model call boundary is replaced with the canary-tested autonomy-v2
adapter; the Room engine, Allen routing, state transitions, and commit behavior
remain the preserved production implementation.
"""

import os

import room_engine_v5_legacy as _legacy

LEGACY_RETRY_POLICY = 'attempts = 9 if role == "expression" else 2'


def _llama_model_run(role: str, payload: dict, timeout: int = 30):
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    import room_private_model_autonomy as _autonomy

    # Keep the strict similarity detector. When it rejects copied wording,
    # accumulate every rejected variant from this model call so later attempts
    # must genuinely rewrite rather than deleting or swapping one token.
    _autonomy._production_rejected_wordings = []

    if not hasattr(_autonomy, "_production_original_request_autonomy"):
        _autonomy._production_original_request_autonomy = _autonomy._request_autonomy

        def _production_request_autonomy(model_url, prompt, request_role, temperature, request_timeout,
                                         self_entity=None, attempt=0, intent=None):
            rejected = [
                str(item or "").strip()
                for item in getattr(_autonomy, "_production_rejected_wordings", [])
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
            return _autonomy._production_original_request_autonomy(
                model_url, prompt, request_role, temperature, request_timeout,
                self_entity, attempt, intent
            )

        _autonomy._request_autonomy = _production_request_autonomy

    if not hasattr(_autonomy, "_production_original_context_echo"):
        _autonomy._production_original_context_echo = _autonomy._has_context_echo

        def _production_context_echo(utterance, compact, n=5):
            matched = _autonomy._production_original_context_echo(
                utterance, compact, n=max(8, int(n))
            )
            if matched:
                print(f"duplicate-detector=phrase utterance={utterance!r}", flush=True)
            return matched

        _autonomy._has_context_echo = _production_context_echo

    if not hasattr(_autonomy.base, "_production_original_too_similar"):
        _autonomy.base._production_original_too_similar = _autonomy.base._too_similar_to_context

        def _production_too_similar(utterance, compact):
            matched = _autonomy.base._production_original_too_similar(utterance, compact)
            if matched:
                text = str(utterance or "").strip()
                rejected = getattr(_autonomy, "_production_rejected_wordings", [])
                if text and text not in rejected:
                    rejected.append(text)
                _autonomy._production_rejected_wordings = rejected[-3:]
                print(f"duplicate-detector=similarity utterance={utterance!r}", flush=True)
            return matched

        _autonomy.base._too_similar_to_context = _production_too_similar

    return _autonomy.run(role, payload, timeout=timeout)


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


# Branch-only probe trigger. No runtime effect.
_PROBE_TRIGGER = 5

if __name__ == "__main__":
    main()
