#!/usr/bin/env python3
"""Layer 2 bootstrap: create Emily and Olivia using Stanford HCI genagents.

This does not call an LLM, add memories, reflect, or start social interaction.
It only uses Stanford's GenerativeAgent class and save() format to create
separate persistent agent workspaces.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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


def main() -> None:
    if not STANFORD.exists():
        raise SystemExit("Run ./bootstrap_upstreams.sh first.")

    ensure_stanford_settings()
    sys.path.insert(0, str(STANFORD))

    from genagents.genagents import GenerativeAgent

    WORKSPACES.mkdir(parents=True, exist_ok=True)

    for spec in load_profiles():
        profile = spec["profile"]
        name = str(profile["name"])
        age = int(profile["age"])
        workspace = WORKSPACES / name.lower()

        agent = GenerativeAgent()
        agent.update_scratch({"first_name": name, "age": age})
        agent.save(str(workspace))
        print(f"Initialized Stanford cognition workspace: {name} ({age})")


if __name__ == "__main__":
    main()
