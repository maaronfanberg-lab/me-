#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from community_cycle import (
    _is_usable_utterance,
    choose_opening_action,
    load_agents,
    next_community_time_step,
)
from first_exchange import SocialBridgeClient, process_one_reply

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"
REPO_ROOT = HERE.parents[1]
MAX_REPLY_TURNS = 10
DEFAULT_REPLY_TURNS = 8
MAX_CONTINUOUS_SECONDS = 19800
MAX_TURN_DELAY_SECONDS = 3600.0
MAX_OPENER_CHARS = 12000


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def publish_live_replay() -> None:
    """Best-effort live publish. A failed push must never stop the conversation."""
    try:
        subprocess.run(
            ["git", "config", "user.name", "github-actions[bot]"],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        replay_glob = "experiments/emily-olivia-society/replay"
        subprocess.run(
            ["git", "add", "-f", replay_glob],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
        if diff.returncode == 0:
            return
        commit = subprocess.run(
            ["git", "commit", "-m", "Update Emily Olivia live replay [skip ci]"],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if commit.returncode != 0:
            return

        for attempt in range(1, 4):
            pull = subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=REPO_ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if pull.returncode != 0:
                subprocess.run(
                    ["git", "rebase", "--abort"],
                    cwd=REPO_ROOT,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(attempt * 2)
                continue

            push = subprocess.run(
                ["git", "push", "origin", "HEAD:main"],
                cwd=REPO_ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if push.returncode == 0:
                return
            time.sleep(attempt * 2)
    except Exception:
        return


def validate_opener(opener: str) -> str:
    """Validate an explicitly supplied seed; blank means autonomous clean start."""
    opener = str(opener or "").strip()
    if not opener:
        return ""
    if len(opener) > MAX_OPENER_CHARS:
        raise ValueError(f"opener exceeds {MAX_OPENER_CHARS} characters.")
    if not _is_usable_utterance(opener):
        raise ValueError("opener contains template, service-assistant, or otherwise unusable dialogue.")
    return opener


async def run_community_session(
    opener: str,
    reply_turns: int,
    continuous_seconds: int = 0,
    turn_delay_seconds: float = 0.0,
) -> dict:
    opener = validate_opener(opener)
    if continuous_seconds <= 0 and (reply_turns < 2 or reply_turns > MAX_REPLY_TURNS):
        raise ValueError(f"reply_turns must be between 2 and {MAX_REPLY_TURNS}; got {reply_turns}.")
    if continuous_seconds < 0 or continuous_seconds > MAX_CONTINUOUS_SECONDS:
        raise ValueError(f"continuous_seconds must be between 0 and {MAX_CONTINUOUS_SECONDS}.")
    if turn_delay_seconds < 0 or turn_delay_seconds > MAX_TURN_DELAY_SECONDS:
        raise ValueError(f"turn_delay_seconds must be between 0 and {MAX_TURN_DELAY_SECONDS:g}.")

    agents = load_agents()
    emily = next(agent for agent in agents if agent.name == "Emily")
    olivia = next(agent for agent in agents if agent.name == "Olivia")
    by_id = {emily.agent_id: emily, olivia.agent_id: olivia}
    base_time_step = next_community_time_step(agents)
    social = SocialBridgeClient()

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPLAY_DIR / "community_session.json"
    stream_path = REPLAY_DIR / "community_session.jsonl"
    error_path = REPLAY_DIR / "community_session_error.json"
    session_id = f"{int(time.time())}-{uuid.uuid4().hex[:10]}"

    bounded_turns: list[dict] = []
    discarded_pending_message_ids: list[int] = []
    stop_reason = "turn_limit_reached"
    started = time.monotonic()
    completed = 0
    latest_turn: dict | None = None
    opening_turn: dict | None = None
    resumed = False
    autonomous_opening = False
    seed: dict = {}
    dialogue_history: list[tuple[str, str]] = []
    reply_time_offset = 0

    try:
        pending: list[dict] = []
        for agent in (emily, olivia):
            observation = await social.observe_social_space(agent.agent_id)
            inbox = observation.get("inbox", [])
            if not isinstance(inbox, list):
                raise RuntimeError(f"Invalid inbox for {agent.name}.")
            pending.extend(inbox)

        if len(pending) > 1:
            raise RuntimeError("Multiple pending cross-agent messages found; refusing ambiguous resume.")

        if pending:
            message = pending[0]
            to_id = int(message["to_id"])
            from_id = int(message["from_id"])
            if to_id not in by_id or from_id not in by_id or to_id == from_id:
                raise RuntimeError("Persisted pending message has invalid routing.")
            content = str(message.get("content", "")).strip()
            if not _is_usable_utterance(content):
                consume_result = await social.consume_message(to_id, int(message["id"]))
                if consume_result.get("success") is not True:
                    raise RuntimeError("Failed to quarantine unusable persisted pending message.")
                discarded_pending_message_ids.append(int(message["id"]))
                pending = []

        if pending:
            message = pending[0]
            to_id = int(message["to_id"])
            from_id = int(message["from_id"])
            current = by_id[to_id]
            other = by_id[from_id]
            seed = {"success": True, "resumed": True, "message": message}
            dialogue_history.append((other.name, str(message["content"])))
            resumed = True
        else:
            if opener:
                seed = await social.send_message(emily.agent_id, olivia.agent_id, opener)
                if seed.get("success") is not True:
                    raise RuntimeError("Explicit seed message delivery failed.")
                dialogue_history.append((emily.name, opener))
            else:
                opening_observation = await social.observe_social_space(emily.agent_id)
                if opening_observation.get("inbox"):
                    raise RuntimeError("Social state changed while preparing autonomous opening.")
                opening_action = choose_opening_action(
                    emily,
                    opening_observation,
                    olivia,
                    time_step=base_time_step,
                    dialogue_history=dialogue_history,
                )
                seed = await social.send_message(
                    emily.agent_id,
                    int(opening_action["recipient_id"]),
                    str(opening_action["content"]),
                )
                if seed.get("success") is not True:
                    raise RuntimeError("Autonomous opening delivery failed.")
                emily.brain.save(str(emily.workspace))
                dialogue_history.append((emily.name, str(opening_action["content"])))
                opening_turn = {
                    "agent": emily.name,
                    "time_step": base_time_step,
                    "observation": opening_observation,
                    "retrieved_memories": opening_action.get("retrieved_memories", []),
                    "action": opening_action,
                    "action_result": seed,
                    "consumed_inbound": None,
                }
                autonomous_opening = True
                reply_time_offset = 1
            current = olivia
            other = emily

        if continuous_seconds > 0:
            append_jsonl(
                stream_path,
                {
                    "type": "session_start",
                    "session_id": session_id,
                    "resumed": resumed,
                    "autonomous_opening": autonomous_opening,
                    "discarded_pending_message_ids": discarded_pending_message_ids,
                    "seed": seed,
                    "opening_turn": opening_turn,
                    "start_time_step": base_time_step,
                },
            )

        offset = 0
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
                time_step=base_time_step + reply_time_offset + offset,
                dialogue_history=dialogue_history,
            )
            completed += 1
            latest_turn = turn

            action = turn.get("action", {})
            if action.get("type") == "message":
                dialogue_history.append((current.name, str(action.get("content", ""))))

            if continuous_seconds > 0:
                append_jsonl(stream_path, {"type": "turn", "session_id": session_id, "index": completed, "turn": turn})
                atomic_write_json(
                    summary_path,
                    {
                        "mode": "continuous_persistent_community_session",
                        "status": "running",
                        "session_id": session_id,
                        "resumed_social_state": resumed,
                        "autonomous_opening": autonomous_opening,
                        "discarded_pending_message_ids": discarded_pending_message_ids,
                        "start_time_step": base_time_step,
                        "opening_turn": opening_turn,
                        "completed_reply_turns": completed,
                        "continuous_seconds": continuous_seconds,
                        "turn_delay_seconds": turn_delay_seconds,
                        "latest_turn": latest_turn,
                    },
                )
                publish_live_replay()
            else:
                bounded_turns.append(turn)

            action_result = turn.get("action_result")
            if action.get("type") != "message":
                stop_reason = str(action.get("reason", "agent_did_not_message"))
                break
            if not isinstance(action_result, dict) or action_result.get("success") is not True:
                stop_reason = "message_delivery_failed"
                break
            if turn.get("consumed_inbound") is not True:
                raise RuntimeError("Successful reply did not consume its inbound message.")

            current, other = other, current
            offset += 1

            if continuous_seconds > 0 and turn_delay_seconds > 0:
                remaining = continuous_seconds - (time.monotonic() - started)
                if remaining > 0:
                    await asyncio.sleep(min(turn_delay_seconds, remaining))
    except Exception as exc:
        atomic_write_json(
            error_path,
            {
                "session_id": session_id,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "resumed_social_state": resumed,
                "autonomous_opening": autonomous_opening,
                "discarded_pending_message_ids": discarded_pending_message_ids,
                "opening_turn": opening_turn,
                "completed_reply_turns": completed,
                "latest_turn": latest_turn,
            },
        )
        publish_live_replay()
        raise
    finally:
        social.close()

    result = {
        "mode": "continuous_persistent_community_session" if continuous_seconds > 0 else "bounded_persistent_community_session",
        "status": "completed",
        "session_id": session_id,
        "limits": {
            "seed_messages": 0 if resumed else 1,
            "requested_reply_turns": reply_turns,
            "maximum_reply_turns": MAX_REPLY_TURNS,
            "maximum_continuous_seconds": MAX_CONTINUOUS_SECONDS,
            "continuous_seconds": continuous_seconds,
            "turn_delay_seconds": turn_delay_seconds,
            "autonomous_loop": continuous_seconds > 0,
        },
        "resumed_social_state": resumed,
        "autonomous_opening": autonomous_opening,
        "discarded_pending_message_ids": discarded_pending_message_ids,
        "start_time_step": base_time_step,
        "opening_turn": opening_turn,
        "completed_reply_turns": completed,
        "stop_reason": stop_reason,
        "seed": seed,
        "latest_turn": latest_turn,
    }

    if continuous_seconds <= 0:
        result["turns"] = bounded_turns

    atomic_write_json(summary_path, result)
    if continuous_seconds > 0:
        append_jsonl(stream_path, {"type": "session_end", "session_id": session_id, "summary": result})
        publish_live_replay()
    if error_path.exists():
        error_path.unlink()
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a persistent Emily + Olivia community session.")
    parser.add_argument(
        "--opener",
        default="",
        help="Optional explicit Emily seed. Blank starts autonomously through the Stanford chain.",
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
        help=f"Keep Emily and Olivia alternating for up to {MAX_CONTINUOUS_SECONDS} seconds; 0 keeps bounded mode.",
    )
    parser.add_argument(
        "--turn-delay-seconds",
        type=float,
        default=0.0,
        help="Minimum pause between successful replies in continuous mode.",
    )
    parser.add_argument("--run", action="store_true", help="Explicitly permit the requested community session.")
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("Refusing to start automatically. Use --run to permit the community session.")

    result = await run_community_session(
        args.opener,
        args.turns,
        continuous_seconds=args.continuous_seconds,
        turn_delay_seconds=args.turn_delay_seconds,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
