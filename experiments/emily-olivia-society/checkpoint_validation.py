#!/usr/bin/env python3
"""Validate an Emily + Olivia checkpoint before it can become live cognition.

A reusable checkpoint must come from a successful completed Community session,
contain structurally clean Stanford workspaces, have a coherent exact replay,
and preserve at most one pending cross-agent message that is exactly the final
delivered message. The validator never authors or rewrites dialogue.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from checkpoint_attractor_guard import detect_question_attractor
from dialogue_attractor import detect_recurring_content_attractor

_MESSAGE_OBSERVATION = re.compile(
    r"^(?:Emily|Olivia) observes a message from (?:Emily|Olivia):\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_STOP_REASONS = {"continuous_window_complete", "turn_limit_reached"}


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_messages(summary: dict) -> list[dict]:
    direct = summary.get("messages")
    if isinstance(direct, list):
        messages = [item for item in direct if isinstance(item, dict)]
        if messages:
            return messages

    out: list[dict] = []
    seed = summary.get("seed")
    if isinstance(seed, dict) and isinstance(seed.get("message"), dict):
        out.append(seed["message"])
    for turn in summary.get("turns", []) if isinstance(summary.get("turns"), list) else []:
        if not isinstance(turn, dict):
            continue
        result = turn.get("action_result")
        if isinstance(result, dict) and isinstance(result.get("message"), dict):
            out.append(result["message"])
    latest = summary.get("latest_turn")
    if isinstance(latest, dict):
        result = latest.get("action_result")
        message = result.get("message") if isinstance(result, dict) else None
        if isinstance(message, dict):
            key = (message.get("id"), message.get("from_id"), message.get("to_id"), message.get("content"))
            existing = {
                (item.get("id"), item.get("from_id"), item.get("to_id"), item.get("content"))
                for item in out
            }
            if key not in existing:
                out.append(message)
    return out


def _message_signature(message: dict) -> tuple[object, object, object, str]:
    return (
        message.get("id"),
        message.get("from_id"),
        message.get("to_id"),
        str(message.get("content", "")).strip(),
    )


def validate_replay(summary_path: Path, error_path: Path | None) -> tuple[dict, list[dict]]:
    if error_path and error_path.exists():
        raise ValueError("checkpoint artifact contains community_session_error.json")
    summary = _read_json(summary_path)
    if not isinstance(summary, dict):
        raise ValueError("community_session.json must be an object")
    if summary.get("status") != "completed":
        raise ValueError("checkpoint session did not complete")
    stop_reason = str(summary.get("stop_reason") or "")
    if stop_reason not in _ALLOWED_STOP_REASONS:
        raise ValueError(f"checkpoint session stopped for non-handoff reason: {stop_reason or 'missing'}")

    messages = exact_messages(summary)
    if len(messages) < 3:
        raise ValueError("checkpoint replay contains fewer than three delivered messages")

    texts: list[str] = []
    expected_speaker: str | None = None
    for index, message in enumerate(messages):
        speaker = str(message.get("from_name", "")).strip()
        recipient = str(message.get("to_name", "")).strip()
        content = str(message.get("content", "")).strip()
        if speaker not in {"Emily", "Olivia"} or recipient not in {"Emily", "Olivia"} or speaker == recipient:
            raise ValueError(f"checkpoint replay message {index} has invalid routing")
        if not content:
            raise ValueError(f"checkpoint replay message {index} is empty")
        if expected_speaker is not None and speaker != expected_speaker:
            raise ValueError("checkpoint replay does not alternate speakers")
        expected_speaker = recipient
        texts.append(content)

    recent = texts[-18:]
    found = detect_question_attractor(recent) or detect_recurring_content_attractor(recent)
    if found:
        raise ValueError(f"checkpoint replay contains recurring dialogue attractor: {found}")
    return summary, messages


def validate_workspace(workspace: Path) -> None:
    for agent in ("emily", "olivia"):
        nodes_path = workspace / agent / "memory_stream" / "nodes.json"
        nodes = _read_json(nodes_path)
        if not isinstance(nodes, list):
            raise ValueError(f"unexpected memory schema for {agent}")
        recent_messages: list[str] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            match = _MESSAGE_OBSERVATION.match(str(node.get("content", "")).strip())
            if match:
                text = match.group(1).strip()
                if text:
                    recent_messages.append(text)
        recent = recent_messages[-18:]
        found = detect_question_attractor(recent) or detect_recurring_content_attractor(recent)
        if found:
            raise ValueError(f"{agent} memory contains recurring dialogue attractor: {found}")


def validate_social_state(social_path: Path | None, final_message: dict) -> bool:
    if social_path is None or not social_path.exists():
        return False
    state = _read_json(social_path)
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("invalid social state schema")
    inboxes = state.get("inboxes")
    if not isinstance(inboxes, dict):
        raise ValueError("invalid social inbox schema")

    pending: list[dict] = []
    for key in ("1", "2"):
        inbox = inboxes.get(key, [])
        if not isinstance(inbox, list):
            raise ValueError("invalid social inbox list")
        pending.extend(item for item in inbox if isinstance(item, dict))
    if len(pending) > 1:
        raise ValueError("checkpoint contains multiple pending cross-agent messages")
    if not pending:
        return False

    message = pending[0]
    from_id = message.get("from_id")
    to_id = message.get("to_id")
    if {from_id, to_id} != {1, 2} or from_id == to_id:
        raise ValueError("checkpoint pending message has invalid routing")
    if _message_signature(message) != _message_signature(final_message):
        raise ValueError("checkpoint pending message is not the final delivered replay message")
    return True


def write_scoped_history(summary: dict, messages: list[dict], destination: Path) -> None:
    """Write only this validated checkpoint epoch for restart-time prompt history."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    session_id = str(summary.get("session_id") or "checkpoint")
    rows: list[dict] = []
    first, *rest = messages
    rows.append({"type": "session_start", "session_id": session_id, "seed": {"message": first}})
    for index, message in enumerate(rest, start=1):
        rows.append(
            {
                "type": "turn",
                "session_id": session_id,
                "index": index,
                "turn": {"action_result": {"message": message}},
            }
        )
    destination.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--social", type=Path)
    parser.add_argument("--error", type=Path)
    parser.add_argument("--history-output", type=Path)
    args = parser.parse_args()

    validate_workspace(args.workspace)
    summary, messages = validate_replay(args.summary, args.error)
    social_restorable = validate_social_state(args.social, messages[-1])
    if args.history_output:
        write_scoped_history(summary, messages, args.history_output)
    print(
        json.dumps(
            {
                "valid": True,
                "message_count": len(messages),
                "social_state_restorable": social_restorable,
                "session_id": summary.get("session_id"),
            }
        )
    )


if __name__ == "__main__":
    main()
