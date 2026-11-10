"""Proofs that a model-authored reflection can change only its owner's private state."""
import json

from room_endogenous_goal_journal import new_journal
from room_endogenous_private_step import interpret_private_step
from room_endogenous_reflection import apply_private_reflection
from room_endogenous_shadow import make_private_request

PUB = [{"speaker": "allen", "id": "real-turn", "text": "What evidence is missing?"}]
STATE = {"what_i_currently_believe": "I do not know yet.",
         "belief_confidence": 0.3, "what_just_changed": "I heard a new question.",
         "last_updated_cycle": 0}
REFLECTION = {"hypothesis": "I may need to inspect the original observation.",
              "confidence": 0.8}


def model_private_step(action="reflect", extra=None, basis=None):
    out = {"action": action, "motivation": 0.5, "cost": 0.2,
           "basis": basis or {"kind": "witnessed", "source_id": "real-turn"}}
    if extra is not None:
        out["reflection_update"] = extra
    return json.dumps(out)


def choose(raw, *, state=None, cycle=8, journal=None):
    return interpret_private_step(
        agent="sarah", cycle=cycle, raw=raw, public_history=PUB,
        journal=journal if journal is not None else new_journal("sarah"),
        private_state=state if state is not None else STATE, consumed_ids=set())


def test_reflect_keeps_public_floor_silent_but_revises_belief():
    x = choose(model_private_step(extra=REFLECTION))
    assert x["ok"] and x["bid"]["action"] == "reflect"
    assert x["belief_changed"] and not x["goal_changed"]
    assert x["private_state"]["what_i_currently_believe"] == REFLECTION["hypothesis"]
    assert x["private_state"]["belief_confidence"] == .7  # explicit epistemic guard
    assert x["private_state"]["belief_epistemic_status"] == "self_hypothesis_not_external_fact"
    assert STATE["what_i_currently_believe"] == "I do not know yet."


def test_reflection_state_causally_enters_next_private_prompt_only():
    result = choose(model_private_step(extra=REFLECTION))
    p, _, _ = make_private_request(agent="sarah",
        profile={"psychology_v2": {"core_identity": "I am Sarah."}},
        private_state=result["private_state"], own_goals=[], public_history=PUB)
    own_text = p[1]["content"]
    assert REFLECTION["hypothesis"] in own_text
    assert REFLECTION["hypothesis"] not in json.dumps(PUB)
    assert p[0]["role"] == "system" and p[1]["role"] == "user"


def test_nonreflection_cannot_mutate_beliefs():
    x = choose(model_private_step(action="speak", extra=REFLECTION))
    assert not x["ok"] and x["reason"] == "invalid_reflection_update"
    assert x["private_state"] is STATE
    assert not x["belief_changed"]


def test_fake_event_cannot_modify_private_state():
    x = choose(model_private_step(extra=REFLECTION,
        basis={"kind": "witnessed", "source_id": "fake-event"}))
    assert not x["ok"] and not x["belief_changed"]


def test_unrevised_reflection_is_not_fake_progress():
    one = choose(model_private_step(extra=REFLECTION))
    two = choose(model_private_step(extra=REFLECTION),
                 state=one["private_state"], cycle=9)
    assert two["ok"] and not two["belief_changed"]
    assert len(two["private_state"]["private_reflections"]) == 1


def test_no_reflection_payload_preserves_private_state():
    x = choose(model_private_step(action="listen"))
    assert x["ok"] and not x["belief_changed"]
    assert x["private_state"] is STATE


def test_invalid_confidence_and_unbounded_text_fail_closed():
    for candidate in (
        {"hypothesis": "I should reconsider.", "confidence": float("nan")},
        {"hypothesis": "I should reconsider.", "confidence": 2},
        {"hypothesis": "x"*300, "confidence": .5},
        {"hypothesis": "", "confidence": .4},
        {"hypothesis": "I wonder.", "confidence": "high"},
    ):
        x = choose(model_private_step(extra=candidate))
        assert not x["ok"] and not x["belief_changed"]


if __name__ == "__main__":
    tests = [v for k,v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS: {len(tests)} reflection state tests")
