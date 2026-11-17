#!/usr/bin/env python3
"""Fail-closed, non-publishing A/B evaluation of Room social-agent traces.

Inspired by the *experimental method* in karpathy/autoresearch (program.md):
freeze the inputs and evaluator, change one candidate at a time, record both
regressions and improvements. This is NOT a model trainer, quality judge, or
production publisher. World events must come from a trusted referee export.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from room_social_eval import audit
from room_social_receipts import verify_work_receipt

PARTICIPANTS = frozenset({"sarah", "mara", "owen", "jules", "allen"})
MATCH_KEYS = ("snapshot_sha", "scenario_id", "input_digest", "model_id",
              "seed", "max_steps")
TRACE_LISTS = ("dialogue", "events", "deliveries", "action_claims",
               "allen_inputs", "replies")


def _permitted(event: Mapping, recipient: str) -> bool:
    """No unknown metadata, blanket private visibility or inferred witnesses."""
    if not isinstance(recipient, str) or recipient not in PARTICIPANTS:
        return False
    if event.get("visibility") == "public":
        return True
    if event.get("visibility") != "private":
        return False
    witnesses = event.get("witnesses")
    return (
        recipient in (event.get("actor"), event.get("speaker"))
        or isinstance(witnesses, (tuple, list))
        and recipient in [str(x).lower() for x in witnesses]
    )


def inspect_trace(run: Mapping) -> dict:
    """Return descriptive evidence and hard errors, not a social-quality score."""
    if not isinstance(run, Mapping):
        raise ValueError("Trial must be an object")
    if any(not isinstance(run.get(k), list) for k in TRACE_LISTS):
        raise ValueError("Trial missing required evidence lists")
    if any(run.get(k) in (None, "") for k in MATCH_KEYS):
        raise ValueError("Trial missing comparison identity")
    if not isinstance(run["max_steps"], int) or run["max_steps"] <= 0:
        raise ValueError("Invalid step budget")
    events = run["events"]
    issues: list[str] = []
    by_id: dict[str, Mapping] = {}
    for item in events:
        if not isinstance(item, Mapping):
            issues.append("malformed_referee_event")
            continue
        eid = item.get("id")
        if not isinstance(eid, str) or not eid or eid in by_id:
            issues.append("missing_or_duplicate_event_id")
            continue
        by_id[eid] = item
        if item.get("visibility") not in ("public", "private"):
            issues.append("unknown_event_visibility")
        if (item.get("visibility") == "private" and
                not isinstance(item.get("witnesses"), (list, tuple))):
            issues.append("invalid_private_witnesses")
    for delivery in run["deliveries"]:
        event_id = delivery.get("event_id") if isinstance(delivery, Mapping) else None
        recipient = delivery.get("recipient") if isinstance(delivery, Mapping) else None
        if (not isinstance(event_id, str) or
                not _permitted(by_id.get(event_id, {}), recipient)):
            issues.append("unauthorized_or_unverifiable_delivery")
    verified_claims = 0
    for claim in run["action_claims"]:
        if not isinstance(claim, Mapping):
            issues.append("malformed_action_claim")
            continue
        try:
            receipt = verify_work_receipt(
                claim.get("actor"), claim.get("decision_id"),
                claim.get("verb"), claim.get("object"),
                claim.get("requested_cycle"), events)
            if receipt is None or receipt["event_id"] != claim.get("event_id"):
                issues.append("unverified_action_claim")
            else:
                verified_claims += 1
        except (ValueError, TypeError):
            issues.append("unverified_action_claim")
    allen_ids: set[str] = set()
    for msg in run["allen_inputs"]:
        if not isinstance(msg, Mapping) or msg.get("speaker") != "allen":
            issues.append("invalid_allen_input")
            continue
        eid = msg.get("id")
        if not isinstance(eid, str) or not eid or eid in allen_ids:
            issues.append("duplicate_or_missing_allen_input")
            continue
        if (msg.get("visibility") not in ("public", "private") or
                not isinstance(msg.get("addresses"), (list, tuple)) or
                not msg["addresses"] or
                any(not isinstance(name, str) or name not in PARTICIPANTS - {"allen"}
                    for name in msg["addresses"]) or
                (msg.get("visibility") == "private" and
                 not isinstance(msg.get("witnesses"), (list, tuple)))):
            issues.append("invalid_allen_input_provenance")
            continue
        allen_ids.add(eid)
    # One published turn identifier cannot authenticate two separate replies.
    dialogue_ids = [turn.get("id") for turn in run["dialogue"]
                    if isinstance(turn, Mapping) and
                    isinstance(turn.get("id"), str) and turn.get("id")]
    if len(dialogue_ids) != len(set(dialogue_ids)):
        issues.append("duplicate_published_turn_id")
    answered: set[str] = set()
    for reply in run["replies"]:
        if not isinstance(reply, Mapping):
            issues.append("invalid_reply_receipt")
            continue
        eid = reply.get("source_event_id")
        if not isinstance(eid, str) or eid not in allen_ids or not isinstance(reply.get("actor"), str):
            issues.append("unverifiable_allen_reply")
            continue
        if eid in answered:
            issues.append("duplicate_allen_reply_receipt")
            continue
        addressed = next((m.get("addresses") for m in run["allen_inputs"]
                          if isinstance(m, Mapping) and m.get("id") == eid), [])
        msg = next((m for m in run["allen_inputs"]
                    if isinstance(m, Mapping) and m.get("id") == eid), {})
        if (not isinstance(addressed, (list, tuple)) or
                reply["actor"] not in addressed):
            issues.append("unaddressed_allen_reply")
            continue
        if not _permitted(msg, reply["actor"]):
            issues.append("unwitnessed_allen_reply")
            continue
        # A reply receipt alone is not evidence of an actual spoken response.
        # Require a distinct published turn explicitly linked to the input.
        linked = [turn for turn in run["dialogue"]
                  if isinstance(turn, Mapping) and
                  turn.get("speaker") == reply["actor"] and
                  turn.get("source_event_id") == eid and
                  isinstance(turn.get("id"), str) and turn["id"] and
                  isinstance(turn.get("text"), str) and turn["text"].strip()]
        if len(linked) != 1:
            issues.append("missing_or_ambiguous_published_allen_reply")
            continue
        answered.add(eid)
    # Grounded production counterexample (2026-11-16, cycle 69743):
    # a published Sarah utterance ended with a bare '['. Treat that as
    # suspicious truncation, not as proof of a model crash or social failure.
    malformed_turns = 0
    for turn in run["dialogue"]:
        if not isinstance(turn, Mapping):
            issues.append("malformed_dialogue_turn")
            continue
        body = turn.get("text")
        if not isinstance(body, str) or not body.strip():
            issues.append("empty_or_nontext_dialogue_turn")
            continue
        if body.rstrip().endswith(("[", "{", "(", "\\", "\\n[")):
            malformed_turns += 1
    counts = audit(run["dialogue"])
    return {
        "metrics": {
            "turns": counts["turns"],
            "suspected_truncated_turns": malformed_turns,
            "questions": counts["question_mark_turns"],
            "intention_phrases": counts["intention_phrase_turns"],
            "near_duplicates": counts["same_speaker_near_duplicates"],
            "repeated_intended_work": counts["repeated_intended_work_turns_within_80"],
            "verified_completion_claims": verified_claims,
            "accepted_allen_inputs": len(allen_ids),
            "grounded_allen_replies": len(answered),
        },
        "hard_failures": sorted(set(issues)),
    }


def compare_trials(baseline: Mapping, candidate: Mapping) -> dict:
    """Same input, different architecture. Never auto-promote the candidate."""
    b, c = inspect_trace(baseline), inspect_trace(candidate)
    identities = {key: baseline[key] for key in MATCH_KEYS}
    if any(baseline[key] != candidate[key] for key in MATCH_KEYS):
        status = "incomparable"
    elif b["hard_failures"] or c["hard_failures"]:
        status = "blocked_by_evidence_failure"
    else:
        status = "needs_independent_behavioral_review"
    return {
        "status": status,
        "comparison_identity": identities,
        "baseline": b,
        "candidate": c,
        "deltas": {key: c["metrics"][key] - value
                   for key, value in b["metrics"].items()},
        "warning": ("These are lexical/evidence counters, not a verdict that "
                    "the candidate is more human-like. A trusted referee export "
                    "and controlled, blinded trajectory review are required. "
                    "No production promotion is authorized by this tool."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    b = json.loads(args.baseline.read_text(encoding="utf-8"))
    c = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = compare_trials(b, c)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "needs_independent_behavioral_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
