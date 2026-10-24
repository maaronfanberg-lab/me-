"""A bounded, evidence-labelled projection of public conversational actions.

Conversation Analysis asks what a contribution makes relevant next, not whether
a sentence has appeared before. This module does not ban words, force novelty,
change topic, or treat an observed reply as proof of shared understanding.
It can only inspect turns the particular character actually witnessed.
"""
from __future__ import annotations

import re

MAX_SEQUENCE_VIEW = 32
_REPAIR = re.compile(
    r"\b(?:i meant|what i meant|that's not what i|not what i meant|"
    r"did you mean|could you clarify|sorry,? i misunderstood|i was wrong)\b", re.I
)
_ACK = re.compile(
    r"\b(?:i see|got it|that answers|thanks,? that|okay,? now i|"
    r"yes,? exactly|right,? that's what)\b", re.I
)
_DECLINE = re.compile(
    r"\b(?:no thanks|i (?:don't|do not) want|i (?:won't|will not)|"
    r"not interested|i decline)\b", re.I
)


def _turn(item, allowed):
    if not isinstance(item, dict):
        return None
    speaker = str(item.get("speaker") or "").lower()
    content = str(item.get("text") or "").strip()
    if speaker not in allowed or not content:
        return None
    cognition = item.get("cognition") if isinstance(item.get("cognition"), dict) else {}
    return {
        "source": str(item.get("id") or ""),
        "speaker": speaker,
        "recipient": str(cognition.get("target") or item.get("target") or "").lower(),
        "action": str(cognition.get("move_type") or item.get("move") or "").lower(),
        "utterance": content[:220],
    }


def _project(turn):
    """An observable candidate for action, never privileged access to intent."""
    if _REPAIR.search(turn["utterance"]):
        return "repair"
    if "?" in turn["utterance"]:
        return "question"
    if turn["action"] in {"disagree", "repair"}:
        return "disagreement" if turn["action"] == "disagree" else "repair"
    if turn["action"] in {"bridge", "support", "disclose"}:
        return turn["action"]
    return "statement"


def _reply_to(turn, proposal):
    if turn["speaker"] == proposal["speaker"]:
        return False
    if proposal["recipient"] and turn["speaker"] != proposal["recipient"]:
        return False
    # A directed answer or annotated answer is potential uptake, never
    # proof of comprehension. A new unrelated group turn is not an answer.
    return (
        turn["recipient"] == proposal["speaker"]
        or turn["action"] in {"answer", "repair", "disagree", "support"}
        or (not proposal["recipient"] and turn["action"] == "answer")
    )


def interaction_frame(encounters, entity, awake):
    """Render question/response/third-position evidence for one participant.

    Strictly avoids inferring hidden beliefs or resolving an action by timer.
    """
    permitted = set(awake) | {"allen"}
    if entity not in permitted:
        return {}
    observed = [_turn(m, permitted) for m in list(encounters or [])[-MAX_SEQUENCE_VIEW:]]
    observed = [t for t in observed if t is not None]
    if not observed:
        return {
            "last_action": None, "pending": [], "recent_uptake": [],
            "evidence": "observed_public_turns_only",
        }
    pending, uptake = [], []
    for index, event in enumerate(observed):
        if "?" not in event["utterance"]:
            continue
        if _project(event) not in {"question", "repair"}:
            continue
        replies = [(j, other) for j, other in enumerate(observed[index + 1:], index + 1)
                   if _reply_to(other, event)]
        reply_index, reply = replies[0] if replies else (None, None)
        entry = {
            "source": event["source"],
            "speaker": event["speaker"],
            "recipient": event["recipient"] or "group",
            "question": event["utterance"],
        }
        if reply is None:
            if event["recipient"] in ("", entity) or event["speaker"] == entity:
                pending.append(entry)
            continue
        followups = [
            later for later in observed[reply_index + 1:reply_index + 4]
            if later["speaker"] == event["speaker"]
        ]
        third = next(
            (later for later in followups
             if _REPAIR.search(later["utterance"]) or _ACK.search(later["utterance"])), None
        )
        entry.update({
            "reply_source": reply["source"],
            "reply_speaker": reply["speaker"],
            "reply": reply["utterance"],
            "uptake": (
                "clarification_requested" if third and _REPAIR.search(third["utterance"])
                else "acknowledged" if third
                else "declined" if _DECLINE.search(reply["utterance"])
                else "response_observed_understanding_unverified"
            ),
        })
        if third:
            entry["third_source"] = third["source"]
        if (event["speaker"] == entity or reply["speaker"] == entity
                or event["recipient"] == entity):
            uptake.append(entry)
    latest = observed[-1]
    return {
        "last_action": {**latest, "kind": _project(latest)},
        "pending": pending[-3:],
        "recent_uptake": uptake[-2:],
        "evidence": "provisional_inference_from_observed_public_turns",
    }
