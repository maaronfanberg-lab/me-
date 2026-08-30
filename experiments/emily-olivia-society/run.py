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
        raise RuntimeError("This community must contain exactly two agents.")
    return agents


async def main() -> None:
    agents = load_agents()
    pairs = [(int(agent["id"]), str(agent["profile"]["name"])) for agent in agents]

    social_space = ControlledSocialSpace(agent_id_name_pairs=pairs)
    environment = CodeGenRouter(env_modules=[social_space])

    # AgentSociety is the upstream Tsinghua runtime class. We call the project
    # a community at our layer; the upstream class name is intentionally unchanged.
    community_runtime = AgentSociety(
        agent_specs=agents,
        agent_class_name="PersonAgent",
        env_router=environment,
        start_t=datetime.now(),
        run_dir=RUN_DIR,
    )

    await community_runtime.init()
    try:
        print("Emily + Olivia Community initialized:", ", ".join(name for _, name in pairs))
        print("Controlled social boundary active: addressed messages only; private memory is not exposed.")
        print("No autonomous interaction is started by this launcher.")
        print("Use community_cycle.py --one-cycle for one explicit research-style cycle.")
    finally:
        await community_runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
