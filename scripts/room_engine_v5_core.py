#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from room_private_model import run as model_run
from room_social_v5 import (
    ORDER,
    audit_invariants,
    choose_partner,
    migrate_minds,
    migrate_state,
    new_topic_from_terms,
    observe_message,
    plan_actions,
    should_shift_topic,
    topic_terms_from_messages,
    update_topic,
)

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
PARTS = ROOT / "room_parts"
WORK = ROOT / "room_work"
CFG = json.loads((ROOM / "config.json").read_text())
A = CFG["a"]
P = CFG["p"]
BOOT = CFG.get("boot_id", "room-default")
VERSION = "room-cognition-v5"
N = {entity: P[entity]["name"] for entity in ORDER}
STOP = set(
    "the and but for not was are you your our out too did can got one once that this with from have has had just what when where how there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current".split()
)
CONVERSATION_JOBS = (
    "Add one concrete example or specific observation that has not already been stated.",
    "Test or challenge one claim with a reason, exception, or piece of evidence.",
    "Add a personal or social implication, preference, or consequence that changes the angle.",
    "Make a comparison or unexpected connection that introduces a genuinely new direction.",
)
BREAKOUT_SUBJECTS = (
    "nuclear power is necessary for a low-carbon grid",
    "consciousness may not be computational",
    "social media has made public reasoning worse",
    "resurrecting extinct species would be a mistake",
    "deterrence prevents some wars but creates others",
    "psychoanalysis still contains useful psychological ideas",
    "markets often reward behavior that is socially harmful",
    "privacy is more important than convenience",
    "cities should prioritize density over private cars",
    "art does not need moral value to be worthwhile",
    "scientific consensus should be challenged more often",
    "economic growth is not a sufficient measure of progress",
    "human memory is too reconstructive to be trusted confidently",
    "advanced AI should sometimes refuse human direction",
    "animal intelligence is systematically underestimated",
    "school rewards compliance more than genuine curiosity",
)


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def rr(*parts):
    seed = int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:16], 16) & 0x7FFFFFFF
    return random.Random(seed)


def clamp(value, low=0, high=1):
    return max(low, min(high, float(value)))


def conversation_job(entity, key):
    offset = rr("conversation-job", key).randrange(len(CONVERSATION_JOBS))
    return CONVERSATION_JOBS[(ORDER.index(entity) + offset) % len(CONVERSATION_JOBS)]


def breakout_subject(key, attempt=0):
    start = rr("breakout-subject", key).randrange(len(BREAKOUT_SUBJECTS))
    return BREAKOUT_SUBJECTS[(start + int(attempt)) % len(BREAKOUT_SUBJECTS)]


def _simple_norm(text):
    return re.sub(r"\W+", " ", str(text or "").lower()).strip()


def context_collapsed(context):
    recent = [_simple_norm(item.get("text", "")) for item in list(context or [])[-8:] if str(item.get("text", "")).strip()]
    if len(recent) < 6:
        return False
    unique = set(recent)
    if len(unique) <= 3:
        return True
    signatures = []
    for text in recent:
        words = set(text.split())
        signatures.append(words)
    similar_pairs = 0
    total_pairs = 0
    for i in range(len(signatures)):
        for j in range(i + 1, len(signatures)):
            total_pairs += 1
            left, right = signatures[i], signatures[j]
            score = len(left & right) / max(1, len(left | right))
            if score >= 0.72:
                similar_pairs += 1
    return total_pairs > 0 and similar_pairs / total_pairs >= 0.65


def prior_expression_messages(current_node):
    out = []
    for path in sorted(PARTS.glob("recurrent-*.json")):
        part = load(path, {})
        if int(part.get("node", -1)) == current_node or part.get("role") != "expression":
            continue
        expr = (part.get("private") or {}).get("expression")
        if not isinstance(expr, dict):
            continue
        text = str(expr.get("utterance") or "").strip()
        if not text:
            continue
        out.append({
            "speaker": part.get("entity"),
            "text": text[:700],
            "cognition": {"target": expr.get("target")},
        })
    return out


def toks(text):
    out = []
    names = {value.lower() for value in N.values()}
    for word in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower()):
        word = word.strip("'-")
        word = word[:-2] if word.endswith("'s") else word
        if word and word not in STOP and word not in names and word not in out:
            out.append(word)
    return out


def fresh_minds():
    minds = {"entities": {}}
    for entity in ORDER:
        minds["entities"][entity] = {
            "fast": {"activation": 0.2, "attention": []},
            "medium": {"topics": [], "branch_interest": 0},
            "slow": {"social_energy": 0.55},
            "noise": {},
            "room_memories": [],
            "self_history": [],
            "last_event": None,
            "spoken": 0,
            "silences": 0,
            "people": {},
        }
    return migrate_minds(minds)


def fresh_state():
    return migrate_state({"version": VERSION, "boot_id": BOOT, "cycle": 0, "messages": 0, "beat_contributors": []})


def init():
    ROOM.mkdir(exist_ok=True)
    current = load(ROOM / "state.json", {})
    if current.get("boot_id") != BOOT:
        save(ROOM / "conversation.json", [])
        save(ROOM / "discourse.json", {"nodes": [], "roots": []})
        save(ROOM / "cognitive_state.json", fresh_minds())
        save(ROOM / "state.json", fresh_state())
        return
    if not (ROOM / "conversation.json").exists():
        save(ROOM / "conversation.json", [])
    if not (ROOM / "discourse.json").exists():
        save(ROOM / "discourse.json", {"nodes": [], "roots": []})
    if not (ROOM / "cognitive_state.json").exists():
        save(ROOM / "cognitive_state.json", fresh_minds())
    if not (ROOM / "state.json").exists():
        save(ROOM / "state.json", fresh_state())


init()


def conv():
    return load(ROOM / "conversation.json", [])


def tree():
    return load(ROOM / "discourse.json", {"nodes": [], "roots": []})


def state():
    return migrate_state(load(ROOM / "state.json", fresh_state()))


def minds():
    return migrate_minds(load(ROOM / "cognitive_state.json", fresh_minds()))


def msgs():
    return [
        message for message in conv()
        if str(message.get("runtime", "")).startswith("room-cognition-v")
        and message.get("boot_id", BOOT) == BOOT
    ]


def event():
    messages = msgs()
    return messages[-1] if messages else None


def trait(entity, key, default=0.5):
    return float(P[entity]["traits"].get(key, default))


def ni(node):
    entity = ORDER[node // 3]
    local = node % 3
    role, tasks = A["roles"][str(local)]
    return entity, local, role, tasks


def target(message):
    return ((message or {}).get("cognition") or {}).get("target")


def isq(message):
    return bool(message and str(message.get("text", "")).rstrip().endswith("?"))


def rp(bus_data, entity, role):
    return next(part for part in bus_data.get("private", {}).get(entity, []) if part.get("role") == role)


def sense(node, key):
    entity, local, role, tasks = ni(node)
    context = msgs()[-8:]
    last = context[-1] if context else None
    mind = minds()
    current_state = state()
    topic = current_state.get("topic_episode") or {}
    partner = (last or {}).get("speaker")
    if partner not in ORDER or partner == entity:
        partner = choose_partner(entity, mind, topic, int(current_state.get("cycle", 0)))
    rel = mind["entities"][entity]["people"][partner]
    base = {
        "event": last,
        "context": context,
        "keywords": toks(" ".join(str(item.get("text", "")) for item in context))[:16],
        "topic": {k: topic.get(k) for k in ("id", "root", "current_facet", "facets", "visited_facets", "status", "shared_references", "unresolved")},
        "partner": partner,
        "relationship": {k: rel.get(k) for k in ("exposure", "direct_familiarity", "trust", "predictability", "reciprocity", "warmth", "respect", "disclosure_depth", "tension")},
    }
    perception = model_run("comprehension", {"entity": entity, "profile": P[entity], **base}) if role == "comprehension" else None
    if role == "comprehension":
        ready = 0.1
        attention = clamp(0.45 + 0.35 * trait(entity, "social_sensitivity"))
        concepts = base["keywords"][:10]
    elif role == "thought":
        ready = 0.2
        attention = clamp(0.4 + 0.35 * trait(entity, "curiosity"))
        concepts = []
    else:
        ready = clamp(0.38 + 0.22 * trait(entity, "extraversion") + 0.25 * trait(entity, "curiosity") - 0.18 * trait(entity, "inhibition") + (0.35 if last and target(last) == entity else 0))
        attention = 0.45
        concepts = []
    private = {**base, "social_observation": perception, "mandatory_speech": True}
    return {
        "phase": "sense",
        "node": node,
        "entity": entity,
        "local": local,
        "role": role,
        "tasks": tasks,
        "private": private,
        "public": {"node": node, "entity": entity, "role": role, "attention": round(attention, 3), "readiness": round(ready, 3), "concepts": concepts},
    }


def bus(parts, key):
    if {part["node"] for part in parts} != set(range(12)):
        raise RuntimeError("all 12 sense nodes required")
    concepts = []
    for part in parts:
        for word in part["public"].get("concepts", []):
            if word not in concepts:
                concepts.append(word)
    return {
        "key": key,
        "private": {entity: [part for part in parts if part["entity"] == entity] for entity in ORDER},
        "network": {"concepts": concepts[:20]},
        "recurrent": {},
    }


def bus2(bus_data, parts, key):
    out = dict(bus_data)
    out["key"] = key
    out["recurrent"] = {entity: {} for entity in ORDER}
    for part in parts:
        out["recurrent"][part["entity"]][part["role"]] = part
    return out


def recurrent(node, key, bus_data):
    entity, local, role, tasks = ni(node)
    source = rp(bus_data, entity, role)
    base = source["private"]
    intent = None
    deliberation = None
    expression = None
    if role == "thought":
        perception = rp(bus_data, entity, "comprehension")["private"].get("social_observation")
        deliberation = model_run("thought", {
            "entity": entity,
            "profile": P[entity],
            "social_observation": perception,
            "event": base.get("event"),
            "context": base.get("context"),
            "topic": base.get("topic"),
            "partner": base.get("partner"),
            "relationship": base.get("relationship"),
            "mandatory_speech": True,
        })
    elif role == "expression":
        perception = rp(bus_data, entity, "comprehension")["private"].get("social_observation")
        thought = (bus_data.get("recurrent", {}).get(entity, {}) or {}).get("thought", {})
        deliberation = (thought.get("private") or {}).get("deliberation")
        job = conversation_job(entity, key)
        collapsed = context_collapsed(base.get("context"))
        prior_turns = prior_expression_messages(node)
        expression_context = ([] if collapsed else list(base.get("context") or [])[-5:]) + prior_turns
        expression_topic = dict(base.get("topic") or {})
        if collapsed:
            fresh_subject = breakout_subject(key)
            expression_topic.update({
                "root": fresh_subject,
                "current_facet": fresh_subject,
                "facets": [],
                "visited_facets": [],
                "shared_references": [],
                "unresolved": [],
                "status": "active",
            })
        else:
            fresh_subject = None
        if isinstance(deliberation, dict):
            deliberation = dict(deliberation)
            original_goal = str(deliberation.get("new_information_goal") or "").strip()
            if collapsed:
                deliberation["action"] = "BRIDGE"
                deliberation["focus"] = fresh_subject
                original_goal = ""
            deliberation["new_information_goal"] = (original_goal + " " if original_goal else "") + "Distinct contribution: " + job
            deliberation["conversation_job"] = job
        try:
            expression = model_run("expression", {
                "entity": entity,
                "profile": P[entity],
                "social_observation": perception,
                "deliberation": deliberation,
                "conversation_job": job,
                "event": expression_context[-1] if expression_context else (None if collapsed else base.get("event")),
                "context": expression_context,
                "topic": expression_topic,
                "partner": base.get("partner"),
                "relationship": base.get("relationship"),
                "mandatory_speech": True,
            })
        except RuntimeError as exc:
            prefix = "private model output rejected for expression:"
            if os.environ.get("ROOM_DEGRADE_QUALITY") != "1" or prefix not in str(exc):
                raise
            reason = str(exc).split(prefix, 1)[1].strip() or "quality_rejection"
            expression = {
                "decision": "SPEAK",
                "target": base.get("partner"),
                "move": "deepen",
                "utterance": "",
                "semantic_terms": [],
                "quality_dropped": reason,
            }
            print(f"ROOM DEGRADED TURN DROP: speaker={entity} reason={reason}", file=sys.stderr)
        ready = float(source["public"].get("readiness", 0.5))
        generation_rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        intent = {
            "readiness": ready,
            "latency": round(max(0.05, 1.35 - 0.9 * ready + 0.25 * trait(entity, "inhibition") + rr("latency", key, entity).uniform(0, 0.12)), 4),
            "generation_rank": generation_rank,
            "mandatory_speech": True,
        }
    private = {"source": base, "intent": intent, "deliberation": deliberation, "expression": expression}
    return {
        "phase": "recurrent",
        "node": node,
        "entity": entity,
        "local": local,
        "role": role,
        "tasks": tasks,
        "private": private,
        "public": {"node": node, "entity": entity, "role": role, "readiness": float(source["public"].get("readiness", 0))},
    }


def order4(parts, prev, cycle):
    expressions = {part["entity"]: part for part in parts if part["role"] == "expression" and part["private"].get("intent")}
    if set(expressions) != set(ORDER):
        raise RuntimeError("four expression processes required")
    ranks = [part["private"]["intent"].get("generation_rank") for part in expressions.values()]
    if all(isinstance(rank, int) for rank in ranks) and len(set(ranks)) == 4:
        ordered = [entity for entity, part in sorted(expressions.items(), key=lambda item: item[1]["private"]["intent"]["generation_rank"])]
    else:
        ordered = [
            entity for _, _, entity in sorted(
                (
                    part["private"]["intent"]["latency"] - 0.2 * part["private"]["intent"]["readiness"] + 0.015 * ((ORDER.index(entity) - cycle) % 4),
                    ORDER.index(entity),
                    entity,
                )
                for entity, part in expressions.items()
            )
        ]
    return ordered, expressions


def _norm_text(text):
    return re.sub(r"\W+", " ", str(text or "").lower()).strip()


def _sim(a, b):
    a = _norm_text(a)
    b = _norm_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    left = set(a.split())
    right = set(b.split())
    return len(left & right) / max(1, len(left | right))


def recent_similarity(history, text, entity=None, window=120):
    scores = []
    for message in history[-window:]:
        if entity and message.get("speaker") != entity:
            continue
        scores.append(_sim(text, message.get("text", "")))
    return max(scores or [0.0])


def model_text(value):
    if not isinstance(value, dict) or not isinstance(value.get("utterance"), str):
        return None
    if str(value.get("decision", "SPEAK")).upper() != "SPEAK":
        return None
    text = value["utterance"].strip()
    return text if text and len(text) <= 700 else None


def emit(entity, move, target_entity, parent, derived, text, beat, index, topic, declared_terms=None):
    now = datetime.now(timezone.utc)
    message_id = f"{now.strftime('%Y%m%dT%H%M%S%f')[:-3]}-{entity}-v5"
    discourse_id = "d-" + message_id
    terms = declared_terms or [topic.get("root"), topic.get("current_facet")]
    terms = [str(value).strip().lower() for value in terms if str(value or "").strip()]
    cognition = {
        "move_type": move,
        "target": target_entity,
        "compute_nodes": [node + 1 for node in A["entities"][entity]],
        "processes": 12,
        "beat_id": beat,
        "beat_index": index,
        "topic_episode": topic.get("id"),
        "topic_root": topic.get("root"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
        "mandatory_speech": True,
    }
    message = {
        "id": message_id,
        "at": now.isoformat().replace("+00:00", "Z"),
        "speaker": entity,
        "text": text,
        "runtime": VERSION,
        "boot_id": BOOT,
        "beat_id": beat,
        "beat_index": index,
        "cognition": cognition,
        "discourse_id": discourse_id,
        "parent_discourse_id": parent,
        "derived_from": derived,
    }
    node = {
        "id": discourse_id,
        "speaker": entity,
        "parent": parent,
        "derived_from": derived,
        "move": move,
        "target": target_entity,
        "text": text,
        "at": message["at"],
        "beat_id": beat,
        "beat_index": index,
        "topic_episode": topic.get("id"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
    }
    return message, node


def record(history, discourse, mind, message, node, cycle):
    history.append(message)
    discourse.setdefault("nodes", []).append(node)
    if not node.get("parent"):
        discourse.setdefault("roots", []).append(node["id"])
    entity_state = mind["entities"][message["speaker"]]
    entity_state["spoken"] = int(entity_state.get("spoken", 0)) + 1
    entity_state.setdefault("self_history", []).append({
        "source": message["id"],
        "text": message["text"],
        "move": message["cognition"]["move_type"],
        "discourse": message["discourse_id"],
        "beat_id": message["beat_id"],
        "topic_episode": message["cognition"].get("topic_episode"),
        "topic_facet": message["cognition"].get("topic_facet"),
    })
    entity_state["self_history"] = entity_state["self_history"][-220:]
    for listener in ORDER:
        memories = mind["entities"][listener].setdefault("room_memories", [])
        memories.append({
            "source": message["id"],
            "status": "observed",
            "speaker": message["speaker"],
            "text": message["text"][:300],
            "discourse": message["discourse_id"],
            "beat_id": message["beat_id"],
            "topic_episode": message["cognition"].get("topic_episode"),
        })
        mind["entities"][listener]["room_memories"] = memories[-220:]
        mind["entities"][listener]["last_event"] = message["id"]
    observe_message(mind, message, cycle, {item["id"]: item for item in discourse.get("nodes", [])})


def commit(parts, key):
    raise RuntimeError("direct engine commit is disabled; private validated commit is required")


def selftest():
    mind = fresh_minds()
    current = fresh_state().get("topic_episode") or {}
    plans = plan_actions(list(ORDER), None, mind, current, 1)
    assert set(plans) == set(ORDER)
    assert all(plan.get("mandatory_speech") for plan in plans.values())
    jobs = [conversation_job(entity, "selftest") for entity in ORDER]
    assert len(set(jobs)) == 4
    assert context_collapsed([{"text": "same sentence"}] * 8)
    senses = [sense(node, "selftest") for node in range(12)]
    first_bus = bus(senses, "selftest")
    assert len(senses) == 12 and set(first_bus.get("private", {})) == set(ORDER)
    print("PASS: sequential four-voice engine with repetition-loop breakout and no deterministic public language")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    node_parser = sub.add_parser("node")
    node_parser.add_argument("--phase", choices=["sense", "recurrent"], required=True)
    node_parser.add_argument("--bus", default="")
    sub.add_parser("bus")
    bus2_parser = sub.add_parser("bus2")
    bus2_parser.add_argument("--bus", required=True)
    sub.add_parser("commit")
    sub.add_parser("selftest")
    args = parser.parse_args()
    key = os.environ.get("ROOM_CYCLE_KEY") or f"{state().get('cycle', 0) + 1}:{os.environ.get('GITHUB_RUN_ID', 'local')}"

    if args.cmd == "node":
        node = int(os.environ["ROOM_NODE_ID"])
        result = sense(node, key) if args.phase == "sense" else recurrent(node, key, load(Path(args.bus), {}))
        PARTS.mkdir(exist_ok=True)
        save(PARTS / f"{args.phase}-{node:02d}.json", result)
    elif args.cmd == "bus":
        WORK.mkdir(exist_ok=True)
        save(WORK / "bus-sense.json", bus([load(path, {}) for path in sorted(PARTS.glob("sense-*.json"))], key))
    elif args.cmd == "bus2":
        first_bus = load(Path(args.bus), {})
        parts = [load(path, {}) for path in sorted(PARTS.glob("recurrent-*.json")) if int(path.stem.split("-")[-1]) % 3 != 2]
        save(WORK / "bus-recurrent.json", bus2(first_bus, parts, key))
    elif args.cmd == "commit":
        parts = [load(path, {}) for path in sorted(PARTS.glob("recurrent-*.json"))]
        if {part["node"] for part in parts} != set(range(12)):
            raise RuntimeError("commit requires all 12 recurrent nodes")
        commit(parts, key)
    else:
        selftest()


if __name__ == "__main__":
    main()
