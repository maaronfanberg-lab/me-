"""Read-only Room conversation baseline counters for pinned research replays.

Simple observable metrics are NOT proxies for understanding, autonomy, or quality.
Keep transcript text out of the result. Compare equivalent windows and verify
the input revision separately; the live feed is a moving 160-turn sample.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

PEOPLE = frozenset({"sarah", "mara", "owen", "jules", "allen"})
_WORDS = re.compile(r"\b[\w']+\b", re.UNICODE)


def summarize(feed: dict) -> dict:
    if not isinstance(feed, dict) or not isinstance(feed.get("conversation"), list):
        raise ValueError("expected Room public feed")
    turns = [
        event for event in feed["conversation"]
        if isinstance(event, dict) and event.get("speaker") in PEOPLE
        and isinstance(event.get("text"), str) and event["text"].strip()
        and isinstance(event.get("id"), str) and event["id"]
    ]
    if not turns:
        raise ValueError("no public turns")
    question_count = sum(event["text"].strip().endswith("?") for event in turns)
    words = [len(_WORDS.findall(event["text"])) for event in turns]
    alternating = sum(
        turns[i]["speaker"] == turns[i - 2]["speaker"]
        and turns[i]["speaker"] != turns[i - 1]["speaker"]
        for i in range(2, len(turns))
    )
    return {
        "window_n": len(turns),
        "first_turn": turns[0]["id"],
        "last_turn": turns[-1]["id"],
        "speaker_counts": dict(sorted(Counter(t["speaker"] for t in turns).items())),
        "questions_ending_with_question_mark": question_count,
        "question_rate": round(question_count / len(turns), 3),
        "mean_words_per_turn": round(sum(words) / len(turns), 1),
        "long_question_turns_over_25_words": sum(
            event["text"].strip().endswith("?") and length > 25
            for event, length in zip(turns, words)
        ),
        "aba_alternation_eligible_windows": alternating,
        "limitations": "These are surface counters, not semantic or human-likeness scores.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True,
                        help="Path to an explicitly selected, pinned public feed.json")
    args = parser.parse_args()
    if not Path(args.feed).is_file():
        parser.error("feed not found")
    report = summarize(json.loads(Path(args.feed).read_text(encoding="utf-8")))
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
