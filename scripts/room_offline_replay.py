"""Deterministic, read-only corpus sampler for The Room.

This is an annotation/replay tool, not a turn-taking policy. It does not
assume that a question mark is a question, that a model's reported move is
correct, or that sleeping characters witnessed public dialogue.

Only public fields are copied into review windows. Source IDs retain
provenance, and caller-supplied observer maps are never inferred from a
present-day awake list.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping


def public_events(feed: Mapping) -> tuple[dict, ...]:
    """Project published events into a privacy-minimal, ordered corpus."""
    raw = feed.get("conversation")
    if not isinstance(raw, list):
        raise ValueError("expected Room feed with conversation list")
    seen: set[str] = set()
    out = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"non-message item at index {index}")
        source_id = str(item.get("id") or "").strip()
        speaker = str(item.get("speaker") or "").lower()
        utterance = str(item.get("text") or "").strip()
        if not source_id or source_id in seen or not speaker or not utterance:
            raise ValueError(f"missing, duplicate, or invalid public event at index {index}")
        seen.add(source_id)
        cognition = item.get("cognition") if isinstance(item.get("cognition"), dict) else {}
        out.append({
            "source_id": source_id,
            "speaker": speaker,
            "utterance": utterance,
            "at": str(item.get("at") or ""),
            "reported_target": str(cognition.get("target") or item.get("target") or ""),
            "reported_move": str(cognition.get("move_type") or item.get("move") or ""),
            "beat_id": str(item.get("beat_id") or ""),
            "ordinal": index,
        })
    return tuple(out)


def read_public_feed(path: str | Path) -> tuple[dict, ...]:
    """Read only; never copy private cognition, profiles, secrets, or memories."""
    source = Path(path)
    return public_events(json.loads(source.read_text(encoding="utf-8")))


def observer_view(
    events: Iterable[Mapping],
    witness_source_ids: Mapping[str, Iterable[str]],
    entity: str,
) -> tuple[dict, ...]:
    """Observed messages MUST come from a witness manifest.

    If no witness evidence exists, return nothing: public visibility is not
    proof that a sleeping participant heard a message.
    """
    witnessed = set(witness_source_ids.get(entity, ()))
    return tuple(dict(event) for event in events if event["source_id"] in witnessed)


def review_windows(
    events: Iterable[Mapping],
    *,
    sample_count: int,
    seed: str,
    preceding: int = 3,
    following: int = 2,
) -> tuple[dict, ...]:
    """Select reproducible sequences without producing automatic labels.

    A question mark or metadata target is only a *sampling cue*, not a CA
    interpretation. Oversample potential adjacency actions where possible,
    but preserve other turns as negative controls.
    """
    ordered = tuple(events)
    if sample_count < 0 or preceding < 0 or following < 0 or not seed:
        raise ValueError("invalid sample window configuration")
    if sample_count == 0 or not ordered:
        return ()
    if len({m["source_id"] for m in ordered}) != len(ordered):
        raise ValueError("duplicate source ID cannot support credible annotation")
    ranked = []
    for i, m in enumerate(ordered):
        cue = bool("?" in m["utterance"] or m.get("reported_target"))
        digest = sha256(f"{seed}:{m['source_id']}".encode()).hexdigest()
        ranked.append((not cue, digest, i))
    # First a mixed prioritization of action candidates, never lexical novelty.
    chosen = sorted(ranked)[:sample_count]
    windows = []
    for _, _, i in sorted(chosen, key=lambda item: item[-1]):
        turn = ordered[i]
        windows.append({
            "anchor_id": turn["source_id"],
            "sampling_cue": (
                "unverified_question_or_recipient_cue"
                if "?" in turn["utterance"] or turn.get("reported_target")
                else "unfiltered_turn"
            ),
            "public_context": [dict(x) for x in ordered[max(0, i-preceding): min(len(ordered), i+following+1)]],
            "human_action_label": None,
            "human_recipient_label": None,
            "human_uptake_label": None,
        })
    return tuple(windows)
