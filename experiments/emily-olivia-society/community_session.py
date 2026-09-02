#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import time
import uuid
from collections import deque
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
DEFERRED_RETRY_DELAY_SECONDS = 1.0
_LEGACY_CANNED_OPENER = "Let's continue naturally from where we left off."


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


def recent_dialogue_history(path: Path, limit: int = 12) -> list[tuple[str, str]]:
    """Recover recent delivered dialogue so restart-time generation sees its own past."""
    if limit <= 0 or not path.exists():
        return []

    tail: deque[str] = deque(maxlen=max(64, limit * 8))
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if line:
                    tail.append(line)
    except OSError:
        return []

    history: list[tuple[str, str]] = []
    seen: set[tuple[object, ...]] = set()
    for line in tail:
        try:
            row = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(row, dict):
            continue

        message = None
        if row.get("type") == "session_start":
            seed = row.get("seed")
            if isinstance(seed, dict):
                message = seed.get("message")
        elif row.get("type") == "turn":
            turn = row.get("turn")
            if isinstance(turn, dict):
                action_result = turn.get("action_result")
                if isinstance(action_result, dict):
                    message = action_result.get("message")

        if not isinstance(message, dict):
            continue
        speaker = str(message.get("from_name", "")).strip()
        content = str(message.get("content", "")).strip()
        if speaker not in {"Emily", "Olivia"} or not _is_usable_utterance(content):
            continue

        message_id = message.get("id")
        key = (
            ("id", message_id, speaker, content)
            if message_id is not None
            else ("text", speaker, content)
        )
        if key in seen:
            continue
        seen.add(key)
        history.append((speaker, content))

    return history[-limit:]


def _contents_api_path(path: Path) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is unavailable for live replay publishing.")
    relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    return f"repos/{repo}/contents/{relative}"


def _remote_content_sha(api_path: str) -> tuple[str, bool]:
    lookup = subprocess.run(
        ["gh", "api", f"{api_path}?ref=main", "--jq", ".sha"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if lookup.returncode == 0:
        return lookup.stdout.strip(), True
    if "404" in lookup.stderr or "Not Found" in lookup.stderr:
        return "", False
    raise RuntimeError(lookup.stderr.strip() or "GitHub contents lookup failed.")


def publish_live_replay(path: Path | None = None) -> bool:
    """Best-effort publish of one small live JSON file through GitHub Contents API.

    This deliberately does not commit or rebase the runner checkout: Emily and
    Olivia mutate their cognition workspaces while talking, so rebasing that
    dirty checkout can fail. Publishing only the current snapshot also avoids
    recommitting the large historical JSONL stream and BitNet logs every turn.
    """
    target = path or (REPLAY_DIR / "community_session.json")
    if not target.exists():
        return False

    try:
        api_path = _contents_api_path(target)
        encoded = base64.b64encode(target.read_bytes()).decode("ascii")
    except Exception as exc:
        print(f"WARNING: could not prepare live replay publish: {exc}", flush=True)
        return False

    last_error = "unknown GitHub contents error"
    for attempt in range(1, 4):
        try:
            sha, exists = _remote_content_sha(api_path)
            payload = {
                "message": "Update Emily Olivia live replay [skip ci]",
                "content": encoded,
                "branch": "main",
            }
            if exists and sha:
                payload["sha"] = sha
            write = subprocess.run(
                ["gh", "api", "--method", "PUT", api_path, "--input", "-"],
                input=json.dumps(payload),
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if write.returncode == 0:
                return True
            last_error = write.stderr.strip() or f"GitHub contents PUT exited {write.returncode}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(attempt * 2)

    print(f"WARNING: live replay publish failed after retries: {last_error}", flush=True)
    return False


def delete_live_replay_file(path: Path) -> bool:
    """Best-effort removal of a stale public live-state marker from main."""
    try:
        api_path = _contents_api_path(path)
    except Exception as exc:
        print(f"WARNING: could not prepare live replay cleanup: {exc}", flush=True)
        return False

    last_error = "unknown GitHub contents error"
    for attempt in range(1, 4):
        try:
            sha, exists = _remote_content_sha(api_path)
            if not exists:
                return True
            payload = {
                "message": "Clear stale Emily Olivia live error [skip ci]",
                "sha": sha,
                "branch": "main",
            }
            delete = subprocess.run(
                ["gh", "api", "--method", "DELETE", api_path, "--input", "-"],
                input=json.dumps(payload),
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if delete.returncode == 0:
                return True
            last_error = delete.stderr.strip() or f"GitHub contents DELETE exited {delete.returncode}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(attempt * 2)

    print(f"WARNING: stale live replay cleanup failed after retries: {last_error}", flush=True)
    return False


def validate_opener(opener: str) -> str:
    """Validate an explicitly supplied seed; blank means autonomous clean start."""
    opener = str(opener or "").strip()
    if not opener:
        return ""
    # GitHub reruns freeze the workflow definition from the original run. Run
    # #95 therefore still passes the pre-fix canned default even while checking
    # out current main. Quarantine exactly that historical input as no opener;
    # it must never be delivered, remembered, or published as agent dialogue.
    if opener.casefold() == _LEGACY_CANNED_OPENER.casefold():
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

    # A healthy new session must not publicly inherit a failure marker from an
    # older run. Clear both the checkout copy and the read-only viewer source.
    error_path.unlink(missing_ok=True)
    if continuous_seconds > 0:
        delete_live_replay_file(error_path)

    bounded_turns: list[dict] = []
    live_messages: list[dict] = []
    discarded_pending_message_ids: list[int] = []
    stop_reason = "turn_limit_reached"
    started = time.monotonic()
    completed = 0
    latest_turn: dict | None = None
    opening_turn: dict | None = None
    resumed = False
    autonomous_opening = False
    seed: dict = {}
    dialogue_history: list[tuple[str, str]] = recent_dialogue_history(stream_path)
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
            pending_history = (other.name, str(message["content"]))
            if not dialogue_history or dialogue_history[-1] != pending_history:
                dialogue_history.append(pending_history)
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

        seed_message = seed.get("message") if isinstance(seed, dict) else None
        if isinstance(seed_message, dict):
            live_messages.append(seed_message)

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
            # Publish the new session immediately, before the first reply finishes.
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
                    "completed_reply_turns": 0,
                    "continuous_seconds": continuous_seconds,
                    "turn_delay_seconds": turn_delay_seconds,
                    "messages": live_messages,
                    "latest_turn": None,
                },
            )
            publish_live_replay()

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
            action = turn.get("action", {})

            # A deferred sample is explicitly recoverable: the inbound message
            # remains unconsumed, so continuous mode should keep the same speaker
            # and try again rather than ending the whole conversation. Do not
            # count or persist it as a completed reply turn.
            if (
                continuous_seconds > 0
                and action.get("type") == "wait"
                and action.get("reason") == "speech_generation_deferred"
            ):
                latest_turn = turn
                append_jsonl(
                    stream_path,
                    {
                        "type": "generation_deferred",
                        "session_id": session_id,
                        "agent": current.name,
                        "time_step": base_time_step + reply_time_offset + offset,
                        "generation_attempts": turn.get("generation_attempts"),
                        "generation_error": turn.get("generation_error"),
                    },
                )
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
                        "messages": live_messages,
                        "latest_turn": latest_turn,
                    },
                )
                publish_live_replay()
                remaining = continuous_seconds - (time.monotonic() - started)
                if remaining > 0:
                    await asyncio.sleep(min(DEFERRED_RETRY_DELAY_SECONDS, remaining))
                continue

            completed += 1
            latest_turn = turn

            if action.get("type") == "message":
                dialogue_history.append((current.name, str(action.get("content", ""))))

            action_result = turn.get("action_result")
            delivered_message = action_result.get("message") if isinstance(action_result, dict) else None
            if continuous_seconds > 0 and isinstance(delivered_message, dict):
                live_messages.append(delivered_message)

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
                        "messages": live_messages,
                        "latest_turn": latest_turn,
                    },
                )
                publish_live_replay()
            else:
                bounded_turns.append(turn)

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
                "messages": live_messages,
                "latest_turn": latest_turn,
            },
        )
        publish_live_replay(error_path)
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

    if continuous_seconds > 0:
        result["messages"] = live_messages
    else:
        result["turns"] = bounded_turns

    atomic_write_json(summary_path, result)
    if continuous_seconds > 0:
        append_jsonl(stream_path, {"type": "session_end", "session_id": session_id, "summary": result})
        publish_live_replay()
    if error_path.exists():
        error_path.unlink()
        if continuous_seconds > 0:
            delete_live_replay_file(error_path)
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