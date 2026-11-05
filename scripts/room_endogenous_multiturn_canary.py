#!/usr/bin/env python3
"""Real 3B multi-turn Room shadow: only genuinely model-generated public turns.

Synthetic visitor event, isolated personal states, two participants,
voluntary speech with self-endorsement, and read-only candidate outbox.
The pending outbox is "heard" only inside this research simulation.
No real Room feed, private state, or workflow heartbeat is touched.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL
from room_endogenous_shadow_beat import shadow_beat
from room_endogenous_transaction_store import initial_store

PARTICIPANTS = ("mara", "jules")
INIT = {
    "id": "simulated-visitor-01", "speaker": "allen",
    "text": (
        "I have two measuring cups both marked 200 mL, but they give "
        "different-looking levels. What could explain that, and can we test "
        "the difference without assuming either cup is correct?"
    ),
}


def run(*, config: dict, speech_model, approval_model,
        goal_model=None, belief_model=None, beats: int = 6) -> dict:
    profile_all = config.get("p") or {}
    profiles = {agent: profile_all[agent] for agent in PARTICIPANTS}
    snapshot = initial_store()
    visible = []
    records = []
    start = time.monotonic()
    for i in range(beats):
        visitors = [INIT] if i == 0 else []
        snap, diag = shadow_beat(
            snapshot=snapshot, cycle=17000+i,
            cycle_id=f"research-3b-beat-{i+1}",
            public_history=visible,
            visitor_messages=visitors,
            profiles=profiles, speech_request=speech_model,
            endorsement_request_model=approval_model,
            goal_request_model=goal_model,
            revision_request_model=belief_model,
            awake=PARTICIPANTS,
            budget_seconds=125.0)
        if visitors:
            visible.extend(visitors)
        new_public = []
        if diag["outbox_id"]:
            message = next((m for m in snap["outbox"] if m["id"] == diag["outbox_id"]), None)
            if message is None or message.get("status") != "pending":
                raise ValueError("lost internally selected outbox record")
            # Simulated in-memory delivery only. Never publish to real Room.
            new_public.append({
                "id": message["id"], "speaker": message["speaker"],
                "text": message["text"],
            })
        visible.extend(new_public)
        records.append({
            "beat": i+1, "decision": diag["decision"],
            "selected": diag["selected"],
            "model_calls": diag["model_calls"],
            "participant_outcomes": diag["participant_outcomes"],
            "private_growth": diag.get("private_growth", {}),
            "source_id": new_public[0]["id"] if new_public else None,
            "model_utterance": new_public[0]["text"] if new_public else None,
        })
        snapshot = snap
    return {
        "experiment": "room_endogenous_3b_multiturn_shadow",
        "model": "Llama-3.2-3B-Instruct",
        "mode": "synthetic_read_only_no_real_publication",
        "initial_public_event": INIT,
        "beats": records,
        "summary": {
            "beats": beats, "public_agent_turns": sum(r["decision"] == "speak" for r in records),
            "silent_beats": sum(r["decision"] == "silent" for r in records),
            "simulated_public_messages": len(visible),
            "model_calls": sum(r["model_calls"] for r in records),
            "owner_created_goals": sum(
                int(bool(event.get("goal_state_changed")))
                for row in records for event in row["private_growth"].values()),
            "owner_revised_beliefs": sum(
                int(bool(event.get("private_state_changed")))
                for row in records for event in row["private_growth"].values()),
            "speakers": dict((a,sum(r["selected"] == a for r in records)) for a in PARTICIPANTS),
            "elapsed_seconds": round(time.monotonic()-start,2),
            "research_state_revision": snapshot["revision"],
            "awaiting_actual_human_naturalness_validation": True,
            "ready_for_live": False,
        },
        "published_live_dialogue": False, "modified_live_room": False,
        "stored_live_memory": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--config", default="room/config.json")
    parser.add_argument("--out", default="room-endogenous-multiturn-3b.json")
    parser.add_argument("--beats", type=int, default=6)
    args = parser.parse_args()
    if not 2 <= args.beats <= 8:
        raise ValueError("bounded multi-turn test requires 2..8 beats")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    speech = local_model_request(endpoint=args.model_url, max_tokens=110,
                                 temperature=.35)
    approve = local_model_request(endpoint=args.model_url, max_tokens=12,
                                  temperature=.35)
    goal_model = local_model_request(endpoint=args.model_url, max_tokens=90)
    belief_model = local_model_request(endpoint=args.model_url, max_tokens=95)
    result = run(config=cfg, speech_model=speech, approval_model=approve,
                 goal_model=goal_model, belief_model=belief_model, beats=args.beats)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",
                              encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
