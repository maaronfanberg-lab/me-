#!/usr/bin/env python3
"""Build a frozen Endogenous Workspace candidate tape from an existing replay.

This is deliberately read-only with respect to Emily and Olivia. It loads their
saved Stanford workspaces only to recover metadata for memories that the normal
Stanford chain already retrieved in a published replay. It never calls remember,
reflect, plan, act, send_message, or save.

The current Stanford retrieval API returns ranked nodes rather than exposed raw
retrieval scores, so the tape records a deterministic rank proxy and labels it
as such. That limitation is explicit rather than silently invented away.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping

from community_cycle import load_agents
from endogenous_workspace import memory_candidate

TAPE_SCHEMA_VERSION = 1


def _turns_from_json(payload: Mapping) -> list[dict]:
    turns: list[dict] = []
    opening = payload.get("opening_turn")
    if isinstance(opening, Mapping):
        turns.append(dict(opening))
    bounded = payload.get("turns")
    if isinstance(bounded, list):
        turns.extend(dict(turn) for turn in bounded if isinstance(turn, Mapping))
    latest = payload.get("latest_turn")
    if isinstance(latest, Mapping):
        candidate = dict(latest)
        signature = (candidate.get("agent"), candidate.get("time_step"))
        if all((turn.get("agent"), turn.get("time_step")) != signature for turn in turns):
            turns.append(candidate)
    return turns


def read_replay_turns(path: str | Path) -> list[dict]:
    path = Path(path)
    if path.suffix == ".jsonl":
        turns: list[dict] = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                continue
            if row.get("type") == "turn" and isinstance(row.get("turn"), Mapping):
                turns.append(dict(row["turn"]))
            elif row.get("type") == "session_start" and isinstance(row.get("opening_turn"), Mapping):
                turns.append(dict(row["opening_turn"]))
        return turns
    payload = json.loads(path.read_text())
    if not isinstance(payload, Mapping):
        raise ValueError("replay JSON must contain an object")
    return _turns_from_json(payload)


def _memory_index(agent: object) -> dict[str, list[object]]:
    index: dict[str, list[object]] = {}
    nodes = list(getattr(agent.brain.memory_stream, "seq_nodes", []) or [])
    for node in nodes:
        text = str(getattr(node, "content", "") or "").strip()
        if text:
            index.setdefault(text, []).append(node)
    return index


def _rank_proxy(rank: int, count: int) -> float:
    if count <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (count - 1)


def _latest_inbound(turn: Mapping) -> str:
    observation = turn.get("observation")
    if not isinstance(observation, Mapping):
        return ""
    inbox = observation.get("inbox")
    if not isinstance(inbox, list) or not inbox:
        return ""
    latest = inbox[-1]
    if not isinstance(latest, Mapping):
        return ""
    return str(latest.get("content") or "").strip()


def build_tape(turns: Iterable[Mapping], agents: Iterable[object], source: str = "") -> dict:
    by_name = {str(agent.name): agent for agent in agents}
    indexes = {name: _memory_index(agent) for name, agent in by_name.items()}
    ticks: list[dict] = []
    unmatched = 0

    for turn in turns:
        agent_name = str(turn.get("agent") or "").strip()
        if agent_name not in by_name:
            continue
        try:
            time_step = int(turn.get("time_step"))
        except (TypeError, ValueError):
            continue
        retrieved = turn.get("retrieved_memories")
        if not isinstance(retrieved, list) or not retrieved:
            continue

        candidates: list[dict] = []
        seen: set[str] = set()
        count = len(retrieved)
        for rank, raw_text in enumerate(retrieved, start=1):
            text = str(raw_text or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            nodes = indexes[agent_name].get(text, [])
            if nodes:
                # If duplicate text exists as multiple Stanford nodes, prefer the
                # most recent node that already existed by this replay time step.
                eligible = [node for node in nodes if int(getattr(node, "created", 0) or 0) <= time_step]
                node = max(eligible or nodes, key=lambda item: int(getattr(item, "created", 0) or 0))
                candidate = memory_candidate(node, time_step)
            else:
                candidate = None
                unmatched += 1

            if candidate is None:
                # Preserve the already-retrieved content but mark metadata as
                # unknown rather than fabricating Stanford importance.
                candidates.append(
                    {
                        "id": f"unmatched:{agent_name}:{time_step}:{rank}",
                        "source": "memory:unmatched_replay",
                        "text": text,
                        "importance": 0.0,
                        "recency": 0.0,
                        "retrieval_score": round(_rank_proxy(rank, count), 6),
                        "retrieval_rank": rank,
                        "metadata_recovered": False,
                    }
                )
            else:
                candidates.append(
                    {
                        "id": candidate.candidate_id,
                        "source": candidate.source,
                        "text": candidate.text,
                        "importance": round(float(candidate.importance), 6),
                        "recency": round(float(candidate.recency), 6),
                        "retrieval_score": round(_rank_proxy(rank, count), 6),
                        "retrieval_rank": rank,
                        "metadata_recovered": True,
                    }
                )

        if candidates:
            ticks.append(
                {
                    "time_step": time_step,
                    "agent": agent_name,
                    "observation": _latest_inbound(turn),
                    "candidates": candidates,
                }
            )

    return {
        "schema_version": TAPE_SCHEMA_VERSION,
        "metadata": {
            "source_replay": source,
            "frozen": True,
            "read_only_reconstruction": True,
            "retrieval_score_mode": "rank_proxy_from_normal_stanford_retrieval_order",
            "unmatched_memory_count": unmatched,
            "tick_count": len(ticks),
            "llm_generation": "none_during_tape_build",
        },
        "ticks": ticks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze existing Stanford retrievals into an EW replay tape.")
    parser.add_argument("--replay", required=True, help="Existing community_session.json or .jsonl")
    parser.add_argument("--out", required=True, help="Output frozen tape JSON")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow a tape with fewer than two recovered turns (useful only for recorder debugging).",
    )
    args = parser.parse_args()

    turns = read_replay_turns(args.replay)
    tape = build_tape(turns, load_agents(), source=str(args.replay))
    if len(tape["ticks"]) < 2 and not args.allow_partial:
        raise SystemExit(
            "Refusing to call this a replay tape: fewer than two retrieved turns were recovered. "
            "Use --allow-partial only for recorder debugging."
        )
    Path(args.out).write_text(json.dumps(tape, indent=2, sort_keys=True) + "\n")
    print(json.dumps(tape["metadata"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
