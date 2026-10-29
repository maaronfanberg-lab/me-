#!/usr/bin/env python3
"""Regression: short upstream contexts must not erase witnessed public history."""
from __future__ import annotations
import json
from unittest.mock import patch
from room_chat_speech import witnessed_context, messages

def turn(i, speaker, text):
    return {"id": "source-%02d" % i, "speaker": speaker, "text": text}

public = [
    turn(1, "jules", "I found a loose connector beside the greenhouse."),
    turn(2, "owen", "I'll check the pressure gauge."),
    turn(3, "mara", "The timer ran for thirty minutes."),
    turn(4, "sarah", "I noticed dry soil near the north wall."),
    turn(5, "owen", "I checked the pressure gauge and it reads 20 kPa."),
    turn(6, "jules", "I tightened the loose connector."),
    turn(7, "mara", "Water is now reaching the north bed."),
    turn(8, "sarah", "That changes the diagnosis."),
    turn(9, "owen", "The pressure is recovering."),
    turn(10, "jules", "Let's see whether the seedlings recover."),
]
payload = {
    "context": [public[-2], public[-1]],
    "event": turn(11, "allen", "Please tell me what actually changed."),
    "profile": {}, "room_cycle": 36405,
}
with patch("pathlib.Path.read_text", return_value=json.dumps({"conversation": public})):
    history = witnessed_context(payload, "mara")
    rendered = messages(payload, "mara")
assert 8 <= len(history) <= 13, history
assert {"source-%02d" % i for i in range(4, 12)} <= {x["id"] for x in history}
assert "source-01" in {x["id"] for x in history}  # older completed observation
assert history[-1]["speaker"] == "allen"
assert len({x["id"] for x in history}) == len(history)
assert "I tightened the loose connector." in rendered[1]["content"]
assert "I checked the pressure gauge and it reads 20 kPa." in rendered[1]["content"]
assert "Please tell me what actually changed." in rendered[1]["content"]
assert "ONGOING FICTIONAL SITUATION" not in rendered[1]["content"]

# Missing or malformed public data must never suppress the live user event.
with patch("pathlib.Path.read_text", side_effect=OSError("unavailable")):
    fallback = witnessed_context(payload, "mara")
assert [x["id"] for x in fallback] == ["source-09", "source-10", "source-11"]

# When upstream already provides enough public turns, do not reopen feed.json.
full = {"context": public[-8:], "profile": {}}
with patch("pathlib.Path.read_text", side_effect=AssertionError("unnecessary read")):
    already = witnessed_context(full, "sarah")
assert len(already) == 8 and already[-1]["id"] == "source-10"

# Replayed public turns may be duplicated in the upstream context, but must
# not be repeated in the prompt, and unpublished user events retain priority.
with patch("pathlib.Path.read_text", return_value=json.dumps({"conversation": public})):
    dup = witnessed_context(dict(payload, context=[public[-1], public[-1]]), "mara")
assert len({x["id"] for x in dup}) == len(dup)
assert dup[-1]["speaker"] == "allen"

# Live-failure regression: after a Sarah/Owen stretch, Jules and Mara were
# absent from the last eight turns, and Owen kept proposing an already
# completed pressure-gauge inspection. Retain those witnessed sources, not
# imaginary interventions or private cognition.
crowded = [
    turn(1, "mara", "I measured the garden pressure gauge at 20 kPa."),
    turn(2, "jules", "I tightened the garden hose connector."),
]
crowded.extend(
    turn(i, "sarah" if i % 2 else "owen",
         "The garden pressure gauge is low, but the dry beds still need water.")
    for i in range(3, 20)
)
request = turn(20, "allen", "What actually changed in the garden?")
with patch("pathlib.Path.read_text",
           return_value=json.dumps({"conversation": crowded})):
    recalled = witnessed_context({
        "context": crowded[-2:], "event": request, "room_cycle": 36450
    }, "sarah")
assert recalled[-1]["id"] == request["id"]
assert {"mara", "jules", "sarah", "owen", "allen"} <= {
    x["speaker"] for x in recalled
}
assert {"source-01", "source-02"} <= {x["id"] for x in recalled}
assert len(recalled) <= 13 and len({x["id"] for x in recalled}) == len(recalled)
assert [x["id"] for x in recalled][-1] == "source-20"

# A completed action from an unrelated earlier scene must not displace
# evidence in a new scene just because both involved somebody inspecting.
unrelated = [
    turn(1, "owen", "I inspected the concert mixer power cable."),
    turn(2, "jules", "The concert sounded much better."),
]
unrelated.extend(
    turn(i, "sarah" if i % 2 else "mara",
         "The library photograph frame has an unclear date on its label.")
    for i in range(3, 20)
)
with patch("pathlib.Path.read_text",
           return_value=json.dumps({"conversation": unrelated})):
    selected = witnessed_context({
        "context": unrelated[-2:], "event": turn(20,"allen","What date is it?")
    }, "sarah")
assert "source-01" not in {x["id"] for x in selected}
assert selected[-1]["speaker"] == "allen"

print("PASS: bounded source-linked history, completed action recall, dedupe, visitor priority and four-voice retention")
