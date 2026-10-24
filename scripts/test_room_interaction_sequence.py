#!/usr/bin/env python3
"""Small observational probes for conversation-action state.

No LLM, lexical blacklist, forced topic pivot, or assumed shared truth.
"""
from __future__ import annotations

from room_interaction_sequence import interaction_frame


AWAKE = ("sarah", "mara", "owen", "jules")


def turn(id, speaker, text, target="", move="deepen"):
    return {
        "id": id, "speaker": speaker, "text": text,
        "cognition": {"target": target, "move_type": move},
    }


question = turn("q1", "mara", "Sarah, where did the moths go?", "sarah", "deepen")
first = interaction_frame([question], "sarah", AWAKE)
assert first["pending"] and first["pending"][0]["source"] == "q1"
assert interaction_frame([question], "owen", AWAKE)["pending"] == []

# A statement about the same subject is not evidence the specific question was answered.
stray = turn("stray", "owen", "The moths are fascinating creatures.", "jules", "deepen")
assert interaction_frame([question, stray], "sarah", AWAKE)["pending"]

answer = turn("a1", "sarah", "They flew toward the marsh after the storm.", "mara", "answer")
second = interaction_frame([question, answer], "sarah", AWAKE)
assert second["pending"] == []
assert second["recent_uptake"][-1]["reply_source"] == "a1"
assert second["recent_uptake"][-1]["uptake"] == "response_observed_understanding_unverified"

ack = turn("ack1", "mara", "I see, that answers my question.", "sarah", "support")
third = interaction_frame([question, answer, ack], "mara", AWAKE)
assert third["recent_uptake"][-1]["uptake"] == "acknowledged"
assert third["recent_uptake"][-1]["third_source"] == "ack1"

repair = turn("repair1", "mara", "No, that's not what I meant. Where did they land?", "sarah", "repair")
third_repair = interaction_frame([question, answer, repair], "sarah", AWAKE)
assert third_repair["recent_uptake"][-1]["uptake"] == "clarification_requested"
assert third_repair["pending"], "An observed repair question can project a next response"

# Explicit refusal is not a defective turn; it is a socially consequential response.
offer = turn("offer", "jules", "Mara, would you join the experiment?", "mara", "bridge")
decline = turn("decline", "mara", "No thanks, I don't want to join.", "jules", "answer")
f = interaction_frame([offer, decline], "jules", AWAKE)
assert f["recent_uptake"][-1]["uptake"] == "declined"

# Productive lexical reuse is preserved, not filtered or flagged as wrong.
repeat = turn("repeat", "sarah", "The moths flew toward the marsh.", "mara", "deepen")
frame = interaction_frame([question, answer, ack, repeat], "sarah", AWAKE)
assert frame["last_action"]["utterance"] == repeat["text"]
assert "repetition" not in str(frame).lower()

# Observer-local: events said while Jules is absent are not made visible later.
assert interaction_frame([question, answer], "jules", ("sarah", "mara", "owen")) == {}

print("PASS: conditional relevance, candidate uptake, third-position repair, refusal, observer scope")
