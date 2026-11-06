"""A character can initiate an owned goal from its earlier self-reflection."""
from room_endogenous_inner_tick import propose_inner_goal
from room_endogenous_reflection import apply_private_reflection, authenticated_reflection_ids
from room_endogenous_goal_journal import new_journal, active_goals

PUBLIC=[{"id":"earlier-01","speaker":"allen",
         "text":"Which part of the experiment matters to you?"}]
PRIOR={"what_i_currently_believe":"I am not sure how the two readings relate.",
       "belief_confidence":.3, "last_updated_cycle":0}
PROFILE={"psychology_v2":{"core_identity":"I want to understand the measurements."}}


def past(owner="mara"):
    result=apply_private_reflection(
        agent=owner, cycle=4, prior_state=PRIOR,
        bid={"speaker":owner,"cycle":4,"action":"reflect",
             "basis":{"kind":"witnessed","source_id":"earlier-01"}},
        update={"hypothesis":"I may have missed the role of the cup's diameter.",
                "confidence":.4})
    return result["state"]


def test_self_authored_memory_can_generate_goal_without_public_input():
    state=past()
    seen=[]
    def own_model(messages,timeout):
        seen.append(messages)
        return "I want to investigate how different diameters affect water levels."
    result=propose_inner_goal(
        owner="mara",cycle=5,profile=PROFILE,private_state=state,
        journal=new_journal("mara"),model_request=own_model)
    assert result["eligible"] and result["ok"] and result["changed"]
    assert result["calls"]==1 and len(seen)==1
    assert result["journal"]["goals"][0]["origin"]["kind"]=="own_reflection"
    assert result["journal"]["goals"][0]["origin"]["source_id"] in authenticated_reflection_ids(
        owner="mara",private_state=state)
    assert result["private_state"] is state
    assert "diameters" in active_goals(result["journal"],owner="mara")[0]["description"]


def test_model_can_still_choose_no_goal_despite_own_memory():
    result=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=past(),journal=new_journal("mara"),
        model_request=lambda *args:"[NO_GOAL]")
    assert result["eligible"] and result["ok"] and not result["changed"]
    assert result["calls"]==1
    assert result["journal"]["goals"]==[]


def test_empty_mental_history_never_invents_own_goal_or_calls_model():
    calls=[]
    result=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=PRIOR,journal=new_journal("mara"),
        model_request=lambda *args:calls.append(True))
    assert not result["eligible"] and not result["changed"]
    assert result["calls"]==0 and not calls


def test_other_character_cannot_reuse_a_private_reflection():
    state=past("sarah")
    calls=[]
    result=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=state,journal=new_journal("mara"),
        model_request=lambda *args:calls.append(True))
    assert not result["eligible"] and not result["changed"] and not calls


def test_corrupted_reflection_never_becomes_private_goal():
    state=past()
    state["private_reflections"][-1]["hypothesis"]="Fabricated replacement."
    called=[]
    result=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=state,journal=new_journal("mara"),
        model_request=lambda *args:called.append(1))
    assert not result["eligible"] and not called


def test_failed_model_call_does_not_invent_intention():
    def failure(*args): raise TimeoutError("offline model")
    result=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=past(),journal=new_journal("mara"),model_request=failure)
    assert result["eligible"] and result["calls"]==1
    assert not result["ok"] and not result["changed"]


def test_existing_personal_goal_does_not_trigger_repeat_goal_genesis():
    state=past()
    first=propose_inner_goal(owner="mara",cycle=5,profile=PROFILE,
        private_state=state,journal=new_journal("mara"),
        model_request=lambda *args:"I want to check the two cups.")
    assert first["changed"]
    result=propose_inner_goal(owner="mara",cycle=6,profile=PROFILE,
        private_state=state,journal=first["journal"],
        model_request=lambda *args: (_ for _ in ()).throw(Exception("unexpected")))
    assert not result["eligible"] and not result["changed"]


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items())
           if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} private self-originated idle goal tests")
