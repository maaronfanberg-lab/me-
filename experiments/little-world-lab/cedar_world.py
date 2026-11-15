#!/usr/bin/env python3
"""Cedar Hollow's live-world behavior layer.

Adds social wellbeing, context-sensitive social appraisal, reciprocity, and
energy limits without changing the underlying town history.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from living_world import WorldEngine


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


class CedarWorldEngine(WorldEngine):
    SOCIAL_STATE_VERSION = 1
    SOCIAL_HISTORY_LIMIT = 18
    ENERGY_COSTS = {
        "move": 2.0,
        "talk": 1.0,
        "help": 3.0,
        "work": 5.0,
        "rest": 0.0,
        "observe": 0.0,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.social_state = {
            name: self._default_social_state(name)
            for name in self.agents
        }

    def _default_social_state(self, name: str) -> dict[str, Any]:
        traits = {str(x).casefold() for x in self.agents[name].traits}
        loneliness = 22.0
        if "sociable" in traits:
            loneliness = 28.0
        elif "independent" in traits or "reserved" in traits:
            loneliness = 18.0
        return {
            "connection": 50.0,
            "loneliness": loneliness,
            "resilience": 50.0,
            "last_meaningful_interaction_tick": int(self.tick),
            "meaningful_interactions": 0,
            "recent_social": [],
        }

    def _ensure_social_state(self) -> None:
        for name in self.agents:
            self.social_state.setdefault(name, self._default_social_state(name))

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: Path,
        backend: Any,
        output_dir: Path | None = None,
    ) -> "CedarWorldEngine":
        engine = super(CedarWorldEngine, cls).from_checkpoint(
            checkpoint, backend=backend, output_dir=output_dir
        )
        data = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        saved = data.get("cedar_social_state")
        if isinstance(saved, dict):
            restored = {}
            for name in engine.agents:
                base = engine._default_social_state(name)
                row = saved.get(name)
                if isinstance(row, dict):
                    base["connection"] = _clamp(row.get("connection", base["connection"]), 0, 100)
                    base["loneliness"] = _clamp(row.get("loneliness", base["loneliness"]), 0, 100)
                    base["resilience"] = _clamp(row.get("resilience", base["resilience"]), 0, 100)
                    base["last_meaningful_interaction_tick"] = int(
                        row.get("last_meaningful_interaction_tick", engine.tick)
                    )
                    base["meaningful_interactions"] = max(
                        0, int(row.get("meaningful_interactions", 0))
                    )
                    history = row.get("recent_social")
                    if isinstance(history, list):
                        base["recent_social"] = [
                            dict(item)
                            for item in history[-engine.SOCIAL_HISTORY_LIMIT:]
                            if isinstance(item, dict)
                        ]
                restored[name] = base
            engine.social_state = restored
        else:
            # Older Cedar checkpoints begin from a neutral social present.
            engine.social_state = {
                name: engine._default_social_state(name)
                for name in engine.agents
            }
        return engine

    def save_checkpoint(self) -> None:
        super().save_checkpoint()
        self._ensure_social_state()
        payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        payload["cedar_social_state_version"] = self.SOCIAL_STATE_VERSION
        payload["cedar_social_state"] = self.social_state
        tmp = self.checkpoint_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.checkpoint_path)

    @staticmethod
    def _recent_actions(agent: Any, limit: int = 6) -> list[dict[str, Any]]:
        rows = []
        for raw in agent.action_history[-max(1, int(limit)):]:
            try:
                value = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def public_social_state(self, name: str) -> dict[str, Any]:
        self._ensure_social_state()
        row = self.social_state[name]
        return {
            "connection": round(float(row["connection"]), 1),
            "loneliness": round(float(row["loneliness"]), 1),
            "resilience": round(float(row["resilience"]), 1),
            "last_meaningful_interaction_tick": int(row["last_meaningful_interaction_tick"]),
            "meaningful_interactions": int(row["meaningful_interactions"]),
            "recent_social": [dict(x) for x in row["recent_social"][-6:]],
        }

    def _record_social(
        self,
        name: str,
        other: str,
        *,
        kind: str,
        direction: str,
        quality: float,
        meaningful: bool,
        reciprocal: bool,
        strained: bool = False,
    ) -> None:
        row = self.social_state[name]
        row["recent_social"].append({
            "tick": int(self.tick),
            "with": other,
            "kind": kind,
            "direction": direction,
            "quality": round(float(quality), 3),
            "meaningful": bool(meaningful),
            "reciprocal": bool(reciprocal),
            "strained": bool(strained),
        })
        row["recent_social"] = row["recent_social"][-self.SOCIAL_HISTORY_LIMIT:]
        if meaningful:
            row["last_meaningful_interaction_tick"] = int(self.tick)
            row["meaningful_interactions"] = int(row["meaningful_interactions"]) + 1

    def _recent_pair_rows(
        self,
        name: str,
        other: str,
        *,
        within: int,
        kind: str | None = None,
        direction: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = []
        for item in self.social_state[name]["recent_social"]:
            if str(item.get("with")) != other:
                continue
            if self.tick - int(item.get("tick", -10_000)) > within:
                continue
            if kind is not None and item.get("kind") != kind:
                continue
            if direction is not None and item.get("direction") != direction:
                continue
            rows.append(item)
        return rows

    def _is_reciprocal(
        self,
        actor: str,
        target: str,
        *,
        kinds: set[str],
        within: int,
    ) -> bool:
        for item in self._recent_pair_rows(
            target, actor, within=within, direction="outgoing"
        ):
            if str(item.get("kind")) in kinds and not bool(item.get("strained")):
                return True
        return False

    def _pair_saturation(self, actor: str, target: str, within: int = 10) -> float:
        recent = self._recent_pair_rows(actor, target, within=within)
        return _clamp(1.0 - 0.16 * len(recent), 0.30, 1.0)

    def _adjust_social(
        self,
        name: str,
        *,
        connection: float = 0.0,
        loneliness: float = 0.0,
        resilience: float = 0.0,
    ) -> None:
        row = self.social_state[name]
        row["connection"] = _clamp(float(row["connection"]) + connection, 0, 100)
        row["loneliness"] = _clamp(float(row["loneliness"]) + loneliness, 0, 100)
        row["resilience"] = _clamp(float(row["resilience"]) + resilience, 0, 100)

    def _age_social_wellbeing(self) -> None:
        self._ensure_social_state()
        for name, agent in self.agents.items():
            row = self.social_state[name]
            since = max(
                0,
                int(self.tick) - int(row["last_meaningful_interaction_tick"]),
            )
            traits = {str(x).casefold() for x in agent.traits}
            sensitivity = 1.0
            if "sociable" in traits:
                sensitivity *= 1.18
            if "independent" in traits:
                sensitivity *= 0.68
            if "reserved" in traits:
                sensitivity *= 0.82

            if since <= 8:
                row["loneliness"] = _clamp(float(row["loneliness"]) - 0.01, 0, 100)
            else:
                company = bool(self._co_located(agent))
                loneliness_rate = 0.007 if company else 0.014
                connection_rate = 0.003 if company else 0.006
                row["loneliness"] = _clamp(
                    float(row["loneliness"]) + loneliness_rate * sensitivity, 0, 100
                )
                row["connection"] = _clamp(
                    float(row["connection"]) - connection_rate * sensitivity, 0, 100
                )

            target_resilience = _clamp(
                50.0
                + 0.28 * (float(row["connection"]) - 50.0)
                - 0.22 * (float(row["loneliness"]) - 35.0),
                20,
                80,
            )
            row["resilience"] = _clamp(
                float(row["resilience"])
                + (target_resilience - float(row["resilience"])) * 0.006,
                0,
                100,
            )

    def step(self) -> list[dict[str, Any]]:
        self._age_social_wellbeing()
        return super().step()

    def observation_for(self, agent_name: str) -> dict[str, Any]:
        self._ensure_social_state()
        observation = super().observation_for(agent_name)
        agent = self.agents[agent_name]
        co_located = list(observation.get("co_located_agents") or [])
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

        social_context = []
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
            social_context.append({
                "name": other,
                "relationship": {
                    "familiarity": round(rel.familiarity, 3) if rel else 0.0,
                    "trust": round(rel.trust, 3) if rel else 0.0,
                },
                "recent_memories_about_them": mentions,
                "recent_interactions_with_them": self._recent_pair_rows(
                    agent.name, other, within=24
                )[-4:],
                "recent_reciprocity": self._is_reciprocal(
                    agent.name, other, kinds={"talk", "help"}, within=18
                ),
            })

        observation["social_context"] = social_context
        observation["social_wellbeing"] = self.public_social_state(agent_name)
        observation["recent_actions"] = self._recent_actions(agent)
        observation["decision_tick"] = int(self.tick)
        observation["self_name"] = agent.name
        observation["self_energy"] = round(float(agent.energy), 1)
        observation["energy_costs"] = dict(self.ENERGY_COSTS)
        return observation

    @staticmethod
    def _feasible_action_types(observation: dict[str, Any]) -> list[str]:
        energy = float(observation.get("self_energy", 100.0))
        feasible = {"rest", "observe"}
        if observation.get("neighbor_locations") and energy >= 2.0:
            feasible.add("move")
        if observation.get("co_located_agents") and energy >= 1.0:
            feasible.add("talk")
        if observation.get("co_located_agents") and energy >= 3.0:
            feasible.add("help")
        if observation.get("resources") and energy >= 5.0:
            feasible.add("work")
        return sorted(feasible)

    def _validate(self, agent: Any, proposed: Any) -> tuple[dict[str, Any], str | None]:
        action, note = super()._validate(agent, proposed)
        if note is not None:
            return action, note
        kind = str(action.get("type") or "")
        required = float(self.ENERGY_COSTS.get(kind, 0.0))
        if float(agent.energy) + 1e-9 < required:
            return {"type": "rest"}, f"insufficient_energy_for_{kind}"
        return action, None

    @staticmethod
    def _words(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9']+", str(text).casefold()))

    def _talk_appraisal(
        self,
        agent: Any,
        target: str,
        utterance: str,
        *,
        reciprocal: bool,
        saturation: float,
    ) -> tuple[float, bool]:
        words = re.findall(r"[a-z0-9']+", utterance.casefold())
        quality = 0.15
        if 4 <= len(words) <= 35:
            quality += 0.20
        if len(words) >= 8:
            quality += 0.12
        if reciprocal:
            quality += 0.20

        context = " ".join(
            list(agent.goals)
            + [agent.location, target]
            + list(self.locations[agent.location].get("resources") or {})
            + [memory.text for memory in agent.memories[-6:]]
        )
        common = {
            "a", "an", "and", "are", "as", "at", "be", "but", "for", "from",
            "i", "in", "is", "it", "me", "my", "of", "on", "or", "that",
            "the", "this", "to", "we", "with", "you", "your",
        }
        overlap = (self._words(utterance) - common) & (self._words(context) - common)
        if overlap:
            quality += 0.17

        rel = agent.relationships.get(target)
        if rel and rel.familiarity >= 0.20:
            quality += 0.06

        repeated_recently = bool(
            self._recent_pair_rows(
                agent.name, target, within=6, kind="talk", direction="outgoing"
            )
        )
        if repeated_recently and not reciprocal:
            quality -= 0.18

        strained_phrases = (
            "leave me",
            "go away",
            "stop talking",
            "don't want",
            "do not want",
            "angry with",
            "mad at",
            "hate you",
            "shut up",
        )
        strained = any(phrase in utterance.casefold() for phrase in strained_phrases)
        if len(words) <= 2:
            quality = min(quality, 0.25)
        if strained:
            quality = min(quality, 0.22)
        return _clamp(quality * saturation, 0, 1), strained

    def _apply_talk_social(
        self,
        agent: Any,
        target: str,
        utterance: str,
        *,
        energy_before: float,
    ) -> None:
        reciprocal = self._is_reciprocal(
            agent.name, target, kinds={"talk", "help"}, within=18
        )
        saturation = self._pair_saturation(agent.name, target)
        quality, strained = self._talk_appraisal(
            agent,
            target,
            utterance,
            reciprocal=reciprocal,
            saturation=saturation,
        )
        meaningful = bool(not strained and quality >= 0.50)

        left = self._relationship(agent.name, target)
        right = self._relationship(target, agent.name)
        if strained:
            left.familiarity = _clamp(left.familiarity + 0.01, 0, 1)
            right.familiarity = _clamp(right.familiarity + 0.01, 0, 1)
            left.trust = _clamp(left.trust - 0.02, -1, 1)
            right.trust = _clamp(right.trust - 0.03, -1, 1)
            self._adjust_social(
                agent.name, connection=-1.2, loneliness=0.45, resilience=-0.15
            )
            self._adjust_social(
                target, connection=-1.5, loneliness=0.60, resilience=-0.20
            )
            energy_support = 0.0
        elif meaningful:
            familiarity_gain = 0.015 + 0.045 * quality
            left.familiarity = _clamp(left.familiarity + familiarity_gain, 0, 1)
            right.familiarity = _clamp(right.familiarity + familiarity_gain, 0, 1)
            if reciprocal and quality >= 0.65:
                left.trust = _clamp(left.trust + 0.01, -1, 1)
                right.trust = _clamp(right.trust + 0.01, -1, 1)

            boost = 1.15 if reciprocal else 1.0
            self._adjust_social(
                agent.name,
                connection=(1.4 + 2.8 * quality) * boost,
                loneliness=-(1.8 + 3.6 * quality) * boost,
                resilience=0.25 * quality,
            )
            self._adjust_social(
                target,
                connection=(1.0 + 2.2 * quality) * boost,
                loneliness=-(1.3 + 2.8 * quality) * boost,
                resilience=0.20 * quality,
            )

            # Connection can make interaction less draining, but never creates
            # a large energy source.
            energy_support = min(
                1.0,
                (0.25 + 0.65 * quality + (0.20 if reciprocal else 0.0))
                * saturation,
            )
            agent.energy = _clamp(agent.energy + energy_support, 0, 100)
            listener_support = min(
                0.55, energy_support * (0.55 if reciprocal else 0.35)
            )
            self.agents[target].energy = _clamp(
                self.agents[target].energy + listener_support, 0, 100
            )
        else:
            familiarity_gain = 0.008 + 0.018 * quality
            left.familiarity = _clamp(left.familiarity + familiarity_gain, 0, 1)
            right.familiarity = _clamp(right.familiarity + familiarity_gain, 0, 1)
            self._adjust_social(
                agent.name, connection=0.15 * quality, loneliness=-0.10 * quality
            )
            self._adjust_social(
                target, connection=0.10 * quality, loneliness=-0.07 * quality
            )
            energy_support = 0.0

        self._record_social(
            agent.name,
            target,
            kind="talk",
            direction="outgoing",
            quality=quality,
            meaningful=meaningful,
            reciprocal=reciprocal,
            strained=strained,
        )
        self._record_social(
            target,
            agent.name,
            kind="talk",
            direction="incoming",
            quality=quality,
            meaningful=meaningful,
            reciprocal=reciprocal,
            strained=strained,
        )
        self._event(
            "social_appraisal",
            actor=agent.name,
            target=target,
            interaction="talk",
            quality=round(quality, 3),
            meaningful=meaningful,
            reciprocal=reciprocal,
            strained=strained,
            energy_before=round(energy_before, 2),
            energy_after=round(float(agent.energy), 2),
            energy_support=round(energy_support, 2),
        )

    def _apply_help_social(
        self,
        agent: Any,
        target: str,
        *,
        helper_energy_before: float,
        target_energy_before: float,
        before_left: tuple[float, float],
        before_right: tuple[float, float],
    ) -> None:
        reciprocal = self._is_reciprocal(
            agent.name, target, kinds={"help"}, within=24
        )
        saturation = self._pair_saturation(agent.name, target, within=14)
        need = _clamp((85.0 - target_energy_before) / 85.0, 0, 1)
        existing_trust = max(0.0, before_left[1], before_right[1])
        quality = _clamp(
            (
                0.22
                + 0.52 * need
                + (0.20 if reciprocal else 0.0)
                + 0.06 * existing_trust
            )
            * saturation,
            0,
            1,
        )
        meaningful = bool(need >= 0.12 and quality >= 0.38)

        # Undo the base engine's fixed relationship jump and replace it with
        # context-sensitive effects.
        left = self._relationship(agent.name, target)
        right = self._relationship(target, agent.name)
        left.familiarity, left.trust = before_left
        right.familiarity, right.trust = before_right

        if meaningful:
            familiarity_gain = 0.025 + 0.045 * quality
            left.familiarity = _clamp(left.familiarity + familiarity_gain, 0, 1)
            right.familiarity = _clamp(right.familiarity + familiarity_gain, 0, 1)
            right.trust = _clamp(
                right.trust + 0.035 + 0.075 * quality, -1, 1
            )
            if reciprocal:
                left.trust = _clamp(
                    left.trust + 0.025 + 0.035 * quality, -1, 1
                )

            boost = 1.22 if reciprocal else 1.0
            self._adjust_social(
                agent.name,
                connection=(1.3 + 2.2 * quality) * boost,
                loneliness=-(1.4 + 2.5 * quality) * boost,
                resilience=0.35 * quality,
            )
            self._adjust_social(
                target,
                connection=(1.8 + 2.8 * quality) * boost,
                loneliness=-(2.0 + 3.2 * quality) * boost,
                resilience=0.45 * quality,
            )

            # Mutual support mainly conserves the helper's energy. The recipient
            # gains more when they actually need help.
            helper_rebate = min(
                2.5,
                (1.1 * quality + (0.9 if reciprocal else 0.0)) * saturation,
            )
            helper_cost = max(0.5, 3.0 - helper_rebate)
            target_gain = 2.0 + 3.0 * need + (0.6 if reciprocal else 0.0)
        else:
            left.familiarity = _clamp(left.familiarity + 0.01, 0, 1)
            right.familiarity = _clamp(right.familiarity + 0.01, 0, 1)
            helper_rebate = 0.0
            helper_cost = 3.0
            target_gain = 1.5 + 1.5 * need

        agent.energy = _clamp(helper_energy_before - helper_cost, 0, 100)
        self.agents[target].energy = _clamp(
            target_energy_before + target_gain, 0, 100
        )

        self._record_social(
            agent.name,
            target,
            kind="help",
            direction="outgoing",
            quality=quality,
            meaningful=meaningful,
            reciprocal=reciprocal,
        )
        self._record_social(
            target,
            agent.name,
            kind="help",
            direction="incoming",
            quality=quality,
            meaningful=meaningful,
            reciprocal=reciprocal,
        )
        self._event(
            "social_appraisal",
            actor=agent.name,
            target=target,
            interaction="help",
            quality=round(quality, 3),
            meaningful=meaningful,
            reciprocal=reciprocal,
            need=round(need, 3),
            helper_energy_before=round(helper_energy_before, 2),
            helper_energy_after=round(float(agent.energy), 2),
            target_energy_before=round(target_energy_before, 2),
            target_energy_after=round(float(self.agents[target].energy), 2),
            helper_energy_conserved=round(helper_rebate, 2),
        )

    def _resolve(
        self,
        agent: Any,
        action: dict[str, Any],
        validation_note: str | None,
    ) -> dict[str, Any]:
        self._ensure_social_state()
        kind = str(action.get("type") or "")
        target = str(action.get("target") or "") if kind in {"talk", "help"} else ""
        energy_before = float(agent.energy)

        target_energy_before = None
        before_left = None
        before_right = None
        if validation_note is None and kind == "help" and target in self.agents:
            target_energy_before = float(self.agents[target].energy)
            left = self._relationship(agent.name, target)
            right = self._relationship(target, agent.name)
            before_left = (float(left.familiarity), float(left.trust))
            before_right = (float(right.familiarity), float(right.trust))

        event = super()._resolve(agent, action, validation_note)
        if validation_note is not None:
            return event

        if kind == "talk" and target in self.agents:
            self._apply_talk_social(
                agent,
                target,
                str(action.get("utterance") or ""),
                energy_before=energy_before,
            )
        elif (
            kind == "help"
            and target in self.agents
            and target_energy_before is not None
            and before_left is not None
            and before_right is not None
        ):
            self._apply_help_social(
                agent,
                target,
                helper_energy_before=energy_before,
                target_energy_before=target_energy_before,
                before_left=before_left,
                before_right=before_right,
            )
        return event
