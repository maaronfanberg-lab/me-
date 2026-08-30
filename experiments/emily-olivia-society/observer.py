#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACES = HERE / "workspaces"
REPLAY_DIR = HERE / "replay"
OBSERVER_OUTPUT = "observer.json"


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def file_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_agent(name: str) -> dict:
    workspace = WORKSPACES / name.lower()
    scratch_path = workspace / "scratch.json"
    nodes_path = workspace / "memory_stream" / "nodes.json"
    embeddings_path = workspace / "memory_stream" / "embeddings.json"
    meta_path = workspace / "meta.json"

    nodes = read_json(nodes_path, [])
    return {
        "name": name,
        "workspace_exists": workspace.exists(),
        "scratch": read_json(scratch_path, {}),
        "memory_count": len(nodes) if isinstance(nodes, list) else 0,
        "memories": nodes if isinstance(nodes, list) else [],
        "files": {
            "scratch": file_digest(scratch_path),
            "nodes": file_digest(nodes_path),
            "embeddings": file_digest(embeddings_path),
            "meta": file_digest(meta_path),
        },
    }


def snapshot_replays() -> list[dict]:
    if not REPLAY_DIR.exists():
        return []

    out = []
    for path in sorted(REPLAY_DIR.glob("*.json")):
        # When stdout is redirected to replay/observer.json, the shell creates
        # that file before observer.py starts. Never let the observer try to
        # parse or hash its own in-progress output.
        if path.name == OBSERVER_OUTPUT:
            continue
        out.append(
            {
                "file": path.name,
                "sha256": file_digest(path),
                "content": read_json(path, {}),
            }
        )
    return out


def build_snapshot() -> dict:
    before = {
        "emily": snapshot_agent("Emily"),
        "olivia": snapshot_agent("Olivia"),
        "replays": snapshot_replays(),
    }

    # Re-read file hashes after all reads to prove observation itself did not mutate state.
    after_hashes = {
        "emily": snapshot_agent("Emily")["files"],
        "olivia": snapshot_agent("Olivia")["files"],
        "replays": [
            {"file": item["file"], "sha256": item["sha256"]}
            for item in snapshot_replays()
        ],
    }

    before_hashes = {
        "emily": before["emily"]["files"],
        "olivia": before["olivia"]["files"],
        "replays": [
            {"file": item["file"], "sha256": item["sha256"]}
            for item in before["replays"]
        ],
    }

    return {
        "mode": "read_only_observation",
        "mutation_detected": before_hashes != after_hashes,
        "agents": {
            "Emily": before["emily"],
            "Olivia": before["olivia"],
        },
        "replays": before["replays"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only observer for the Emily + Olivia Community."
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact summary instead of the full persisted state.",
    )
    args = parser.parse_args()

    snapshot = build_snapshot()
    if snapshot["mutation_detected"]:
        raise SystemExit("Read-only invariant failed: persisted state changed during observation.")

    if args.summary:
        compact = {
            "mode": snapshot["mode"],
            "mutation_detected": False,
            "agents": {
                name: {
                    "workspace_exists": data["workspace_exists"],
                    "memory_count": data["memory_count"],
                }
                for name, data in snapshot["agents"].items()
            },
            "replay_files": [item["file"] for item in snapshot["replays"]],
        }
        print(json.dumps(compact, indent=2))
    else:
        print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
