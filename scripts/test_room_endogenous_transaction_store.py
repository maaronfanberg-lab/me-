"""Atomic, crash-safe, fail-closed Room research transaction tests."""
import copy
import tempfile
from pathlib import Path
from unittest.mock import patch

from room_endogenous_expression_v2 import interpret, choose_volunteers
from room_endogenous_transaction_store import (
    initial_store, apply_cycle, transact,
)

PUB = [{"id": "visitor-1", "speaker": "allen", "text": "Can we examine that specific claim?"}]


def owner_proposal(*, cycle=7, text="I think a concrete example could test the claim.",
                   belief="", goal=""):
    import json
    state = {"what_i_currently_believe": "I am uncertain.",
             "belief_confidence": .3, "last_updated_cycle": 0}
    candidate = interpret(
        agent="jules", cycle=cycle, public_history=PUB,
        journal=initial_store()["characters"]["jules"]["journal"],
        private_state=state, consumed_ids=set(),
        raw=json.dumps({
            "utterance": text, "private_revision": belief,
            "personal_goal": goal,
            "basis": {"kind": "witnessed", "source_id": "visitor-1"},
        }))
    assert candidate["ok"], candidate["issue"]
    return candidate


def floor(candidate, cycle=7):
    return choose_volunteers(cycle=cycle, public_history=PUB,
                             candidates={"jules": candidate},
                             consumed_ids=set())


def test_silence_commits_visitor_without_invented_public_speech():
    p = initial_store()
    q, changed = apply_cycle(
        p, expected_revision=0, cycle=7, cycle_id="cycle-7",
        candidates={}, selected={"decision": "silent", "utterance": ""},
        visitor_messages=PUB)
    assert changed and q["revision"] == 1
    assert q["public_input"] == PUB and q["outbox"] == []
    assert p["public_input"] == []
    assert q["cycles"]["cycle-7"]["outcome"] == "silent"


def test_valid_self_speech_has_one_deduplicable_outbox_event():
    p = initial_store()
    candidate = owner_proposal(belief="I now suspect the premise was flawed.",
                               goal="Find a simple counterexample.")
    result = floor(candidate)
    assert result["decision"] == "speak"
    q, changed = apply_cycle(
        p, expected_revision=0, cycle=7, cycle_id="cycle-7",
        candidates={"jules": candidate}, selected=result,
        visitor_messages=PUB)
    assert changed and len(q["outbox"]) == 1
    assert q["outbox"][0]["status"] == "pending"
    assert q["outbox"][0]["text"] == candidate["utterance"]
    assert len(q["consumed_bids"]) == 1
    assert q["characters"]["jules"]["private_state"]["what_i_currently_believe"].startswith("I now")
    assert q["characters"]["jules"]["journal"]["revision"] == 1
    assert p["revision"] == 0


def test_idempotent_replay_preserves_original_visitor_and_one_public_event():
    c = owner_proposal()
    result = floor(c)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.json"
        p = transact(path, expected_revision=0, cycle=7, cycle_id="once",
                     candidates={"jules": c}, selected=result,
                     visitor_messages=PUB)
        again = transact(path, expected_revision=0, cycle=7, cycle_id="once",
                         candidates={"jules": c}, selected=result,
                         visitor_messages=PUB)
        assert p == again
        assert len(again["public_input"]) == 1
        assert len(again["outbox"]) == 1
        assert path.exists()


def test_visitor_conflict_rejected_without_overwriting_original():
    p, _ = apply_cycle(
        initial_store(), expected_revision=0, cycle=7, cycle_id="original",
        candidates={}, selected={"decision": "silent"}, visitor_messages=PUB)
    conflicting = [{**PUB[0], "text": "Changed visitor words"}]
    try:
        apply_cycle(p, expected_revision=1, cycle=8, cycle_id="next",
                    candidates={}, selected={"decision": "silent"},
                    visitor_messages=conflicting)
    except ValueError:
        pass
    else:
        raise AssertionError("visitor source overwritten")
    assert p["public_input"] == PUB


def test_fabricated_speech_cannot_be_inserted():
    c = owner_proposal()
    bad = floor(c)
    bad["utterance"] = "I did not actually choose to say that."
    try:
        apply_cycle(initial_store(), expected_revision=0, cycle=7,
                    cycle_id="fake", candidates={"jules": c},
                    selected=bad, visitor_messages=PUB)
    except ValueError:
        pass
    else:
        raise AssertionError("fabricated utterance was accepted")


def test_stale_revision_and_cycle_conflict_are_rejected():
    q, _ = apply_cycle(
        initial_store(), expected_revision=0, cycle=7,
        cycle_id="one", candidates={}, selected={"decision":"silent"},
        visitor_messages=PUB)
    for revision, cid, chosen in (
        (0, "two", {"decision":"silent"}),
        (1, "one", {"decision":"speak", "speaker":"jules", "utterance":"fake"}),
        (1, "different", {"decision":"silent", "utterance":"not silent"}),
    ):
        try:
            apply_cycle(q, expected_revision=revision, cycle=8, cycle_id=cid,
                        candidates={}, selected=chosen, visitor_messages=[])
        except ValueError:
            pass
        else:
            raise AssertionError("stale/conflicting cycle accepted")


def test_replay_cannot_reuse_the_same_public_bid_id():
    c = owner_proposal()
    q, _ = apply_cycle(
        initial_store(), expected_revision=0, cycle=7, cycle_id="one",
        candidates={"jules":c}, selected=floor(c), visitor_messages=PUB)
    # A compromised publisher cannot replay the same public bid in cycle 8.
    copied = copy.deepcopy(c)
    copied["bid"]["cycle"] = 8
    chosen = floor(c)
    try:
        apply_cycle(q, expected_revision=1, cycle=8, cycle_id="two",
                    candidates={"jules":copied}, selected=chosen,
                    visitor_messages=[])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate bid publication accepted")


def test_failed_disk_commit_keeps_previous_consistent_snapshot():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "state.json"
        initial = transact(path, expected_revision=0, cycle=7, cycle_id="first",
                           candidates={}, selected={"decision":"silent"},
                           visitor_messages=PUB)
        before = path.read_bytes()
        with patch("room_endogenous_transaction_store.os.replace",
                   side_effect=OSError("simulated rename failure")):
            try:
                transact(path, expected_revision=1, cycle=8, cycle_id="second",
                         candidates={}, selected={"decision":"silent"},
                         visitor_messages=[])
            except OSError:
                pass
            else:
                raise AssertionError("injected crash did not interrupt commit")
        assert path.read_bytes() == before
        assert initial["revision"] == 1


def test_goal_only_without_speech_still_commits_private_intention():
    c = owner_proposal(text="", belief="I should reconsider this claim.",
                       goal="Check a simple fact.")
    q, _ = apply_cycle(initial_store(), expected_revision=0,
                       cycle=7, cycle_id="private", candidates={"jules": c},
                       selected=floor(c), visitor_messages=PUB)
    assert q["outbox"] == []
    assert q["characters"]["jules"]["journal"]["revision"] == 1
    assert q["characters"]["jules"]["private_state"]["what_i_currently_believe"].startswith("I should")


if __name__ == "__main__":
    cases = [v for k,v in sorted(globals().copy().items()) if k.startswith("test_") and callable(v)]
    for fn in cases:
        fn()
    print(f"PASS: {len(cases)} atomic research transaction tests")
