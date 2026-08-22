#!/usr/bin/env python3
"""Generate one autonomous Sara turn from the current public Room feed.

This script does not perform network writes. It reads a Room feed plus the current
Sara session, calls the existing private model boundary, and writes one POST-ready
Sara message. The caller owns OIDC authentication and transport.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Install the same participant-aware/sanitized private-model boundary used by
# the live Room before importing the model module itself. This makes Sara a
# legal model identity without turning her into a core 12-node Room entity.
import room_engine_v5 as _room_engine_v5  # noqa: F401
import room_private_model as model

ROOM_VOICES = ("sarah", "mara", "owen", "jules")
SARA_TRAITS = {
    "openness": 0.86,
    "curiosity": 0.91,
    "social_sensitivity": 0.92,
    "skepticism": 0.72,
    "agreeableness": 0.70,
    "attention_persistence": 0.74,
}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def auto_id(source_id: str) -> str:
    digest = hashlib.sha256(source_id.encode()).hexdigest()[:16]
    return f"sara-auto-{digest}"


def session_ids(session: dict) -> set[str]:
    out: set[str] = set()
    for turn in session.get("turns", []):
        if not isinstance(turn, dict):
            continue
        message = turn.get("message", turn)
        if isinstance(message, dict) and message.get("id"):
            out.add(str(message["id"]))
    return out


def build_turn(feed: dict, session: dict, model_run=model.run) -> dict | None:
    conversation = feed.get("conversation")
    if not isinstance(conversation, list) or not conversation:
        return None
    context = [m for m in conversation[-12:] if isinstance(m, dict) and str(m.get("text") or "").strip()]
    if not context:
        return None
    latest = context[-1]
    source_id = str(latest.get("id") or "").strip()
    if not source_id:
        return None

    turn_id = auto_id(source_id)
    if turn_id in session_ids(session):
        return None

    partner = str(latest.get("speaker") or "").strip().lower()
    if partner not in ROOM_VOICES:
        return None

    state = feed.get("state") if isinstance(feed.get("state"), dict) else {}
    topic = state.get("topic_episode") if isinstance(state.get("topic_episode"), dict) else {}
    relationship = {
        "exposure": 0.2,
        "direct_familiarity": 0.08,
        "trust": 0.1,
        "predictability": 0.1,
        "reciprocity": 0.1,
        "warmth": 0.12,
        "respect": 0.12,
        "disclosure_depth": 0.0,
        "tension": 0.0,
    }
    payload = {
        "entity": "sara",
        "profile": {"traits": SARA_TRAITS},
        "event": latest,
        "context": context,
        "partner": partner,
        "relationship": relationship,
        "topic": topic,
        "keywords": list(topic.get("recent_terms") or [])[:6],
    }
    thought = model_run("thought", dict(payload)) or {}
    expression_payload = dict(payload)
    expression_payload["deliberation"] = thought
    expression = model_run("expression", expression_payload) or {}
    text = str(expression.get("utterance") or "").strip()
    if not text:
        raise RuntimeError("Sara model returned an empty expression")
    target = str(expression.get("target") or "").strip().lower()
    if target and target not in ROOM_VOICES:
        raise RuntimeError(f"Sara model returned invalid target: {target}")

    return {
        "id": turn_id,
        "speaker": "sara",
        "display_name": "Sara",
        "text": text[:700],
    }


def selftest() -> int:
    feed = {
        "state": {"topic_episode": {"root": "story", "current_facet": "character", "recent_terms": ["story", "character"]}},
        "conversation": [
            {"id": "room-1", "speaker": "sarah", "text": "What makes the character difficult to trust?"},
            {"id": "room-2", "speaker": "mara", "text": "Maybe the interesting part is what she refuses to explain."},
        ],
    }
    calls: list[tuple[str, dict]] = []

    def fake_run(role: str, payload: dict):
        calls.append((role, payload))
        if role == "thought":
            return {"action": "DEEPEN", "preferred_partner": "mara", "focus": "uncertainty"}
        if role == "expression":
            return {
                "decision": "SPEAK",
                "target": "mara",
                "move": "deepen",
                "utterance": "I wonder whether refusing to explain is what preserves the uncertainty, rather than merely hiding information.",
                "semantic_terms": ["uncertainty", "explanation"],
            }
        raise AssertionError(role)

    first = build_turn(feed, {"turns": []}, fake_run)
    assert first is not None
    assert first["speaker"] == "sara"
    assert first["id"] == auto_id("room-2")
    assert first["text"]
    assert [role for role, _ in calls] == ["thought", "expression"]
    assert calls[0][1]["entity"] == "sara"
    assert calls[0][1]["partner"] == "mara"

    duplicate_session = {"turns": [{"message": {"id": first["id"], "speaker": "sara", "text": first["text"]}}]}
    calls.clear()
    assert build_turn(feed, duplicate_session, fake_run) is None
    assert calls == []

    non_room_feed = {"state": {}, "conversation": [{"id": "sara-1", "speaker": "sara", "text": "hello"}]}
    assert build_turn(non_room_feed, {"turns": []}, fake_run) is None
    print("PASS: Sara live generator produces one deterministic, idempotent turn from a Room voice")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=ROOT / "room" / "feed.json")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.session is None or args.output is None:
        parser.error("--session and --output are required outside --selftest")
    turn = build_turn(load_json(args.feed), load_json(args.session))
    if turn is None:
        print("No fresh Room event for Sara.")
        return 0
    args.output.write_text(json.dumps(turn, separators=(",", ":")) + "\n")
    print(f"Prepared {turn['id']} for Sara")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
