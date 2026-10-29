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
assert len(history) == 8, history
assert [x["id"] for x in history] == ["source-%02d" % i for i in range(4, 12)]
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

print("PASS: bounded source-linked history, completed action recall, dedupe, and visitor priority")
