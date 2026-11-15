#!/usr/bin/env python3
"""Measure observable Room behavior without grading eloquence or injecting dialogue.

Usage: python3 scripts/room_behavior_audit.py room/feed.json
       python3 scripts/room_behavior_audit.py before.json after.json
"""
import json
from pathlib import Path
import re
import sys

from room_concordia_world import witnessed_action

PEOPLE = {"sarah", "mara", "owen", "jules"}
ABSTRACT = re.compile(
    r"\b(?:labyrinth|self.referential|recursive|ontolog\w*|"
    r"mirroring|reflections?|feedback loops?|narratives?|"
    r"collective unconscious|emergent behavior|cognitive biases)\b", re.I
)
RESPONSE = re.compile(
    r"\b(?:window|lamp|kettle|plant|notebook|chair|cup|water|"
    r"opened|closed|filled|boiled|poured|wrote|moved|watered)\b", re.I
)


def measure(feed):
    turns = feed.get("conversation") or []
    if not isinstance(turns, list):
        raise ValueError("conversation must be a list")
    turns = [x for x in turns if isinstance(x, dict)
             and str(x.get("speaker", "")).lower() in PEOPLE
             and isinstance(x.get("text"), str) and x["text"].strip()]
    total = len(turns)
    actions = []
    abstract = 0
    object_mentions = 0
    followups = 0
    for index, turn in enumerate(turns):
        text = turn["text"]
        actor = turn["speaker"].lower()
        if ABSTRACT.search(text):
            abstract += 1
        if RESPONSE.search(text):
            object_mentions += 1
        action = witnessed_action(actor, text)
        if action:
            actions.append({"index": index, "speaker": actor, "action": action,
                            "id": turn.get("id")})
            if any(RESPONSE.search(x["text"]) for x in turns[index + 1:index + 4]):
                followups += 1
    # These are proxies, not proof of understanding or natural conversation.
    return {"turns": total, "first_person_actions": len(actions),
            "distinct_action_speakers": len({x["speaker"] for x in actions}),
            "action_followups_within_three_turns": followups,
            "abstract_vocabulary_turn_share": round(abstract / total, 3) if total else None,
            "physical_object_turn_share": round(object_mentions / total, 3) if total else None,
            "actions": actions[-12:]}


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: room_behavior_audit.py before.json [after.json]")
    reports = []
    for name in sys.argv[1:]:
        reports.append({"source": name, **measure(json.loads(Path(name).read_text()))})
    if len(reports) == 2:
        a, b = reports
        reports.append({"comparison": {
            "action_delta": b["first_person_actions"] - a["first_person_actions"],
            "followup_delta": b["action_followups_within_three_turns"] -
                              a["action_followups_within_three_turns"],
            "abstract_share_delta": (round(b["abstract_vocabulary_turn_share"] -
                                           a["abstract_vocabulary_turn_share"], 3)
                                     if a["abstract_vocabulary_turn_share"] is not None
                                     and b["abstract_vocabulary_turn_share"] is not None
                                     else None)}})
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
