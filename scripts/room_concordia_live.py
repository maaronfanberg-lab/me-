#!/usr/bin/env python3
"""Publish real Concordia-driven events into the existing live Room.

The native DeepMind scheduler and entities decide who acts. This adapter only
preserves the Room's existing public conversation schema and relay feed.
No local imitation of Concordia scheduling or compulsory speech selection.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from concordia.components.game_master import interrupt_response_parsing

import room_concordia_native as native
import room_life
import room_engine_v5 as c
from room_conversational_floor import audible_addressee

CHECKPOINT = "native-concordia-state.json"
ALLOWED = frozenset((*native.PARTICIPANTS, "allen"))


def _load(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def _save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _new_input(conversation, ack_path, prior_checkpoint):
    # The relay-ack list identifies accepted current external inputs, not
    # historical Allen words previously injected into the public log.
    acked = set(_load(ack_path, {}).get("ids", []))
    prior = set(prior_checkpoint.get("seen_allen_messages", []))
    recent = [
        m for m in conversation
        if m.get("speaker") == "allen" and m.get("id")
        and m.get("id") not in prior
        and any(hashlib.sha256(str(external).encode()).hexdigest()[:10]
                in str(m["id"]) for external in acked)
    ]
    return recent


def _message_from_concordia(raw: str, name: str, history: list) -> str:
    # Native Concordia emits an action + trailing JSON control block.
    # The JSON must never appear as character dialogue in the Room viewer.
    lead = re.sub(r"^\s*" + re.escape(name) + r"\s*:\s*", "", str(raw), flags=re.I)
    text, meta = interrupt_response_parsing.extract_json_block(lead)
    text = text.strip()
    if not isinstance(meta.get("mask"), list) or not isinstance(meta.get("timer"), dict):
        return ""
    if not text or len(text) > 520:
        return ""
    bad = ("system prompt", "hidden prompt", "developer message",
           "chain of thought", "room_prompt_", "output json", "return json")
    if any(marker in text.lower() for marker in bad):
        return ""
    words = re.findall(r"[a-z0-9']+", text.lower())
    if len(words) >= 10 and len(set(words)) <= 3:
        return ""
    if text in {item.get("text") for item in history[-18:] if isinstance(item, dict)}:
        return ""
    # Do not publish another person's supposed speech.
    if re.match(r"^(?:Sarah|Mara|Owen|Jules|Allen)\s*:\s*", text):
        return ""
    return text


def _semantic_echo(text: str, speaker: str, history: list) -> bool:
    """Reject recycled speech, including paraphrases and repeated promises.

    The prior exact-string filter missed 'I'll simplify...' versus
    'Let's simplify...' and repeated symbolic observations. This uses
    lexical evidence rather than an LLM judging its own output.
    """
    def terms(value):
        return set(re.findall(r"[a-z]{4,}", str(value).lower())) - {
            "that", "this", "with", "from", "will", "would", "could",
            "into", "about", "have", "your", "their", "there", "what",
            "when", "where", "lets", "just", "some", "more", "very",
            "then", "they", "them", "were", "been", "here", "also",
        }
    words = terms(text)
    if len(words) < 3:
        return False
    recent = [item for item in history[-35:] if isinstance(item, dict)
              and item.get("speaker") in native.PARTICIPANTS]
    def ngrams(value, n=9):
        sequence = re.findall(r"[a-z0-9']+", str(value).lower())
        return {tuple(sequence[i:i + n])
                for i in range(max(0, len(sequence) - n + 1))}
    new_phrases = ngrams(text)
    for item in recent:
        # Copying nine successive words is not a new autobiographical
        # experience, even when the rest of the sentence is rephrased.
        # This is also more discriminating than blanket topic repetition.
        if new_phrases and new_phrases & ngrams(item.get("text", "")):
            return True
        old = terms(item.get("text", ""))
        if len(old) < 3:
            continue
        similarity = len(words & old) / max(1, min(len(words), len(old)))
        if similarity >= 0.85 and len(words & old) >= 3:
            return True
    # A short abstract phrase repeated across speakers is still an echo.
    recurring = ("space between", "hidden harmonies", "subtle pattern",
                 "gentle inquiry", "meaning and chaos", "whispers and meaning")
    if any(phrase in text.lower() and sum(
            phrase in str(item.get("text", "")).lower() for item in recent) >= 2
           for phrase in recurring):
        return True
    return False


def beat(root: Path, *, mode: str, ack_path: Path, steps: int = 1) -> dict:
    room = root / "room"
    conversation = _load(room / "conversation.json", [])
    state = _load(room / "state.json", {})
    minds = c.migrate_minds(_load(room / "cognitive_state.json", c.fresh_minds()))
    discourse = _load(room / "discourse.json", {"nodes": [], "roots": []})
    live = _load(room / "live.json", {})
    checkpoint_path = room / CHECKPOINT
    checkpoint = _load(checkpoint_path, {}) if checkpoint_path.is_file() else {}
    new_input = _new_input(conversation, ack_path, checkpoint)
    upcoming_cycle = int(state.get("cycle", 0)) + 1
    life_path = room / "life.json"
    life_world = (_load(life_path, {}) if life_path.is_file()
                  else room_life.initial(c.CFG, upcoming_cycle))
    room_life.validate(life_world, c.CFG)
    room_life.repair_profile_goals(life_world, c.CFG)
    # Native agents see the verified current environment BEFORE they choose.
    world_contexts = {
        who: room_life.context(life_world, who)
        for who in native.PARTICIPANTS
    }
    delivered_world_ids = list(checkpoint.get("delivered_life_event_ids") or [])
    already_delivered = set(delivered_world_ids)
    pending_world_events = [
        e for e in life_world["events"][-12:]
        if e.get("visibility") == "public" and e.get("id") not in already_delivered
    ]
    user_event = "\n".join(f"Allen: {m.get('text','')}" for m in new_input)
    # One-time transition away from the old repeated, abstract dialogue.
    # The public Room history and all existing relationships remain intact.
    # Do NOT re-prime a new autonomous memory bank with the same stale turns.
    bootstrap_policy = 2
    old_seen = list(checkpoint.get("seen_allen_messages", []))
    resume = checkpoint_path if checkpoint.get("bootstrap_policy") == bootstrap_policy else None
    last_witnessed = str(checkpoint.get("last_witnessed_public_id") or "")
    witnessed = [m for m in conversation if isinstance(m, dict)
                 and m.get("id") and m.get("speaker") in ALLOWED]
    if last_witnessed:
        indices = [i for i, m in enumerate(witnessed)
                   if str(m["id"]) == last_witnessed]
        recent_public = witnessed[indices[-1] + 1:] if indices else witnessed[-4:]
    else:
        recent_public = witnessed[-4:]
    # This is a real Concordia engine tick, not a call to the legacy Room floor.
    output = native.run(
        mode=mode,
        steps=steps,
        root=root,
        start_time=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        state_in=resume,
        state_out=checkpoint_path,
        bootstrap_context=(),
        recent_public=recent_public,
        world_contexts=world_contexts,
        world_events=pending_world_events,
        user_event=user_event,
    )
    checkpoint = _load(checkpoint_path, {})
    checkpoint["bootstrap_policy"] = bootstrap_policy
    checkpoint["delivered_life_event_ids"] = list(dict.fromkeys([
        *delivered_world_ids, *output.get("injected_world_events", [])
    ]))[-120:]
    if witnessed:
        checkpoint["last_witnessed_public_id"] = str(witnessed[-1]["id"])
    checkpoint["seen_allen_messages"] = list(
        dict.fromkeys([*old_seen, *(str(m["id"]) for m in new_input)])
    )[-300:]
    _save(checkpoint_path, checkpoint)

    cycle = upcoming_cycle
    # This referee never decides who speaks: Concordia already did that.
    # It executes only verified structured work chosen by those agents and
    # advances their existing commitments even in a silent beat.
    room_life.advance(life_world, c.CFG, cycle, output.get("steps") or [])
    beat_id = f"beat-{c.BOOT}-{cycle:06d}"
    current_topic = state.get("topic_episode") or {}
    spoken = []
    publication = {"actions": 0, "invalid_format": 0, "semantic_echo": 0,
                   "published": 0, "new_allen_inputs": len(new_input),
                   "new_witnessed_turns": len(recent_public)}
    for step in output.get("steps") or []:
        for candidate_name, raw in (step.get("actions") or {}).items():
            speaker = candidate_name.lower()
            if speaker not in native.PARTICIPANTS:
                continue
            publication["actions"] += 1
            text = _message_from_concordia(raw, candidate_name, conversation)
            if not text:
                publication["invalid_format"] += 1
                continue
            if _semantic_echo(text, speaker, [*conversation, *spoken]):
                publication["semantic_echo"] += 1
                continue
            # Do not make conversation sound as if it is still about an old
            # stuck topic solely because the archival index says so.
            words = c.toks(text)[:5]
            if not spoken:
                current_topic = c.new_topic_from_terms(words or ["conversation"], cycle, None)
            target = audible_addressee(speaker, text)
            previous = (spoken[-1] if spoken else (conversation[-1] if conversation else {}))
            message, node = c.emit(
                speaker, "deepen", target, previous.get("discourse_id"),
                None, text, beat_id, len(spoken), current_topic, words,
            )
            message["cognition"]["mandatory_speech"] = False
            message["cognition"]["native_concordia"] = True
            message["cognition"]["compute_nodes"] = []
            message["cognition"]["processes"] = 1
            c.record(conversation, discourse, minds, message, node, cycle)
            spoken.append(message)
            publication["published"] += 1
    if spoken:
        current_topic = c.update_topic(current_topic, spoken, cycle)
        current_topic["participants"] = [*native.PARTICIPANTS, "allen"]
        state["topic_episode"] = current_topic

    at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state.update({
        "version": c.VERSION,
        "boot_id": c.BOOT,
        "cycle": cycle,
        "last_run": at,
        "messages": len(conversation[-1000:]),
        "last_beat_id": beat_id,
        "beat_contributors": [msg["speaker"] for msg in spoken],
        "beat_message_count": len(spoken),
        "native_publication_diagnostics": publication,
        "silence_cycles": 0 if spoken else int(state.get("silence_cycles") or 0) + 1,
        "conversational_floor": "native_concordia_interrupt_driven",
        "independent_life": {
            "cycle": life_world["processed_cycle"],
            "active_tasks": sum(bool(v.get("task"))
                                for v in life_world["lives"].values()),
            "completed_tasks": sum(int(v.get("completed", 0))
                                   for v in life_world["lives"].values()),
        },
        "native_concordia": {
            "framework": output["framework"],
            "engine": output["engine_class"],
            "scheduler": output["scheduler_class"],
            "simulated_time": output["simulated_time"],
            "mode": mode,
            "verified_world_interrupts": len(output.get("injected_world_events", [])),
        },
    })
    if spoken:
        state["last_public_event"] = spoken[-1]["id"]
        state["last_speaker"] = spoken[-1]["speaker"]

    # Keep the established viewer/feed schema intact while ensuring the
    # published backend identity is truthful.
    public_minds = live.get("minds") or {"schema": 5, "entities": {}}
    entities = public_minds.setdefault("entities", {})
    for name in native.PARTICIPANTS:
        profile = c.P[name]
        prior = entities.setdefault(name, {})
        prior["name"] = profile["name"]
        prior["status"] = (
            "sleeping" if name in c.CFG.get("sleeping_entities", []) else "awake"
        )
        prior["genome"] = profile["traits"]
        development = prior.setdefault("development", {})
        development["spoken"] = minds["entities"][name].get("spoken", 0)
        development["silences"] = minds["entities"][name].get("silences", 0)
        prior["memory"] = [
            {"source": m.get("source"), "speaker": m.get("speaker"), "text": m.get("text")}
            for m in minds["entities"][name].get("room_memories", [])[-12:]
        ]

    network = dict(live.get("network") or {})
    network.update({
        "engine": "concordia.environment.engines.simultaneous.Simultaneous",
        "native_concordia": True,
        "speech_selection": "interrupt_driven.GameMaster",
        "mandatory_speech": False,
        "compute_nodes": len(output["players"]),
        "active_processes": len(output["players"]),
    })
    live.update({
        "generated_at": at,
        "architecture_version": "room-native-concordia-v1",
        "boot_id": c.BOOT,
        "state": state,
        "minds": public_minds,
        "profiles": c.P,
        "conversation": conversation[-1000:],
        "discourse": discourse,
        "topic_episode": state.get("topic_episode"),
        "network": network,
        "room_life": room_life.public_snapshot(life_world),
    })
    _save(life_path, life_world)
    _save(room / "conversation.json", conversation[-1000:])
    discourse["nodes"] = discourse.get("nodes", [])[-1200:]
    discourse["roots"] = discourse.get("roots", [])[-300:]
    _save(room / "discourse.json", discourse)
    _save(room / "cognitive_state.json", minds)
    _save(room / "state.json", state)
    _save(room / "live.json", live)
    _save(root / "society" / "live.json", live)
    return {"cycle": cycle, "spoke": [m["speaker"] for m in spoken],
            "quiet": not spoken, "engine": output["engine_class"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("scripted", "llama"), default="llama")
    parser.add_argument("--root", type=Path, default=native.ROOT)
    parser.add_argument("--ack-path", type=Path, default=Path("room_work/allen-ack.json"))
    args = parser.parse_args()
    print(json.dumps(beat(args.root, mode=args.mode, ack_path=args.ack_path)))


if __name__ == "__main__":
    main()
