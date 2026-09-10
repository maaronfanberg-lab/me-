#!/usr/bin/env python3
"""Cedar Hollow's live-world behavior layer.

This keeps the general WorldEngine rules intact while giving Cedar residents
better awareness of the people around them and of their own recent behavior.
"""
from __future__ import annotations

import json
from typing import Any

from living_world import WorldEngine


class CedarWorldEngine(WorldEngine):
    """WorldEngine with richer social observations for Cedar Hollow."""

    @staticmethod
    def _recent_actions(agent: Any, limit: int = 6) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw in agent.action_history[-max(1, int(limit)):]:
            try:
                value = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def observation_for(self, agent_name: str) -> dict[str, Any]:
        observation = super().observation_for(agent_name)
        agent = self.agents[agent_name]
        co_located = list(observation.get("co_located_agents") or [])

        # Make people part of memory retrieval. Previously retrieval was driven by
        # goals, place, resources, and incidents, so a resident standing beside an
        # old acquaintance could fail to retrieve any memory about that person.
        place = self.locations[agent.location]
        local_recent = list(observation.get("recent_local_incidents") or [])
        query = " ".join(
            agent.goals
            + [agent.location]
            + list(place.get("resources") or {})
            + local_recent
            + co_located
        )
        observation["relevant_private_memories"] = self._relevant_memories(agent, query)

        social_context: list[dict[str, Any]] = []
        for other in co_located:
            rel = agent.relationships.get(other)
            mentions = [
                {
                    "tick": memory.tick,
                    "text": memory.text,
                    "importance": memory.importance,
                }
                for memory in reversed(agent.memories)
                if other.casefold() in memory.text.casefold()
            ][:4]
            social_context.append(
                {
                    "name": other,
                    "relationship": {
                        "familiarity": round(rel.familiarity, 3) if rel else 0.0,
                        "trust": round(rel.trust, 3) if rel else 0.0,
                    },
                    "recent_memories_about_them": mentions,
                }
            )

        observation["social_context"] = social_context
        observation["recent_actions"] = self._recent_actions(agent)
        observation["decision_tick"] = int(self.tick)
        observation["self_name"] = agent.name
        return observation

    def _resolve(self, agent: Any, action: dict[str, Any], validation_note: str | None) -> dict[str, Any]:
        kind = str(action.get("type") or "")
        target = str(action.get("target") or "") if kind == "talk" else ""
        event = super()._resolve(agent, action, validation_note)

        # A real conversation makes two residents more familiar, but does not
        # automatically make them trust one another. What was said remains the
        # meaningful information and is already remembered by everyone present.
        if validation_note is None and kind == "talk" and target in self.agents:
            for left, right in ((agent.name, target), (target, agent.name)):
                rel = self._relationship(left, right)
                rel.familiarity = min(1.0, max(0.0, rel.familiarity + 0.04))
        return event
