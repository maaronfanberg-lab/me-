#!/usr/bin/env python3
"""Grounded, persistent lives for the *native* Concordia Room.

Inspired mechanisms are not substituted for Concordia: the real agents and
DeepMind's interrupt-driven Game Master still choose actions and attention.
This module is only an auditable *environment/referee*: it accepts a limited
structured work intention, tracks its execution across otherwise quiet beats,
and reports the real state. It never writes character dialogue or invents
success, discoveries, measurements, or anyone else's internal thoughts.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
import re

PEOPLE = ("sarah", "mara", "owen", "jules")
VERSION = 1
# Concrete affordances, not a topic-of-the-day or a dialogue rotation.
AFFORDANCES = {
    "inspect": {"window", "plant", "bookshelf", "samples", "instruments", "notebook"},
    "measure": {"window", "plant", "samples", "instruments"},
    "write": {"notebook", "board"},
    "test": {"samples", "instruments", "board"},
    "organize": {"bookshelf", "notebook", "table"},
    "prepare": {"table", "instruments", "samples"},
    "rest": {"chair"},
}
DURATION = {"inspect": 2, "measure": 3, "write": 2,
            "test": 3, "organize": 2, "prepare": 2, "rest": 2}
COUNTER = {"inspect": "observations", "measure": "measurements",
           "write": "written_pages", "test": "tests",
           "organize": "organized_sets", "prepare": "prepared_sets"}
STOP = set("about after again also and any are been because being can could does for from have into just more only other over same should some that the their there these they this those through very want were what when where which while will with would your".split())


def initial(config: Mapping, cycle: int) -> dict:
    profiles = config.get("p") or {}
    lives = {}
    for name in PEOPLE:
        psychology = (profiles.get(name) or {}).get("psychology_v2") or {}
        interests = psychology.get("motives") or []
        lives[name] = {
            "goal": str(interests[0])[:140] if interests else "Pursue a personal interest.",
            "goal_source": "existing_character_profile",
            "task": None, "completed": 0, "reflections": [],
        }
    return {
        "version": VERSION, "processed_cycle": int(cycle) - 1,
        "objects": {name: {"observations": 0, "measurements": 0,
                           "written_pages": 0, "tests": 0,
                           "organized_sets": 0, "prepared_sets": 0}
                    for name in sorted({item for items in AFFORDANCES.values()
                                        for item in items})},
        "lives": lives, "events": [],
    }


def validate(world: dict, config: Mapping) -> None:
    if world.get("version") != VERSION:
        raise ValueError("incompatible Room life schema; refusing silent reset")
    if set(world.get("lives") or {}) != set(PEOPLE):
        raise ValueError("Room life snapshot has missing or extra characters")
    if not isinstance(world.get("objects"), dict) or not isinstance(world.get("events"), list):
        raise ValueError("Room life snapshot is incomplete")
    if not isinstance(world.get("processed_cycle"), int):
        raise ValueError("Room life snapshot has invalid clock")


def repair_profile_goals(world: dict, config: Mapping) -> int:
    """Correct earlier live-model placeholder goals, never reset actual work.

    This only repairs invalid *agent_chosen* goal labels from the original
    single-example rollout; it leaves completed work, memories and all
    meaningful existing goals untouched.
    """
    repaired = 0
    for name in PEOPLE:
        life = world["lives"][name]
        if life.get("goal_source") != "agent_chosen":
            continue
        goal = str(life.get("goal") or "").strip()
        boilerplate = {
            "reorganize", "my own specific project", "my personal project",
            "my next task", "something interesting",
        }
        if (goal.lower() not in boilerplate
                and len(goal) >= 24 and len(goal.split()) >= 4):
            continue
        psyche = ((config.get("p") or {}).get(name) or {}).get("psychology_v2") or {}
        motives = psyche.get("motives") or []
        if not motives:
            continue
        life["goal"] = str(motives[0])[:140]
        life["goal_source"] = "existing_character_profile"
        repaired += 1
    return repaired


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", str(text).lower())) - STOP


def retrieve(world: dict, who: str, query: str, *, limit: int = 4) -> list[dict]:
    """Stanford-style relevance + recency + importance, evidence IDs intact."""
    events = world.get("events", [])[-120:]
    if who not in PEOPLE or not events:
        return []
    tokens = tokenize(query)
    latest = max(int(world.get("processed_cycle", 0)), 1)
    ranked = []
    for item in events:
        # Only observations of shared, factual world events, not another
        # agent's unshared private thoughts or private future intentions.
        if item.get("visibility") != "public" and item.get("actor") != who:
            continue
        overlap = len(tokens & tokenize(item.get("description", "")))
        relevance = overlap / max(1, len(tokens))
        elapsed = max(0, latest - int(item.get("cycle", latest)))
        recency = 1.0 / (1.0 + elapsed / 12.0)
        importance = min(5, max(0, int(item.get("importance", 1)))) / 5
        score = 0.50 * relevance + 0.25 * recency + 0.25 * importance
        ranked.append((score, int(item.get("cycle", 0)), item))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [copy.deepcopy(row[2]) for row in ranked[:max(0, limit)]]


def context(world: dict, who: str) -> str:
    """An agent receives its own goal and verified shared state, not an order to speak."""
    if who not in PEOPLE:
        return ""
    life = world["lives"][who]
    active = life.get("task")
    activity = (
        f"Active private task: {active['verb']} {active['object']}"
        f" ({active['progress']}/{active['duration']} verified intervals)."
        if active else "No private task currently underway."
    )
    items = []
    for name, state in sorted(world["objects"].items()):
        evidence = [f"{k}={v}" for k, v in state.items() if v]
        if evidence:
            items.append(f"{name}: {', '.join(evidence)}")
    facts = "; ".join(items[-10:]) or "No completed work has yet changed shared objects."
    history = retrieve(world, who, life["goal"] + " " + str(active or ""), limit=4)
    memories = " | ".join(
        f"[{v['id']}] {v['description']}" for v in history
    ) or "No relevant verified outcomes yet."
    reflections = life.get("reflections", [])[-2:]
    inference = " | ".join(f"TENTATIVE (not verified): {r['text']}" for r in reflections)
    if not inference:
        inference = "No evidence-linked private reflections recorded."
    return (
        f"YOUR PERSISTENT LIFE, distinct from the public conversation:\n"
        f"Your current goal: {life['goal']} (chosen from your profile or your own subsequent work).\n"
        f"{activity}\n"
        f"Verified shared physical state: {facts}\n"
        f"Relevant witnessed outcomes: {memories}\n"
        f"Private interpretations: {inference}\n"
        f"Available independent work verbs/objects: "
        + "; ".join(f"{v}({','.join(sorted(objects))})"
                    for v, objects in AFFORDANCES.items())
        + ". Optional work uses the JSON keys verb and object; choose "
          "actual values independently from the affordances above, and "
          "retain your current personal goal unless you have a meaningful "
          "new one. Work is not completed merely because it is proposed. "
          "A different "
          "actor's intention is not a fact. You may remain quietly occupied."
    )[:4400]


def _event(world: dict, cycle: int, actor: str, kind: str,
           description: str, *, importance: int = 1,
           visibility: str = "public") -> None:
    event_id = f"life-{cycle:07d}-{actor}-{kind}-{len(world['events']):04d}"
    world["events"].append({
        "id": event_id, "cycle": cycle, "actor": actor, "kind": kind,
        "description": description[:280], "importance": importance,
        "visibility": visibility,
    })
    world["events"] = world["events"][-120:]


def _finish(world: dict, cycle: int, actor: str, task: dict) -> None:
    verb, obj = task["verb"], task["object"]
    if verb in COUNTER:
        key = COUNTER[verb]
        world["objects"][obj][key] += 1
        outcome = f"{actor.capitalize()} finished {verb} work at {obj}; one {key.replace('_',' ')} recorded."
    else:
        outcome = f"{actor.capitalize()} completed a rest interval at {obj}."
    _event(world, cycle, actor, "work_completed", outcome, importance=4)
    world["lives"][actor]["completed"] += 1
    world["lives"][actor]["task"] = None


def _literal_work_from_action(action: str, actor: str) -> dict | None:
    """Accept an agent's unambiguous present-tense work, not plans or claims.

    Some local model actions contain a valid scheduler JSON control but omit
    the optional work field. A strict surface form can still be treated as
    the agent's request to begin work. The referee, not the utterance,
    determines whether that work completes on a later beat.
    """
    line = str(action).strip()
    line = re.sub(r"^" + re.escape(actor) + r"\s*:\s*", "", line, flags=re.I)
    if len(line) > 110 or "\n" in line:
        return None
    match = re.fullmatch(
        r"I\s+(?:quietly\s+)?"
        r"(inspect|measure|test|organize|prepare)\s+"
        r"(?:(?:the|my)\s+)?"
        r"(window|plant|bookshelf|samples|instruments|notebook|board|table)"
        r"(?:\s+quietly)?[.!]?",
        line, flags=re.I,
    )
    if match:
        verb, obj = (v.lower() for v in match.groups())
        if obj in AFFORDANCES[verb]:
            return {"verb": verb, "object": obj}
    match = re.fullmatch(
        r"I\s+(?:quietly\s+)?write\s+(?:in|on|at)\s+"
        r"(?:(?:the|my)\s+)?(notebook|board)(?:\s+quietly)?[.!]?",
        line, flags=re.I,
    )
    if match:
        return {"verb": "write", "object": match.group(1).lower()}
    match = re.fullmatch(
        r"I\s+(?:quietly\s+)?rest\s+in\s+"
        r"(?:(?:the|my)\s+)?chair[.!]?",
        line, flags=re.I,
    )
    if match:
        return {"verb": "rest", "object": "chair"}
    return None


def advance(world: dict, config: Mapping, cycle: int, steps: list[dict]) -> dict:
    """Pure deterministic transition: existing commitments progress in quiet.

    The work *choice* is made by a real Concordia agent's structured output.
    The referee cannot write a character line or secretly select a new task.
    A given published Room cycle is applied exactly once.
    """
    validate(world, config)
    old = world["processed_cycle"]
    if cycle <= old:
        if cycle == old:
            return world  # publication retry; never double-apply an action
        raise ValueError("Room life clock moved backwards")
    if cycle != old + 1:
        raise ValueError("Room life cannot skip unpublished cycles")

    # Progress commitments made on PREVIOUS beats, without asking anyone to
    # speak and without assuming a fictional discovery or outcome.
    for name in PEOPLE:
        task = world["lives"][name].get("task")
        if task and task.get("started_cycle", cycle) < cycle:
            task["progress"] = min(task["duration"], int(task["progress"]) + 1)
            if task["progress"] >= task["duration"]:
                _finish(world, cycle, name, task)

    from concordia.components.game_master import interrupt_response_parsing
    for step in steps or []:
        for candidate, output in (step.get("actions") or {}).items():
            name = str(candidate).lower()
            if name not in PEOPLE:
                continue
            _action, metadata = interrupt_response_parsing.extract_json_block(str(output))
            if not isinstance(metadata, dict):
                continue
            work = metadata.get("work")
            # A missing optional work field does not nullify a clearly chosen
            # action. Never infer from wishes, future plans, compound claims,
            # malformed controls, or an explicitly invalid work field.
            if "work" not in metadata:
                work = _literal_work_from_action(_action, str(candidate))
            # A structurally incomplete model response cannot mutate the
            # environment even if it happens to contain a plausible work word.
            if not isinstance(metadata.get("mask"), list) or not isinstance(
                    metadata.get("timer"), dict):
                continue
            if isinstance(work, dict):
                verb = str(work.get("verb") or "").lower().strip()
                obj = str(work.get("object") or "").lower().strip()
                if verb in AFFORDANCES and obj in AFFORDANCES[verb]:
                    life = world["lives"][name]
                    if life.get("task") is None:
                        # Goals are durable projects, not one-word action
                        # commands. A rejected new task must not rewrite them.
                        goal = str(work.get("goal") or "").strip()
                        if (24 <= len(goal) <= 140 and len(goal.split()) >= 4
                                and not re.search(
                                    r"(?i)system prompt|developer message|chain of thought",
                                    goal,
                                )):
                            life["goal"] = goal
                            life["goal_source"] = "agent_chosen"
                        life["task"] = {
                            "verb": verb, "object": obj, "duration": DURATION[verb],
                            "progress": 0, "started_cycle": cycle,
                        }
                        _event(world, cycle, name, "work_started",
                               f"{name.capitalize()} began {verb} at {obj}.",
                               importance=2, visibility="public")
                    # If already busy, a new work request is not magically
                    # completed and cannot silently overwrite a commitment.
            reflection = metadata.get("reflection")
            if isinstance(reflection, dict):
                claim = str(reflection.get("text") or "").strip()
                sources = reflection.get("evidence")
                valid_ids = {e["id"] for e in world["events"][-80:]}
                if (12 <= len(claim) <= 180 and isinstance(sources, list)
                        and 1 <= len(sources) <= 3
                        and all(isinstance(i, str) and i in valid_ids for i in sources)):
                    existing = world["lives"][name]["reflections"]
                    if not any(x.get("text") == claim for x in existing):
                        existing.append({"text": claim, "evidence": sources,
                                         "cycle": cycle, "status": "tentative"})
                        world["lives"][name]["reflections"] = existing[-12:]
    world["processed_cycle"] = cycle
    return world


def public_snapshot(world: dict) -> dict:
    """Bounded metadata for the existing Room feed; NOT synthetic dialogue."""
    return {
        "cycle": world["processed_cycle"],
        "objects": {
            k: {key: n for key, n in v.items() if n}
            for k, v in world["objects"].items()
            if any(v.values())
        },
        "activities": {
            who: {
                "goal": state["goal"], "task": state["task"],
                "completed": state["completed"],
            } for who, state in world["lives"].items()
        },
        "recent_events": [
            {k: v for k, v in e.items() if k in
             {"id", "cycle", "actor", "kind", "description"}}
            for e in world["events"][-8:] if e.get("visibility") == "public"
        ],
    }
