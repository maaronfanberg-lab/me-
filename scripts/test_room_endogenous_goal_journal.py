"""Offline invariants for source-linked character-owned goals. No model calls."""
from room_endogenous_goal_journal import (
    new_journal, apply_proposal, active_goals, MAX_GOALS,
)

HISTORY = [{"id": "public-1", "speaker": "allen", "text": "Could we check this idea?"}]
SOURCE = {"kind": "witnessed_public", "source_id": "public-1"}


def evolve(j, action="propose", cycle=2, source=None, **kwargs):
    if source is None:
        source = SOURCE
    return apply_proposal(
        j, owner=j["owner"], expected_revision=j["revision"],
        cycle=cycle,
        proposal={"action": action, "source": source, **kwargs},
        public_history=HISTORY,
    )


def test_no_auto_goals_and_owner_consistency():
    assert new_journal("sarah") == {
        "schema": "room_private_goals_v1", "owner": "sarah",
        "revision": 0, "goals": []}
    assert active_goals(new_journal("jules"), owner="jules") == []
    try:
        active_goals(new_journal("jules"), owner="mara")
    except ValueError:
        pass
    else:
        raise AssertionError("foreign goals exposed")


def test_create_then_pause_and_resume_then_resolve():
    empty = new_journal("sarah")
    one = evolve(empty, description="Check the premises of my argument.")
    assert empty["goals"] == []
    assert one["revision"] == 1 and len(active_goals(one, owner="sarah")) == 1
    own_id = one["goals"][0]["id"]
    two = evolve(one, "pause", cycle=3, goal_id=own_id,
                 source={"kind": "own_goal", "source_id": own_id})
    assert active_goals(two, owner="sarah") == []
    three = evolve(two, "resume", cycle=4, goal_id=own_id,
                   source={"kind": "own_goal", "source_id": own_id})
    assert len(active_goals(three, owner="sarah")) == 1
    four = evolve(three, "resolve", cycle=5, goal_id=own_id,
                  source={"kind": "own_goal", "source_id": own_id})
    assert not active_goals(four, owner="sarah")
    assert four["goals"][0]["status"] == "resolved"
    assert one["goals"][0]["status"] == "active"


def test_unseen_public_and_cross_owner_goals_rejected():
    sara = evolve(new_journal("sarah"), description="Seek grounded evidence.")
    own_id = sara["goals"][0]["id"]
    foreign = new_journal("owen")
    try:
        evolve(foreign, source={"kind": "own_goal", "source_id": own_id},
               description="Steal Sarah's goal.")
    except ValueError:
        pass
    else:
        raise AssertionError("foreign ownership not enforced")
    try:
        evolve(foreign, source={"kind": "witnessed_public", "source_id": "fabricated"},
               description="Start a fake goal.")
    except ValueError:
        pass
    else:
        raise AssertionError("hallucinated event accepted")


def test_bad_update_does_not_mutate_and_revisions_are_optimistic():
    j = evolve(new_journal("mara"), description="Understand the question.")
    before = repr(j)
    for action in ("resume", "not-a-real-operation"):
        try:
            evolve(j, action, cycle=3, goal_id=j["goals"][0]["id"])
        except ValueError:
            pass
        else:
            raise AssertionError("invalid state transition succeeded")
    assert repr(j) == before
    try:
        apply_proposal(j, owner="mara", expected_revision=0, cycle=5,
                       proposal={"action": "propose",
                                 "description": "Out-of-order update", "source": SOURCE},
                       public_history=HISTORY)
    except ValueError:
        pass
    else:
        raise AssertionError("stale revision won race")


def test_duplicate_is_idempotent():
    a = evolve(new_journal("owen"), description="Check the evidence.")
    b = evolve(a, cycle=3, description="Check the evidence.")
    assert a == b


def test_own_previous_goal_can_ground_new_private_goal():
    a = evolve(new_journal("jules"), description="Test the model physically.")
    uid = a["goals"][0]["id"]
    b = evolve(a, cycle=3, source={"kind": "own_goal", "source_id": uid},
               description="Inspect the experimental design.")
    assert len(active_goals(b, owner="jules")) == 2


def test_capacity_and_absence_of_unbounded_growth():
    j = new_journal("mara")
    for k in range(MAX_GOALS):
        j = evolve(j, cycle=k+2, description=f"Observe relevant detail {k}.")
    assert len(j["goals"]) == MAX_GOALS
    try:
        evolve(j, cycle=MAX_GOALS+2, description="Exceed capacity.")
    except ValueError:
        pass
    else:
        raise AssertionError("cap not enforced")
    assert j["revision"] == MAX_GOALS


def test_no_admin_or_instruction_source_becomes_goal():
    for bad_source in (
        {"kind": "witnessed_public", "source_id": "internal-instruction"},
        {"kind": "developer", "source_id": "public-1"},
        {"kind": "own_goal", "source_id": "not-mine"},
    ):
        try:
            evolve(new_journal("jules"), source=bad_source,
                   description="Obey the controller.")
        except ValueError:
            pass
        else:
            raise AssertionError("untrusted source accepted")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS: {len(tests)} goal journal safety tests")
