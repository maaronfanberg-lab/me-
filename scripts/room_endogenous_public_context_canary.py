#!/usr/bin/env python3
"""Read-only 3B private-intention shadow of current PUBLIC Room feed.

The full model request stays on loopback on the isolated GitHub runner.
No live Room state, participant private memory, public message, or relay is
changed. Logs and artifacts contain only bounded counts/statuses and a hash
of the source cycle, NEVER raw public dialogue or private prompt text.

This is diagnostic, not a release to the live Room.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from room_endogenous_shadow import local_model_request
from room_endogenous_shadow_beat import shadow_beat
from room_endogenous_transaction_store import initial_store

AGENTS = ("sarah", "mara", "owen", "jules")
MAX_PUBLIC = 12


def filtered_history(feed: object) -> list[dict]:
    if not isinstance(feed, dict):
        raise ValueError("invalid public feed")
    conversation = feed.get("conversation")
    if not isinstance(conversation, list):
        raise ValueError("missing public conversation")
    safe = []
    seen=set()
    for item in conversation[-40:]:
        if (not isinstance(item,dict)
                or item.get("speaker") not in set(AGENTS) | {"allen"}
                or not isinstance(item.get("id"),str)
                or not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,128}",item["id"])
                or not isinstance(item.get("text"),str)
                or not item["text"].strip()
                or item["id"] in seen):
            continue
        safe.append({"id":item["id"], "speaker":item["speaker"],
                     "text":item["text"][:380]})
        seen.add(item["id"])
    return safe[-MAX_PUBLIC:]


def evaluate(*, feed: dict, config: dict, speech_request,
             endorsement_request_model, budget_seconds=160.0) -> dict:
    public=filtered_history(feed)
    cfg=config.get("p") or {}
    if not isinstance(cfg,dict):
        raise ValueError("missing Room profiles")
    sleeping = (feed.get("state") or {}).get("sleeping_entities") or []
    sleeping = set(sleeping) if isinstance(sleeping,list) else set()
    awake=tuple(a for a in AGENTS if a not in sleeping and isinstance(cfg.get(a),dict))
    if not awake:
        raise ValueError("no awake Room characters")
    cycle = (feed.get("state") or {}).get("cycle")
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid source cycle")
    source_key = hashlib.sha256(
        (str(cycle)+"|"+(public[-1]["id"] if public else "empty")).encode()
    ).hexdigest()[:20]
    out,report=shadow_beat(
        snapshot=initial_store(),cycle=cycle+1,
        cycle_id="research-live-"+source_key,
        public_history=public,visitor_messages=[],
        profiles={a:cfg[a] for a in awake},
        speech_request=speech_request,
        endorsement_request_model=endorsement_request_model,
        awake=awake,budget_seconds=budget_seconds)
    # Produce only aggregate/status data, never actual history, model
    # completions, or private self state, even when injected text is hostile.
    return {
        "experiment":"room_public_context_read_only_3b",
        "source_cycle":cycle,
        "source_fingerprint":source_key,
        "public_events_examined":len(public),
        "awake_agents":len(awake),
        "model_calls_attempted":report["model_calls"],
        "decision":report["decision"],
        "selected_agent":report["selected"],
        "suppressed_private_claims":sum(
            v=="asserts_other_mind_private_state"
            for v in report["participant_outcomes"].values()),
        "suppressed_repeated_speech":sum(
            v=="near_duplicate_public_speech"
            for v in report["participant_outcomes"].values()),
        "model_failures":sum(
            v in {"model_unavailable_or_invalid","invalid_or_unwitnessed_speech_candidate"}
            for v in report["participant_outcomes"].values()),
        "publications":0,"wrote_live_memory":False,
        "wrote_room_feed":False,"relay_invoked":False,"ready_for_live":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",required=True)
    p.add_argument("--config",default="room/config.json")
    p.add_argument("--model-url",required=True)
    p.add_argument("--out",default="room-public-context-shadow-metrics.json")
    args=p.parse_args()
    feed=json.loads(Path(args.feed).read_text(encoding="utf-8"))
    config=json.loads(Path(args.config).read_text(encoding="utf-8"))
    output=evaluate(
        feed=feed,config=config,
        speech_request=local_model_request(endpoint=args.model_url,max_tokens=105,temperature=.35),
        endorsement_request_model=local_model_request(endpoint=args.model_url,max_tokens=12,temperature=.35))
    Path(args.out).write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(output,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
