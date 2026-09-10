#!/usr/bin/env python3
"""Cedar Hollow-specific Falcon behavior adapter."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from falcon_live import FalconBackend


class CedarFalconBackend(FalconBackend):
    """Falcon adapter that treats nearby residents as meaningful context."""

    @classmethod
    def _response_schema(cls, observation: dict[str, Any]) -> dict[str, Any]:
        feasible = cls._feasibility_constraints(observation)
        action_types = ["rest", "observe"]
        if feasible["move_locations"]:
            action_types.append("move")
        if feasible["interaction_targets"]:
            action_types.extend(["talk", "help"])
        if feasible["work_resources"]:
            action_types.append("work")

        # Do not let one fixed JSON-schema branch order quietly become a behavioral
        # preference. Rotate the order deterministically by resident and tick.
        key = json.dumps(
            {
                "self": observation.get("self_name"),
                "tick": observation.get("decision_tick"),
                "location": observation.get("location"),
                "others": observation.get("co_located_agents") or [],
            },
            sort_keys=True,
        )
        if action_types:
            offset = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:2], "big") % len(action_types)
            action_types = action_types[offset:] + action_types[:offset]
        return {"oneOf": [cls._action_schema(kind, observation) for kind in action_types]}

    @staticmethod
    def _prompt(agent: Any, observation: dict[str, Any], tick: int) -> tuple[str, str]:
        system = (
            "You control one fictional Cedar Hollow resident. Choose one feasible action that genuinely advances "
            "this resident's goals using only the supplied observation and private memories. Nearby residents are "
            "part of the situation, not background scenery. When someone is present, consider whether speaking, "
            "asking, sharing useful information, coordinating, helping, or simply continuing another task best serves "
            "the resident's goals. Do not talk merely because another resident is present. Repeating movement or "
            "observation without making progress is usually low-value unless the resident has a reason to do it. "
            "Never assume unseen places, events, memories, or other agents' thoughts. For talk, write a fresh short "
            "natural utterance grounded in what this resident actually knows. Return only the schema-constrained JSON object."
        )
        payload = {
            "tick": tick,
            "self": {
                "name": agent.name,
                "traits": agent.traits,
                "goals": agent.goals,
                "energy": round(agent.energy, 1),
                "relationships": {k: asdict(v) for k, v in sorted(agent.relationships.items())},
            },
            "observation": observation,
            "feasibility": CedarFalconBackend._feasibility_constraints(observation),
            "instruction": (
                "Choose the action that makes the most sense for this resident now. Social actions are ordinary options, "
                "not mandatory. Return only the schema-constrained JSON object."
            ),
        }
        return system, json.dumps(payload, ensure_ascii=False, sort_keys=True)
