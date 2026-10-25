#!/usr/bin/env python3
"""Choose one conversational *opportunity* before generating public speech.

An addressed recipient takes precedence over unsolicited contributions.
Otherwise we use each character's already-computed private intention,
personal traits and relationship context. This is a bounded text-only
engineering approximation to turn selection, not a rule against repeated
words, not a topic-rotation quota, and not a license to fabricate agreement.

Phase-1 integration always returns an awake speaker. Genuine voluntary
silence requires a separate heartbeat/recovery protocol before deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ORDER = ("sarah", "mara", "owen", "jules")
ACTIONS = {"answer", "deepen", "disclose", "compare", "disagree", "repair",
           "support", "callback", "bridge", "close"}
NODE = {"sarah": 2, "mara": 5, "owen": 8, "jules": 11}


def _norm(value):
    return str(value or "").strip().lower()


def _target(event):
    if not isinstance(event, dict):
        return ""
    cognition = event.get("cognition")
    cognition = cognition if isinstance(cognition, dict) else {}
    return _norm(cognition.get("target") or event.get("target"))


def is_directed(event, recipient):
    """Require an *audible* vocative, not the generator's hidden target alone."""
    speaker = _norm((event or {}).get("speaker"))
    target = _norm(recipient)
    if not isinstance(event, dict) or target not in ORDER or speaker == target:
        return False
    if _target(event) != target:
        return False
    spoken = str(event.get("text") or "")
    return bool(re.search(r"\b" + re.escape(target) + r"\b\s*[,?!:]", spoken, re.I))


def last_participant_turn(history):
    """Match the same evidence projection in selection and publication."""
    return next((event for event in reversed(history)
                 if isinstance(event, dict)
                 and _norm(event.get("speaker")) in (*ORDER, "allen")), None)


def last_participant_source_id(history):
    return (last_participant_turn(history) or {}).get("id")


def _score(entity, last, thought, profile, relationships):
    """Importance to this character, not novelty or speaker rotation."""
    delib = thought if isinstance(thought, dict) else {}
    traits = profile.get("traits") if isinstance(profile, dict) else {}
    traits = traits if isinstance(traits, dict) else {}
    speaker = _norm((last or {}).get("speaker"))
    partner = _norm(delib.get("preferred_partner"))
    action = _norm(delib.get("action"))
    score = (0.32 * float(traits.get("curiosity", .5))
             + 0.26 * float(traits.get("extraversion", .5))
             - 0.20 * float(traits.get("inhibition", .5)))
    if speaker and speaker != entity and partner == speaker:
        score += .48
    if speaker == entity and _norm(delib.get("unresolved_thread")):
        score += .08  # genuine continuation of a stated unfinished concern
    if action in {"answer", "repair"} and partner == speaker and speaker != entity:
        score += .19
    if action in {"disagree", "disclose"}:
        score += .08
    if _norm(delib.get("unresolved_thread")):
        score += .09
    relation = ((relationships or {}).get(entity) or {}).get(speaker) or {}
    score += .08 * float(relation.get("reciprocity", 0))
    return score


def choose_next(history, bus, config, minds, *, rank=0):
    """Return the rank-th *independently plausible* speaker opportunity.

    Rank 1 is a liveness fallback only after rank 0 had a technical failure.
    It is not a novelty quota or a demand that a reluctant person speak.
    """
    if not isinstance(history, list) or not isinstance(bus, dict):
        raise ValueError("conversation and recurrent bus must be readable")
    sleeping = {_norm(e) for e in config.get("sleeping_entities", ())}
    awake = [e for e in ORDER if e not in sleeping]
    if not awake:
        raise RuntimeError("no awake character, cannot select a speaker")
    if type(rank) is not int or not 0 <= rank < len(awake):
        raise ValueError("requested candidate is outside the awake group")
    last = last_participant_turn(history)
    author = _norm((last or {}).get("speaker"))
    target = _target(last)
    addressed = (target if target in awake and author != target
                 and is_directed(last, target) else None)
    profile = config.get("p") if isinstance(config.get("p"), dict) else {}
    state = minds.get("entities") if isinstance(minds.get("entities"), dict) else {}
    recurrent = bus.get("recurrent") if isinstance(bus.get("recurrent"), dict) else {}
    relationships = {e: (state.get(e) or {}).get("people") for e in awake}
    ranked = []
    for entity in awake:
        thought = (((recurrent.get(entity) or {}).get("thought") or {}).get("private") or {}).get("deliberation") or {}
        score = _score(entity, last, thought, profile.get(entity) or {}, relationships)
        seed = f"{(last or {}).get('id', '')}|{entity}|{_norm(thought.get('action'))}"
        tie = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / (16 ** 8)
        ranked.append((score, tie, entity))
    ordered = [item[2] for item in sorted(ranked, reverse=True)]
    if addressed:
        ordered.remove(addressed)
        ordered.insert(0, addressed)
    chosen = ordered[rank]
    reason = ("addressed_recipient" if rank == 0 and addressed == chosen
              else "technical_fallback_opportunity" if rank > 0
              else "open_floor_relevance")
    return {"speaker": chosen, "node": NODE[chosen], "reason": reason,
            "candidate_rank": rank, "candidate_speakers": ordered,
            "source_id": (last or {}).get("id"), "source_speaker": author}


def checked_floor(selection, *, awake, required=False):
    if not isinstance(selection, dict):
        raise ValueError("missing floor decision")
    speaker = _norm(selection.get("speaker"))
    allowed = {e for e in awake if e in ORDER}
    if speaker not in allowed or selection.get("node") != NODE[speaker]:
        raise ValueError("invalid or sleeping selected character")
    if required and selection.get("reason") not in {"addressed_recipient", "open_floor_relevance", "technical_fallback_opportunity"}:
        raise ValueError("unrecognized floor choice")
    return speaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rank", type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "room/config.json").read_text(encoding="utf-8"))
    history = json.loads((root / "room/conversation.json").read_text(encoding="utf-8"))
    minds = json.loads((root / "room/cognitive_state.json").read_text(encoding="utf-8"))
    bus = json.loads(Path(args.bus).read_text(encoding="utf-8"))
    decision = choose_next(history, bus, config, minds, rank=args.rank)
    decision["cycle_key"] = str(bus.get("key") or "")
    decision["bus_sha256"] = hashlib.sha256(Path(args.bus).read_bytes()).hexdigest()
    checked_floor(decision, awake=[e for e in ORDER if e not in config.get("sleeping_entities", [])], required=True)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(decision, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Room next conversational opportunity:", decision["speaker"],
          "because", decision["reason"])


if __name__ == "__main__":
    main()
