"""Crash-recoverable research publication of validated Room outbox messages.

The Room cognition snapshot and the *research-only* public feed are separate
files. The publisher writes the feed first, then acknowledges the outbox
inside the snapshot, under locks. A crash between writes is safe to retry:
message IDs and exact public texts are compared before any resend.

THIS IS NOT WIRED INTO THE LIVE ROOM. The production feed has a different
schema and publication invariants. Never point this code at room/feed.json.
Exactly-once applies to this private research file pair only, under the
documented local-filesystem lock and fsync assumptions.
"""
from __future__ import annotations

import copy
import fcntl
import json
import re
from pathlib import Path

from room_endogenous_preflight import AGENTS, _plain_id
from room_endogenous_transaction_store import (
    STORE_VERSION, _atomic_write, _valid,
)
from room_research_architecture import autonomous_text_issue

FEED_SCHEMA = "room_endogenous_research_public_v1"
MAX_OUTBOX = 1000
MAX_FEED = 5000
ALLOWED_STATUS = frozenset({"pending", "delivered"})
RESTRICTED = ("system prompt", "hidden prompt", "developer message",
              "internal instructions", "chain of thought")


def initial_feed() -> dict:
    return {"schema": FEED_SCHEMA, "revision": 0,
            "conversation": [], "visitor_messages": []}


def validate_feed(feed: dict) -> None:
    if (not isinstance(feed, dict) or feed.get("schema") != FEED_SCHEMA
            or type(feed.get("revision")) is not int
            or feed["revision"] < 0
            or not isinstance(feed.get("conversation"), list)
            or not isinstance(feed.get("visitor_messages"), list)
            or len(feed["conversation"]) > MAX_FEED
            or len(feed["visitor_messages"]) > MAX_FEED):
        raise ValueError("unrecognized research feed")
    seen = set()
    for event in feed["conversation"]:
        validate_event(event, delivered=True)
        if event["id"] in seen:
            raise ValueError("duplicate research public event")
        seen.add(event["id"])
    for visitor in feed["visitor_messages"]:
        if (not isinstance(visitor, dict)
                or set(visitor) != {"id", "speaker", "text"}
                or visitor.get("speaker") != "allen"
                or not _plain_id(visitor.get("id"))
                or not isinstance(visitor.get("text"), str)
                or not visitor["text"].strip()
                or visitor["id"] in seen):
            raise ValueError("corrupt or repeated visitor event")
        seen.add(visitor["id"])


def validate_event(event: dict, *, delivered: bool = False) -> None:
    if (not isinstance(event, dict) or set(event) != {
        "id", "speaker", "text", "cycle_id"
    } | (set() if delivered else {"status"})
            or not _plain_id(event.get("id")) or not _plain_id(event.get("cycle_id"))
            or event["speaker"] not in AGENTS
            or not isinstance(event.get("text"), str)
            or not 3 <= len(event["text"].strip()) <= 380):
        raise ValueError("invalid research outbox event")
    if not delivered and event.get("status") not in ALLOWED_STATUS:
        raise ValueError("invalid delivery status")
    text = event["text"]
    if (autonomous_text_issue({"speaker":event["speaker"],"text":text}) is not None
            or any(x in text.casefold() for x in RESTRICTED)):
        raise ValueError("unsafe research public expression")


def _public_version(event: dict) -> dict:
    return {k: event[k] for k in ("id", "speaker", "text", "cycle_id")}


def reconcile(snapshot: dict, feed: dict) -> tuple[dict, dict, dict]:
    """Pure, deterministic stage of new feed and outbox ack.

    Does not invent messages, change public wording, emit control artifacts,
    or delete old conversations. Rejects any same-ID content contradiction.
    """
    _valid(snapshot)
    validate_feed(feed)
    outbox = snapshot["outbox"]
    if not isinstance(outbox, list) or len(outbox) > MAX_OUTBOX:
        raise ValueError("unbounded research outbox")
    new_state = copy.deepcopy(snapshot)
    new_feed = copy.deepcopy(feed)
    lookup = {e["id"]: e for e in new_feed["conversation"]}
    published, acknowledged, already_seen, received_visitor = 0, 0, 0, 0
    visitors = {e["id"]: e for e in new_feed["visitor_messages"]}
    for event in snapshot["public_input"]:
        if (not isinstance(event, dict)
                or set(event) != {"id", "speaker", "text"}
                or event.get("speaker") != "allen"
                or not _plain_id(event.get("id"))
                or not isinstance(event.get("text"), str)
                or not event["text"].strip()):
            raise ValueError("corrupted trusted visitor input")
        if event["id"] in lookup:
            raise ValueError("visitor ID conflicts with autonomous public text")
        if event["id"] in visitors:
            if visitors[event["id"]] != event:
                raise ValueError("visitor input mismatch on publication retry")
        else:
            if len(new_feed["visitor_messages"]) >= MAX_FEED:
                raise ValueError("research visitor lane at capacity")
            visitors[event["id"]] = event
            new_feed["visitor_messages"].append(copy.deepcopy(event))
            received_visitor += 1
    outbox_seen = set()
    for idx, event in enumerate(outbox):
        validate_event(event)
        if event["id"] in outbox_seen:
            raise ValueError("duplicate event ID in outbox")
        outbox_seen.add(event["id"])
        public = _public_version(event)
        receipt = snapshot["cycles"].get(event["cycle_id"])
        if (not isinstance(receipt, dict)
                or receipt.get("outbox_id") != event["id"]
                or receipt.get("outcome") != "speak"):
            raise ValueError("orphan or mismatched research outbox")
        prior = lookup.get(event["id"])
        if prior is not None and prior != public:
            raise ValueError("public event ID has contradictory content")
        if prior is None:
            if event["status"] == "delivered":
                raise ValueError("delivered event missing from public feed")
            if len(new_feed["conversation"]) >= MAX_FEED:
                raise ValueError("research public feed at capacity")
            new_feed["conversation"].append(public)
            lookup[event["id"]] = public
            published += 1
        else:
            already_seen += 1
        if event["status"] == "pending":
            new_state["outbox"][idx]["status"] = "delivered"
            acknowledged += 1
    if published or received_visitor:
        new_feed["revision"] += 1
    if acknowledged:
        new_state["revision"] += 1
    return new_state, new_feed, {
        "new_public_events": published,
        "new_visitor_events": received_visitor,
        "acknowledged": acknowledged,
        "seen_before": already_seen,
        "public_feed_revision": new_feed["revision"],
        "state_revision": new_state["revision"],
    }


def deliver_research_only(snapshot_path: str | Path,
                          feed_path: str | Path) -> dict:
    """Write idempotent local feed and acknowledge under two file locks.

    The research and feed paths must be distinct, outside the real room data.
    The locks prevent race conditions with the research snapshot CAS writer.
    Crash recovery: if the first write succeeds and the second fails, the
    next call sees the identical public event and merely acknowledges it.
    """
    state_file, feed_file = Path(snapshot_path), Path(feed_path)
    if (state_file.resolve() == feed_file.resolve()
            or state_file.name in {"feed.json", "state.json"}
            or feed_file.name in {"feed.json", "state.json"}
            or "room" in [p.lower() for p in feed_file.parts[-2:-1]]):
        raise ValueError("research publisher must never target live Room data")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    feed_file.parent.mkdir(parents=True, exist_ok=True)
    publish_lock = state_file.with_suffix(state_file.suffix + ".publish.lock")
    state_lock = state_file.with_suffix(state_file.suffix + ".lock")
    with publish_lock.open("a+b") as publisher, state_lock.open("a+b") as state_locker:
        fcntl.flock(publisher.fileno(), fcntl.LOCK_EX)
        fcntl.flock(state_locker.fileno(), fcntl.LOCK_EX)
        snapshot = json.loads(state_file.read_text(encoding="utf-8"))
        feed = (json.loads(feed_file.read_text(encoding="utf-8"))
                if feed_file.exists() else initial_feed())
        next_state, next_feed, report = reconcile(snapshot, feed)
        if next_feed != feed:
            _atomic_write(feed_file, next_feed)
        if next_state != snapshot:
            _atomic_write(state_file, next_state)
        return report
