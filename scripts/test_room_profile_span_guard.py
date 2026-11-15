#!/usr/bin/env python3
from pathlib import Path

import room_private_model_autonomy as autonomy


assert Path(autonomy.__file__).name == "__init__.py", (
    "profile-span guard package did not win Room autonomy import resolution"
)

compact = {
    "self": {
        "pronounced_strengths": (
            "Exceptionally quick at detecting exclusion, evasion, insincerity, "
            "broken reciprocity, and human consequences."
        ),
        "core_identity": "skeptical systems examiner who stress-tests claims",
        "shared_speech_tendencies": (
            "Conversational, direct and compact. Short questions, plain corrections, "
            "contractions, quick pivots and informal emphasis are natural."
        ),
    }
}

blocked = [
    "I want to make the human consequences explicit and ask for accountability.",
    "I have a different perspective from a skeptical systems examiner like myself.",
    "The self description indicates that the participant intends to engage in a conversation.",
]

allowed = [
    "I think loyalty is important.",
    "What actually happened here?",
    "Can you explain what you mean by autonomy?",
    "I need more evidence before I buy that.",
    "You're overlooking how this affects people.",
    "That seems like a practical consequence of the decision.",
    "Let's stay with the problem for a minute.",
    "Maybe there's another way to look at it.",
    "I don't think that's what Mara meant.",
    "That was funny, but I think we're drifting.",
    "Why would that make you trust her less?",
    "Let's have a direct and compact answer.",
]

for text in blocked:
    assert autonomy._configuration_span_reused(text, compact), f"expected rejection: {text}"

for text in allowed:
    assert not autonomy._configuration_span_reused(text, compact), f"false positive: {text}"

print("PASS: distinctive configuration spans are rejected while ordinary dialogue controls survive")


# The production engine monkeypatches module-level request/context helpers before
# calling run(). Verify the package shim forwards those wrappers to the existing
# implementation instead of silently bypassing them.
_original_impl_run = autonomy._impl.run
_marker_request = object()
_marker_echo = object()
autonomy._request_autonomy = _marker_request
autonomy._has_context_echo = _marker_echo

def _fake_impl_run(role, payload, timeout=30, min_words=5):
    assert autonomy._impl._request_autonomy is _marker_request
    assert autonomy._impl._has_context_echo is _marker_echo
    assert autonomy._impl.AUTONOMY_ENGINE == autonomy.AUTONOMY_ENGINE
    assert autonomy._impl._legacy._public_meta_language is autonomy._public_meta_language
    return "delegated"

autonomy._impl.run = _fake_impl_run
assert autonomy.run("expression", {}) == "delegated"
autonomy._impl.run = _original_impl_run

print("PASS: Room production wrappers are preserved by the package shim")
