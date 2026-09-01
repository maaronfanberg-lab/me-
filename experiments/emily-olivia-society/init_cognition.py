#!/usr/bin/env python3
"""Layer 2 bootstrap: create Emily and Olivia using Stanford HCI genagents.

This does not call an LLM, add memories, reflect, or start social interaction.
It only uses Stanford's GenerativeAgent and save() format to create
separate persistent agent workspaces.

Existing complete workspaces are preserved. Malformed derived reflection nodes
are removed without touching observations. Interrupted restored checkpoints that
are demonstrably trapped in a repeated-short-question attractor are rejected
before initialization. An incomplete existing workspace causes a hard failure
rather than being overwritten.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from checkpoint_attractor_guard import reject_interrupted_checkpoint_attractor
from reflection_hygiene import sanitize_memory_stream

HERE = Path(__file__).resolve().parent
STANFORD = HERE / "vendor" / "stanford-genagents"
WORKSPACES = HERE / "workspaces"


def ensure_stanford_settings() -> None:
    settings = STANFORD / "simulation_engine" / "settings.py"
    if settings.exists():
        return
    settings.write_text(
        "from pathlib import Path\n"
        "import os\n\n"
        "OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')\n"
        "KEY_OWNER = os.environ.get('KEY_OWNER', 'emily-olivia-experiment')\n"
        "DEBUG = False\n"
        "MAX_CHUNK_SIZE = 4\n"
        "LLM_VERS = os.environ.get('STANFORD_LLM_MODEL', 'gpt-4o-mini')\n"
        "BASE_DIR = f'{Path(__file__).resolve().parent.parent}'\n"
        "POPULATIONS_DIR = f'{BASE_DIR}/agent_bank/populations'\n"
        "LLM_PROMPT_DIR = f'{BASE_DIR}/simulation_engine/prompt_template'\n",
        encoding="utf-8",
    )


def load_profiles() -> list[dict]:
    raw = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
    agents = raw.get("agents", [])
    if len(agents) != 2:
        raise RuntimeError("This experiment must contain exactly two agents.")
    return agents


def workspace_state(workspace: Path) -> str:
    if not workspace.exists():
        return "missing"

    required = [
        workspace / "scratch.json",
        workspace / "meta.json",
        workspace / "memory_stream" / "nodes.json",
        workspace / "memory_stream" / "embeddings.json",
    ]
    if all(path.exists() and path.stat().st_size > 0 for path in required):
        return "complete"
    return "incomplete"


def main() -> None:
    if not STANFORD.exists():
        raise SystemExit("Run ./bootstrap_upstreams.sh first.")

    ensure_stanford_settings()
    sys.path.insert(0, str(STANFORD))

    rejected = reject_interrupted_checkpoint_attractor()
    if rejected:
        print(
            "Rejected interrupted Community checkpoint trapped in a repeated "
            "short-question attractor; initializing clean cognition."
        )

    from genagents.genagents import GenerativeAgent

    WORKSPACES.mkdir(parents=True, exist_ok=True)

    for spec in load_profiles():
        profile = spec["profile"]
        name = str(profile["name"])
        age = int(profile["age"])
        workspace = WORKSPACES / name.lower()
        state = workspace_state(workspace)

        if state == "complete":
            agent = GenerativeAgent(str(workspace))
            removed = sanitize_memory_stream(agent.memory_stream)
            if removed:
                agent.save(str(workspace))
                print(
                    f"Sanitized {len(removed)} malformed Stanford reflection node(s) for {name}."
                )
            print(f"Preserving existing Stanford cognition workspace: {name}")
            continue
        if state == "incomplete":
            raise SystemExit(
                f"Refusing to overwrite incomplete cognition workspace for {name}: {workspace}"
            )

        agent = GenerativeAgent()
        agent.update_scratch({"first_name": name, "age": age})
        agent.save(str(workspace))
        print(f"Initialized Stanford cognition workspace: {name} ({age})")


if __name__ == "__main__":
    main()
