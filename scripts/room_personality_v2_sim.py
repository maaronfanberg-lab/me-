#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "room" / "config.json").read_text())
PEOPLE = ("sarah", "mara", "owen", "jules")
PROFILE_KEYS = {
    "core_identity", "values", "motives", "agency_style", "communion_style",
    "attention_magnets", "attention_blindspots", "reciprocity_style",
    "topic_mobility", "evidence_style", "disagreement_style",
    "affiliation_style", "status_sensitivity", "praise_response",
    "criticism_response", "schema_vulnerabilities", "coping_patterns",
    "repair_recovery", "private_self", "education", "cognitive_style",
    "humor_style", "flirtation_style",
}


def no_numbers(value):
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return False
    if isinstance(value, dict):
        return all(no_numbers(item) for item in value.values())
    if isinstance(value, list):
        return all(no_numbers(item) for item in value)
    return True


profiles = {}
for person in PEOPLE:
    profile = (CFG["p"][person] or {}).get("psychology_v2")
    assert isinstance(profile, dict), f"RED baseline: {person} has no fixed psychology_v2 profile"
    assert set(profile) == PROFILE_KEYS, f"{person}: current psychology_v2 profile shape mismatch; missing={sorted(PROFILE_KEYS - set(profile))}; extra={sorted(set(profile) - PROFILE_KEYS)}"
    assert no_numbers(profile), f"{person}: psychology_v2 contains slider-like numeric data"
    profiles[person] = profile

from room_personality_v2 import appraise  # noqa: E402

scenarios = {
    "greeting": {"speaker": "allen", "text": "Hi everyone"},
    "topic": {"speaker": "allen", "text": "Let's talk about the platypus"},
    "proof": {"speaker": "allen", "text": "Proof?"},
    "mara_why": {"speaker": "allen", "text": "Mara, why?"},
    "critique_owen": {"speaker": "allen", "text": "Owen, that argument makes no sense."},
    "exclude_mara": {"speaker": "allen", "text": "Sarah and Jules get it. Mara doesn't. Everyone but Mara understands."},
    "exclude_jules": {"speaker": "allen", "text": "Sarah and Mara get it. Jules doesn't. Everyone but Jules understands."},
    "odd": {"speaker": "allen", "text": "Platypuses have electroreceptors in their bills."},
    "repair": {"speaker": "allen", "text": "Sorry, Mara. I was too harsh."},
    "fragment": {"speaker": "allen", "text": "Recursive causation"},
}
context = [
    {"speaker": "sarah", "text": "Public interest should be considered in every debate."},
    {"speaker": "owen", "text": "We need evidence about public interest."},
]
results = {
    (person, scenario): appraise(person, profiles[person], event, context)
    for person in PEOPLE
    for scenario, event in scenarios.items()
}

# Fresh social bids must beat inherited topic inertia and preserve the actual words.
for person in PEOPLE:
    assert results[(person, "greeting")]["priority"] == "ground_latest_turn"
    assert "greeting" in results[(person, "greeting")]["situation"]
    assert results[(person, "topic")]["priority"] == "ground_latest_turn"
    assert "platypus" in results[(person, "topic")]["grounding"]["terms"]
    assert results[(person, "proof")]["priority"] == "ground_latest_turn"
    assert "evidence_request" in results[(person, "proof")]["situation"]
    assert "utterance" not in results[(person, "topic")], "appraiser must not script public speech"

# Same situation, four coherent lenses instead of four rewordings of one persona.
odd_lenses = {person: tuple(results[(person, "odd")]["personality_lens"]) for person in PEOPLE}
assert len(set(odd_lenses.values())) == 4, odd_lenses
# The contemporary 23-field profiles put novelty responses inside distinct
# cognitive styles, not the retired novelty_response field.
assert "unusual" in " ".join(odd_lenses["jules"]).lower()
assert "test" in " ".join(odd_lenses["owen"]).lower()
assert "hypotheses" in " ".join(odd_lenses["sarah"]).lower()
assert "people" in " ".join(odd_lenses["mara"]).lower()

# Current character profiles have no declared schema vulnerabilities.
# The appraiser must identify the *social target* without fabricating clinical
# schema labels or transforming observations into psychodynamic certainty.
for person in PEOPLE:
    for scenario in ("exclude_mara", "exclude_jules", "critique_owen"):
        assert results[(person, scenario)]["schema_activation"] == [], (
            person, scenario, "unconfigured psychological vulnerability invented"
        )
assert results[("mara", "exclude_mara")]["social_targeting"].get("exclusion") is True
assert results[("jules", "exclude_jules")]["social_targeting"].get("exclusion") is True
assert not results[("owen", "exclude_mara")]["social_targeting"].get("exclusion")
assert not results[("mara", "exclude_jules")]["social_targeting"].get("exclusion")
assert results[("owen", "critique_owen")]["social_targeting"].get("criticism_or_rejection") is True

# Repair is generic, but recovery style remains person-specific.
for person in PEOPLE:
    assert "repair_bid" in results[(person, "repair")]["situation"]
assert len({tuple(results[(person, "repair")]["personality_lens"]) for person in PEOPLE}) == 4

# Verify production integration, not merely the standalone appraiser.
import room_engine_v5  # noqa: F401,E402 -- installs the wrapper bridge
import room_private_model as private_model  # noqa: E402

payload = {
    "entity": "jules",
    "profile": CFG["p"]["jules"],
    "event": scenarios["topic"],
    "context": context + [scenarios["topic"]],
    "topic": {"root": "public interest", "current_facet": "debate", "facets": [], "shared_references": [], "unresolved": []},
    "partner": "allen",
    "relationship": {},
}
compact = private_model._compact_payload(payload, "expression", "jules")
pctx = compact.get("personality_context")
assert isinstance(pctx, dict), "production compact payload lost personality_context"
current = pctx.get("current") or {}
assert current.get("latest_words") == "Let's talk about the platypus"
assert "platypus" in (current.get("grounding_terms") or [])
assert current.get("salience") == "ground_latest_turn"
assert any("tangent" in str(item).lower() or "new topics" in str(item).lower()
           for item in current.get("personality_lens") or [])
assert pctx.get("identity") == profiles["jules"]["core_identity"]

# Clinical/schema labels are internal mechanics, never language-model vocabulary.
mara_payload = {
    "entity": "mara",
    "profile": CFG["p"]["mara"],
    "event": scenarios["exclude_mara"],
    "context": context + [scenarios["exclude_mara"]],
    "topic": {"root": "public interest", "current_facet": "debate", "facets": [], "shared_references": [], "unresolved": []},
    "partner": "allen",
    "relationship": {},
}
mara_compact = private_model._compact_payload(mara_payload, "expression", "mara")
mara_current = ((mara_compact.get("personality_context") or {}).get("current") or {})
assert mara_current.get("activated_sensitivities") == [], "no clinical vulnerability is configured for Mara"
serialized = json.dumps(mara_compact.get("personality_context") or {}, ensure_ascii=False).lower()
for forbidden in ("schema", "abandonment", "mistrust", "unrelenting", "insufficient-self-control"):
    assert forbidden not in serialized, f"clinical/internal label leaked into private-model payload: {forbidden}"
assert "social systems" in serialized and "people" in serialized, "Mara's actual interpretive lens must survive"

print("PASS personality-v2: 23 current layers, no sliders, grounded bids, distinct cognitive styles, no ungrounded clinical activations, precise social targeting and private bridge")
