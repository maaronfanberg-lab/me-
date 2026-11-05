"""One read-only endogenous Room beat with atomic candidate state transitions.

Model-authored natural speech, model-authored self-endorsement, independent
character contexts, strictly sourced public history, and a private outbox.
No direct public feed writer, workflow scheduling, or live Room import.

In a real deployment an external publisher MUST deduplicate outbox IDs and
acknowledge them before publishing. This prototype never claims pending
messages were delivered.
"""
from __future__ import annotations

import copy
import time
from collections.abc import Mapping

from room_endogenous_goal_journal import VERSION, active_goals
from room_endogenous_speech_option import build_request, parse
from room_endogenous_self_endorse import (
    endorsement_request, interpret_endorsement, apply_endorsement,
)
from room_endogenous_expression_v2 import choose_volunteers
from room_endogenous_transaction_store import apply_cycle
from room_endogenous_preflight import AGENTS
from room_endogenous_shadow import witnessed_tail

ORDER = ("sarah", "mara", "owen", "jules")
MAX_TOTAL_CALLS = 8
MAX_BEAT_SECONDS = 180.0


def _private_seed(agent: str, profile: dict) -> dict:
    psych = profile.get("psychology_v2")
    psych = psych if isinstance(psych, dict) else {}
    seed = psych.get("private_self")
    seed = seed if isinstance(seed, dict) else {}
    return {
        "what_i_currently_believe": str(seed.get("what_i_currently_believe")
                                        or "I do not have enough evidence yet.")[:160],
        "belief_confidence": .35,
        "what_just_changed": str(seed.get("what_just_changed")
                                 or "I am observing this exchange.")[:150],
        "last_updated_cycle": 0,
    }


def shadow_beat(*, snapshot: dict, cycle: int, cycle_id: str,
                public_history: list[dict], visitor_messages: list[dict],
                profiles: Mapping, speech_request, endorsement_request_model,
                awake: tuple[str, ...] = ORDER,
                budget_seconds: float = MAX_BEAT_SECONDS) -> tuple[dict, dict]:
    """Return candidate snapshot and diagnostics; never publish or mutate input."""
    if (type(cycle) is not int or cycle < 0 or not isinstance(cycle_id, str)
            or not isinstance(public_history, list) or not isinstance(visitor_messages, list)
            or not isinstance(profiles, Mapping) or not isinstance(snapshot, dict)
            or not callable(speech_request) or not callable(endorsement_request_model)
            or not isinstance(awake, tuple) or len(awake) > 4
            or len(set(awake)) != len(awake) or any(a not in AGENTS for a in awake)
            or type(budget_seconds) not in (float, int) or not 0 < budget_seconds <= MAX_BEAT_SECONDS):
        raise ValueError("invalid shadow beat")
    if not isinstance(snapshot.get("characters"), dict):
        raise ValueError("missing snapshot characters")
    previous = (snapshot.get("cycles") or {}).get(cycle_id)
    if isinstance(previous, dict):
        # A retry must not silently drop a *new* or altered visitor message.
        # Existing exact public sources may be supplied again idempotently.
        existing = {item.get("id"): item.get("text") for item in snapshot.get("public_input", [])
                    if isinstance(item, dict) and item.get("speaker") == "allen"}
        for item in visitor_messages:
            if (not isinstance(item, dict) or item.get("speaker") != "allen"
                    or item.get("id") not in existing
                    or item.get("text") != existing[item.get("id")]):
                raise ValueError("conflicting or new visitor input on replayed cycle")
        # Duplicate workflow delivery is an idempotent replay, not a reason
        # to let a stochastic model invent a different outcome for the cycle.
        return copy.deepcopy(snapshot), {
            "mode": "research_only_shadow", "cycle": cycle,
            "decision": previous["outcome"], "selected": None,
            "outbox_id": previous.get("outbox_id"), "model_calls": 0,
            "participant_outcomes": {}, "state_revision": snapshot["revision"],
            "committed_research_beat": False, "replayed": True,
            "live_room_written": False, "public_dialogue_published": False,
        }
    history = public_history + visitor_messages
    witnessed = witnessed_tail(history)
    attempts = {}
    candidates = {}
    calls = 0
    started = time.monotonic()
    for agent in awake:
        if calls >= MAX_TOTAL_CALLS or time.monotonic()-started >= budget_seconds:
            attempts[agent] = "inference_budget_exhausted"
            continue
        profile = profiles.get(agent)
        owned = snapshot["characters"].get(agent)
        if not isinstance(profile, dict) or not isinstance(owned, dict):
            attempts[agent] = "owner_state_unavailable"
            continue
        journal = owned.get("journal")
        if not isinstance(journal, dict) or journal.get("owner") != agent or journal.get("schema") != VERSION:
            attempts[agent] = "invalid_owner_journal"
            continue
        private = owned.get("private_state") or _private_seed(agent, profile)
        if not isinstance(private, dict):
            attempts[agent] = "invalid_private_state"
            continue
        if not witnessed and not active_goals(journal, owner=agent):
            attempts[agent] = "no_public_source_or_own_goal"
            continue
        try:
            request = build_request(agent=agent, profile=profile,
                                    private_state=private, journal=journal,
                                    public_history=history)
            remaining = budget_seconds-(time.monotonic()-started)
            if remaining <= 0:
                attempts[agent] = "inference_budget_exhausted"
                continue
            raw = speech_request(request, min(34.0,remaining))
            calls += 1
            candidate = parse(agent=agent, cycle=cycle, raw=raw,
                              public_history=history, journal=journal,
                              private_state=private, consumed_ids=set(snapshot.get("consumed_bids", [])))
            if not candidate.get("ok"):
                attempts[agent] = "invalid_or_unwitnessed_speech_candidate"
                continue
            if candidate.get("utterance"):
                remaining = budget_seconds-(time.monotonic()-started)
                if remaining <= 0:
                    candidates[agent] = apply_endorsement(candidate, None)
                    attempts[agent] = "no_time_for_self_endorsement"
                    continue
                review = endorsement_request(agent=agent, profile=profile,
                                             private_state=private, journal=journal,
                                             public_history=history,
                                             draft=candidate["utterance"])
                response = endorsement_request_model(review, min(34.0,remaining))
                calls += 1
                endorsement = interpret_endorsement(response)
                candidate = apply_endorsement(candidate, endorsement)
                attempts[agent] = "self_endorsed" if endorsement is True else (
                    "self_declined" if endorsement is False else "invalid_self_review")
            else:
                attempts[agent] = "owner_silent"
            candidates[agent] = candidate
        except Exception:
            attempts[agent] = "model_unavailable_or_invalid"
    selected = choose_volunteers(
        cycle=cycle, public_history=history,
        candidates=candidates,
        consumed_ids=set(snapshot.get("consumed_bids", [])), awake=awake)
    next_state, changed = apply_cycle(
        snapshot, expected_revision=snapshot["revision"],
        cycle=cycle, cycle_id=cycle_id, candidates=candidates,
        selected=selected, visitor_messages=visitor_messages)
    return next_state, {
        "mode": "research_only_shadow",
        "cycle": cycle,
        "decision": selected["decision"],
        "selected": selected.get("speaker"),
        "outbox_id": next_state["cycles"][cycle_id]["outbox_id"],
        "model_calls": calls,
        "participant_outcomes": attempts,
        "state_revision": next_state["revision"],
        "committed_research_beat": changed,
        "live_room_written": False,
        "public_dialogue_published": False,
    }
