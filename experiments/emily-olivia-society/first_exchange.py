#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from community_cycle import load_agents, observation_text, choose_action
from controlled_social_space import ControlledSocialSpace

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"


async def process_one_reply(agent, other, social, time_step: int) -> dict:
    observation = await social.observe_social_space(agent.agent_id)
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"agent": agent.name, "action": {"type": "wait", "reason": "no_new_message"}}

    latest = inbox[-1]
    memory = observation_text(agent, observation)
    agent.brain.remember(memory, time_step=time_step)

    query = f"Current interaction with {other.name}"
    retrieved = agent.brain.memory_stream.retrieve([query], time_step=time_step, n_count=12)
    relevant = [node.content for node in retrieved.get(query, [])]

    action = choose_action(agent, observation, other)
    result = None
    if action["type"] == "message":
        result = await social.send_message(
            agent.agent_id,
            int(action["recipient_id"]),
            str(action["content"]),
        )

    await social.consume_message(agent.agent_id, int(latest["id"]))
    agent.brain.save(str(agent.workspace))

    return {
        "agent": agent.name,
        "observation": observation,
        "retrieved_memories": relevant,
        "action": action,
        "action_result": result,
    }


async def run_first_exchange(opener: str) -> dict:
    agents = load_agents()
    emily = next(a for a in agents if a.name == "Emily")
    olivia = next(a for a in agents if a.name == "Olivia")
    social = ControlledSocialSpace([(a.agent_id, a.name) for a in agents])

    seed = await social.send_message(emily.agent_id, olivia.agent_id, opener)
    olivia_turn = await process_one_reply(olivia, emily, social, time_step=1)
    emily_turn = await process_one_reply(emily, olivia, social, time_step=2)

    transcript = {
        "mode": "bounded_first_exchange",
        "limits": {
            "seed_messages": 1,
            "reply_turns": 2,
            "autonomous_loop": False,
        },
        "seed": seed,
        "turns": [olivia_turn, emily_turn],
    }

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    (REPLAY_DIR / "first_exchange.json").write_text(
        json.dumps(transcript, indent=2),
        encoding="utf-8",
    )
    return transcript


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first bounded Emily + Olivia exchange.")
    parser.add_argument(
        "--opener",
        default="Hello, Olivia.",
        help="The single initial message from Emily to Olivia.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit one seed message, Olivia's reply, and Emily's reply, then stop.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("Refusing to start automatically. Use --run for exactly one bounded first exchange.")

    result = await run_first_exchange(args.opener)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
