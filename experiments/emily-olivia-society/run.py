#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety

from controlled_social_space import ControlledSocialSpace

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE / "run"


def load_agents() -> list[dict]:
    data = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
    agents = data.get("agents")
    if not isinstance(agents, list) or len(agents) != 2:
        raise RuntimeError("This experiment must contain exactly two agents.")
    return agents


async def main() -> None:
    agents = load_agents()
    pairs = [(int(agent["id"]), str(agent["profile"]["name"])) for agent in agents]

    social_space = ControlledSocialSpace(agent_id_name_pairs=pairs)
    environment = CodeGenRouter(env_modules=[social_space])

    society = AgentSociety(
        agent_specs=agents,
        agent_class_name="PersonAgent",
        env_router=environment,
        start_t=datetime.now(),
        run_dir=RUN_DIR,
    )

    await society.init()
    try:
        print("Two-agent society initialized:", ", ".join(name for _, name in pairs))
        print("Layer 3 social boundary active: addressed messages only; private memory is not exposed.")
        print("No autonomous interaction is started by this launcher yet.")
    finally:
        await society.close()


if __name__ == "__main__":
    asyncio.run(main())
