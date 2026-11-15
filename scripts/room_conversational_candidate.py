#!/usr/bin/env python3
"""Read-only first-pass integrity check before attempting selected-turn commit.

The publication gate remains authoritative. This preflight lets a different
eligible participant receive the floor after a *model* failure without
partially writing state. It cannot make an unsafe utterance acceptable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import room_private_commit as commit
from room_sequence_uptake import validate_uptake


def validate_candidate(part: dict, entity: str, history: list[dict], topic: dict):
    if not isinstance(part, dict) or part.get("entity") != entity or part.get("role") != "expression":
        raise ValueError("wrong character or part role")
    if int(part.get("node", -1)) != commit._floor.NODE[entity]:
        raise ValueError("incorrect expression node")
    private = part.get("private") if isinstance(part.get("private"), dict) else {}
    if not isinstance(private.get("intent"), dict):
        raise ValueError("missing expression intent")
    expr = private.get("expression")
    if not isinstance(expr, dict) or not commit.semantic_values(expr):
        raise ValueError("no structured expression")
    text = commit.c.model_text(expr)
    if not text:
        raise ValueError("empty or invalid model speech")
    terms = commit.clean_terms(expr, topic, text)
    # A short repair/acknowledgment may contain no *new* subject words.
    # Publication applies the same clean_terms and quality gate; it must not
    # synthesize topic vocabulary just to satisfy preflight.
    commit.validate_public_expression(entity, text, terms, history[-8:])
    validate_uptake(history=history, speaker=entity, utterance=text,
                    move=str(expr.get("move") or ""))
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", required=True)
    parser.add_argument("--speaker", required=True)
    args = parser.parse_args()
    if args.speaker not in commit.AWAKE_ORDER:
        raise SystemExit("selected speaker not awake")
    part = json.loads(Path(args.part).read_text(encoding="utf-8"))
    validate_candidate(part, args.speaker,
                       commit.c.conv(),
                       commit.c.state().get("topic_episode") or {})
    print("PASS: selected expression preflight integrity")


if __name__ == "__main__":
    main()
