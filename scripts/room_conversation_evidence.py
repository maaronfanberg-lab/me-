#!/usr/bin/env python3
"""Read-only, source-linked Room conversational baseline evidence.

Counts are diagnostic, never quality verdicts. A repeated question can be a
repair and a one-word reply can be excellent. Human review must determine
actual uptake, grounding and meaningful progress.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PUBLIC = {"sarah", "mara", "jules", "owen", "allen"}
AUTONOMOUS = PUBLIC - {"allen"}


def key(text: object) -> str:
    return " ".join(re.findall(r"\w+", str(text or "").casefold(), re.UNICODE))


def extract(payload: object, limit: int = 160) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("feed must be an object")
    items = payload.get("conversation")
    if not isinstance(items, list):
        raise ValueError("feed must contain a conversation array")
    public = [
        {"id": str(x["id"]), "speaker": str(x["speaker"]).lower(),
         "text": str(x["text"])}
        for x in items
        if isinstance(x, dict)
        and str(x.get("speaker") or "").lower() in PUBLIC
        and str(x.get("id") or "").strip()
        and str(x.get("text") or "").strip()
    ]
    if limit < 1:
        raise ValueError("limit must be positive")
    return public[-limit:]


def analyze(turns: list[dict]) -> dict:
    """Observations only: never infer coherence from lexical similarity."""
    repeats = []
    question_echoes = []
    short = []
    counts = {speaker: 0 for speaker in sorted(AUTONOMOUS)}
    max_same_action = 0
    current_run = 0
    prior_key = ""
    for i, turn in enumerate(turns):
        speaker = str(turn["speaker"])
        spoken = str(turn["text"]).strip()
        normalized = key(spoken)
        if speaker in counts:
            counts[speaker] += 1
        if speaker in AUTONOMOUS and len(normalized.split()) <= 3:
            short.append({"id": turn["id"], "speaker": speaker, "text": spoken})
        if i and normalized == prior_key:
            previous = turns[i - 1]
            repeats.append({"previous_id": previous["id"], "current_id": turn["id"],
                            "previous_speaker": previous["speaker"], "speaker": speaker,
                            "previous_text": previous["text"], "text": spoken})
            current_run += 1
            if str(previous["text"]).strip().endswith("?") and spoken.endswith("?"):
                question_echoes.append({"previous_id": previous["id"],
                                         "current_id": turn["id"]})
        else:
            current_run = 1
        max_same_action = max(max_same_action, current_run)
        prior_key = normalized
    autonomous_count = sum(counts.values())
    return {
        "sample_turns": len(turns),
        "autonomous_turns": autonomous_count,
        "speaker_counts": counts,
        "exact_adjacent_repeats": len(repeats),
        "contiguous_question_echoes": len(question_echoes),
        "short_autonomous_1to3_word_turns": len(short),
        "short_autonomous_rate": round(len(short) / autonomous_count, 5) if autonomous_count else None,
        "longest_identical_action_run": max_same_action,
        "repeat_evidence": repeats[:20],
        "short_turn_evidence": short[:20],
        "limitations": "Structural diagnostics only. Cannot prove or disprove genuine responsiveness, semantic progress, intentional repair or appropriate short replies.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--feed", default="room/feed.json")
    p.add_argument("--limit", type=int, default=160)
    args = p.parse_args()
    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    result = analyze(extract(feed, args.limit))
    result["generated_at"] = feed.get("generated_at")
    state = feed.get("state") if isinstance(feed.get("state"), dict) else {}
    result["cycle"] = state.get("cycle")
    result["deployed_floor"] = state.get("conversational_floor")
    result["floor_health"] = state.get("conversational_floor_health")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
