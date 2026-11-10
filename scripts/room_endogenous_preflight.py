"""Fail-closed arbiter for independently authored, provenance-bound Room intentions.

RESEARCH ONLY. No live Room entrypoint imports this module. It never generates
intentions, public dialogue, goals or events. An agent must author its own private
bid before it can be considered. Absence of a valid bid is silence, not failure.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping

AGENTS = frozenset({"sarah", "mara", "owen", "jules"})
MAX_CANDIDATES = 4
MAX_BID_AGE = 2
MAX_PUBLIC_LOOKBACK = 32


def _plain_id(value: object, limit: int = 128) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and all(
        ch.isascii() and (ch.isalnum() or ch in "-_:.@") for ch in value
    )


def _bounded_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0.0 <= value <= 1.0


def validate_bid(agent: str, bid: object, *, cycle: int,
                 public_history: list[dict], own_goal_ids: set[str],
                 consumed_ids: set[str]) -> str | None:
    """Return rejection category or None; never inspect another agent's state."""
    if agent not in AGENTS or not isinstance(bid, Mapping):
        return "invalid_envelope"
    if bid.get("speaker") != agent:
        return "foreign_identity"
    if bid.get("schema") != "room_endogenous_bid_v1":
        return "invalid_schema"
    if not _plain_id(bid.get("bid_id")):
        return "invalid_bid_id"
    if agent + ":" + bid["bid_id"] in consumed_ids:
        return "already_consumed"
    timestamp = bid.get("cycle")
    if type(timestamp) is not int or timestamp > cycle or cycle - timestamp > MAX_BID_AGE:
        return "stale_or_future_bid"
    if bid.get("action") not in {"speak", "listen", "reflect", "wait"}:
        return "invalid_action"
    if not _bounded_number(bid.get("motivation")) or not _bounded_number(bid.get("cost")):
        return "unbounded_motivation"
    evidence = bid.get("basis")
    if not isinstance(evidence, Mapping):
        return "missing_basis"
    kind = evidence.get("kind")
    if kind == "witnessed":
        source_id = evidence.get("source_id")
        observed = {
            item.get("id") for item in public_history[-MAX_PUBLIC_LOOKBACK:]
            if isinstance(item, Mapping)
            and isinstance(item.get("speaker"), str)
            and item.get("speaker").lower() in AGENTS | {"allen"}
            and isinstance(item.get("text"), str) and item["text"].strip()
            and _plain_id(item.get("id"))
        }
        if not _plain_id(source_id) or source_id not in observed:
            return "unwitnessed_source"
    elif kind == "own_goal":
        goal_id = evidence.get("goal_id")
        if not _plain_id(goal_id) or goal_id not in own_goal_ids:
            return "unknown_own_goal"
    else:
        return "unsupported_basis"
    return None


def choose_private_bid(*, cycle: int, public_history: list[dict],
                       bids: Mapping, goal_ids: Mapping, consumed_ids: set[str],
                       awake: tuple[str, ...] = ("sarah", "mara", "owen", "jules")) -> dict:
    """One privately initiated speaker or genuine silence; no synthetic speech.

    This module performs no model inference. Bids are separately produced by the
    owner agent, based on its *own* state; the arbiter may verify goal membership
    but must not use another person's private goals to score that agent.
    """
    if type(cycle) is not int or cycle < 0:
        raise ValueError("invalid cycle")
    if not isinstance(public_history, list) or not isinstance(bids, Mapping) or not isinstance(goal_ids, Mapping):
        raise ValueError("invalid input")
    if not isinstance(consumed_ids, set) or len(awake) > MAX_CANDIDATES or len(set(awake)) != len(awake):
        raise ValueError("invalid membership")
    if any(agent not in AGENTS for agent in awake):
        raise ValueError("unknown agent")
    candidates = []
    rejected = {}
    for agent in awake:
        bid = bids.get(agent)
        if bid is None:
            continue
        raw_goals = goal_ids.get(agent)
        safe_goals = ({g for g in raw_goals if _plain_id(g)}
                      if isinstance(raw_goals, (list, tuple, set, frozenset)) else set())
        issue = validate_bid(agent, bid, cycle=cycle,
                             public_history=public_history,
                             own_goal_ids=safe_goals, consumed_ids=consumed_ids)
        if issue:
            rejected[agent] = issue
            continue
        if bid["action"] != "speak":
            continue  # private reflection or listening is not a public utterance
        gain = float(bid["motivation"]) - float(bid["cost"])
        if gain <= 0:
            continue  # this owner preferred not to speak
        # The agent's numeric reports are NOT comparable across agents.
        # Ranking by claimed urgency rewards exaggeration and voice capture.
        # Use a source-bound deterministic lottery only among volunteered bids.
        tie = hashlib.sha256(f"{cycle}:{agent}:{bid['bid_id']}".encode()).hexdigest()
        candidates.append((tie, agent, bid["bid_id"]))
    if not candidates:
        return {"decision": "silent", "speaker": None,
                "bid_id": None, "rejected": rejected}
    _, speaker, bid_id = max(candidates)
    return {"decision": "speak", "speaker": speaker,
            "bid_id": bid_id, "rejected": rejected}


def accept_selected_bid(result: Mapping, consumed_ids: set[str]) -> set[str]:
    """Pure post-publication transition. Call ONLY after a committed real turn.

    Failed generation, rejected publication and silence must never consume a bid.
    Persist the returned set atomically with the accepted public message.
    """
    if result.get("decision") != "speak" or result.get("speaker") not in AGENTS:
        return set(consumed_ids)
    bid_id = result.get("bid_id")
    if not _plain_id(bid_id):
        raise ValueError("missing selected bid")
    return set(consumed_ids) | {result["speaker"] + ":" + bid_id}
