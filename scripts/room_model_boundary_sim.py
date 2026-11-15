#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "room" / "config.json").read_text())

# Install the production wrapper before probing the exact model-facing payload.
import room_engine_v5  # noqa: F401,E402
import room_private_model as private_model  # noqa: E402

base = {
    "entity": "mara",
    "profile": CFG["p"]["mara"],
    "event": {"speaker": "allen", "text": "Hi Mara"},
    "context": [{"speaker": "allen", "text": "Hi Mara"}],
    "keywords": ["mara"],
    "topic": {"root": "friendship", "current_facet": "greeting", "facets": [], "shared_references": [], "unresolved": []},
    "partner": "allen",
    "relationship": {},
    "social_observation": {"participation": "DIRECT_ADDRESSEE"},
    "deliberation": {"action": "ANSWER", "focus": "greeting", "new_information_goal": "", "conversation_job": ""},
    "conversation_job": "",
    "mandatory_speech": True,
}

# These represent arbitrary future developer-only fields. A denylist-based
# boundary leaks them automatically; an allowlist boundary cannot.
canaries = {
    "developer_only_canary": "NEVER_MODEL_VISIBLE_73A",
    "research_notes_canary": "NEVER_MODEL_VISIBLE_73B",
    "operator_notes_canary": {"text": "NEVER_MODEL_VISIBLE_73C"},
    "internal_debug_canary": ["NEVER_MODEL_VISIBLE_73D"],
}

for role in ("comprehension", "thought", "expression"):
    payload = {**base, **canaries}
    compact = private_model._compact_payload(payload, role, "mara" if role == "expression" else None)
    serialized = json.dumps(compact, ensure_ascii=False)
    for key, value in canaries.items():
        assert key not in compact, f"RED: unknown internal field crossed model boundary for {role}: {key}"
        marker = value if isinstance(value, str) else next(iter(value.values())) if isinstance(value, dict) else value[0]
        assert marker not in serialized, f"RED: developer canary reached model payload for {role}"

# Required conversational information must still survive the boundary.
expr = private_model._compact_payload(base, "expression", "mara")
assert ((expr.get("event") or {}).get("text")) == "Hi Mara"
assert expr.get("partner") == "allen"
assert isinstance(expr.get("personality_context"), dict)
assert "profile" not in expr
assert "relationship" not in expr
assert "social_observation" not in expr

print("PASS: model boundary is allowlist-only; unknown developer fields cannot reach cognition")
