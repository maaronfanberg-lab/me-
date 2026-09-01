#!/usr/bin/env python3
"""Reject semantically stuck interrupted Community checkpoints before reuse.

The guard does not judge topics or author replacement memories. It detects two
generic failure shapes in interrupted checkpoints: repeated short-question
variants and recurring meaningful phrase clusters that have become self-
reinforcing observations across restarts.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

from dialogue_attractor import detect_recurring_content_attractor

HERE = Path(__file__).resolve().parent
WORKSPACES = HERE / "workspaces"
REPLAY = HERE / "replay"
RESTORE_REPORT = REPLAY / "checkpoint_restore.json"
_RESET_REPLAY_FILES = (
    "social_state.json",
    "community_session.json",
    "community_session.jsonl",
    "community_session_error.json",
)

_MESSAGE_RE = re.compile(
    r"\bobserves\s+a\s+message\s+from\s+(?:Emily|Olivia)\s*:\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "hers", "him", "his", "how", "i", "if", "in",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours",
    "she", "so", "that", "the", "their", "theirs", "them", "they", "this",
    "to", "us", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your", "yours",
    "emily", "olivia",
}


def _message_text(node: object) -> str:
    if not isinstance(node, dict):
        return ""
    content = str(node.get("content", "")).strip()
    match = _MESSAGE_RE.search(content)
    return match.group(1).strip() if match else ""


def _normalized(text: str) -> tuple[str, ...]:
    return tuple(word.lower() for word in _WORD_RE.findall(text))


def _content_words(text: str) -> tuple[str, ...]:
    return tuple(
        word for word in _normalized(text)
        if word not in _STOP and len(word) >= 3
    )


def _recent_messages(workspace: Path, limit: int = 18) -> list[str]:
    nodes_path = workspace / "memory_stream" / "nodes.json"
    try:
        nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(nodes, list):
        return []
    messages = [_message_text(node) for node in nodes]
    return [text for text in messages if text][-limit:]


def detect_question_attractor(messages: list[str]) -> dict | None:
    """Detect repeated variants of the same short question without topic rules."""
    questions = [text for text in messages if "?" in text]
    short_questions = [
        text for text in questions
        if 1 <= len(_content_words(text)) <= 5 and len(_normalized(text)) <= 14
    ]
    if len(short_questions) < 3:
        return None

    normalized_counts = Counter(" ".join(_normalized(text)) for text in short_questions)
    repeated_exact = [text for text, count in normalized_counts.items() if count >= 2]
    if repeated_exact:
        return {
            "reason": "repeated_short_question",
            "count": max(normalized_counts[text] for text in repeated_exact),
            "example": repeated_exact[0],
        }

    token_messages: dict[str, int] = Counter()
    for text in short_questions:
        for token in set(_content_words(text)):
            token_messages[token] += 1
    dominant = [(token, count) for token, count in token_messages.items() if count >= 3]
    if dominant:
        token, count = max(dominant, key=lambda item: item[1])
        return {
            "reason": "repeated_short_question_topic",
            "count": count,
            "token": token,
        }
    return None


def reject_interrupted_checkpoint_attractor() -> dict | None:
    """Clear only a restored interrupted checkpoint that is demonstrably stuck."""
    try:
        report = json.loads(RESTORE_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict) or report.get("restored") is not True:
        return None

    conclusion = str(report.get("source_run_conclusion") or "unknown").lower()
    if conclusion == "success":
        return None

    detections = []
    for agent_name in ("emily", "olivia"):
        messages = _recent_messages(WORKSPACES / agent_name)
        found = detect_question_attractor(messages)
        if not found:
            found = detect_recurring_content_attractor(messages)
        if found:
            detections.append({"agent": agent_name, **found})

    if not detections:
        return None

    # A rejected cognition checkpoint and its social/replay transcript are one
    # continuity epoch. Keeping the old JSONL after clearing cognition makes the
    # next paper-derived opening compare itself against the very attractor we just
    # rejected. Historical evidence remains available in Git history and the
    # source workflow artifact; the live epoch starts clean here.
    shutil.rmtree(WORKSPACES, ignore_errors=True)
    cleared_replay_files: list[str] = []
    for filename in _RESET_REPLAY_FILES:
        path = REPLAY / filename
        try:
            path.unlink()
            cleared_replay_files.append(filename)
        except FileNotFoundError:
            pass

    report.update(
        {
            "restored": False,
            "reason": "interrupted_checkpoint_dialogue_attractor",
            "social_state_restored": False,
            "replay_epoch_reset": True,
            "cleared_replay_files": cleared_replay_files,
            "rejected_attractors": detections,
        }
    )
    RESTORE_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = reject_interrupted_checkpoint_attractor()
    print(json.dumps(result or {"rejected": False}, indent=2))
