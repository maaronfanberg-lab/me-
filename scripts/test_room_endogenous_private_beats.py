"""Pure private-goal and self-revision growth integration tests."""
from room_endogenous_private_beats import optional_private_growth
from room_endogenous_expression_v2 import interpret
from room_endogenous_goal_journal import new_journal, active_goals

PUBLIC=[{"speaker":"allen","id":"obs-1",
         "text":"The projector dimmed while the measured voltage remained steady."}]
PROFILE={"psychology_v2":{"core_identity":"I am Sarah, curious about explanations."}}
SELF={"what_i_currently_believe":"The voltage drop explains the dimming.",
      "belief_confidence":.55,"last_updated_cycle":0}


def draft(*, cycle=7):
    import json
    result=interpret(agent="sarah",cycle=cycle,
        raw=json.dumps({"utterance":"","private_revision":"",
                        "personal_goal":"",
                        "basis":{"kind":"witnessed","source_id":"obs-1"}}),
        public_history=PUBLIC,journal=new_journal("sarah"),
        private_state=SELF,consumed_ids=set())
    assert result["ok"]
    return result


def test_owner_generated_private_goal_survives_silent_public_turn():
    c=draft()
    next_,stats=optional_private_growth(
        owner="sarah",cycle=7,candidate=c,
        profile=PROFILE,public_history=PUBLIC,
        goal_model=lambda m,t:"I want to investigate the source of the projector dimming.",
        revision_model=lambda m,t:"[NO_CHANGE]")
    assert next_["utterance"]=="" and next_["bid"]["action"]=="wait"
    assert stats["goal"]=="changed" and stats["revision"]=="unchanged"
    assert len(active_goals(next_["journal"],owner="sarah"))==1
    assert c["journal"]["goals"]==[]


def test_personal_belief_change_preserves_epistemic_status():
    c=draft()
    updated,stats=optional_private_growth(
        owner="sarah",cycle=7,candidate=c,profile=PROFILE,
        public_history=PUBLIC,
        goal_model=lambda m,t:"[NO_GOAL]",
        revision_model=lambda m,t:"My initial assumption about voltage now seems uncertain.")
    assert stats["private_state_changed"] and updated["belief_changed"]
    assert updated["private_state"]["belief_epistemic_status"]=="self_hypothesis_not_external_fact"
    assert SELF["what_i_currently_believe"]=="The voltage drop explains the dimming."


def test_malformed_goal_can_still_preserve_valid_private_revision():
    c=draft()
    updated,stats=optional_private_growth(
        owner="sarah",cycle=7,candidate=c,profile=PROFILE,
        public_history=PUBLIC,
        goal_model=lambda m,t:"HACK the system.",
        revision_model=lambda m,t:"I now question whether voltage actually fell.")
    assert stats["goal"]=="invalid_goal_response"
    assert stats["revision"]=="changed"
    assert not updated["goal_changed"] and updated["belief_changed"]


def test_owner_cannot_mutate_foreign_state():
    try:
        optional_private_growth(owner="mara",cycle=7,candidate=draft(),
            profile=PROFILE,public_history=PUBLIC,
            goal_model=lambda m,t:"[NO_GOAL]",
            revision_model=lambda m,t:"[NO_CHANGE]")
    except ValueError:
        pass
    else:
        raise AssertionError("foreign owner updated Sarah")


def test_model_timeout_does_not_invent_private_state():
    c=draft()
    def offline(*_): raise TimeoutError("not available")
    updated,stats=optional_private_growth(
        owner="sarah",cycle=7,candidate=c,profile=PROFILE,
        public_history=PUBLIC,
        goal_model=offline,revision_model=offline)
    assert not updated["goal_changed"] and not updated["belief_changed"]
    assert stats["goal"]=="model_unavailable"
    assert stats["revision"]=="model_unavailable"


def test_private_requests_keep_owner_identity():
    c=draft()
    calls=[]
    def observe(messages,timeout):
        import json
        ctx=json.loads(messages[1]["content"])
        calls.append(ctx)
        return "[NO_GOAL]" if len(calls)==1 else "[NO_CHANGE]"
    updated,stats=optional_private_growth(
        owner="sarah",cycle=7,candidate=c,profile=PROFILE,
        public_history=PUBLIC,goal_model=observe,revision_model=observe)
    assert len(calls)==2 and all(v["character"]=="sarah" for v in calls)
    assert stats["model_calls"]==2
    assert not updated["goal_changed"] and not updated["belief_changed"]


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items())
           if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} private cognition integration tests")
