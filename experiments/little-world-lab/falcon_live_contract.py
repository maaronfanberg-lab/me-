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
        system, user = FalconBackend._prompt(agent, observation, tick)
        system += (
            f" This is an integration contract probe, not a natural-behavior sample. "
            f"For this probe you must choose the feasible action type '{self.required_action_type}'. "
            "Do not choose another action type. Use only the supplied feasibility values. "
            "For talk, create a short new natural utterance from the visible context; no canned line is supplied."
        )
        payload = json.loads(user)
        payload["verification_probe"] = {
            "required_action_type": self.required_action_type,
            "attempt": self.attempt,
        }
        if self.previous_error:
            payload["verification_probe"]["previous_validation_error"] = self.previous_error
            payload["instruction"] = (
                f"Previous attempt failed with {self.previous_error}. Correct that constraint and return "
                f"one feasible {self.required_action_type} JSON action only."
            )
        else:
            payload["instruction"] = (
                f"Return one feasible {self.required_action_type} JSON action only for this verification probe."
            )
        return system, json.dumps(payload, ensure_ascii=False, sort_keys=True)


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
    parser.add_argument("--max-tokens", type=int, default=160)
    parser.add_argument("--max-attempts", type=int, default=3)
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
