"""Silent heartbeat produces owner goals, not manufactured conversations."""
from room_endogenous_inner_cycle import silent_inner_cycle
from room_endogenous_reflection import apply_private_reflection
from room_endogenous_transaction_store import initial_store
from room_endogenous_goal_journal import active_goals

PROFILE={"psychology_v2":{"core_identity":"Mara cares about concrete observations."}}


def state_with_prior_reflection():
    s=initial_store()
    base={"what_i_currently_believe":"I have not explained the differing levels.",
          "belief_confidence":.3,"last_updated_cycle":0}
    change=apply_private_reflection(
        agent="mara",cycle=3,prior_state=base,
        bid={"speaker":"mara","cycle":3,"action":"reflect",
             "basis":{"kind":"witnessed","source_id":"historical-public-1"}},
        update={"hypothesis":"Different widths might explain what I saw.",
                "confidence":.45})
    assert change["changed"]
    s["characters"]["mara"]["private_state"]=change["state"]
    s["last_cycle"]=3
    return s


def test_true_quiet_world_still_allows_own_source_bound_private_goal():
    s=state_with_prior_reflection()
    result,report=silent_inner_cycle(
        snapshot=s,owner="mara",cycle=4,cycle_id="silent-own-thought",
        profile=PROFILE,
        model_request=lambda m,t:"I want to test the relationship between cup width and volume.")
    assert report["goal_changed"] and report["decision"]=="silent"
    assert result["outbox"]==[]
    assert result["revision"]==1
    assert s["characters"]["mara"]["journal"]["goals"]==[]
    goals=active_goals(result["characters"]["mara"]["journal"],owner="mara")
    assert len(goals)==1 and "cup width" in goals[0]["description"]
    assert goals[0]["id"].startswith("self-")


def test_model_can_voluntarily_decline_inner_goal_without_speech():
    s=state_with_prior_reflection()
    result,report=silent_inner_cycle(
        snapshot=s,owner="mara",cycle=4,cycle_id="quiet-choice",
        profile=PROFILE,model_request=lambda m,t:"[NO_GOAL]")
    assert report["decision"]=="silent" and not report["goal_changed"]
    assert result["outbox"]==[]
    assert result["characters"]["mara"]["journal"]["goals"]==[]


def test_duplicate_silent_cycle_skips_new_model_inference():
    s=state_with_prior_reflection()
    first,report=silent_inner_cycle(
        snapshot=s,owner="mara",cycle=4,cycle_id="silent-once",
        profile=PROFILE,
        model_request=lambda m,t:"I want to compare two cup dimensions.")
    again,report2=silent_inner_cycle(
        snapshot=first,owner="mara",cycle=4,cycle_id="silent-once",
        profile=PROFILE,model_request=lambda *args: (_ for _ in ()).throw(
            Exception("replayed stochastic inference")))
    assert first==again and report2["replayed"] and report2["model_calls"]==0


def test_silence_without_authenticated_self_memory_never_calls_model():
    s=initial_store()
    result,report=silent_inner_cycle(
        snapshot=s,owner="mara",cycle=1,cycle_id="silent-empty",
        profile=PROFILE,model_request=lambda *args: (_ for _ in ()).throw(
            Exception("no source existed")))
    assert not report["goal_changed"] and report["model_calls"]==0
    assert result["outbox"]==[]


def test_peer_cannot_borrow_another_character_private_reflection():
    s=state_with_prior_reflection()
    s["characters"]["owen"]["private_state"]=s["characters"]["mara"]["private_state"]
    outcome,report=silent_inner_cycle(
        snapshot=s,owner="owen",cycle=4,cycle_id="foreign-source",
        profile=PROFILE,model_request=lambda *args: (_ for _ in ()).throw(
            Exception("wrong-owner inference")))
    assert not report["goal_changed"] and report["model_calls"]==0
    assert outcome["characters"]["owen"]["journal"]["goals"]==[]


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items())
           if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} silent self-originated memory heartbeat tests")
