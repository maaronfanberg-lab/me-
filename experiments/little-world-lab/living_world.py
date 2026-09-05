#!/usr/bin/env python3
"""Little World Lab: an auditable, model-pluggable multi-agent sandbox.

The language model proposes one structured action. The engine alone owns world
state, validates the proposal, resolves consequences, writes the event log, and
decides which observations become private memories.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

ALLOWED_ACTIONS = {"move", "talk", "help", "work", "rest", "observe"}
MAX_UTTERANCE = 240
DEFAULT_MEMORY_LIMIT = 6
REPEAT_WINDOW = 4
REPEAT_LIMIT = 3


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", str(text).casefold()))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stable_index(text: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % modulo


@dataclass
class Memory:
    id: str
    tick: int
    text: str
    importance: float = 1.0
    tags: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    familiarity: float = 0.0
    trust: float = 0.0


@dataclass
class Agent:
    name: str
    traits: list[str]
    goals: list[str]
    location: str
    energy: float = 75.0
    memories: list[Memory] = field(default_factory=list)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    action_history: list[str] = field(default_factory=list)


class ModelBackend(Protocol):
    def choose_action(self, *, agent: Agent, observation: dict[str, Any], tick: int) -> dict[str, Any]:
        ...


class StubBackend:
    """Deterministic engine exerciser. Its output is not behavioral evidence."""

    def choose_action(self, *, agent: Agent, observation: dict[str, Any], tick: int) -> dict[str, Any]:
        if agent.energy < 25:
            return {"type": "rest"}
        visible_resources = sorted(observation.get("resources", {}))
        neighbors = list(observation.get("neighbor_locations", []))
        others = list(observation.get("co_located_agents", []))
        choice = _stable_index(f"{agent.name}:{tick}", 5)
        if choice == 0 and visible_resources:
            return {"type": "work", "resource": visible_resources[0]}
        if choice == 1 and neighbors:
            return {"type": "move", "location": neighbors[0]}
        if choice == 2 and others:
            return {"type": "help", "target": others[0]}
        if choice == 3:
            return {"type": "rest"}
        return {"type": "observe"}


class BitNetBackend:
    """OpenAI-compatible localhost backend, suitable for BitNet llama-server."""

    def __init__(
        self,
        endpoint: str | None = None,
        model: str | None = None,
        timeout: int = 900,
        temperature: float = 0.7,
        max_tokens: int = 220,
    ) -> None:
        self.endpoint = endpoint or os.environ.get(
            "LIVING_WORLD_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions"
        )
        self.model = model or os.environ.get("LIVING_WORLD_MODEL_NAME", "community-bitnet")
        self.timeout = int(timeout)
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = str(text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("model did not return exactly one JSON object") from exc
        if not isinstance(value, dict):
            raise ValueError("model JSON response must be an object")
        return value

    @staticmethod
    def _prompt(agent: Agent, observation: dict[str, Any], tick: int) -> tuple[str, str]:
        system = (
            "You control one fictional agent inside a simulation. Choose exactly one feasible action "
            "from the supplied action schema using only the observations and private memories shown. "
            "Do not assume knowledge of unseen places, events, memories, or other agents' thoughts. "
            "Return JSON only. Do not explain your reasoning."
        )
        schema = {
            "move": {"type": "move", "location": "<one neighbor location>"},
            "talk": {"type": "talk", "target": "<co-located agent>", "utterance": "<natural speech>"},
            "help": {"type": "help", "target": "<co-located agent>"},
            "work": {"type": "work", "resource": "<visible resource>"},
            "rest": {"type": "rest"},
            "observe": {"type": "observe"},
        }
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
            "action_schema": schema,
            "instruction": "Return one JSON action object and nothing else.",
        }
        return system, json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def choose_action(self, *, agent: Agent, observation: dict[str, Any], tick: int) -> dict[str, Any]:
        system, user = self._prompt(agent, observation, tick)
        request_data = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": _clamp(self.temperature, 0.0, 2.0),
            "max_tokens": max(32, min(self.max_tokens, 256)),
            "stream": False,
        }
        health_url = self.endpoint.split("/v1/chat/completions", 1)[0].rstrip("/") + "/health"
        try:
            with urllib.request.urlopen(health_url, timeout=min(self.timeout, 5)) as response:
                if not (200 <= response.status < 300):
                    raise RuntimeError(f"BitNet health check returned HTTP {response.status}")
        except Exception as exc:
            raise RuntimeError(f"BitNet server is not healthy at {health_url}: {exc}") from exc

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(request_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"BitNet HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"BitNet request failed: {exc.reason}") from exc
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("BitNet response contained no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str):
            raise RuntimeError("BitNet response contained no message content")
        return self._extract_json(text)


class WorldEngine:
    def __init__(
        self,
        config: dict[str, Any],
        backend: ModelBackend,
        output_dir: Path,
        seed: int = 1,
        actors_per_tick: int = 2,
        checkpoint_every: int = 5,
    ) -> None:
        self.config = config
        self.backend = backend
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.event_path = self.output_dir / "events.jsonl"
        self.checkpoint_path = self.output_dir / "checkpoint.json"
        self.metrics_path = self.output_dir / "metrics.json"
        self.metrics_stream_path = self.output_dir / "metrics.jsonl"
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.tick = 0
        self.sequence = 0
        self.actors_per_tick = max(1, int(actors_per_tick))
        self.checkpoint_every = max(1, int(checkpoint_every))
        self.locations: dict[str, dict[str, Any]] = {
            name: {
                "neighbors": list(info.get("neighbors", [])),
                "resources": {str(k): int(v) for k, v in (info.get("resources") or {}).items()},
            }
            for name, info in (config.get("locations") or {}).items()
        }
        if not self.locations:
            raise ValueError("config.locations is required")
        self.agents: dict[str, Agent] = {}
        for row in config.get("agents") or []:
            name = str(row["name"]).strip()
            location = str(row["location"]).strip()
            if location not in self.locations:
                raise ValueError(f"unknown start location for {name}: {location}")
            if name in self.agents:
                raise ValueError(f"duplicate agent: {name}")
            self.agents[name] = Agent(
                name=name,
                traits=[str(x) for x in row.get("traits", [])],
                goals=[str(x) for x in row.get("goals", [])],
                location=location,
                energy=float(row.get("energy", 75)),
            )
        if not (1 <= len(self.agents) <= 32):
            raise ValueError("config must contain 1-32 agents")
        self.incidents = sorted(
            [dict(item) for item in config.get("incidents", [])],
            key=lambda x: int(x.get("tick", 0)),
        )
        self.applied_incidents: set[str] = set()
        self._recent_utterances: dict[str, collections.deque[str]] = {
            name: collections.deque(maxlen=8) for name in self.agents
        }

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: Path,
        backend: ModelBackend,
        output_dir: Path | None = None,
    ) -> "WorldEngine":
        data = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        engine = cls(
            data["config"],
            backend,
            output_dir or Path(checkpoint).parent,
            seed=int(data["seed"]),
            actors_per_tick=int(data["actors_per_tick"]),
            checkpoint_every=int(data["checkpoint_every"]),
        )
        engine.tick = int(data["tick"])
        engine.sequence = int(data["sequence"])
        engine.locations = data["locations"]
        engine.applied_incidents = set(data.get("applied_incidents", []))
        engine.agents = {}
        for name, row in data["agents"].items():
            engine.agents[name] = Agent(
                name=row["name"],
                traits=list(row["traits"]),
                goals=list(row["goals"]),
                location=row["location"],
                energy=float(row["energy"]),
                memories=[Memory(**m) for m in row.get("memories", [])],
                relationships={k: Relationship(**v) for k, v in row.get("relationships", {}).items()},
                action_history=list(row.get("action_history", [])),
            )
        engine._recent_utterances = {
            name: collections.deque(row.get("recent_utterances", []), maxlen=8)
            for name, row in data["agents"].items()
        }
        return engine

    def _memory_id(self, agent_name: str, text: str) -> str:
        raw = f"{self.tick}:{self.sequence}:{agent_name}:{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def _remember(self, agent_name: str, text: str, importance: float = 1.0, tags: list[str] | None = None) -> None:
        agent = self.agents[agent_name]
        agent.memories.append(
            Memory(
                id=self._memory_id(agent_name, text),
                tick=self.tick,
                text=str(text)[:600],
                importance=float(_clamp(importance, 0.0, 10.0)),
                tags=list(tags or []),
            )
        )
        if len(agent.memories) > 500:
            agent.memories = agent.memories[-500:]

    def _relevant_memories(self, agent: Agent, query: str, limit: int = DEFAULT_MEMORY_LIMIT) -> list[dict[str, Any]]:
        q = _tokens(query)
        scored: list[tuple[float, Memory]] = []
        for memory in agent.memories:
            overlap = len(q & _tokens(memory.text))
            age = max(0, self.tick - memory.tick)
            recency = max(0.0, 4.0 - age * 0.12)
            score = overlap * 3.0 + memory.importance + recency
            scored.append((score, memory))
        scored.sort(key=lambda pair: (pair[0], pair[1].tick, pair[1].id), reverse=True)
        return [
            {"id": m.id, "tick": m.tick, "text": m.text, "importance": m.importance}
            for _, m in scored[:limit]
        ]

    def _co_located(self, agent: Agent) -> list[str]:
        return sorted(
            other.name for other in self.agents.values()
            if other.name != agent.name and other.location == agent.location
        )

    def observation_for(self, agent_name: str) -> dict[str, Any]:
        agent = self.agents[agent_name]
        place = self.locations[agent.location]
        local_recent = []
        for incident in self.incidents:
            incident_id = str(incident.get("id") or f"incident-{incident.get('tick')}")
            if incident_id in self.applied_incidents and incident.get("location") == agent.location:
                local_recent.append(str(incident.get("description") or incident.get("type") or "local incident"))
        query = " ".join(agent.goals + [agent.location] + list(place["resources"]) + local_recent)
        return {
            "location": agent.location,
            "neighbor_locations": list(place["neighbors"]),
            "resources": dict(place["resources"]),
            "co_located_agents": self._co_located(agent),
            "recent_local_incidents": local_recent[-4:],
            "relevant_private_memories": self._relevant_memories(agent, query),
        }

    def _event(self, kind: str, **payload: Any) -> dict[str, Any]:
        self.sequence += 1
        event = {"tick": self.tick, "seq": self.sequence, "kind": kind, **payload}
        with self.event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _apply_incidents(self) -> None:
        for incident in self.incidents:
            if int(incident.get("tick", -1)) != self.tick:
                continue
            incident_id = str(incident.get("id") or f"incident-{self.tick}-{self.sequence}")
            if incident_id in self.applied_incidents:
                continue
            location = str(incident.get("location") or "")
            if location not in self.locations:
                self._event("incident_rejected", incident=incident_id, reason="unknown_location")
                self.applied_incidents.add(incident_id)
                continue
            resource = incident.get("resource")
            delta = int(incident.get("delta", 0))
            before = None
            after = None
            if resource is not None:
                resource = str(resource)
                before = int(self.locations[location]["resources"].get(resource, 0))
                after = max(0, before + delta)
                self.locations[location]["resources"][resource] = after
            description = str(incident.get("description") or incident.get("type") or "A local change occurred.")
            self.applied_incidents.add(incident_id)
            self._event(
                "incident",
                incident=incident_id,
                location=location,
                resource=resource,
                before=before,
                after=after,
                description=description,
            )
            for agent in self.agents.values():
                if agent.location == location:
                    self._remember(agent.name, description, importance=5.0, tags=["incident", location])

    def _action_signature(self, action: dict[str, Any]) -> str:
        compact = {k: action.get(k) for k in sorted(action) if k != "utterance"}
        if action.get("type") == "talk":
            compact["utterance"] = re.sub(r"\s+", " ", str(action.get("utterance") or "").strip().casefold())
        return json.dumps(compact, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _utterance_similarity(a: str, b: str) -> float:
        def grams(value: str) -> set[tuple[str, ...]]:
            words = re.findall(r"[a-z0-9']+", value.casefold())
            if len(words) < 3:
                return {tuple(words)} if words else set()
            return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}
        left, right = grams(a), grams(b)
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    def _validate(self, agent: Agent, proposed: Any) -> tuple[dict[str, Any], str | None]:
        if not isinstance(proposed, dict):
            return {"type": "observe"}, "proposal_not_object"
        action_type = str(proposed.get("type") or "").strip().lower()
        if action_type not in ALLOWED_ACTIONS:
            return {"type": "observe"}, "unknown_action_type"
        action: dict[str, Any] = {"type": action_type}
        if action_type == "move":
            location = str(proposed.get("location") or "").strip()
            if location not in self.locations[agent.location]["neighbors"]:
                return {"type": "observe"}, "move_not_neighbor"
            action["location"] = location
        elif action_type in {"talk", "help"}:
            target = str(proposed.get("target") or "").strip()
            if target not in self._co_located(agent):
                return {"type": "observe"}, "target_not_co_located"
            action["target"] = target
            if action_type == "talk":
                utterance = re.sub(r"\s+", " ", str(proposed.get("utterance") or "").strip())
                if not utterance:
                    return {"type": "observe"}, "empty_utterance"
                action["utterance"] = utterance[:MAX_UTTERANCE]
                normalized = action["utterance"].casefold()
                for recent in self._recent_utterances[agent.name]:
                    if self._utterance_similarity(normalized, recent) >= 0.72:
                        return {"type": "observe"}, "repeated_utterance"
        elif action_type == "work":
            resource = str(proposed.get("resource") or "").strip()
            if resource not in self.locations[agent.location]["resources"]:
                return {"type": "observe"}, "unknown_local_resource"
            action["resource"] = resource
        signature = self._action_signature(action)
        history = agent.action_history[-REPEAT_WINDOW:]
        if history.count(signature) >= REPEAT_LIMIT - 1:
            return {"type": "observe"}, "repeated_action_loop"
        return action, None

    def _relationship(self, a: str, b: str) -> Relationship:
        return self.agents[a].relationships.setdefault(b, Relationship())

    def _resolve(self, agent: Agent, action: dict[str, Any], validation_note: str | None) -> dict[str, Any]:
        before_location = agent.location
        outcome: dict[str, Any] = {"ok": validation_note is None}
        if validation_note:
            outcome["validation_note"] = validation_note
        kind = action["type"]

        if kind == "move":
            agent.location = action["location"]
            agent.energy = _clamp(agent.energy - 2, 0, 100)
            outcome.update({"from": before_location, "to": agent.location})
            memory_text = f"I moved from {before_location} to {agent.location}."
            observers = [agent.name]
        elif kind == "talk":
            target = action["target"]
            utterance = action["utterance"]
            agent.energy = _clamp(agent.energy - 1, 0, 100)
            self._recent_utterances[agent.name].append(utterance.casefold())
            memory_text = f"{agent.name} said to {target}: {utterance}"
            observers = [x.name for x in self.agents.values() if x.location == agent.location]
            outcome["heard_by"] = sorted(observers)
        elif kind == "help":
            target = action["target"]
            agent.energy = _clamp(agent.energy - 3, 0, 100)
            self.agents[target].energy = _clamp(self.agents[target].energy + 5, 0, 100)
            self._relationship(target, agent.name).trust = _clamp(
                self._relationship(target, agent.name).trust + 0.12, -1, 1
            )
            self._relationship(agent.name, target).familiarity = _clamp(
                self._relationship(agent.name, target).familiarity + 0.05, 0, 1
            )
            memory_text = f"{agent.name} helped {target} at {agent.location}."
            observers = [x.name for x in self.agents.values() if x.location == agent.location]
        elif kind == "work":
            resource = action["resource"]
            before = int(self.locations[agent.location]["resources"][resource])
            self.locations[agent.location]["resources"][resource] = before + 1
            agent.energy = _clamp(agent.energy - 5, 0, 100)
            memory_text = f"{agent.name} worked on {resource} at {agent.location}."
            outcome.update({"resource": resource, "before": before, "after": before + 1})
            observers = [x.name for x in self.agents.values() if x.location == agent.location]
        elif kind == "rest":
            before = agent.energy
            agent.energy = _clamp(agent.energy + 15, 0, 100)
            memory_text = f"I rested at {agent.location}."
            outcome.update({"energy_before": round(before, 1), "energy_after": round(agent.energy, 1)})
            observers = [agent.name]
        else:
            memory_text = f"I paused to observe {agent.location}."
            observers = [agent.name]

        event = self._event(
            "action",
            actor=agent.name,
            location=before_location if kind == "move" else agent.location,
            action=action,
            outcome=outcome,
        )
        for observer in sorted(set(observers)):
            self._remember(
                observer,
                memory_text,
                importance=2.5 if kind in {"talk", "help"} else 1.2,
                tags=["action", kind, agent.name],
            )
        signature = self._action_signature(action)
        agent.action_history.append(signature)
        agent.action_history = agent.action_history[-12:]
        return event

    def _actors_for_tick(self) -> list[str]:
        names = sorted(self.agents)
        order_rng = random.Random(f"{self.seed}:turn_order:{self.tick}")
        order_rng.shuffle(names)
        return names[: min(self.actors_per_tick, len(names))]

    def step(self) -> list[dict[str, Any]]:
        self.tick += 1
        self._apply_incidents()
        events = []
        for name in self._actors_for_tick():
            agent = self.agents[name]
            observation = self.observation_for(name)
            try:
                proposed = self.backend.choose_action(agent=agent, observation=observation, tick=self.tick)
            except Exception as exc:
                proposed = {"type": "observe"}
                note = f"backend_error:{type(exc).__name__}"
                self._event("backend_error", actor=name, error_type=type(exc).__name__, message=str(exc)[:300])
            else:
                note = None
            action, validation_note = self._validate(agent, proposed)
            if validation_note:
                note = validation_note
                self._event(
                    "proposal_rejected",
                    actor=name,
                    proposed=proposed if isinstance(proposed, dict) else repr(proposed)[:300],
                    reason=validation_note,
                )
            events.append(self._resolve(agent, action, note))
        snapshot = self.compute_metrics()
        with self.metrics_stream_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot, sort_keys=True) + "\n")
        if self.tick % self.checkpoint_every == 0:
            self.save_checkpoint()
        return events

    def run(self, ticks: int) -> dict[str, Any]:
        for _ in range(max(0, int(ticks))):
            self.step()
        self.save_checkpoint()
        metrics = self.compute_metrics()
        self.metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return metrics

    def save_checkpoint(self) -> None:
        payload = {
            "version": 1,
            "config": self.config,
            "seed": self.seed,
            "tick": self.tick,
            "sequence": self.sequence,
            "actors_per_tick": self.actors_per_tick,
            "checkpoint_every": self.checkpoint_every,
            "locations": self.locations,
            "applied_incidents": sorted(self.applied_incidents),
            "agents": {},
        }
        for name, agent in sorted(self.agents.items()):
            row = asdict(agent)
            row["recent_utterances"] = list(self._recent_utterances[name])
            payload["agents"][name] = row
        tmp = self.checkpoint_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.checkpoint_path)

    def compute_metrics(self) -> dict[str, Any]:
        actions = collections.Counter()
        pairs: set[tuple[str, str]] = set()
        utterances: list[str] = []
        rejected = 0
        backend_errors = 0
        location_counts = collections.Counter()
        if self.event_path.exists():
            for line in self.event_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("kind") == "action":
                    action = event.get("action") or {}
                    kind = str(action.get("type") or "unknown")
                    actions[kind] += 1
                    actor = str(event.get("actor") or "")
                    location_counts[str(event.get("location") or "")] += 1
                    target = action.get("target")
                    if actor and target:
                        pairs.add(tuple(sorted((actor, str(target)))))
                    if kind == "talk":
                        utterances.append(re.sub(r"\s+", " ", str(action.get("utterance") or "").casefold()).strip())
                elif event.get("kind") == "proposal_rejected":
                    rejected += 1
                elif event.get("kind") == "backend_error":
                    backend_errors += 1
        total_actions = sum(actions.values())
        action_entropy = 0.0
        if total_actions:
            for count in actions.values():
                p = count / total_actions
                action_entropy -= p * math.log2(p)
        location_total = sum(location_counts.values())
        location_entropy = 0.0
        if location_total:
            for count in location_counts.values():
                p = count / location_total
                location_entropy -= p * math.log2(p)
        repeats = len(utterances) - len(set(utterances))
        return {
            "ticks": self.tick,
            "agents": len(self.agents),
            "total_actions": total_actions,
            "action_counts": dict(sorted(actions.items())),
            "action_entropy_bits": round(action_entropy, 4),
            "location_entropy_bits": round(location_entropy, 4),
            "unique_interaction_pairs": len(pairs),
            "proposal_rejections": rejected,
            "backend_errors": backend_errors,
            "talk_turns": len(utterances),
            "exact_repeated_utterance_rate": round(repeats / len(utterances), 4) if utterances else 0.0,
            "note": "These are engineering diagnostics, not measures of human realism or consciousness.",
        }


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_backend(args: argparse.Namespace) -> ModelBackend:
    if args.backend == "stub":
        return StubBackend()
    return BitNetBackend(
        endpoint=args.endpoint,
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Little World Lab simulation.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("world.json"))
    parser.add_argument("--backend", choices=("stub", "bitnet"), default="stub")
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--actors-per-tick", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("runs") / f"run-{int(time.time())}")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=220)
    args = parser.parse_args()

    backend = build_backend(args)
    if args.resume:
        engine = WorldEngine.from_checkpoint(args.resume, backend=backend, output_dir=args.output)
    else:
        engine = WorldEngine(
            load_config(args.config),
            backend=backend,
            output_dir=args.output,
            seed=args.seed,
            actors_per_tick=args.actors_per_tick,
            checkpoint_every=args.checkpoint_every,
        )
    metrics = engine.run(args.ticks)
    print(json.dumps({"output": str(args.output), "metrics": metrics}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
