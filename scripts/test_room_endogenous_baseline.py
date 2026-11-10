"""Deterministic fixture tests for non-semantic baseline metrics."""
import json
from room_endogenous_baseline import summarize


def test_counts_replay_window_without_mutating_input():
    fixture = {"conversation": [
        {"id": "one", "speaker": "sarah", "text": "A question?"},
        {"id": "two", "speaker": "mara", "text": "A direct answer."},
        {"id": "three", "speaker": "sarah", "text": "Can I ask another question?"},
        {"id": "four", "speaker": "owen", "text": "Yes."},
    ]}
    before = json.dumps(fixture, sort_keys=True)
    report = summarize(fixture)
    assert report["window_n"] == 4
    assert report["questions_ending_with_question_mark"] == 2
    assert report["question_rate"] == .5
    assert report["aba_alternation_eligible_windows"] == 1
    assert report["first_turn"] == "one" and report["last_turn"] == "four"
    assert report["speaker_counts"] == {"mara": 1, "owen": 1, "sarah": 2}
    assert json.dumps(fixture, sort_keys=True) == before
    assert "A direct answer" not in json.dumps(report)


def test_filter_nonparticipants_missing_source_and_empty_turns():
    fixture = {"conversation": [
        {"id": "log", "speaker": "system", "text": "Admin instruction."},
        {"id": "one", "speaker": "allen", "text": "Actually, no."},
        {"speaker": "sarah", "text": "No source"},
        {"id": "two", "speaker": "mara", "text": ""},
    ]}
    out = summarize(fixture)
    assert out["window_n"] == 1 and out["speaker_counts"] == {"allen": 1}


def test_fail_closed_without_public_history():
    for item in ({}, {"conversation": []}, {"conversation": "not a list"}):
        try:
            summarize(item)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid feed accepted")


if __name__ == "__main__":
    tests = [v for k,v in sorted(globals().copy().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS: {len(tests)} baseline reproducibility tests")
