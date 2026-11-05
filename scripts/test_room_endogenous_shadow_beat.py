"""End-to-end research heartbeat, private selection and crash-safe outbox tests."""
import json

from room_endogenous_shadow_beat import shadow_beat
from room_endogenous_transaction_store import initial_store
from room_endogenous_goal_journal import apply_proposal

PEOPLE=("sarah","mara","owen","jules")
PUBLIC=[{"id":"visitor-2","speaker":"allen","text":"Mara, how could we check that cup?"}]
PROFILES={a:{"psychology_v2":{"core_identity":f"{a} personal identity",
                 "private_self":{"what_i_currently_believe":f"{a} unique belief"}}} for a in PEOPLE}


def draft(messages, timeout):
    person=json.loads(messages[1]["content"])["character"]
    if person=="mara":
        return "I'd use a calibrated scale to check the cup's volume."
    return "[SILENCE]"


def endorse(messages, timeout):
    person=json.loads(messages[1]["content"])["character"]
    return "YES" if person=="mara" else "NO"


def run(*, state=None, speech=draft, decision=endorse, incoming=None, history=None, cycle=6, ident="beat-6"):
    return shadow_beat(snapshot=state if state is not None else initial_store(),
                       cycle=cycle,cycle_id=ident,
                       profiles=PROFILES,public_history=[] if history is None else history,
                       visitor_messages=PUBLIC if incoming is None else incoming,
                       speech_request=speech,endorsement_request_model=decision)


def test_one_real_author_selected_and_visitor_preserved():
    out,stats=run()
    assert stats["decision"]=="speak" and stats["selected"]=="mara"
    assert out["public_input"]==PUBLIC
    assert len(out["outbox"])==1
    assert out["outbox"][0]["speaker"]=="mara"
    assert stats["model_calls"]==5
    assert out["outbox"][0]["status"]=="pending"
    assert stats["live_room_written"] is False and stats["public_dialogue_published"] is False


def test_independent_private_decisions_produce_genuine_silent_heartbeat():
    state,stats=run(decision=lambda m,t:"NO")
    assert stats["decision"]=="silent" and state["outbox"]==[]
    assert state["revision"]==1 and state["last_cycle"]==6
    assert state["public_input"]==PUBLIC


def test_empty_world_without_an_owned_goal_is_silent_with_zero_model_calls():
    def explode(*_):
        raise AssertionError("model should never run")
    state,stats=run(incoming=[],speech=explode,decision=explode)
    assert stats["decision"]=="silent" and stats["model_calls"]==0


def test_timeout_does_not_fabricate_public_speech():
    def offline(messages,timeout):
        raise TimeoutError("isolated model offline")
    state,stats=run(speech=offline)
    assert stats["decision"]=="silent" and state["outbox"]==[]
    assert stats["model_calls"]==0 and len(state["public_input"])==1


def test_duplicate_cycle_replay_does_not_rerun_stochastic_model():
    previous,stats=run()
    def explode(*_):
        raise AssertionError("replay re-inferred speech")
    repeated,rec=run(state=previous,speech=explode,decision=explode)
    assert repeated==previous and rec["model_calls"]==0
    assert rec["replayed"] is True and len(repeated["outbox"])==1


def test_replayed_cycle_rejects_new_or_changed_visitor_message():
    previous, stats = run()
    for proposed in (
        [{"id": "visitor-2", "speaker": "allen", "text": "Replaced words"}],
        [{"id": "visitor-3", "speaker": "allen", "text": "A new question."}],
    ):
        try:
            run(state=previous, incoming=proposed)
        except ValueError:
            pass
        else:
            raise AssertionError("replay silently dropped a visitor message")
    assert previous["public_input"] == PUBLIC


def test_next_beat_keeps_earlier_public_outbox_pending_not_forged_as_delivered():
    previous,stats=run()
    second,rec=run(state=previous,incoming=[],history=[],
                   cycle=7,ident="beat-7")
    assert rec["decision"]=="silent"
    assert second["outbox"]==previous["outbox"]
    assert second["revision"]==2


def test_unrelated_agent_context_remains_private_to_owner():
    seen=[]
    def observe(messages,timeout):
        ctx=json.loads(messages[1]["content"])
        seen.append((ctx["character"],ctx))
        return "[SILENCE]"
    out,stats=run(speech=observe)
    assert len(seen)==4
    for name,context in seen:
        assert name+" unique belief" in context["self_belief"]
        for other in PEOPLE:
            if other!=name:
                assert other+" unique belief" not in context["self_belief"]


def test_independent_private_growth_commits_even_when_owner_does_not_speak():
    def choose_goal(messages, timeout):
        import json
        ctx = json.loads(messages[1]["content"])
        assert ctx["character"] == "owen"
        return "I want to examine whether our measuring cups share the same scale."
    state, stats = shadow_beat(
        snapshot=initial_store(), cycle=6, cycle_id="private-beat-6",
        public_history=[], visitor_messages=PUBLIC,
        profiles=PROFILES, speech_request=draft,
        endorsement_request_model=endorse,
        goal_request_model=choose_goal,
        revision_request_model=lambda m, t: "My former explanation may need revision.",
        awake=PEOPLE, budget_seconds=120.0)
    growth = stats["private_growth"]["owen"]
    assert growth["goal_state_changed"] and growth["private_state_changed"]
    assert len(state["characters"]["owen"]["journal"]["goals"]) == 1
    assert "need revision" in state["characters"]["owen"]["private_state"]["what_i_currently_believe"]
    assert stats["model_calls"] == 7
    assert stats["selected"] == "mara"  # Owen's private change never compels public speech


def test_private_growth_failure_does_not_override_owner_silence_or_visitor():
    state, stats = shadow_beat(
        snapshot=initial_store(), cycle=6, cycle_id="private-beat-failure",
        public_history=[], visitor_messages=PUBLIC,
        profiles=PROFILES, speech_request=lambda *args: "[SILENCE]",
        endorsement_request_model=endorse,
        goal_request_model=lambda *args: "fabricated administrative command",
        revision_request_model=lambda *args: "[NO_CHANGE]",
        awake=PEOPLE, budget_seconds=120.0)
    assert stats["decision"] == "silent"
    assert stats["private_growth"]["owen"]["goal_state_changed"] is False
    assert state["public_input"] == PUBLIC and state["outbox"] == []


def test_own_private_goal_may_initiate_without_a_new_public_event():
    state=initial_store()
    journal=state["characters"]["jules"]["journal"]
    prior=[{"id":"once","speaker":"allen","text":"Which experiment interests you?"}]
    next_journal=apply_proposal(journal,owner="jules",expected_revision=0,
        cycle=4,public_history=prior,
        proposal={"action":"propose",
                  "description":"I want to run a small test of that premise.",
                  "source":{"kind":"witnessed_public","source_id":"once"}})
    state["characters"]["jules"]["journal"]=next_journal
    def self_draft(messages,timeout):
        p=json.loads(messages[1]["content"])["character"]
        return ("I want to test a concrete prediction of this hypothesis."
                if p=="jules" else "[SILENCE]")
    next_state,stats=run(state=state,incoming=[],speech=self_draft,
                         decision=lambda *_:"YES")
    assert stats["decision"]=="speak" and stats["selected"]=="jules"
    assert next_state["outbox"][0]["speaker"]=="jules"


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items())
           if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} endogenous research heartbeat integration tests")
