#!/usr/bin/env python3
"""Run or resume Cedar Hollow one or more ticks and emit a read-only live snapshot.

This module does not publish network data and does not bypass WorldEngine.
Falcon remains only a proposer. WorldEngine validates, resolves, and owns state.
A workflow may copy ``live-state.json`` to a public read-only branch for viewers.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from falcon_live import FalconBackend
from living_world import WorldEngine, load_config

LIVE_STATE_VERSION = 1
DEFAULT_EVENT_TAIL = 120


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_event_tail(path: Path, limit: int = DEFAULT_EVENT_TAIL) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-max(1, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _session_metadata(output_dir: Path, session_id: str) -> dict[str, Any]:
    path = output_dir / "live-session.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    data = {"session_id": str(session_id), "started_at": _utc_now()}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def build_live_state(
    engine: WorldEngine,
    *,
    status: str,
    session_id: str,
    model: str,
    temperature: float,
    event_tail: int = DEFAULT_EVENT_TAIL,
) -> dict[str, Any]:
    """Return public simulation state suitable for a read-only viewer."""
    metadata = _session_metadata(engine.output_dir, session_id)
    agents = {
        name: {
            "name": agent.name,
            "traits": list(agent.traits),
            "goals": list(agent.goals),
            "location": agent.location,
            "energy": round(agent.energy, 1),
            "memories": [asdict(memory) for memory in agent.memories[-12:]],
            "relationships": {
                other: asdict(rel)
                for other, rel in sorted(agent.relationships.items())
            },
        }
        for name, agent in sorted(engine.agents.items())
    }
    return {
        "version": LIVE_STATE_VERSION,
        "status": str(status),
        "updated_at": _utc_now(),
        "session_id": str(metadata.get("session_id") or session_id),
        "started_at": metadata.get("started_at"),
        "tick": int(engine.tick),
        "seed": int(engine.seed),
        "actors_per_tick": int(engine.actors_per_tick),
        "model": str(model),
        "temperature": float(temperature),
        "world_name": str(engine.config.get("name") or "Cedar Hollow"),
        "locations": {
            name: {
                "neighbors": list(row.get("neighbors", [])),
                "resources": dict(row.get("resources", {})),
            }
            for name, row in sorted(engine.locations.items())
        },
        "agents": agents,
        "recent_events": _read_event_tail(engine.event_path, event_tail),
        "metrics": engine.compute_metrics(),
        "read_only_note": (
            "This snapshot is observational. The viewer cannot propose actions or mutate WorldEngine state."
        ),
    }


def write_live_state(
    engine: WorldEngine,
    output_path: Path,
    *,
    status: str,
    session_id: str,
    model: str,
    temperature: float,
    event_tail: int = DEFAULT_EVENT_TAIL,
) -> dict[str, Any]:
    state = build_live_state(
        engine,
        status=status,
        session_id=session_id,
        model=model,
        temperature=temperature,
        event_tail=event_tail,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(output_path)
    return state


def load_or_create_engine(
    *,
    config_path: Path,
    output_dir: Path,
    backend: FalconBackend,
    seed: int,
    actors_per_tick: int,
    checkpoint_every: int,
) -> WorldEngine:
    checkpoint = output_dir / "checkpoint.json"
    if checkpoint.exists():
        return WorldEngine.from_checkpoint(checkpoint, backend=backend, output_dir=output_dir)
    return WorldEngine(
        load_config(config_path),
        backend=backend,
        output_dir=output_dir,
        seed=seed,
        actors_per_tick=actors_per_tick,
        checkpoint_every=checkpoint_every,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance Cedar Hollow and emit a live read-only snapshot.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("world.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path)
    parser.add_argument("--ticks", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--actors-per-tick", type=int, default=2)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--status", choices=["starting", "live", "complete", "error"], default="live")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--event-tail", type=int, default=DEFAULT_EVENT_TAIL)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    state_output = args.state_output or (args.output / "live-state.json")

    backend = FalconBackend(
        endpoint=args.endpoint,
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    engine = load_or_create_engine(
        config_path=args.config,
        output_dir=args.output,
        backend=backend,
        seed=args.seed,
        actors_per_tick=args.actors_per_tick,
        checkpoint_every=args.checkpoint_every,
    )

    for _ in range(max(0, int(args.ticks))):
        engine.step()
    engine.save_checkpoint()
    state = write_live_state(
        engine,
        state_output,
        status=args.status,
        session_id=args.session_id,
        model=args.model or backend.model,
        temperature=args.temperature,
        event_tail=args.event_tail,
    )
    print(json.dumps({
        "state_output": str(state_output),
        "status": state["status"],
        "tick": state["tick"],
        "session_id": state["session_id"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
