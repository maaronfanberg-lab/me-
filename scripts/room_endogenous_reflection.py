"""Private, provenance-bound self-revision for a simulated Room character.

A reflection must come from the same character's validated model-authored bid.
It is stored explicitly as a *hypothesis*, never external fact or public speech.
No rule converts reflection into speech, and unchanged reflection adds no state.
Research-only pure transition, not wired to the live Room.
"""
from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping

from room_endogenous_preflight import AGENTS

MAX_HYPOTHESIS_CHARS = 250
MAX_HISTORY = 12


def _plain(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def apply_private_reflection(*, agent: str, cycle: int, bid: Mapping,
                             prior_state: dict, update: object) -> dict:
    """Return candidate state and changed flag; fail-closed on malformed inputs."""
    if (agent not in AGENTS or type(cycle) is not int or cycle < 0
            or not isinstance(prior_state, dict) or not isinstance(bid, Mapping)
            or bid.get("speaker") != agent or type(bid.get("cycle")) is not int
            or bid.get("cycle") != cycle):
        raise ValueError("invalid reflection owner, cycle or state")
    original = copy.deepcopy(prior_state)
    if update is None:
        return {"state": original, "changed": False}
    if bid.get("action") != "reflect":
        raise ValueError("only a reflect intention may revise private belief")
    basis = bid.get("basis")
    if (not isinstance(basis, Mapping)
            or basis.get("kind") not in {"witnessed", "own_goal"}
            or not isinstance(basis.get("source_id") if basis.get("kind") == "witnessed"
                               else basis.get("goal_id"), str)):
        raise ValueError("missing validated reflection provenance")
    if not isinstance(update, Mapping) or set(update) != {"hypothesis", "confidence"}:
        raise ValueError("unbounded reflection update")
    hypothesis = _plain(update["hypothesis"])
    confidence = update["confidence"]
    if (not hypothesis or len(hypothesis) > MAX_HYPOTHESIS_CHARS
            or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError("invalid private self hypothesis")
    last_cycle = original.get("last_updated_cycle", 0)
    if type(last_cycle) is not int or cycle < last_cycle:
        raise ValueError("out of order private revision")
    prior = _plain(original.get("what_i_currently_believe"))
    prior_confidence = original.get("belief_confidence")
    # Exact unchanged hypothesis and confidence must not manufacture progress.
    effective_confidence = min(float(confidence), 0.7)
    if prior.casefold() == hypothesis.casefold() and prior_confidence == effective_confidence:
        return {"state": original, "changed": False}
    history = original.get("private_reflections", [])
    if not isinstance(history, list):
        raise ValueError("corrupted private reflection journal")
    evidence_id = basis.get("source_id") if basis.get("kind") == "witnessed" else basis.get("goal_id")
    original["what_i_currently_believe"] = hypothesis
    original["belief_confidence"] = effective_confidence
    original["belief_epistemic_status"] = "self_hypothesis_not_external_fact"
    original["what_just_changed"] = "I reconsidered my private hypothesis."
    original["private_reflections"] = (history + [{
        "cycle": cycle, "hypothesis": hypothesis,
        "confidence": effective_confidence,
        "basis_kind": basis["kind"], "source_id": evidence_id,
        "status": "unverified_self_interpretation",
    }])[-MAX_HISTORY:]
    original["last_updated_cycle"] = cycle
    original["private_reflection_revision"] = int(original.get("private_reflection_revision", 0)) + 1
    return {"state": original, "changed": True}
