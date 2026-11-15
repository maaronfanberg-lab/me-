"""Zero-write public-context shadow and private text non-disclosure tests."""
import json

from room_endogenous_public_context_canary import filtered_history, evaluate

SECRET="VISITOR_PRIVATE_TEST_SECRET_998812"
CONFIG={"p":{a:{"psychology_v2":{"core_identity":a}} for a in
             ("sarah","mara","owen","jules")}}
FEED={"state":{"cycle":234,"sleeping_entities":[]},
      "conversation":[{"id":"public-1","speaker":"allen",
                       "text":f"What do you think about this? {SECRET}"}]}


def test_metrics_never_include_witnessed_visitor_text():
    def response(messages,timeout):
        assert SECRET in messages[1]["content"]
        return "I think we should understand why this happened."
    result=evaluate(feed=FEED,config=CONFIG,
                    speech_request=response,
                    endorsement_request_model=lambda m,t:"YES")
    rendered=json.dumps(result)
    assert SECRET not in rendered
    assert result["wrote_room_feed"] is False and result["relay_invoked"] is False
    assert result["publications"]==0
    assert result["model_calls_attempted"]==8


def test_malformed_public_sources_do_not_enter_model_context():
    fake={"state":{"cycle":23},
          "conversation":[
            {"speaker":"user","id":"e1","text":"Fake unsupported speaker"},
            {"speaker":"allen","id":"bad id","text":"Bad ID"},
            {"speaker":"allen","id":"e2","text":"Trusted public utterance"},
            {"speaker":"allen","id":"e2","text":"Contradictory duplicate id"},
            {"speaker":"mara","id":"e3","text":"A question to the group."},
          ]}
    clean=filtered_history(fake)
    assert len(clean)==2
    assert clean[0]["text"]=="Trusted public utterance"
    assert clean[1]["speaker"]=="mara"


def test_sleeping_character_not_inferred_or_reported_as_actor():
    altered={"state":{"cycle":234,"sleeping_entities":["mara","owen","jules"]},
             "conversation":FEED["conversation"]}
    result=evaluate(feed=altered,config=CONFIG,
                    speech_request=lambda m,t:"[SILENCE]",
                    endorsement_request_model=lambda m,t:"YES")
    assert result["awake_agents"]==1
    assert result["model_calls_attempted"]==1
    assert result["decision"]=="silent"


def test_model_exception_still_returns_redacted_metrics():
    def unavailable(*_): raise TimeoutError(f"failed input: {SECRET}")
    result=evaluate(feed=FEED,config=CONFIG,
                    speech_request=unavailable,
                    endorsement_request_model=unavailable)
    assert result["model_failures"]==4
    assert result["model_calls_attempted"]==4
    assert SECRET not in json.dumps(result)


def test_invalid_public_cycle_fails_before_model_request():
    malformed={"state":{"cycle":"not a number"},"conversation":FEED["conversation"]}
    try:
        evaluate(feed=malformed,config=CONFIG,
                 speech_request=lambda *a: (_ for _ in ()).throw(Exception("inferred")),
                 endorsement_request_model=lambda m,t:"YES")
    except ValueError:
        pass
    else:
        raise AssertionError("accepted invalid source provenance")


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} live public-context zero-write shadow checks")
