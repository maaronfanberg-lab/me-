"""Private, source-linked goal journal for isolated endogenous Room experiments.

No speech generation, no external goal injection, no automatic task creation.
The owning model must *propose* every goal. This module validates provenance
and preserves changes across simulated cycles with optimistic revision checks.

RESEARCH ONLY. The journal is not connected to the live Room.
"""
from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Mapping

from room_endogenous_preflight import AGENTS

VERSION = "room_private_goals_v1"
MAX_GOALS = 12
MAX_WORDS = 50
MAX_TEXT = 260
MAX_PUBLIC_LOOKBACK = 32
VALID_ACTIONS = frozenset({"propose", "pause", "resume", "resolve", "abandon"})
ACTIVE_STATES = frozenset({"active", "paused"})
_TERM_PATTERN = re.compile(r"^[a-zA-Z0-9_.:@-]{1,128}$")


def valid_id(value):
    return isinstance(value, str) and bool(_TERM_PATTERN.fullmatch(value))


def new_journal(owner):
    if owner not in AGENTS:
        raise ValueError("not a Room character")
    return {"schema": VERSION, "owner": owner, "revision": 0, "goals": []}


def _copy_checked(journal, owner, expected_revision, cycle):
    if not isinstance(journal, Mapping) or journal.get("schema") != VERSION or journal.get("owner") != owner:
        raise ValueError("wrong-owner journal")
    rev = journal.get("revision")
    if type(rev) is not int or rev < 0 or rev != expected_revision or type(cycle) is not int or cycle < 0:
        raise ValueError("stale or corrupted revision")
    goals = journal.get("goals")
    if not isinstance(goals, list) or len(goals) > MAX_GOALS:
        raise ValueError("malformed goal collection")
    for goal in goals:
        if (not isinstance(goal, Mapping) or not valid_id(goal.get("id"))
                or goal.get("owner") != owner or goal.get("status") not in
                ("active", "paused", "resolved", "abandoned")
                or type(goal.get("last_cycle")) is not int
                or goal["last_cycle"] > cycle):
            raise ValueError("corrupted goal entry")
    if len({g["id"] for g in goals}) != len(goals):
        raise ValueError("duplicate goal IDs")
    return copy.deepcopy(journal)


def _source_exists(source, owner, goals, history):
    if not isinstance(source, Mapping) or set(source) != {"kind", "source_id"}:
        return False
    kind, source_id = source.get("kind"), source.get("source_id")
    if not valid_id(source_id):
        return False
    if kind == "witnessed_public":
        return any(
            isinstance(turn, Mapping) and turn.get("id") == source_id
            and turn.get("speaker") in (AGENTS | {"allen"})
            and isinstance(turn.get("text"), str) and turn["text"].strip()
            for turn in history[-MAX_PUBLIC_LOOKBACK:]
        )
    if kind == "own_goal":
        return any(goal["id"] == source_id and goal["owner"] == owner
                   for goal in goals)
    return False


def apply_proposal(journal, *, owner, expected_revision, cycle, proposal, public_history):
    """Validate owner-authored goal operation or raise without mutation.

    The caller is responsible for proving the proposal came from that
    owner's independent model inference. This module cannot prove intent
    merely by receiving a dictionary.
    """
    snapshot = _copy_checked(journal, owner, expected_revision, cycle)
    if not isinstance(proposal, Mapping) or not isinstance(public_history, list):
        raise ValueError("invalid proposal envelope")
    action = proposal.get("action")
    if action not in VALID_ACTIONS:
        raise ValueError("unsupported goal operation")
    goals = snapshot["goals"]
    source = proposal.get("source")
    if not _source_exists(source, owner, goals, public_history):
        raise ValueError("unwitnessed or unowned source")
    if action == "propose":
        if set(proposal) != {"action", "description", "source"}:
            raise ValueError("unexpected goal proposal field")
        description = proposal["description"]
        if (not isinstance(description, str) or len(description) > MAX_TEXT
                or not description.strip() or len(description.split()) > MAX_WORDS):
            raise ValueError("empty or unbounded goal")
        normalized = " ".join(description.split()).strip()
        if any(g["description"].casefold() == normalized.casefold()
               and g["status"] in ACTIVE_STATES for g in goals):
            return snapshot  # idempotent, no fake newly discovered goal
        if len(goals) >= MAX_GOALS:
            raise ValueError("goal capacity reached")
        digest = hashlib.sha256(
            f"{owner}|{cycle}|{source['kind']}|{source['source_id']}|{normalized}".encode()
        ).hexdigest()[:24]
        goal_id = "self-" + digest
        if any(g["id"] == goal_id for g in goals):
            return snapshot
        goals.append({"id": goal_id, "owner": owner,
                      "description": normalized, "status": "active",
                      "created_cycle": cycle, "last_cycle": cycle,
                      "origin": dict(source),
                      "events": [{"cycle": cycle, "action": action, "source": dict(source)}]})
    else:
        if set(proposal) != {"action", "goal_id", "source"}:
            raise ValueError("unexpected update field")
        gid = proposal["goal_id"]
        selected = next((g for g in goals if g["id"] == gid), None)
        if selected is None:
            raise ValueError("goal belongs to another character or does not exist")
        if action == "pause" and selected["status"] != "active":
            raise ValueError("only active goals can pause")
        if action == "resume" and selected["status"] != "paused":
            raise ValueError("only paused goals can resume")
        if action in {"resolve", "abandon"} and selected["status"] not in ACTIVE_STATES:
            raise ValueError("terminal goal cannot be reopened without evidence")
        selected["status"] = {"pause": "paused", "resume": "active",
                              "resolve": "resolved", "abandon": "abandoned"}[action]
        selected["last_cycle"] = cycle
        selected["events"].append({"cycle": cycle, "action": action, "source": dict(source)})
        selected["events"] = selected["events"][-16:]
    snapshot["revision"] += 1
    return snapshot


def active_goals(journal, *, owner):
    if not isinstance(journal, Mapping) or journal.get("owner") != owner or journal.get("schema") != VERSION:
        raise ValueError("journal wrong owner")
    return [{"id": goal["id"], "description": goal["description"]}
            for goal in journal.get("goals", []) if goal.get("status") == "active"
            and goal.get("owner") == owner]
