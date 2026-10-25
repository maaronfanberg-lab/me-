"""Interactional project selection for the Room's single-speaker expression stage.

The observed transcript remains available to comprehension and private thought.
The expression stage distinguishes a response obligation from a locally
unclaimed floor. When the floor is unclaimed, an agent can initiate something
that genuinely interests *that person* rather than treating the last utterance
as a command to paraphrase it.

No lexical bans, n-gram similarity penalties, artificial topic list, speaker
rotation, or synthetic memories. A question, named address, or Allen's accepted
message always retains the actual source text for an appropriate response.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from room_conversational_floor import is_directed

AUTONOMOUS = ("sarah", "mara", "owen", "jules")


def _lower(x: Any) -> str:
    return str(x or "").strip().lower()


def response_project(latest: Mapping | None, entity: str) -> bool:
    """Is there observable conversational business calling for uptake?

    This is an opportunity, not evidence that the other speaker's claim is
    true or that any specific response/consent is required.
    """
    if not isinstance(latest, Mapping):
        return False
    speaker = _lower(latest.get("speaker"))
    text = str(latest.get("text") or "").strip()
    if not text or speaker == _lower(entity):
        return False
    if speaker == "allen":
        return True
    if speaker not in AUTONOMOUS:
        return False
    if is_directed(dict(latest), entity):
        return True
    if text.endswith("?"):
        return True  # An unaddressed question opens a group response opportunity.
    if re.search(
        r"\b(?:tell me|what do you think|your thoughts|can someone|could someone|"
        r"would someone|any ideas|please explain)\b", text, re.I
    ):
        return True
    return False


def invitation_project(latest: Mapping | None) -> bool:
    """An audible offer invites acceptance, refusal, clarification or negotiation.

    An invitation is *not* evidence that its recipient already agreed, was
    criticized or has committed to any collaboration.
    """
    if not isinstance(latest, Mapping):
        return False
    utterance = str(latest.get("text") or "")
    return bool(re.search(
        r"\b(?:collaborat(?:e|ion)|work together|join me|"
        r"would you like to|shall we|let's|we could work|could we explore)\b",
        utterance, re.I,
    ))


def _authored_resources(profile: Mapping | None) -> dict:
    """Actual established character resources, not invented biographical facts."""
    profile = profile if isinstance(profile, Mapping) else {}
    psych = profile.get("psychology_v2")
    psych = psych if isinstance(psych, Mapping) else {}
    education = psych.get("education")
    education = education if isinstance(education, Mapping) else {}
    def bounded(items, limit=5):
        return [str(x).strip()[:160] for x in items[:limit] if str(x or "").strip()] if isinstance(items, list) else []
    return {
        "knowledge_domains": bounded(education.get("graduate_domains"), 5),
        "personal_motives": bounded(psych.get("motives"), 3),
        "values": bounded(psych.get("values"), 4),
        "attention": bounded(psych.get("attention_magnets"), 3),
    }


def expression_project(
    *,
    entity: str,
    latest: Mapping | None,
    context: list,
    profile: Mapping | None,
    private_self_state: Mapping | None,
) -> dict:
    """One immutable per-beat plan carrying source and provenance to expression.

    A response retains the literal transcript. A self-initiated contribution
    uses an authored motivational basis and only stable self-knowledge:
    unconscious reliance on a repeatedly echoed private belief is not evidence
    that there is an outstanding conversational question.
    """
    event = dict(latest) if isinstance(latest, Mapping) else None
    source_id = event.get("id") if event else None
    if response_project(event, entity):
        proposal = invitation_project(event)
        return {
            "event": event,
            "context": list(context[-3:]),
            "private_self_state": private_self_state,
            "interaction_project": {
                "kind": "respond_to_proposal" if proposal else "respond_or_repair",
                "observed_source_id": source_id,
                "prior_speaker": event.get("speaker"),
                "evidence": "public_utterance",
                "proposal_status": "unanswered" if proposal else None,
                "reply_opportunities": (
                    ["accept", "decline", "clarify", "counteroffer"]
                    if proposal else None
                ),
            },
        }

    psyche = private_self_state if isinstance(private_self_state, Mapping) else {}
    stable = {k: psyche[k] for k in ("who_i_am", "what_i_want")
              if isinstance(psyche.get(k), str) and psyche[k].strip()}
    return {
        # No direct response is outstanding. The recent turns are still
        # independently observed, but no old subject is selected for expression.
        "event": None,
        "context": [],
        "private_self_state": stable,
        "interaction_project": {
            "kind": "self_initiated_contribution",
            "observed_source_id": source_id,
            "prior_speaker": event.get("speaker") if event else None,
            "evidence": "user_authored_character_motivations",
            "resources": _authored_resources(profile),
        },
    }
