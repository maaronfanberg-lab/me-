#!/usr/bin/env python3
"""Falcon-specific live adapter for Little World Lab.

The model is allowed to propose one action. WorldEngine remains the only code
that validates and mutates simulation state.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

from living_world import Agent, BitNetBackend, WorldEngine, load_config

MAX_RESPONSE_SCAN_CHARS = 12_000


def extract_first_complete_json_object(text: str, max_chars: int = MAX_RESPONSE_SCAN_CHARS) -> dict[str, Any]:
    """Return the first complete top-level JSON object without repairing text.

    Leading/trailing prose is tolerated because small local models sometimes
    ignore formatting instructions. Braces inside quoted JSON strings do not
    affect balancing. Truncated or malformed objects are rejected rather than
    guessed at or auto-closed.
    """
    source = str(text or "")
    if len(source) > max_chars:
        source = source[:max_chars]
    if source.lstrip().startswith("["):
        raise ValueError("model JSON response must be an object, not an array")
    start = source.find("{")
    if start < 0:
        raise ValueError("model response contained no JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("model JSON object is malformed")
            if depth == 0:
                candidate = source[start : index + 1]
                try:
                    value = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise ValueError("model JSON object is malformed") from exc
                if not isinstance(value, dict):
                    raise ValueError("model JSON response must be an object")
                return value

    raise ValueError("model JSON object was truncated or unclosed")


class FalconBackend(BitNetBackend):
    """OpenAI-compatible Falcon adapter with schema-constrained JSON output."""

    _extract_json = staticmethod(extract_first_complete_json_object)

    @staticmethod
    def _feasibility_constraints(observation: dict[str, Any]) -> dict[str, list[str]]:
        """Expose only action arguments the engine currently considers local/visible.

        This does not validate or resolve anything. It simply prevents the prompt
        and decoder from making a small model rediscover constraints already
        present in its observation, while WorldEngine remains the authority on
        acceptance and state mutation.
        """
        move_locations = sorted(
            {str(value).strip() for value in observation.get("neighbor_locations", []) if str(value).strip()}
        )
        interaction_targets = sorted(
            {str(value).strip() for value in observation.get("co_located_agents", []) if str(value).strip()}
        )
        resources = observation.get("resources") or {}
        work_resources = sorted({str(value).strip() for value in resources if str(value).strip()})
        return {
            "move_locations": move_locations,
            "interaction_targets": interaction_targets,
            "work_resources": work_resources,
            "always_allowed": ["rest", "observe"],
        }

    @staticmethod
    def _action_schema(action_type: str, observation: dict[str, Any]) -> dict[str, Any]:
        feasible = FalconBackend._feasibility_constraints(observation)
        properties: dict[str, Any] = {"type": {"type": "string", "enum": [action_type]}}
        required = ["type"]
        if action_type == "move":
            values = feasible["move_locations"]
            if not values:
                raise ValueError("move has no feasible locations")
            properties["location"] = {"type": "string", "enum": values}
            required.append("location")
        elif action_type == "talk":
            values = feasible["interaction_targets"]
            if not values:
                raise ValueError("talk has no feasible targets")
            properties["target"] = {"type": "string", "enum": values}
            properties["utterance"] = {"type": "string", "minLength": 1, "maxLength": 160}
            required.extend(["target", "utterance"])
        elif action_type == "help":
            values = feasible["interaction_targets"]
            if not values:
                raise ValueError("help has no feasible targets")
            properties["target"] = {"type": "string", "enum": values}
            required.append("target")
        elif action_type == "work":
            values = feasible["work_resources"]
            if not values:
                raise ValueError("work has no feasible resources")
            properties["resource"] = {"type": "string", "enum": values}
            required.append("resource")
        elif action_type not in {"rest", "observe"}:
            raise ValueError(f"unsupported action type: {action_type}")
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    @classmethod
    def _response_schema(cls, observation: dict[str, Any]) -> dict[str, Any]:
        """Constrain generation to syntactically and locally feasible actions.

        llama.cpp converts this JSON schema to a generation grammar. The engine
        still revalidates every proposal, so constrained decoding reduces model
        format noise without moving authority out of WorldEngine.
        """
        feasible = cls._feasibility_constraints(observation)
        branches = [cls._action_schema("rest", observation), cls._action_schema("observe", observation)]
        if feasible["move_locations"]:
            branches.append(cls._action_schema("move", observation))
        if feasible["interaction_targets"]:
            branches.append(cls._action_schema("talk", observation))
            branches.append(cls._action_schema("help", observation))
        if feasible["work_resources"]:
            branches.append(cls._action_schema("work", observation))
        return {"oneOf": branches}

    @staticmethod
    def _canonicalize_proposal(proposed: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        """Normalize one narrow legacy Falcon schema alias without weakening safety.

        Older unconstrained Falcon runs sometimes emitted a visible work resource
        under the generic key ``location``. Keep the compatibility normalization
        for old callers, but only when the value is already in the visible local
        resource allowlist. New schema-constrained requests should not need it.
        """
        if not isinstance(proposed, dict):
            return proposed
        normalized = dict(proposed)
        if str(normalized.get("type") or "").strip().lower() != "work":
            return normalized
        if str(normalized.get("resource") or "").strip():
            return normalized
        allowed = set(FalconBackend._feasibility_constraints(observation)["work_resources"])
        alias_value = str(normalized.get("location") or "").strip()
        if alias_value and alias_value in allowed:
            normalized.pop("location", None)
            normalized["resource"] = alias_value
        return normalized

    @staticmethod
    def _prompt(agent: Agent, observation: dict[str, Any], tick: int) -> tuple[str, str]:
        system = (
            "You control one fictional simulation agent. Choose one action that advances the agent's goals "
            "using only the supplied observation and private memories. Never assume unseen places, events, "
            "memories, or other agents' thoughts. The server constrains your response to a feasible JSON "
            "action schema, so focus on choosing the best available action. For talk, write a fresh short "
            "natural utterance. Do not copy a placeholder or explain your reasoning."
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
            "feasibility": FalconBackend._feasibility_constraints(observation),
            "instruction": "Choose one feasible action. Return only the schema-constrained JSON object.",
        }
        return system, json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def choose_action(self, *, agent: Agent, observation: dict[str, Any], tick: int) -> dict[str, Any]:
        system, user = self._prompt(agent, observation, tick)
        schema = self._response_schema(observation)
        request_data = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": max(0.0, min(self.temperature, 2.0)),
            "max_tokens": max(32, min(self.max_tokens, 256)),
            "stream": False,
            "response_format": {"type": "json_object", "schema": schema},
        }
        health_url = self.endpoint.split("/v1/chat/completions", 1)[0].rstrip("/") + "/health"
        try:
            with urllib.request.urlopen(health_url, timeout=min(self.timeout, 5)) as response:
                if not (200 <= response.status < 300):
                    raise RuntimeError(f"Falcon health check returned HTTP {response.status}")
        except Exception as exc:
            raise RuntimeError(f"Falcon server is not healthy at {health_url}: {exc}") from exc

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
            raise RuntimeError(f"Falcon HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falcon request failed: {exc.reason}") from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Falcon response contained no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str):
            raise RuntimeError("Falcon response contained no message content")
        proposed = self._extract_json(text)
        return self._canonicalize_proposal(proposed, observation)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Little World Lab with the isolated Falcon adapter.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("world.json"))
    parser.add_argument("--ticks", type=int, default=4)
    parser.add_argument("--actors-per-tick", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("runs") / f"falcon-{int(time.time())}")
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    backend = FalconBackend(
        endpoint=args.endpoint,
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
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
