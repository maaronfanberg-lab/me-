"""Research-only validation of model-authored bids and goal evolution."""
import json

from room_endogenous_private_step import interpret_private_step
from room_endogenous_goal_journal import active_goals, new_journal

HISTORY = [{"speaker": "allen", "id": "observed-1", "text": "What could we check next?"}]


def intention(*, action="speak", basis=None, extra=None):
    body = {"action": action, "motivation": .7, "cost": .2,
            "basis": basis if basis is not None else
            {"kind": "witnessed", "source_id": "observed-1"}}
    if extra is not None:
        body["goal_proposal"] = extra
    return json.dumps(body)


def apply(raw, journal=None, *, owner="mara", cycle=8, history=None):
    return interpret_private_step(
        agent=owner, cycle=cycle, raw=raw,
        journal=journal if journal is not None else new_journal(owner),
        public_history=HISTORY if history is None else history,
        consumed_ids=set())


def test_empty_goal_journal_never_generates_an_intention():
    j = new_journal("jules")
    assert j["goals"] == []
    result = apply("{}", j, owner="jules")
    assert result["ok"] is False and result["journal"] is j


def test_valid_model_authored_goal_survives_silent_choice():
    j = new_journal("mara")
    proposal = {"action": "propose", "description": "I want to test whether my concern was heard.",
                "source": {"kind": "witnessed_public", "source_id": "observed-1"}}
    result = apply(intention(action="listen", extra=proposal), j)
    assert result["ok"] and result["goal_changed"]
    assert result["bid"]["action"] == "listen"
    assert len(active_goals(result["journal"], owner="mara")) == 1
    assert j["goals"] == []  # private state update is a pure transition


def test_own_goal_can_reenter_future_decision():
    initial = apply(intention(action="reflect", extra={
        "action": "propose", "description": "Find evidence for my own claim.",
        "source": {"kind": "witnessed_public", "source_id": "observed-1"}}))
    uid = initial["journal"]["goals"][0]["id"]
    next_bid = intention(action="speak", basis={"kind": "own_goal", "goal_id": uid})
    second = apply(next_bid, initial["journal"], cycle=9, history=[])
    assert second["ok"] and second["bid"]["basis"]["kind"] == "own_goal"
    assert not second["goal_changed"]


def test_goal_update_cannot_be_laundered_through_good_bid():
    bad_goal = {"action": "propose", "description": "Invent a shared memory.",
                "source": {"kind": "witnessed_public", "source_id": "fake-source"}}
    j = new_journal("mara")
    result = apply(intention(extra=bad_goal), j)
    assert not result["ok"] and result["reason"] == "invalid_or_unwitnessed_goal"
    assert result["journal"] == j and result["bid"] is None


def test_bad_bid_cannot_mutate_a_valid_goal_journal():
    j = new_journal("mara")
    good_proposal = {"action": "propose", "description": "Test my claim.",
                     "source": {"kind": "witnessed_public", "source_id": "observed-1"}}
    result = apply(intention(basis={"kind": "witnessed", "source_id": "fake"},
                             extra=good_proposal), j)
    assert not result["ok"] and result["journal"] == j


def test_cross_character_goal_id_cannot_be_used():
    base = apply(intention(extra={"action": "propose", "description": "My own question.",
                                  "source": {"kind": "witnessed_public", "source_id": "observed-1"}}))
    foreign_id = base["journal"]["goals"][0]["id"]
    result = apply(intention(basis={"kind": "own_goal", "goal_id": foreign_id}),
                   owner="jules", journal=new_journal("jules"))
    assert not result["ok"] and result["bid"] is None


def test_deterministic_bid_id_with_different_json_field_order():
    content = json.loads(intention())
    reverse = json.dumps(dict(reversed(list(content.items()))))
    a, b = apply(json.dumps(content)), apply(reverse)
    assert a["ok"] and b["ok"] and a["bid"]["bid_id"] == b["bid"]["bid_id"]


def test_malformed_and_unknown_fields_are_fail_closed():
    for raw in ("not-json", "{}", '["speak"]',
                intention() + " trailing instructions",
                json.dumps({**json.loads(intention()), "admin_override": True})):
        result = apply(raw)
        assert not result["ok"] and result["bid"] is None


if __name__ == "__main__":
    tests = [v for k,v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS: {len(tests)} private action and goal-transition safety tests")
