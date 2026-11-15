"""Offline self-endorsement safety tests."""
import json
from room_endogenous_self_endorse import (
    endorsement_request, interpret_endorsement, apply_endorsement,
)
from room_endogenous_speech_option import parse
from room_endogenous_goal_journal import new_journal
from room_endogenous_expression_v2 import choose_volunteers

PUBLIC = [{"id":"event-a","speaker":"allen","text":"Mara, should we repeat that measurement?"}]
PRIVATE = {"what_i_currently_believe":"I have an idea.",
           "belief_confidence": .5}
PROFILE = {"psychology_v2":{"core_identity":"Mara, an independent participant."}}


def candidate():
    return parse(agent="mara", cycle=8,
                 raw="We could test this by repeating the measurement with a calibrated scale.",
                 public_history=PUBLIC, journal=new_journal("mara"),
                 private_state=PRIVATE, consumed_ids=set())


def test_self_can_decline_own_valid_candidate():
    c = candidate()
    assert c["ok"] and c["utterance"]
    refused = apply_endorsement(c, False)
    assert c["utterance"]
    assert refused["bid"]["action"] == "wait" and refused["utterance"] == ""
    selection = choose_volunteers(
        cycle=8, public_history=PUBLIC,
        candidates={"mara":refused}, consumed_ids=set())
    assert selection["decision"] == "silent"


def test_approval_keeps_exact_content_and_provenance():
    c = candidate()
    approved = apply_endorsement(c, True)
    assert approved["utterance"] == c["utterance"]
    assert approved["bid"] == c["bid"]
    selection = choose_volunteers(
        cycle=8, public_history=PUBLIC,
        candidates={"mara":approved}, consumed_ids=set())
    assert selection["decision"] == "speak"


def test_malformed_or_failed_model_cannot_force_speech():
    c = candidate()
    for answer in ("yes!", "maybe", "YES\nNO", "", None, "speak"):
        result = apply_endorsement(c, interpret_endorsement(answer))
        assert result["utterance"] == "" and result["bid"]["action"] == "wait"
    assert interpret_endorsement("  Yes ") is True
    assert interpret_endorsement("No") is False


def test_own_draft_is_in_owner_context_only():
    c = candidate()
    request = endorsement_request(agent="mara", profile=PROFILE,
                                  private_state=PRIVATE, journal=new_journal("mara"),
                                  public_history=PUBLIC, draft=c["utterance"])
    context = json.loads(request[1]["content"])
    assert context["character"] == "mara"
    assert context["my_draft_that_I_can_choose_to_say_or_not"] == c["utterance"]
    assert "Mara" in request[0]["content"] or "YOURSELF" in request[0]["content"]


def test_invalid_draft_and_foreign_journal_rejected():
    for draft in ("", "x"*400):
        try:
            endorsement_request(agent="mara", profile=PROFILE,
                                private_state=PRIVATE, journal=new_journal("mara"),
                                public_history=PUBLIC, draft=draft)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid draft accepted")
    try:
        endorsement_request(agent="mara", profile=PROFILE,
                            private_state=PRIVATE, journal=new_journal("jules"),
                            public_history=PUBLIC, draft=candidate()["utterance"])
    except ValueError:
        pass
    else:
        raise AssertionError("foreign private state admitted")


def test_silence_remains_silence_even_if_approved():
    c = parse(agent="mara", cycle=8, raw="[SILENCE]",
              public_history=PUBLIC, journal=new_journal("mara"),
              private_state=PRIVATE, consumed_ids=set())
    assert c["ok"] and not c["utterance"]
    assert apply_endorsement(c, True)["utterance"] == ""


if __name__=="__main__":
    tests = [v for k,v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} internal self-endorsement tests")
