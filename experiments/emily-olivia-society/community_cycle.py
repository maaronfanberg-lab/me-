#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
STANFORD = HERE / "vendor" / "stanford-genagents"
WORKSPACES = HERE / "workspaces"


@dataclass
class CommunityAgent:
    agent_id: int
    name: str
    workspace: Path
    brain: object


def load_specs() -> list[dict]:
    raw = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
    specs = raw.get("agents", [])
    if len(specs) != 2:
        raise RuntimeError("Emily + Olivia Community requires exactly two agents.")
    return specs


def ensure_stanford_importable() -> None:
    if not STANFORD.exists():
        raise SystemExit("Run ./bootstrap_upstreams.sh first.")
    sys.path.insert(0, str(STANFORD))


def load_agents() -> list[CommunityAgent]:
    ensure_stanford_importable()
    from genagents.genagents import GenerativeAgent

    out: list[CommunityAgent] = []
    for spec in load_specs():
        agent_id = int(spec["id"])
        name = str(spec["profile"]["name"])
        workspace = WORKSPACES / name.lower()
        if not (workspace / "scratch.json").exists():
            raise SystemExit("Run .venv-stanford/bin/python init_cognition.py first.")
        out.append(
            CommunityAgent(
                agent_id=agent_id,
                name=name,
                workspace=workspace,
                brain=GenerativeAgent(str(workspace)),
            )
        )
    return out


def latest_community_time_step(agents: list[CommunityAgent]) -> int:
    """Return the highest Stanford memory timestamp already persisted."""
    latest = 0
    for agent in agents:
        for node in agent.brain.memory_stream.seq_nodes:
            latest = max(
                latest,
                int(getattr(node, "created", 0) or 0),
                int(getattr(node, "last_retrieved", 0) or 0),
            )
    return latest


def next_community_time_step(agents: list[CommunityAgent]) -> int:
    """Return a monotonic next timestamp after all persisted community memory."""
    return latest_community_time_step(agents) + 1


def observation_text(agent: CommunityAgent, observation: dict) -> str:
    inbox = observation.get("inbox", [])
    if not inbox:
        return f"{agent.name} observes that the community contains Emily and Olivia and there are no new addressed messages."

    latest = inbox[-1]
    return (
        f"{agent.name} observes a message from {latest['from_name']}: "
        f"{latest['content']}"
    )


def choose_action(agent: CommunityAgent, observation: dict, other: CommunityAgent) -> dict:
    """Use Stanford's interaction code to produce one possible social action.

    No action is generated when there is no new addressed message. This keeps
    Layer 4 bounded and prevents boot-time autonomous conversation.
    """
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    latest = inbox[-1]
    dialogue = [
        [latest["from_name"], latest["content"]],
    ]
    response = agent.brain.utterance(
        dialogue,
        context=(
            f"You are {agent.name}. You are in a two-person community with {other.name}. "
            "Respond naturally to the addressed message."
        ),
    )
    text = str(response).strip()
    if not text:
        return {"type": "wait", "reason": "empty_utterance"}
    return {"type": "message", "recipient_id": other.agent_id, "content": text}


async def run_one_cycle() -> None:
    from controlled_social_space import ControlledSocialSpace

    agents = load_agents()
    pairs = [(agent.agent_id, agent.name) for agent in agents]
    social = ControlledSocialSpace(pairs)
    base_time_step = next_community_time_step(agents)

    cycle_log: list[dict] = []

    for offset, agent in enumerate(agents):
        other = next(a for a in agents if a.agent_id != agent.agent_id)
        time_step = base_time_step + offset

        # 1. Observe shared environment.
        observation = await social.observe_social_space(agent.agent_id)

        # 2. Remember the observation using Stanford's actual memory stream.
        memory = observation_text(agent, observation)
        agent.brain.remember(memory, time_step=time_step)

        # 3. Retrieve relevant memories using Stanford's actual retrieval path.
        retrieved = agent.brain.memory_stream.retrieve(
            [f"Current interaction with {other.name}"],
            time_step=time_step,
            n_count=12,
        )
        relevant = [
            node.content
            for node in retrieved.get(f"Current interaction with {other.name}", [])
        ]

        # 4. Think / choose an action through Stanford's interaction code.
        action = choose_action(agent, observation, other)

        # 5. Act in the AgentSociety-derived social environment, if needed.
        action_result = None
        if action["type"] == "message":
            action_result = await social.send_message(
                agent.agent_id,
                int(action["recipient_id"]),
                str(action["content"]),
            )

        # 6. Persist private memory after the cycle.
        agent.brain.save(str(agent.workspace))

        cycle_log.append(
            {
                "agent": agent.name,
                "time_step": time_step,
                "observation": observation,
                "retrieved_memories": relevant,
                "action": action,
                "action_result": action_result,
            }
        )

    print(
        json.dumps(
            {
                "start_time_step": base_time_step,
                "cycles": cycle_log,
            },
            indent=2,
        )
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded Emily + Olivia community cycle.")
    parser.add_argument(
        "--one-cycle",
        action="store_true",
        help="Explicitly permit exactly one observe→remember→retrieve→choose→act cycle per agent.",
    )
    args = parser.parse_args()

    if not args.one_cycle:
        raise SystemExit(
            "Refusing to start automatically. Use --one-cycle to permit exactly one bounded cycle."
        )

    await run_one_cycle()


if __name__ == "__main__":
    asyncio.run(main())
