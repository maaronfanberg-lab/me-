"""Research-only crash-safe transaction store for endogenous Room proposals.

This store is NOT a public feed writer. It atomically commits privately
validated candidate-state changes and a source-addressed *outbox* of pending
public messages, including the possibility of genuine silence.

External publication requires a separate consumer that deduplicates message IDs;
an on-disk outbox alone does not guarantee cross-system exactly-once delivery.
No production Room runner imports this module.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import fcntl

from room_endogenous_preflight import AGENTS, _plain_id
from room_endogenous_goal_journal import new_journal, VERSION
from room_endogenous_public_hygiene import publication_issue
from room_endogenous_reflection import authenticated_reflection_ids

STORE_VERSION = "room_endogenous_research_store_v1"


def initial_store() -> dict:
    return {"schema": STORE_VERSION, "revision": 0, "last_cycle": -1,
            "characters": {agent: {"journal": new_journal(agent),
                                   "private_state": {}} for agent in sorted(AGENTS)},
            "public_input": [], "outbox": [], "cycles": {}, "consumed_bids": []}


def _valid(snapshot):
    if (not isinstance(snapshot, dict) or snapshot.get("schema") != STORE_VERSION
            or type(snapshot.get("revision")) is not int
            or type(snapshot.get("last_cycle")) is not int
            or not isinstance(snapshot.get("outbox"), list)
            or not isinstance(snapshot.get("public_input"), list)
            or not isinstance(snapshot.get("cycles"), dict)
            or not isinstance(snapshot.get("consumed_bids"), list)
            or not isinstance(snapshot.get("characters"), dict)):
        raise ValueError("invalid research snapshot")
    if set(snapshot["characters"]) != AGENTS:
        raise ValueError("agent membership mismatch")


def _payload_fingerprint(selected, incoming):
    value = {
        "selected": {k: selected.get(k) for k in ("decision", "speaker", "bid_id", "utterance")},
        "incoming": incoming,
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def apply_cycle(snapshot: dict, *, expected_revision: int, cycle: int,
                cycle_id: str, candidates: dict, selected: dict,
                visitor_messages: list[dict]) -> tuple[dict, bool]:
    """Return new snapshot and commit-needed flag. No input mutation.

    Selected public speech must match the exact owner-authored candidate.
    A successful commit is a pending *outbox* record, not a completed external
    publication. Silence still advances a durable cognitive heartbeat.
    """
    _valid(snapshot)
    if (type(expected_revision) is not int or type(cycle) is not int
            or cycle < 0 or not _plain_id(cycle_id)
            or not isinstance(candidates, dict) or not isinstance(selected, dict)
            or not isinstance(visitor_messages, list)):
        raise ValueError("invalid transaction")
    clean_visitor = []
    submitted_visitor = []
    existing = {x["id"]: x for x in snapshot["public_input"]}
    for event in visitor_messages:
        if (not isinstance(event, dict) or event.get("speaker") != "allen"
                or not _plain_id(event.get("id"))
                or not isinstance(event.get("text"), str)
                or not event["text"].strip()):
            raise ValueError("untrusted visitor input")
        public = {"id": event["id"], "speaker": "allen", "text": event["text"]}
        submitted_visitor.append(public)
        if event["id"] in existing and existing[event["id"]] != public:
            raise ValueError("conflicting visitor source")
        if event["id"] not in existing:
            clean_visitor.append(public)
            existing[event["id"]] = public
    signature = _payload_fingerprint(selected, submitted_visitor)
    prior = snapshot["cycles"].get(cycle_id)
    if prior is not None:
        if prior["fingerprint"] != signature:
            raise ValueError("same cycle ID with different public results")
        return copy.deepcopy(snapshot), False
    if snapshot["revision"] != expected_revision or cycle <= snapshot["last_cycle"]:
        raise ValueError("stale transaction")

    next_state = copy.deepcopy(snapshot)
    for name, candidate in candidates.items():
        if name not in AGENTS or not isinstance(candidate, dict):
            raise ValueError("unknown private candidate")
        if not candidate.get("ok"):
            continue
        bid = candidate.get("bid")
        journal = candidate.get("journal")
        private = candidate.get("private_state")
        if (not isinstance(bid, dict) or bid.get("speaker") != name
                or bid.get("cycle") != cycle or not isinstance(journal, dict)
                or journal.get("schema") != VERSION or journal.get("owner") != name
                or not isinstance(private, dict)):
            raise ValueError("invalid candidate identity or state")
        old_journal = snapshot["characters"][name]["journal"]
        if candidate.get("private_only"):
            old_private = snapshot["characters"][name]["private_state"]
            references = authenticated_reflection_ids(owner=name, private_state=old_private)
            new_entries = journal.get("goals")
            old_entries = old_journal.get("goals")
            if (bid.get("schema") != "room_private_cognition_step_v1"
                    or bid.get("action") != "wait"
                    or candidate.get("utterance")
                    or private != old_private
                    or not isinstance(old_entries, list)
                    or not isinstance(new_entries, list)
                    or len(new_entries) != len(old_entries) + 1
                    or new_entries[:-1] != old_entries
                    or journal.get("revision") != old_journal.get("revision", -2) + 1
                    or not isinstance(new_entries[-1], dict)
                    or new_entries[-1].get("owner") != name
                    or new_entries[-1].get("status") != "active"):
                raise ValueError("unauthorized silent private-state transition")
            origin = new_entries[-1].get("origin")
            if (not isinstance(origin, dict)
                    or origin.get("kind") != "own_reflection"
                    or origin.get("source_id") not in references
                    or bid.get("source_id") != origin["source_id"]):
                raise ValueError("unowned private reflection origin")
        if (type(journal.get("revision")) is not int
                or journal["revision"] not in (old_journal["revision"], old_journal["revision"] + 1)):
            raise ValueError("invalid goal revision")
        next_state["characters"][name] = {
            "journal": copy.deepcopy(journal),
            "private_state": copy.deepcopy(private),
        }

    event_out = None
    decision = selected.get("decision")
    if decision == "speak":
        agent = selected.get("speaker")
        candidate = candidates.get(agent)
        if (agent not in AGENTS or not isinstance(candidate, dict)
                or not candidate.get("ok")
                or candidate.get("utterance") != selected.get("utterance")
                or not candidate.get("utterance")
                or candidate.get("bid", {}).get("bid_id") != selected.get("bid_id")
                or candidate.get("bid", {}).get("action") != "speak"):
            raise ValueError("fabricated or mismatched public speech")
        # Defense in depth: publisher cannot bypass earlier volunteer-stage
        # quality checks and insert a previous conversation line again.
        earlier = [{"speaker": e["speaker"], "text": e["text"]}
                   for e in snapshot["outbox"] if isinstance(e, dict)
                   and e.get("speaker") in AGENTS and isinstance(e.get("text"), str)]
        issue = publication_issue(speaker=agent, text=selected["utterance"],
                                  public_history=earlier)
        if issue:
            raise ValueError("research public utterance quarantined: " + issue)
        consumed_key = agent + ":" + selected["bid_id"]
        if consumed_key in next_state["consumed_bids"]:
            raise ValueError("bid already published in earlier cycle")
        next_state["consumed_bids"].append(consumed_key)
        # ID is stable for retry and must be externally deduplicated by ID.
        stable_id = "room-bid-" + hashlib.sha256(
            f"{cycle_id}|{agent}|{selected['bid_id']}".encode()
        ).hexdigest()[:26]
        event_out = {
            "id": stable_id, "speaker": agent,
            "text": selected["utterance"],
            "cycle_id": cycle_id, "status": "pending",
        }
        next_state["outbox"].append(event_out)
    elif decision != "silent" or selected.get("utterance", ""):
        raise ValueError("invalid silence result")
    next_state["public_input"].extend(clean_visitor)
    next_state["last_cycle"] = cycle
    next_state["revision"] += 1
    next_state["cycles"][cycle_id] = {
        "fingerprint": signature,
        "outcome": decision,
        "outbox_id": event_out["id"] if event_out else None,
    }
    return next_state, True


def _atomic_write(path: Path, snapshot: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                         prefix=path.name+".", suffix=".tmp",
                                         delete=False) as f:
            temp_path = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def transact(path: str | Path, *, expected_revision: int, cycle: int,
             cycle_id: str, candidates: dict, selected: dict,
             visitor_messages: list[dict]) -> dict:
    """Lock, CAS, fsync and atomically rename a research-state file."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    lock = file.with_suffix(file.suffix + ".lock")
    with lock.open("a+b") as locked:
        fcntl.flock(locked.fileno(), fcntl.LOCK_EX)
        current = json.loads(file.read_text(encoding="utf-8")) if file.exists() else initial_store()
        proposed, changed = apply_cycle(
            current, expected_revision=expected_revision, cycle=cycle,
            cycle_id=cycle_id, candidates=candidates, selected=selected,
            visitor_messages=visitor_messages)
        if changed:
            _atomic_write(file, proposed)
        return proposed
