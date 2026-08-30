#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from community_cycle import load_agents, next_community_time_step
from first_exchange import SocialBridgeClient, process_one_reply

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"
MAX_REPLY_TURNS = 10
DEFAULT_REPLY_TURNS = 8


async def run_community_session(opener: str, reply_turns: int) -> dict:
    if reply_turns < 2 or reply_turns > MAX_REPLY_TURNS:
        raise ValueError(
            f"reply_turns must be between 2 and {MAX_REPLY_TURNS}; got {reply_turns}."
        )

    agents = load_agents()
    emily = next(agent for agent in agents if agent.name == "Emily")
    olivia = next(agent for agent in agents if agent.name == "Olivia")
    base_time_step = next_community_time_step(agents)
    social = SocialBridgeClient()

    turns: list[dict] = []
    stop_reason = "turn_limit_reached"

    try:
        seed = await social.send_message(emily.agent_id, olivia.agent_id, opener)
        current = olivia
        other = emily

        for offset in range(reply_turns):
            turn = await process_one_reply(
                current,
                other,
                social,
                time_step=base_time_step + offset,
            )
            turns.append(turn)

            action = turn.get("action", {})
            action_result = turn.get("action_result")
            if action.get("type") != "message":
                stop_reason = str(action.get("reason", "agent_did_not_message"))
                break
            if not isinstance(action_result, dict) or not action_result.get("success"):
                stop_reason = "message_delivery_failed"
                break

            current, other = other, current
    finally:
        social.close()

    result = {
        "mode": "bounded_persistent_community_session",
        "limits": {
            "seed_messages": 1,
            "requested_reply_turns": reply_turns,
            "maximum_reply_turns": MAX_REPLY_TURNS,
            "autonomous_loop": False,
        },
        "start_time_step": base_time_step,
        "completed_reply_turns": len(turns),
        "stop_reason": stop_reason,
        "seed": seed,
        "turns": turns,
    }

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    (REPLAY_DIR / "community_session.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one bounded persistent Emily + Olivia community session."
    )
    parser.add_argument(
        "--opener",
        default="Hello, Olivia.",
        help="The one explicit seed message from Emily to Olivia.",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=DEFAULT_REPLY_TURNS,
        help=f"Maximum reply turns after the seed message (2-{MAX_REPLY_TURNS}).",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit one bounded multi-turn session, then stop.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit(
            "Refusing to start automatically. Use --run for one bounded community session."
        )

    result = await run_community_session(args.opener, args.turns)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
