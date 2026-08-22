#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import room_engine_v5 as c
from room_semantic_epoch import migrate_files

TARGETS = ("sarah", "mara", "owen", "jules")
PARTICIPANTS = ("allen", "sara")
DEFAULT_PARTICIPANT = "allen"
MAX_TEXT = 700
OBSERVED_IDS_KEY = "participant_observation_ids"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def participant_for(item: dict) -> str:
    speaker = str(item.get("speaker") or DEFAULT_PARTICIPANT).strip().lower()
    return speaker if speaker in PARTICIPANTS else DEFAULT_PARTICIPANT


def infer_target(text: str):
    low = str(text or "").strip().lower()
    for target in TARGETS:
        if re.match(rf"^@?{re.escape(target)}\b", low):
            return target
    return None


def clean_terms(text: str, topic: dict):
    terms = c.toks(text)[:4]
    if not terms:
        for value in (topic.get("current_facet"), topic.get("root")):
            value = str(value or "").strip().lower()
            if value and value not in terms:
                terms.append(value)
    return terms[:4]


def inject(item: dict, history: list, discourse: dict, state: dict):
    source_id = str(item.get("id") or "").strip()
    text = re.sub(r"\s+", " ", str(item.get("text") or "").strip())[:MAX_TEXT]
    participant = participant_for(item)
    if not source_id or not text:
        return None

    digest = hashlib.sha256(source_id.encode()).hexdigest()[:10]
    at = parse_time(item.get("at") or "")
    message_id = f"{at.strftime('%Y%m%dT%H%M%S%f')[:-3]}-{participant}-v5-{digest}"
    if any(message.get("id") == message_id for message in history):
        return source_id

    topic = state.get("topic_episode") or {}
    cycle = int(state.get("cycle", 0)) + 1
    beat = f"beat-{c.BOOT}-{cycle:06d}"
    target = infer_target(text)
    terms = clean_terms(text, topic)
    parent = history[-1].get("discourse_id") if history else None
    move = "follow_up" if text.rstrip().endswith("?") else "deepen"
    discourse_id = "d-" + message_id
    stamp = at.isoformat().replace("+00:00", "Z")

    # External participants are deliberately represented in the same public
    # conversational shape as the Room speakers. There is no human/operator flag
    # in the context the entities receive.
    cognition = {
        "move_type": move,
        "target": target,
        "compute_nodes": [13, 14, 15],
        "processes": 12,
        "beat_id": beat,
        "beat_index": -1,
        "topic_episode": topic.get("id"),
        "topic_root": topic.get("root"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
        "mandatory_speech": True,
    }
    message = {
        "id": message_id,
        "at": stamp,
        "speaker": participant,
        "text": text,
        "runtime": c.VERSION,
        "boot_id": c.BOOT,
        "beat_id": beat,
        "beat_index": -1,
        "cognition": cognition,
        "discourse_id": discourse_id,
        "parent_discourse_id": parent,
        "derived_from": None,
    }
    node = {
        "id": discourse_id,
        "speaker": participant,
        "parent": parent,
        "derived_from": None,
        "move": move,
        "target": target,
        "text": text,
        "at": stamp,
        "beat_id": beat,
        "beat_index": -1,
        "topic_episode": topic.get("id"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
    }
    history.append(message)
    discourse.setdefault("nodes", []).append(node)
    if not parent:
        discourse.setdefault("roots", []).append(discourse_id)
    return source_id


def _message_cycle(message: dict, fallback: int) -> int:
    match = re.search(r"-(\d{6})$", str(message.get("beat_id") or ""))
    return int(match.group(1)) if match else int(fallback)


def _remember_for_listener(mind: dict, listener: str, message: dict) -> None:
    entity = (mind.get("entities") or {}).get(listener)
    if not isinstance(entity, dict):
        return
    source = str(message.get("id") or "")
    participant = str(message.get("speaker") or DEFAULT_PARTICIPANT).lower()
    memories = list(entity.get("room_memories") or [])
    if source and not any(str(item.get("source") or "") == source for item in memories if isinstance(item, dict)):
        cognition = message.get("cognition") or {}
        memories.append({
            "source": source,
            "status": "observed",
            "speaker": participant,
            "text": str(message.get("text") or "")[:300],
            "discourse": message.get("discourse_id"),
            "beat_id": message.get("beat_id"),
            "topic_episode": cognition.get("topic_episode"),
        })
        deduped = {}
        for item in memories:
            if not isinstance(item, dict):
                continue
            key = str(item.get("source") or "")
            if key:
                deduped[key] = item
        entity["room_memories"] = [deduped[key] for key in sorted(deduped)][-220:]
    last_event = str(entity.get("last_event") or "")
    if source and (not last_event or source > last_event):
        entity["last_event"] = source


def observe_participant_history(mind: dict, history: list, discourse: dict, state: dict) -> int:
    """Persist each retained external participant turn into social memory exactly once."""
    if not isinstance(mind, dict):
        return 0
    seen = {str(value) for value in list(mind.get(OBSERVED_IDS_KEY) or []) if str(value)}
    by = {
        str(node.get("id")): node
        for node in list((discourse or {}).get("nodes") or [])
        if isinstance(node, dict) and node.get("id")
    }
    fallback_cycle = int((state or {}).get("cycle", 0))
    observed = 0
    for message in list(history or []):
        if not isinstance(message, dict) or str(message.get("speaker") or "").lower() not in PARTICIPANTS:
            continue
        source = str(message.get("id") or "")
        if not source or source in seen:
            continue
        for listener in TARGETS:
            _remember_for_listener(mind, listener, message)
        c.observe_message(mind, message, _message_cycle(message, fallback_cycle), by)
        seen.add(source)
        observed += 1
    mind[OBSERVED_IDS_KEY] = sorted(seen)[-1000:]
    return observed


# Backward-compatible public helper retained for existing Allen simulators.
def observe_allen_history(mind: dict, history: list, discourse: dict, state: dict) -> int:
    return observe_participant_history(mind, history, discourse, state)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: room_participant.py INBOX_JSON ACK_JSON")

    # This is the one serialized ingress point before all 12 cognition nodes run.
    # On the first post-repair beat it archives poisoned semantic history and
    # preserves social/personality continuity; later beats are idempotent no-ops.
    migrate_files()

    inbox_path = Path(sys.argv[1])
    ack_path = Path(sys.argv[2])
    inbox = load_json(inbox_path, {"messages": []})
    pending = inbox.get("messages") if isinstance(inbox, dict) else []
    if not isinstance(pending, list):
        pending = []

    history = c.conv()
    discourse = c.tree()
    state = c.state()
    mind = c.minds()
    ack_ids = []
    injected_speakers = []
    for item in pending[:20]:
        if not isinstance(item, dict):
            continue
        source_id = inject(item, history, discourse, state)
        if source_id:
            ack_ids.append(source_id)
            injected_speakers.append(participant_for(item))

    observed_count = observe_participant_history(mind, history, discourse, state)

    if ack_ids:
        c.save(c.ROOM / "conversation.json", history[-1000:])
        discourse["nodes"] = discourse.get("nodes", [])[-1200:]
        discourse["roots"] = discourse.get("roots", [])[-300:]
        c.save(c.ROOM / "discourse.json", discourse)
        print(f"Injected {len(ack_ids)} participant turn(s) into the Room context: {','.join(injected_speakers)}")

    if observed_count:
        c.save(c.ROOM / "cognitive_state.json", mind)
        print(f"Observed {observed_count} previously unseen participant turn(s) into Room social memory")

    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(json.dumps({"ids": ack_ids}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
