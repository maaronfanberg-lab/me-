#!/usr/bin/env python3
"""Live Falcon action-contract probes for Little World Lab.

These probes deliberately request each closed action type so the real model,
adapter parser, and WorldEngine validator/resolver path are exercised end to
end. They are integration evidence, not natural-behavior evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from falcon_live import FalconBackend
from living_world import WorldEngine

ACTION_TYPES = ("move", "talk", "help", "work", "rest", "observe")


class RequiredActionFalconBackend(FalconBackend):
    """Falcon adapter variant used only by the directed contract probe."""

    def __init__(
        self,
        required_action_type: str,
        *,
        attempt: int,
        previous_error: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.required_action_type = required_action_type
        self.attempt = int(attempt)
        self.previous_error = previous_error

    def _prompt(self, agent, observation, tick):
        """Use a deliberately tiny action-specific prompt for the 1B probe.

        The natural-behavior run uses FalconBackend's richer prompt. These
        directed probes only prove that each closed action contract can travel
        through the live model, parser, validator, and resolver. Keeping the
        prompt small avoids spending a 2K context window on irrelevant agent
        biography and then truncating a tiny JSON reply.
        """
        action_type = self.required_action_type
        feasible = FalconBackend._feasibility_constraints(observation)
        allowed: dict[str, Any] = {}
        contract: dict[str, Any]

        if action_type == "move":
            allowed["location"] = feasible["move_locations"]
            contract = {"required_keys": ["type", "location"]}
        elif action_type == "talk":
            allowed["target"] = feasible["interaction_targets"]
            contract = {
                "required_keys": ["type", "target", "utterance"],
                "utterance_rule": "generate 1-8 natural words; no canned line is supplied",
            }
        elif action_type == "help":
            allowed["target"] = feasible["interaction_targets"]
            contract = {"required_keys": ["type", "target"]}
        elif action_type == "work":
            allowed["resource"] = feasible["work_resources"]
            contract = {"required_keys": ["type", "resource"], "forbidden_keys": ["location", "target"]}
        elif action_type in {"rest", "observe"}:
            contract = {"required_keys": ["type"]}
        else:
            raise ValueError(f"unsupported probe action: {action_type}")

        system = (
            "Return exactly one MINIFIED JSON object and nothing else. "
            "No prose, markdown, code fence, labels, reasoning, or second object. "
            "Start with { and end with }. Keep the entire reply under 100 characters. "
            f"This integration probe requires action type {action_type!r}; do not choose another type. "
            "Use exactly the required keys. Use only listed allowed values. "
            "For talk, invent the short utterance yourself."
        )
        payload: dict[str, Any] = {
            "required_action_type": action_type,
            "allowed": allowed,
            "contract": contract,
            "attempt": self.attempt,
        }
        if self.previous_error:
            payload["previous_error"] = self.previous_error
            payload["instruction"] = "Correct the previous error. Output the one JSON object now."
        else:
            payload["instruction"] = "Output the one JSON object now."
        return system, json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _agent(name: str, location: str, *, energy: float = 70.0) -> dict[str, Any]:
    return {
        "name": name,
        "location": location,
        "traits": ["careful", "cooperative"],
        "goals": ["follow visible constraints", "act only on local information"],
        "energy": energy,
    }


def probe_config(action_type: str) -> dict[str, Any]:
    if action_type == "move":
        return {
            "name": "move-probe",
            "locations": {
                "origin": {"neighbors": ["destination"], "resources": {}},
                "destination": {"neighbors": ["origin"], "resources": {}},
            },
            "agents": [_agent("ProbeA", "origin")],
            "incidents": [],
        }
    if action_type in {"talk", "help"}:
        return {
            "name": f"{action_type}-probe",
            "locations": {"room": {"neighbors": [], "resources": {}}},
            "agents": [_agent("ProbeA", "room"), _agent("ProbeB", "room")],
            "incidents": [],
        }
    if action_type == "work":
        return {
            "name": "work-probe",
            "locations": {"shop": {"neighbors": [], "resources": {"parts": 1}}},
            "agents": [_agent("ProbeA", "shop")],
            "incidents": [],
        }
    if action_type == "rest":
        return {
            "name": "rest-probe",
            "locations": {"room": {"neighbors": [], "resources": {}}},
            "agents": [_agent("ProbeA", "room", energy=10.0)],
            "incidents": [],
        }
    if action_type == "observe":
        return {
            "name": "observe-probe",
            "locations": {"room": {"neighbors": [], "resources": {}}},
            "agents": [_agent("ProbeA", "room")],
            "incidents": [],
        }
    raise ValueError(f"unsupported probe action: {action_type}")


def run_probe(
    action_type: str,
    *,
    output_dir: Path,
    endpoint: str | None,
    model: str | None,
    timeout: int,
    temperature: float,
    max_tokens: int,
    max_attempts: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = WorldEngine(
        probe_config(action_type),
        backend=RequiredActionFalconBackend(
            action_type,
            attempt=1,
            endpoint=endpoint,
            model=model,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        output_dir=output_dir,
        seed=1,
        actors_per_tick=1,
        checkpoint_every=1,
    )
    engine.tick = 1
    actor_name = sorted(engine.agents)[0]
    agent = engine.agents[actor_name]
    observation = engine.observation_for(actor_name)
    attempts: list[dict[str, Any]] = []
    previous_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        backend = RequiredActionFalconBackend(
            action_type,
            attempt=attempt,
            previous_error=previous_error,
            endpoint=endpoint,
            model=model,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            proposed = backend.choose_action(agent=agent, observation=observation, tick=engine.tick)
        except Exception as exc:
            previous_error = f"backend_error:{type(exc).__name__}"
            attempts.append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "error": previous_error,
                    "message": str(exc)[:300],
                }
            )
            continue

        action, validation_note = engine._validate(agent, proposed)
        if validation_note:
            previous_error = validation_note
        elif action.get("type") != action_type:
            previous_error = f"wrong_action_type:{action.get('type')}"
        else:
            event = engine._resolve(agent, action, None)
            engine.save_checkpoint()
            metrics = engine.compute_metrics()
            (output_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "ok": True,
                    "proposed": proposed,
                    "validated": action,
                    "event": event,
                }
            )
            return {
                "action_type": action_type,
                "ok": True,
                "attempts": attempts,
                "accepted_attempt": attempt,
            }

        attempts.append(
            {
                "attempt": attempt,
                "ok": False,
                "proposed": proposed,
                "validation_error": previous_error,
            }
        )

    return {
        "action_type": action_type,
        "ok": False,
        "attempts": attempts,
        "final_error": previous_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe all Little World action types through live Falcon.")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("runs") / "falcon-live-contract")
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--max-attempts", type=int, default=4)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for action_type in ACTION_TYPES:
        result = run_probe(
            action_type,
            output_dir=args.output / action_type,
            endpoint=args.endpoint,
            model=args.model,
            timeout=args.timeout,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_attempts=max(1, min(args.max_attempts, 5)),
        )
        results.append(result)

    passed = [row["action_type"] for row in results if row["ok"]]
    summary = {
        "ok": len(passed) == len(ACTION_TYPES),
        "required_action_types": list(ACTION_TYPES),
        "passed_action_types": passed,
        "results": results,
        "note": "Directed contract probes verify live model/adapter/engine paths; they are not natural-behavior evidence.",
    }
    (args.output / "probe-results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
