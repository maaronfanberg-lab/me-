#!/usr/bin/env python3
"""Falcon-specific live adapter for Little World Lab.

The model is allowed to propose one action. WorldEngine remains the only code
that validates and mutates simulation state.
"""
from __future__ import annotations

import argparse
import json
import time
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
    """OpenAI-compatible Falcon adapter with bounded JSON extraction."""

    _extract_json = staticmethod(extract_first_complete_json_object)

    @staticmethod
    def _feasibility_constraints(observation: dict[str, Any]) -> dict[str, list[str]]:
        """Expose only action arguments the engine currently considers local/visible.

        This does not validate or resolve anything. It simply prevents the prompt
        from making a small model rediscover constraints already present in its
        observation, while WorldEngine remains the authority on acceptance.
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
    def _prompt(agent: Agent, observation: dict[str, Any], tick: int) -> tuple[str, str]:
        system = (
            "Output one JSON object immediately. Your first non-whitespace character must be { and "
            "your last non-whitespace character must be }. Do not think aloud. Do not use markdown, "
            "analysis, explanations, labels, or preambles. You control one fictional simulation agent. "
            "Choose exactly one feasible action using only the observation and private memories shown. "
            "Never assume unseen places, events, memories, or other agents' thoughts. Use only values "
            "listed in the feasibility constraints. If move_locations is empty, do not move; otherwise "
            "a move location must be one of those values and must not be the current location unless it "
            "is explicitly listed. Talk/help targets must be in interaction_targets. Work resources must "
            "be in work_resources. If one of those lists is empty, do not choose its dependent action. "
            "For talk, generate a fresh short natural utterance yourself rather than copying a placeholder. "
            "Prefer a concrete feasible action that advances the agent's stated goals when one is available; "
            "use rest or observe when they genuinely fit. Valid action forms are: "
            '{"type":"move","location":"NAME"}; '
            '{"type":"talk","target":"NAME","utterance":"WORDS"}; '
            '{"type":"help","target":"NAME"}; '
            '{"type":"work","resource":"NAME"}; '
            '{"type":"rest"}; '
            '{"type":"observe"}. '
            "Choose now and output only the object."
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
            "instruction": "Choose one feasible action that obeys the feasibility lists. JSON object only.",
        }
        return system, json.dumps(payload, ensure_ascii=False, sort_keys=True)


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
