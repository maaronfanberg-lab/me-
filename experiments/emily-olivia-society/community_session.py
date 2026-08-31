#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from community_cycle import load_agents, next_community_time_step
from first_exchange import SocialBridgeClient, process_one_reply

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"
MAX_REPLY_TURNS = 10
DEFAULT_REPLY_TURNS = 8


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


async def run_community_session(
    opener: str,
    reply_turns: int,
    continuous_seconds: int = 0,
    turn_delay_seconds: float = 0.0,
) -> dict:
    if continuous_seconds <= 0 and (reply_turns < 2 or reply_turns > MAX_REPLY_TURNS):
        raise ValueError(
            f"reply_turns must be between 2 and {MAX_REPLY_TURNS}; got {reply_turns}."
        )
    if continuous_seconds < 0:
        raise ValueError("continuous_seconds must be zero or greater.")
    if turn_delay_seconds < 0:
        raise ValueError("turn_delay_seconds must be zero or greater.")

    agents = load_agents()
    emily = next(agent for agent in agents if agent.name == "Emily")
    olivia = next(agent for agent in agents if agent.name == "Olivia")
    by_id = {emily.agent_id: emily, olivia.agent_id: olivia}
    base_time_step = next_community_time_step(agents)
    social = SocialBridgeClient()

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPLAY_DIR / "community_session.json"
    stream_path = REPLAY_DIR / "community_session.jsonl"
    if continuous_seconds > 0:
        stream_path.write_text("", encoding="utf-8")

    bounded_turns: list[dict] = []
    stop_reason = "turn_limit_reached"
    started = time.monotonic()
    completed = 0
    latest_turn: dict | None = None
    resumed = False

    try:
        pending: list[dict] = []
        for agent in (emily, olivia):
            observation = await social.observe_social_space(agent.agent_id)
            pending.extend(observation.get("inbox", []))

        if pending:
            message = max(pending, key=lambda item: int(item.get("id", 0)))
            current = by_id[int(message["to_id"])]
            other = by_id[int(message["from_id"])]
            seed = {"success": True, "resumed": True, "message": message}
            resumed = True
        else:
            seed = await social.send_message(emily.agent_id, olivia.agent_id, opener)
            current = olivia
            other = emily

        offset = 0

        if continuous_seconds > 0:
            append_jsonl(
                stream_path,
                {"type": "resume" if resumed else "seed", "seed": seed},
            )

        while True:
            elapsed = time.monotonic() - started
            if continuous_seconds > 0:
                if elapsed >= continuous_seconds:
                    stop_reason = "continuous_window_complete"
                    break
            elif offset >= reply_turns:
                stop_reason = "turn_limit_reached"
                break

            turn = await process_one_reply(
                current,
                other,
                social,
                time_step=base_time_step + offset,
            )
            completed += 1
            latest_turn = turn

            if continuous_seconds > 0:
                append_jsonl(stream_path, {"type": "turn", "index": completed, "turn": turn})
                write_json(
                    summary_path,
                    {
                        "mode": "continuous_persistent_community_session",
                        "status": "running",
                        "resumed_social_state": resumed,
                        "start_time_step": base_time_step,
                        "completed_reply_turns": completed,
                        "continuous_seconds": continuous_seconds,
                        "turn_delay_seconds": turn_delay_seconds,
                        "latest_turn": latest_turn,
                    },
                )
            else:
                bounded_turns.append(turn)

            action = turn.get("action", {})
            action_result = turn.get("action_result")
            if action.get("type") != "message":
                stop_reason = str(action.get("reason", "agent_did_not_message"))
                break
            if not isinstance(action_result, dict) or not action_result.get("success"):
                stop_reason = "message_delivery_failed"
                break

            current, other = other, current
            offset += 1

            if continuous_seconds > 0 and turn_delay_seconds > 0:
                remaining = continuous_seconds - (time.monotonic() - started)
                if remaining > 0:
                    await asyncio.sleep(min(turn_delay_seconds, remaining))
    finally:
        social.close()

    result = {
        "mode": (
            "continuous_persistent_community_session"
            if continuous_seconds > 0
            else "bounded_persistent_community_session"
        ),
        "limits": {
            "seed_messages": 0 if resumed else 1,
            "requested_reply_turns": reply_turns,
            "maximum_reply_turns": MAX_REPLY_TURNS,
            "continuous_seconds": continuous_seconds,
            "turn_delay_seconds": turn_delay_seconds,
            "autonomous_loop": continuous_seconds > 0,
        },
        "resumed_social_state": resumed,
        "start_time_step": base_time_step,
        "completed_reply_turns": completed,
        "stop_reason": stop_reason,
        "seed": seed,
        "latest_turn": latest_turn,
    }

    if continuous_seconds <= 0:
        result["turns"] = bounded_turns

    write_json(summary_path, result)
    if continuous_seconds > 0:
        append_jsonl(stream_path, {"type": "session_end", "summary": result})
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a persistent Emily + Olivia community session."
    )
    parser.add_argument(
        "--opener",
        default="Hello, Olivia.",
        help="Seed message used only when no pending social message can be resumed.",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=DEFAULT_REPLY_TURNS,
        help=f"Maximum reply turns after the seed message (2-{MAX_REPLY_TURNS}) in bounded mode.",
    )
    parser.add_argument(
        "--continuous-seconds",
        type=int,
        default=0,
        help="Keep Emily and Olivia alternating for this many seconds; 0 keeps bounded mode.",
    )
    parser.add_argument(
        "--turn-delay-seconds",
        type=float,
        default=0.0,
        help="Minimum pause between successful replies in continuous mode.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit the requested community session.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit(
            "Refusing to start automatically. Use --run to permit the community session."
        )

    result = await run_community_session(
        args.opener,
        args.turns,
        continuous_seconds=args.continuous_seconds,
        turn_delay_seconds=args.turn_delay_seconds,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
