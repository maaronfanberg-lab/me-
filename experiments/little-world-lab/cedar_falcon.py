#!/usr/bin/env python3
"""Cedar Hollow-specific Falcon behavior adapter."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from falcon_live import FalconBackend


class CedarFalconBackend(FalconBackend):
    """Falcon adapter that treats social wellbeing as meaningful context."""

    @classmethod
    def _response_schema(cls, observation: dict[str, Any]) -> dict[str, Any]:
        feasible = cls._feasibility_constraints(observation)
        energy = float(observation.get("self_energy", 100.0))

        action_types = ["rest", "observe"]
        if feasible["move_locations"] and energy >= 2.0:
            action_types.append("move")
        if feasible["interaction_targets"] and energy >= 1.0:
            action_types.append("talk")
        if feasible["interaction_targets"] and energy >= 3.0:
            action_types.append("help")
        if feasible["work_resources"] and energy >= 5.0:
            action_types.append("work")

        # Rotate feasible schema branches so fixed JSON-schema order does not
        # quietly become a standing behavioral preference.
        key = json.dumps(
            {
                "self": observation.get("self_name"),
                "tick": observation.get("decision_tick"),
                "location": observation.get("location"),
                "others": observation.get("co_located_agents") or [],
                "energy": energy,
            },
            sort_keys=True,
        )
        if action_types:
            offset = (
                int.from_bytes(
                    hashlib.sha256(key.encode("utf-8")).digest()[:2], "big"
                )
                % len(action_types)
            )
            action_types = action_types[offset:] + action_types[:offset]
        return {
            "oneOf": [
                cls._action_schema(kind, observation)
                for kind in action_types
            ]
        }

    @staticmethod
    def _prompt(
        agent: Any,
        observation: dict[str, Any],
        tick: int,
    ) -> tuple[str, str]:
        system = (
            "You control one fictional Cedar Hollow resident. Choose one feasible "
            "action that genuinely advances this resident's goals using only the "
            "supplied observation and private memories. Nearby residents are part "
            "of the situation, not background scenery. Social wellbeing describes "
            "the resident's current context, not a score to maximize. Meaningful, "
            "responsive contact can reduce isolation; empty or repetitive chatter "
            "has little value. Useful help matters more when someone actually needs "
            "it, and reciprocal support can make difficult periods less draining. "
            "Do not talk or help merely to trigger a benefit. Consider relationship "
            "history, recent reciprocity, the resident's traits, goals, energy, and "
            "what is happening now. When energy is low, choose actions the resident "
            "can actually sustain; rest is a legitimate action. Repeating movement "
            "or observation without progress is usually low-value unless there is "
            "a reason for it. Never assume unseen places, events, memories, or "
            "other residents' thoughts. For talk, write a fresh short natural "
            "utterance grounded in what this resident actually knows. Return only "
            "the schema-constrained JSON object."
        )
        payload = {
            "tick": tick,
            "self": {
                "name": agent.name,
                "traits": agent.traits,
                "goals": agent.goals,
                "energy": round(agent.energy, 1),
                "relationships": {
                    k: asdict(v)
                    for k, v in sorted(agent.relationships.items())
                },
            },
            "observation": observation,
            "feasibility": CedarFalconBackend._feasibility_constraints(
                observation
            ),
            "energy_note": (
                "The response schema already removes actions this resident lacks "
                "energy to perform."
            ),
            "instruction": (
                "Choose the action that makes the most sense for this resident now. "
                "Social actions are ordinary options, not mandatory. Prefer genuine "
                "purpose over gaming any wellbeing value. Return only the "
                "schema-constrained JSON object."
            ),
        }
        return system, json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        )
