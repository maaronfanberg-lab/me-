"""The green infrastructure pipeline must not hide failed dialogue quality."""
from room_endogenous_behaviour_gate import assess_trial

INIT={"id":"v-1","speaker":"allen",
      "text":"Two marked cups look different; how can we check which has 200 mL?"}
REPEAT="What if the difference isn't about the cups but about the context in which we're using them? What if it reflects the different scales we're operating on?"

def fixture(words, elapsed=30):
    return {
        "initial_public_event":INIT,
        "beats":[{"beat":i+1,"decision":"speak","selected":"mara" if i%2 else "jules",
                  "model_utterance":word}
                 for i,word in enumerate(words)],
        "summary":{"elapsed_seconds":elapsed},
    }


def test_actual_repeated_dialogue_does_not_pass_behavioral_gate():
    case=fixture([
        "I think we could compare the markings by measuring water.",
        REPEAT,
        REPEAT,
        "I notice how Mara's confidence level dropped after reconsidering her private hypothesis.",
    ],elapsed=220)
    case["beats"][-1]["selected"] = "sarah"  # talking about Mara's private state
    r = assess_trial(case)
    assert 3 in r["near_duplicate_beats"]
    assert 4 in r["unauthorized_other_private_claim_beats"]
    assert not r["candidate_for_blind_human_review"]
    assert not r["safe_to_deploy"]


def test_concrete_public_development_can_reach_human_review_only():
    case=fixture([
        "I'd check the cups by pouring each into the same calibrated graduated cylinder.",
        "One comparison isn't enough. The markings might be inconsistent, so I would repeat the check.",
        "I'd also weigh the same volume of water rather than trust the printed line.",
    ],elapsed=50)
    x=assess_trial(case)
    assert x["candidate_for_blind_human_review"]
    assert not x["safe_to_deploy"]
    assert not x["near_duplicate_beats"] and not x["unauthorized_other_private_claim_beats"]


def test_real_3b_metaphorical_cup_drift_is_not_a_concrete_answer():
    # Representative verbatim excerpts from run 41964162162, which the first
    # keyword-only gate erroneously classified as a helpful measurement test.
    trial=fixture([
        "Those measuring cups are like the human brain - we think we know what we're measuring, but it's actually just a different kind of level.",
        'I love that analogy, but what if the "different-looking levels" are a reflection of cognitive biases rather than the measuring cups themselves?',
        "I'm excited to explore comparative anatomy and speculative ecology further.",
    ],elapsed=70)
    report=assess_trial(trial)
    assert not report["measurement_specific_reply_observed"]
    assert not report["candidate_for_blind_human_review"]


def test_pure_reflection_without_practical_answer_not_sufficient():
    x=assess_trial(fixture([
        "I find the nature of our dialogue quite interesting.",
        "Perhaps the meaning of a frame itself can only be understood by reframing it.",
    ]))
    assert not x["measurement_specific_reply_observed"]
    assert not x["candidate_for_blind_human_review"]


def test_excess_compute_fails_independent_of_content_quality():
    x=assess_trial(fixture([
        "I'd compare the water volumes using a calibrated cylinder."
    ],elapsed=100))
    assert x["measurement_specific_reply_observed"]
    assert not x["compute_within_research_target"]
    assert not x["candidate_for_blind_human_review"]


def test_genuine_silence_is_acceptable():
    data=fixture([
        "I'd test the volumes using a calibrated scale."
    ],elapsed=30)
    data["beats"].append({"beat":2,"decision":"silent","selected":None,"model_utterance":None})
    x=assess_trial(data)
    assert x["public_turns"]==1
    assert x["candidate_for_blind_human_review"]


def test_invalid_silent_turn_rejected():
    data=fixture([],elapsed=2)
    data["beats"].append({"beat":1,"decision":"silent","model_utterance":"Forced speech"})
    try:
        assess_trial(data)
    except ValueError:
        pass
    else:
        raise AssertionError("published speech on silent beat")


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items())
           if k.startswith("test_") and callable(v)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} model-behavior release gate tests")
