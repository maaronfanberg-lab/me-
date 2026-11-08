#!/usr/bin/env python3
"""Concordia-inspired, deterministic Room environment referee.

Agents author their own speech. The referee interprets only published,
attributed first-person actions and updates a persistent fictional world.
It never supplies a line of character dialogue, a motive, or a memory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

PEOPLE = frozenset(("sarah", "mara", "owen", "jules"))
VERSION = 1
FILE = "concordia-world.json"


def cycle_of(turn):
    try:
        return int(str(turn.get("beat_id") or "").rsplit("-", 1)[-1])
    except (TypeError, ValueError):
        return None


_ACTIONS = (
    ("open_window", r"(?:open|opened|push open|pushed open) the window"),
    ("close_window", r"(?:close|closed|shut) the window"),
    ("lamp_on", r"(?:turn|turned|switch|switched) (?:on the lamp|the lamp on)"),
    ("lamp_off", r"(?:turn|turned|switch|switched) (?:off the lamp|the lamp off)"),
    ("fill_kettle", r"(?:fill|filled) the kettle"),
    ("boil_kettle", r"(?:boil|boiled|heat|heated) the kettle"),
    ("pour_tea", r"(?:pour|poured) (?:a cup of tea|tea into a cup)"),
    ("water_plant", r"(?:water|watered) the plant"),
    ("write_notebook", r"(?:write|wrote|scribble|scribbled) (?:a note|something|a page) in the notebook"),
    ("move_chair", r"(?:move|moved|pull|pulled) (?:a|the) chair (?:over )?to the window"),
)


def witnessed_action(speaker, text):
    """Fail-closed recognizer for actually asserted physical acts, not plans."""
    if speaker not in PEOPLE or not isinstance(text, str) or len(text) > 500:
        return None
    match = re.match(r"^\s*I\s+(?:just\s+|now\s+)?", text, re.I)
    if not match or text.strip().endswith("?"):
        return None
    phrase = text[match.end():]
    if re.match(r"(?:will|would|could|should|might|may|want|plan|hope|try|tried|didn't|don't|did not|never|can't|cannot|won't|am going to)\b", phrase, re.I):
        return None
    for name, grammar in _ACTIONS:
        m = re.match(r"(?:" + grammar + r")\b", phrase, re.I)
        if m:
            tail = phrase[m.end():]
            if re.search(r"\b(?:if|would|might|yesterday|earlier|tomorrow|last night|pretend|imagine)\b", tail, re.I):
                return None
            return name
    return None


def premature_result(speaker, text):
    """Prevent the actor from inventing the referee's result in the same turn."""
    return bool(witnessed_action(speaker, text) and re.search(
        r"\b(?:revealed|reveals|discovered|found|turns out|it worked|"
        r"it failed|there (?:is|was|are|were)|I (?:see|saw|noticed))\b", text, re.I))


def initial(cycle):
    return {
        "version": VERSION, "processed_cycle": cycle,
        "objects": {"window": "closed", "lamp": "on", "kettle": "empty",
                    "cups": 0, "plant": "dry", "notebook_pages": 0,
                    "chair": "table", "kettle_heated_at": None,
                    "plant_watered_at": None},
        "recent_actions": [],
    }


def age(world, new_cycle):
    if new_cycle < world["processed_cycle"]:
        raise ValueError("world clock moved backwards")
    things = world["objects"]
    heated = things["kettle_heated_at"]
    if heated is not None and things["kettle"] in ("hot", "warm"):
        passed = new_cycle - heated
        if passed >= 16:
            things["kettle"] = "cold"
        elif passed >= 5:
            things["kettle"] = "warm"
    watered = things["plant_watered_at"]
    if watered is not None and new_cycle - watered >= 90:
        things["plant"] = "dry"
    world["processed_cycle"] = new_cycle


def resolve(world, speaker, action, source_id, cycle):
    """World constraints, not another model's invented character behavior."""
    o = world["objects"]
    if action == "open_window":
        changed = o["window"] != "open"
        o["window"] = "open"
        outcome = "The window is open." if changed else "The window was already open."
    elif action == "close_window":
        changed = o["window"] != "closed"
        o["window"] = "closed"
        outcome = "The window is closed." if changed else "The window was already closed."
    elif action in ("lamp_on", "lamp_off"):
        new = "on" if action == "lamp_on" else "off"
        changed = o["lamp"] != new
        o["lamp"] = new
        outcome = f"The lamp is {new}." if changed else f"The lamp was already {new}."
    elif action == "fill_kettle":
        changed = True
        o["kettle"] = "filled"
        o["kettle_heated_at"] = None
        outcome = "The kettle contains fresh water."
    elif action == "boil_kettle":
        changed = o["kettle"] != "empty"
        if changed:
            o["kettle"] = "hot"
            o["kettle_heated_at"] = cycle
        outcome = "The kettle water is hot." if changed else "The empty kettle cannot boil water."
    elif action == "pour_tea":
        changed = o["kettle"] in ("hot", "warm")
        if changed:
            o["cups"] += 1
            o["kettle"] = "empty"
            o["kettle_heated_at"] = None
        outcome = "A cup of hot water was poured." if changed else "No hot water is ready to pour."
    elif action == "water_plant":
        changed = o["plant"] == "dry"
        o["plant"] = "watered"
        o["plant_watered_at"] = cycle
        outcome = "The plant's soil is moist." if changed else "The plant's soil was already moist."
    elif action == "write_notebook":
        changed = True
        o["notebook_pages"] += 1
        outcome = "One additional page is written in the shared notebook; its contents were not specified."
    elif action == "move_chair":
        changed = o["chair"] != "window"
        o["chair"] = "window"
        outcome = "The chair is by the window." if changed else "The chair was already by the window."
    else:
        raise ValueError("unrecognized physical action")
    event = {"source_id": source_id, "source_cycle": cycle,
             "actor": speaker, "action": action, "changed": changed,
             "outcome": outcome}
    world["recent_actions"] = (world["recent_actions"] + [event])[-12:]
    return event


def update(world, published, through_cycle):
    """Replay strictly new, attributed, already-committed public turns."""
    if not isinstance(published, list):
        raise ValueError("missing published conversation")
    seen = set()
    previous = world["processed_cycle"]
    new = []
    for turn in published:
        if not isinstance(turn, dict):
            continue
        cycle = cycle_of(turn)
        if cycle is None or cycle <= previous or cycle > through_cycle:
            continue
        uid = str(turn.get("id") or "").strip()
        if not uid or uid in seen or not str(turn.get("text") or "").strip():
            raise ValueError("new turn lacks unique public evidence")
        seen.add(uid)
        new.append((cycle, uid, turn))
    new.sort()
    if through_cycle > previous and (not new or new[0][0] != previous + 1
                                     or new[-1][0] != through_cycle):
        raise ValueError("missing intervening public turn; refuse to invent world updates")
    if len({item[0] for item in new}) != len(new):
        raise ValueError("ambiguous public cycle")
    for cycle, uid, turn in new:
        age(world, cycle)
        actor = str(turn.get("speaker") or "").strip().lower()
        action = witnessed_action(actor, turn.get("text"))
        if action:
            resolve(world, actor, action, uid, cycle)
    return world


def sync(root, live):
    """Called only after a committed Room beat, before feed publication."""
    if os.environ.get("ROOM_CONCORDIA_WORLD_ENABLE") != "1":
        return None
    root = Path(root)
    path = root / "room" / FILE
    if not isinstance(live, dict):
        raise ValueError("missing public Room state")
    cycle = int((live.get("state") or {}).get("cycle"))
    if path.exists():
        world = json.loads(path.read_text())
        if world.get("version") != VERSION or not isinstance(world.get("objects"), dict):
            raise ValueError("incompatible world snapshot; refuse reset")
    else:
        world = initial(cycle - 1)
    if cycle < world["processed_cycle"]:
        raise ValueError("stale published state")
    if cycle == world["processed_cycle"]:
        return world
    update(world, live.get("conversation"), cycle)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(world, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)
    return world


def notice(entity, root):
    """Independent environmental observation, never fake dialogue or motive."""
    if (os.environ.get("ROOM_CONCORDIA_WORLD_ENABLE") != "1" or
            entity not in PEOPLE):
        return ""
    root = Path(root)
    try:
        w = json.loads((root / "room" / FILE).read_text())
        state = json.loads((root / "room" / "state.json").read_text())
        if w.get("version") != VERSION or w["processed_cycle"] != state["cycle"]:
            return ""
        o = w["objects"]
        pieces = [
            "FICTIONAL ROOM ENVIRONMENT (not character speech): A shared studio has a window, "
            "a lamp, a kettle, a plant, a notebook and a chair.",
            f"Current physical state: window {o['window']}; lamp {o['lamp']}; "
            f"kettle {o['kettle']}; prepared cups {o['cups']}; plant soil {o['plant']}; "
            f"notebook pages {o['notebook_pages']}; chair by {o['chair']}.",
        ]
        recent = w.get("recent_actions") or []
        if recent and w["processed_cycle"] - recent[-1]["source_cycle"] <= 3:
            item = recent[-1]
            pieces.append(f"Verified outcome after {item['actor']}'s public action "
                          f"(source {item['source_id']}): {item['outcome']}")
        pieces.append("These are optional physical circumstances, not an assigned topic or task. "
                      "You can converse, ignore the objects, or act voluntarily. "
                      "Only your actual published first-person action changes this environment; "
                      "wait for a later observation before claiming its outcome.")
        return " ".join(pieces)
    except (OSError, ValueError, KeyError, TypeError):
        return ""
