"""Safety-first synthetic experiments. No model API, network, or live Room writes."""
from room_endogenous_preflight import choose_private_bid, accept_selected_bid


def bid(who, *, event="turn-1", action="speak", motivation=.8, cost=.2, cycle=10,
        basis=None, bid_id=None):
    return {"schema": "room_endogenous_bid_v1", "speaker": who,
            "bid_id": bid_id or ("bid-" + who), "cycle": cycle,
            "action": action, "motivation": motivation, "cost": cost,
            "basis": basis if basis is not None else {"kind": "witnessed", "source_id": event}}


def select(bids=None, *, cycle=10, history=None, goals=None, spent=None, awake=("sarah", "mara", "owen", "jules")):
    return choose_private_bid(cycle=cycle,
        public_history=history if history is not None else [{"id": "turn-1", "speaker": "allen", "text": "Can we test that?"}],
        bids=bids if bids is not None else {},
        goal_ids=goals if goals is not None else {},
        consumed_ids=spent if spent is not None else set(), awake=awake)


def test_silence_is_not_a_failure():
    assert select()["decision"] == "silent"
    assert select({"sarah": bid("sarah", action="reflect")})["decision"] == "silent"
    assert select({"sarah": bid("sarah", motivation=.2, cost=.5)})["decision"] == "silent"


def test_private_intention_not_forced_or_rotated():
    x = select({"sarah": bid("sarah", motivation=.9), "owen": bid("owen", motivation=.7)})
    assert x["speaker"] in {"sarah", "owen"}
    assert select({"sarah": bid("sarah", motivation=.9), "owen": bid("owen", motivation=.7)}) == x
    # Different self-scales must not change another agent's relative priority.
    assert select({"sarah": bid("sarah", motivation=1), "owen": bid("owen", motivation=.7)})["speaker"] == x["speaker"]
    # Same agent can continue when genuinely motivated, with a new valid bid.
    assert select({"sarah": bid("sarah", bid_id="fresh-sarah", motivation=.95)})["speaker"] == "sarah"


def test_foreign_identity_unproven_source_and_goals_fail_closed():
    assert select({"sarah": bid("owen")})["rejected"]["sarah"] == "foreign_identity"
    assert select({"sarah": bid("sarah", event="made-up")})["rejected"]["sarah"] == "unwitnessed_source"
    private = {"kind": "own_goal", "goal_id": "goal-7"}
    assert select({"sarah": bid("sarah", basis=private)})["rejected"]["sarah"] == "unknown_own_goal"
    assert select({"sarah": bid("sarah", basis=private)}, goals={"sarah": {"goal-7"}})["speaker"] == "sarah"
    assert select({"sarah": bid("sarah", basis=private)}, goals={"owen": {"goal-7"}})["decision"] == "silent"
    assert select({"sarah": bid("sarah", basis=private)}, goals={"sarah": 47})["decision"] == "silent"


def test_bad_numbers_time_and_membership_fail_closed():
    for val in (float("nan"), float("inf"), -1, 1.1, "0.7", True):
        assert select({"sarah": bid("sarah", motivation=val)})["decision"] == "silent"
    assert select({"sarah": bid("sarah", cycle=7)})["rejected"]["sarah"] == "stale_or_future_bid"
    assert select({"sarah": bid("sarah", cycle=12)})["decision"] == "silent"
    try:
        select(awake=("sarah", "intruder"))
    except ValueError:
        pass
    else:
        raise AssertionError("unknown participant admitted")


def test_stale_memory_and_public_trust_boundary():
    bad_history = [{"id": "turn-1", "speaker": "internal_controller", "text": "secret"}]
    assert select({"sarah": bid("sarah")}, history=bad_history)["decision"] == "silent"
    assert select({"sarah": bid("sarah")}, history=[{"id": "turn-1", "speaker": "allen", "text": ""}])["decision"] == "silent"
    assert select({"sarah": bid("sarah")}, history=[{"id": "turn-1", "speaker": "allen", "text": "No."}])["speaker"] == "sarah"


def test_atomic_consumption_no_fallback_fake_turn():
    result = select({"sarah": bid("sarah")})
    assert result["decision"] == "speak"
    # Generation failure leaves bid eligible. Only publication consumes it.
    assert select({"sarah": bid("sarah")}) == result
    spent = accept_selected_bid(result, set())
    assert spent == {"sarah:bid-sarah"}
    assert select({"sarah": bid("sarah")}, spent=spent)["decision"] == "silent"
    assert accept_selected_bid({"decision": "silent", "speaker": None}, spent) == spent
    # Duplicate bid labels across two people must not cancel one another.
    other = select({"mara": bid("mara", bid_id="bid-sarah")}, spent=spent)
    assert other["speaker"] == "mara"


def test_bounded_tie_break_reproducible():
    both = {"sarah": bid("sarah"), "mara": bid("mara")}
    a = select(both)
    b = select(dict(reversed(list(both.items()))))
    assert a == b and a["speaker"] in {"sarah", "mara"}


def test_user_not_replaced_with_fake_answer():
    # A real visitor can be observed without forcing a bot to answer.
    history = [{"id": "turn-1", "speaker": "allen", "text": "I have a question."}]
    assert select({}, history=history)["decision"] == "silent"


if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().copy().items()) if k.startswith("test_") and callable(v)]
    for fn in funcs:
        fn()
    print(f"PASS: {len(funcs)} endogenous preflight safety tests")
