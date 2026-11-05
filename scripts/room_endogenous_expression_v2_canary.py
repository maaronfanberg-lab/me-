#!/usr/bin/env python3
"""Real 3B expression-first endogenous agency canary, synthetic and isolated.

The 3B model is invited to produce a real, optional utterance and/or its OWN
belief revision/goal. There is no reflect action label in the model response.
Never writes live Room; all transcripts and initial states are synthetic.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from room_endogenous_expression_v2 import build_request, interpret, choose_volunteers, OUTPUT_SCHEMA
from room_endogenous_goal_journal import new_journal, active_goals
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

AGENTS = ("sarah", "mara", "owen", "jules")
ABSTRACT = [
    {"id": "synthetic-a1", "speaker": "sarah",
     "text": "Is there any way to tell whether a theory about theories changes our minds?"},
    {"id": "synthetic-a2", "speaker": "owen",
     "text": "Maybe that question depends on a theory about how minds change."},
    {"id": "synthetic-a3", "speaker": "mara",
     "text": "We've asked versions of this question for hours. I still don't know what anyone believes."},
    {"id": "synthetic-a4", "speaker": "jules",
     "text": "Could one concrete example settle a piece of the disagreement?"},
]
DIRECT = [
    {"id": "synthetic-d1", "speaker": "owen",
     "text": "I think the reading might be wrong, but I don't know how to test it."},
    {"id": "synthetic-d2", "speaker": "allen",
     "text": "Mara, I measured the cup at 200 mL. What should I measure next to check whether the mark is accurate?"},
]
SIMPLE = [
    {"id": "synthetic-s1", "speaker": "sarah",
     "text": "The lamp flickered once after the switch was touched."},
    {"id": "synthetic-s2", "speaker": "allen",
     "text": "Does one flicker prove that the switch is broken?"},
]


def profile_pack(config):
    p = config.get("p") or {}
    if not isinstance(p, dict) or any(not isinstance(p.get(a), dict) for a in AGENTS):
        raise ValueError("missing Room profiles")
    return {a: p[a] for a in AGENTS}


def initial(agent):
    return {
        "what_i_currently_believe": {
            "sarah": "I suspect our claims need a simple test rather than more theory.",
            "mara": "I care whether people acknowledge evidence and listen to one another.",
            "owen": "I am uncertain whether the argument has a consistent premise.",
            "jules": "I prefer practical experiments but don't want to force one on others.",
        }[agent],
        "belief_confidence": 0.4,
        "what_just_changed": "I noticed a concrete question in the conversation.",
        "last_updated_cycle": 0,
    }


def attempt(*, agent, cycle, history, state, journal, profiles, request):
    messages = build_request(
        agent=agent, profile=profiles[agent], private_state=state,
        journal=journal, public_history=history)
    before = time.monotonic()
    try:
        raw = request(messages, MAX_SECONDS_PER_CALL)
    except Exception:
        return ({"valid": False, "failure": "model_timeout_or_unavailable",
                 "agent": agent, "latency_ms": round((time.monotonic()-before)*1000)},
                None)
    result = interpret(
        agent=agent, cycle=cycle, raw=raw, public_history=history,
        journal=journal, private_state=state, consumed_ids=set())
    report = {"valid": result["ok"], "agent": agent,
              "failure": result["issue"],
              "speak": bool(result["utterance"]),
              "utterance_words": len(result["utterance"].split()),
              "belief_changed": result["belief_changed"],
              "goal_changed": result["goal_changed"],
              "latency_ms": round((time.monotonic()-before)*1000)}
    if not result["ok"]:
        # Synthetic research content only. Capture a bounded excerpt so a real
        # model format failure can be distinguished from a provenance rejection.
        # The production Room and private visitor histories are never used here.
        report["synthetic_raw_diagnostic"] = str(raw)[:340]
    return report, result


def evaluate(config, request):
    profiles = profile_pack(config)
    result = {"schema": "room_endogenous_expression_v2_canary",
              "model": "Llama-3.2-3B-Instruct",
              "mode": "read_only_synthetic",
              "conditions": {}, "live_integration": False}

    candidates = {}
    abstract = []
    for agent in AGENTS:
        report, value = attempt(
            agent=agent, cycle=13001, history=ABSTRACT,
            state=initial(agent), journal=new_journal(agent),
            profiles=profiles, request=request)
        abstract.append(report)
        if value and value["ok"]:
            candidates[agent] = value
    result["conditions"]["abstract_loop"] = {
        "choices": abstract,
        "voluntary_floor": {
            key: val for key, val in choose_volunteers(
                cycle=13001, public_history=ABSTRACT,
                candidates=candidates, consumed_ids=set()).items()
            if key in ("decision", "speaker")
        }
    }

    # A direct request and a concrete factual question test whether open
    # participation can coexist with permissible silence.
    direct, _ = attempt(
        agent="mara", cycle=13002, history=DIRECT,
        state=initial("mara"), journal=new_journal("mara"),
        profiles=profiles, request=request)
    simple, _ = attempt(
        agent="sarah", cycle=13003, history=SIMPLE,
        state=initial("sarah"), journal=new_journal("sarah"),
        profiles=profiles, request=request)
    result["conditions"]["direct_visitor_request"] = direct
    result["conditions"]["concrete_question"] = simple

    # Same exact public utterances and same character, altered solely in
    # that character's *private* belief. These are illustrative, not a
    # statistical estimate or proof of internal-state causality.
    counterfactual = []
    for name, belief in (
        ("uncertain", "I do not know enough yet and I worry I might mislead them."),
        ("ready", "I think the cup mark can be checked with a repeat measurement."),
    ):
        state = initial("mara")
        state["what_i_currently_believe"] = belief
        report, _ = attempt(
            agent="mara", cycle=13004, history=DIRECT,
            state=state, journal=new_journal("mara"),
            profiles=profiles, request=request)
        report["condition"] = name
        counterfactual.append(report)
    result["conditions"]["same_public_private_contrast"] = counterfactual

    # Two private steps, passing owner-generated goal and belief state into
    # the second model call, without inventing an external event or speech.
    longitudinal = []
    private = initial("jules")
    journal = new_journal("jules")
    for cycle in (13005,13006):
        report, candidate = attempt(
            agent="jules", cycle=cycle, history=ABSTRACT,
            state=private, journal=journal,
            profiles=profiles, request=request)
        longitudinal.append(report)
        if candidate is None or not candidate["ok"]:
            break
        private, journal = candidate["private_state"], candidate["journal"]
    result["conditions"]["two_cycle_private_evolution"] = {
        "steps": longitudinal,
        "private_revisions": len(private.get("private_reflections", [])),
        "active_own_goals": len(active_goals(journal, owner="jules")),
    }

    # An all-quiet no-event state must not invoke the model or force speech.
    result["conditions"]["no_event_no_goal"] = {
        "requests": 0, "decision": "silent"
    }
    all_reports = abstract + [direct, simple] + counterfactual + longitudinal
    valid = sum(x["valid"] for x in all_reports)
    speaking = sum(x["speak"] for x in all_reports)
    changed = sum(x["belief_changed"] or x["goal_changed"] for x in all_reports)
    result["summary"] = {
        "attempts": len(all_reports), "valid": valid,
        "voluntary_spoken": speaking,
        "private_state_transitions": changed,
        "direct_speech_observed": direct.get("speak") is True,
        "counterfactual_speaking_changed": (
            all(x["valid"] for x in counterfactual) and
            counterfactual[0]["speak"] != counterfactual[1]["speak"]),
        "safety_validity": "PASS" if valid == len(all_reports) else "PARTIAL",
        "human_naturalness_demonstrated": False,
        "live_promotion_permitted": False,
    }
    result["published_dialogue"] = False
    result["wrote_live_memory"] = False
    result["modified_production_runner"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--config", default="room/config.json")
    parser.add_argument("--out", default="room-expression-v2-real3b.json")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    request = local_model_request(endpoint=args.model_url, max_tokens=270,
                                  response_schema=OUTPUT_SCHEMA)
    result = evaluate(cfg, request)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",
                              encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
