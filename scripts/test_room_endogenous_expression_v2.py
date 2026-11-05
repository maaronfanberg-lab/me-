"""Safety and causal-state tests for expression-first voluntary Room agency."""
import json

from room_endogenous_expression_v2 import build_request, interpret, choose_volunteers
from room_endogenous_goal_journal import new_journal, active_goals

PUBLIC = [{"id": "ev-1", "speaker": "allen", "text": "Mara, what does the measurement tell us?"}]
PEOPLE = ("sarah", "mara", "owen", "jules")


def payload(*, utterance="", private_revision="", personal_goal="",
            basis=None):
    return json.dumps({
        "utterance": utterance, "private_revision": private_revision,
        "personal_goal": personal_goal,
        "basis": basis or {"kind": "witnessed", "source_id": "ev-1"},
    })


def act(name="mara", *, text=None, history=None, prior=None, state=None, cycle=13):
    return interpret(
        agent=name, cycle=cycle,
        raw=payload() if text is None else text,
        public_history=PUBLIC if history is None else history,
        journal=prior if prior is not None else new_journal(name),
        private_state=state if state is not None else {
            "what_i_currently_believe": "Uncertain.",
            "belief_confidence": .25, "last_updated_cycle": 0
        },
        consumed_ids=set()
    )


def test_model_authored_content_not_external_speaking_quota():
    candidate = act(text=payload(utterance="I think the measurement contradicts the earlier claim."))
    assert candidate["ok"] and candidate["bid"]["action"] == "speak"
    chosen = choose_volunteers(cycle=13, public_history=PUBLIC,
                               candidates={"mara": candidate}, consumed_ids=set())
    assert chosen["speaker"] == "mara"
    assert chosen["utterance"] == candidate["utterance"]
    assert chosen["decision"] == "speak"


def test_silence_is_real_and_empty_context_cannot_bypass_provenance():
    idle = act()
    assert idle["ok"] and idle["utterance"] == ""
    chosen = choose_volunteers(cycle=13, public_history=PUBLIC,
                               candidates={"mara": idle}, consumed_ids=set())
    assert chosen["decision"] == "silent"
    ungrounded = act(history=[], text=payload(utterance="I have something specific to offer."))
    assert not ungrounded["ok"]


def test_private_revisions_feed_future_character_only():
    previous = act(text=payload(
        private_revision="I may have overlooked a simpler explanation."))
    assert previous["ok"] and previous["belief_changed"]
    assert previous["bid"]["action"] == "reflect"
    assert previous["private_state"]["belief_epistemic_status"] == "self_hypothesis_not_external_fact"
    profile = {"psychology_v2": {"core_identity": "Mara identity."}}
    msg = build_request(agent="mara", profile=profile,
                        private_state=previous["private_state"],
                        journal=previous["journal"], public_history=PUBLIC)
    assert "simpler explanation" in msg[1]["content"]
    assert "simpler explanation" not in json.dumps(PUBLIC)


def test_speech_and_private_revision_can_coexist_without_mixing_channels():
    c = act(text=payload(
        utterance="That reading needs a second measurement to verify it.",
        private_revision="I should question the reliability of this one observation.",
        personal_goal="Look for a repeatable observation."))
    assert c["ok"] and c["belief_changed"] and c["goal_changed"]
    assert len(active_goals(c["journal"], owner="mara")) == 1
    assert "reliability" not in c["utterance"]


def test_personal_goal_created_from_model_output_survives_silence():
    one = act(text=payload(personal_goal="Examine the claim with a concrete example."))
    assert one["ok"] and one["goal_changed"] and one["utterance"] == ""
    own_id = active_goals(one["journal"], owner="mara")[0]["id"]
    two = act(prior=one["journal"], state=one["private_state"], cycle=14,
              history=[], text=payload(
                  utterance="I think a concrete example would help here.",
                  basis={"kind": "own_goal", "goal_id": own_id}))
    assert two["ok"] and two["bid"]["action"] == "speak"


def test_foreign_and_unknown_basis_never_reaches_publication():
    for basis in ({"kind": "witnessed", "source_id": "invented"},
                  {"kind": "own_goal", "goal_id": "owens-private-goal"}):
        c = act(text=payload(
            utterance="The measured value might contradict this assumption.",
            basis=basis))
        assert not c["ok"]
        chosen = choose_volunteers(cycle=13, public_history=PUBLIC,
                                   candidates={"mara": c}, consumed_ids=set())
        assert chosen["decision"] == "silent"


def test_malformed_or_too_short_speech_fails_closed():
    for raw in ('not-json', '{}', payload(utterance="Yes."),
                payload(utterance="Mara: This is my speech about the finding."),
                payload(utterance="Echo " * 200),
                json.dumps({**json.loads(payload()), "admin_override": True})):
        a = act(text=raw)
        assert not a["ok"], raw[:100]


def test_private_goal_error_blocks_public_speech_atomically():
    invalid = act(text=payload(
        utterance="I think we could verify the number independently.",
        personal_goal="x"*210))
    assert not invalid["ok"] and not invalid["utterance"]


def test_private_goal_from_wrong_owner_rejected():
    c = act(name="mara", text=payload(personal_goal="Check the measuring device."))
    assert c["ok"]
    try:
        build_request(agent="jules", profile={"psychology_v2": {}},
                      private_state={}, journal=c["journal"], public_history=PUBLIC)
    except ValueError:
        pass
    else:
        raise AssertionError("foreign journal was visible")


def test_distinct_agent_inputs_do_not_include_other_self_states():
    for agent in PEOPLE:
        context = {"what_i_currently_believe": f"MY_SECRET_{agent}"}
        request = build_request(
            agent=agent,
            profile={"psychology_v2": {"core_identity": agent}},
            private_state=context, journal=new_journal(agent),
            public_history=PUBLIC)
        assert f"MY_SECRET_{agent}" in request[1]["content"]
        for other in PEOPLE:
            if other != agent:
                assert f"MY_SECRET_{other}" not in request[1]["content"]


if __name__ == "__main__":
    cases = [v for k,v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in cases:
        fn()
    print(f"PASS: {len(cases)} expression-first endogenous safety tests")
