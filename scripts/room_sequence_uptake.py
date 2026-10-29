"""Evidence-linked conversational action continuity, not vocabulary policing.

A second-position turn may answer, disagree, refuse, acknowledge, counter,
or initiate a repair. Repeating a question may be a legitimate *first*
repair initiation, but an identical unanswered question cannot repeatedly
masquerade as an answer. This module enforces an interactional project,
never a forbidden word, topic list, or arbitrary novelty quota.

All inference is provisional and based on witnessed public source IDs.
"""
from __future__ import annotations

import re
from typing import Mapping

from room_conversational_floor import public_participant_turns


def _utterance_key(value: object) -> str:
    """Equality of the *whole conversational action*, not token overlap."""
    words = re.findall(r"[\w']+", str(value or "").casefold(), re.UNICODE)
    return " ".join(words)



def _final_question_action(value: object) -> str:
    """Identity of a final spoken question, excluding earlier statements.

    A speaker may preface a question with background information. Repeating
    only the final question is still an exact question-action echo, not an
    answer. This does not compare topical vocabulary or arbitrary n-grams.
    """
    spoken = str(value or "").strip()
    if not spoken.endswith("?"):
        return ""
    final = re.split(r"(?<=[.!?])\s+", spoken)[-1]
    return _utterance_key(final)


def question_sequence(context: list, latest: Mapping | None) -> dict:
    """Identify unresolved question echoes without equating hearing with agreement."""
    if not isinstance(latest, Mapping) or not str(latest.get("text") or "").strip().endswith("?"):
        return {"kind": "not_question_sequence", "echoes": 0}
    current = _final_question_action(latest.get("text"))
    if not current:
        return {"kind": "not_question_sequence", "echoes": 0}
    public = public_participant_turns(list(context or []))
    # Count echoes within the current *contiguous* question sequence.
    # An intervening substantive turn can answer, reject, or redirect the
    # question. Without semantic evidence we must not call a later reuse
    # of the wording an unresolved echo of the earlier action.
    preceding = [
        item for item in public
        if str(item.get("id")) != str(latest.get("id"))
    ]
    prior = []
    for item in reversed(preceding):
        spoken = str(item.get("text") or "").strip()
        if _final_question_action(spoken) != current:
            break
        prior.append(item)
    prior.reverse()
    first = prior[0] if prior else latest
    return {
        "kind": "unanswered_question_echo" if prior else "question_open",
        "echoes": len(prior),
        "first_source_id": first.get("id"),
        "current_source_id": latest.get("id"),
        "response_possibilities": [
            "answer", "disagree", "refuse", "clarify", "counter_question", "repair"
        ],
    }


def validate_uptake(
    *, history: list, speaker: str, utterance: str, move: str
) -> None:
    """Fail a pseudo-answer that simply republishes an unresolved question.

    Legitimate purposeful quotation and genuine first repair initiation pass.
    This gate checks only complete exact question-echo actions, never topic
    words or n-gram similarity. It cannot evaluate the wider meaning of prose.
    """
    public = public_participant_turns(history)
    if not public:
        return
    latest = public[-1]
    if str(latest.get("speaker") or "").casefold() == str(speaker).casefold():
        return
    text = str(latest.get("text") or "").strip()
    candidate = str(utterance or "").strip()
    # A full long copy is not a new conversational action, even when a
    # model labels it "repair". Short exact questions remain valid as a first
    # other-initiated clarification; shared words and substantive quotations
    # followed by one's own response are unrestricted.
    source_words = _utterance_key(text).split()
    min_echo_words = 20 if text.endswith("?") else 12
    if (len(source_words) >= min_echo_words
            and _utterance_key(candidate) == _utterance_key(text)):
        raise ValueError("unchanged_full_turn_echo")
    if not (text.endswith("?") and candidate.endswith("?")):
        return
    if _utterance_key(candidate) not in {
        _utterance_key(text), _final_question_action(text)
    }:
        return
    action = str(move or "").strip().lower()
    if action not in {"repair", "clarify"}:
        raise ValueError("question_not_answered_or_repaired")
    # Repair may quote a trouble source once. If someone has already echoed
    # the question as the next action, an identical third turn advances no
    # intersubjective understanding; a new question or explanation may.
    project = question_sequence(public[:-1], latest)
    if project["echoes"]:
        raise ValueError("repair_sequence_not_advanced")
