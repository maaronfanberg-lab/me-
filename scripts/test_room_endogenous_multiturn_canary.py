"""No model or live Room dependency: bounded, checkpointed multi-beat simulation."""
from room_endogenous_multiturn_canary import run, INIT

PROFILES={"p": {
    "mara":{"psychology_v2":{"core_identity":"Mara independently tests claims."}},
    "jules":{"psychology_v2":{"core_identity":"Jules asks about practical experiments."}},
}}


def plain_speech(messages, timeout):
    import json
    person=json.loads(messages[1]["content"])["character"]
    if person=="mara":
        return "We could check both marks with the same graduated cylinder."
    return "[SILENCE]"


def test_checkpoint_after_every_completed_beat_even_with_silence():
    checkpoints=[]
    result=run(config=PROFILES,speech_model=plain_speech,
               approval_model=lambda m,t:"NO",
               beats=3,on_beat=lambda rows,state:checkpoints.append({
                   "length":len(rows),"revision":state["revision"]}))
    assert [x["length"] for x in checkpoints]==[1,2,3]
    assert [x["revision"] for x in checkpoints]==[1,2,3]
    assert result["summary"]["beats"]==3
    assert result["summary"]["silent_beats"]==3
    assert result["summary"]["public_agent_turns"]==0
    assert result["published_live_dialogue"] is False


def test_checkpoint_preserves_each_actual_public_turn_without_invention():
    checkpoints=[]
    def remember(rows,state):
        checkpoints.append((len(rows),len(state["outbox"])))
    result=run(config=PROFILES,speech_model=plain_speech,
               approval_model=lambda m,t:"YES",
               beats=2,on_beat=remember)
    assert checkpoints[0]==(1,1)
    assert len(result["beats"])==2
    assert result["beats"][0]["model_utterance"].startswith("We could check")
    assert result["summary"]["research_state_revision"]==2


def test_model_failure_still_creates_valid_silent_checkpoint():
    def dead(*_):
        raise TimeoutError("isolated 3B unavailable")
    checkpoints=[]
    result=run(config=PROFILES,speech_model=dead,
               approval_model=dead,
               beats=2,on_beat=lambda records,state:checkpoints.append(len(records)))
    assert checkpoints==[1,2]
    assert result["summary"]["silent_beats"]==2
    assert result["summary"]["model_calls"]==4
    assert result["summary"]["ready_for_live"] is False


if __name__ == "__main__":
    tests=[value for key,value in sorted(globals().copy().items()) if key.startswith("test_") and callable(value)]
    for fn in tests: fn()
    print(f"PASS: {len(tests)} bounded checkpoint multi-turn tests")
