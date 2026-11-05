"""Publication hygiene is content safety, not a scripted conversation manager."""
from room_endogenous_public_hygiene import publication_issue, _is_close_copy

H=[
 {"id":"c-1","speaker":"jules","text":"I think it's interesting that we're discussing the measuring cups, but what if the discrepancy isn't just about the cups themselves, but about the context in which we're using them? What if the difference in levels is actually a reflection of the different scales we're operating on?"},
 {"id":"c-2","speaker":"allen","text":"I'd like to test the actual volume."},
]


def test_exact_model_loop_blocked_even_from_another_character():
    assert publication_issue(speaker="mara",text=H[0]["text"],
                             public_history=H)=="near_duplicate_public_speech"


def test_small_paraphrase_repeat_blocked_without_topic_ban():
    original="The room was quiet as we considered whether the second cup was calibrated differently, and then we looked for a known reference volume to compare against it."
    same="The room was quiet as we considered whether the second cup was calibrated differently, and then we looked for a known reference volume to compare against it again."
    assert _is_close_copy(same, original)
    changed="The room was quiet, but I used a calibrated scale and measured 200 grams of water, which contradicts our earlier guess about the marks."
    assert not _is_close_copy(changed,original)


def test_related_subject_and_valid_disagreement_untouched():
    assert publication_issue(speaker="mara",
         text="I disagree. The same level doesn't imply equal volume because the cups can have different widths.",
         public_history=H) is None


def test_invented_access_to_peers_private_beliefs_blocked():
    for spoken in (
        "I notice how Mara's confidence level has dropped after reconsidering her private hypothesis about measuring cups.",
        "Jules's private belief has changed after the last observation.",
        "The private hypothesis of Owen shows that he believes the markings were wrong.",
    ):
        assert publication_issue(speaker="sarah",text=spoken,
                                 public_history=H)=="asserts_other_mind_private_state",spoken


def test_public_observation_of_uncertainty_not_treated_as_private_access():
    spoken="Mara sounded uncertain when she said the two cup measurements might not agree."
    assert publication_issue(speaker="sarah",text=spoken,public_history=H) is None


def test_self_disclosure_does_not_automatically_get_censored():
    assert publication_issue(speaker="sarah",
        text="My private hypothesis about the cup might be wrong. I want another measurement.",
        public_history=H) is None


def test_no_auto_silence_for_first_time_relevant_utterance():
    assert publication_issue(speaker="mara",
        text="I'd compare the mass of water in both cups using a calibrated digital scale.",
        public_history=H) is None


def test_invalid_publication_context_fails_closed():
    for speaker in ("allen","system","jules2"):
        assert publication_issue(speaker=speaker,text="Hello there.",
                                 public_history=[])=="invalid_publication_context"


if __name__=="__main__":
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith("test_") and callable(v)]
    for test in tests: test()
    print(f"PASS: {len(tests)} endogenous public repetition and mind-privacy tests")
