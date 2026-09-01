#!/usr/bin/env python3
"""Build a frozen Endogenous Workspace tape from one Community Run artifact.

The Community artifact contains the full JSONL turn stream plus the final Emily
and Olivia Stanford memory stores. This script joins already-recorded retrieval
content back to real Stanford nodes and recovers the original node importance
and creation time. It never calls an LLM, sends dialogue, writes Stanford
memory, or enables Endogenous Workspace.

Retrieval score itself is not persisted by Stanford, so retrieval order remains
an explicitly labelled rank proxy. Unlike the earlier Git-history proxy, node
importance and recency are real for every selected tick.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

SCHEMA_VERSION = 1


def _normalize(text: object) -> str:
    return " ".join(str(text or "").strip().split())


def _candidate_id(source: str, text: str) -> str:
    payload = f"{source}\n{_normalize(text)}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:20]


def _rank_proxy(rank: int, count: int) -> float:
    if count <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (count - 1)


def _read_nodes(root: Path, agent: str) -> dict[str, list[dict]]:
    path = root / "workspaces" / agent.lower() / "memory_stream" / "nodes.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a node list")
    out: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        text = _normalize(row.get("content"))
        if text:
            out.setdefault(text, []).append(dict(row))
    return out


def _turn_rows(jsonl_path: Path) -> list[dict]:
    out: list[dict] = []
    for line_index, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, Mapping):
            continue
        turn = None
        if row.get("type") == "turn" and isinstance(row.get("turn"), Mapping):
            turn = dict(row["turn"])
        elif row.get("type") == "session_start" and isinstance(row.get("opening_turn"), Mapping):
            turn = dict(row["opening_turn"])
        if turn is None:
            continue
        turn["_session_id"] = str(row.get("session_id") or "")
        turn["_line_index"] = line_index
        out.append(turn)
    return out


def _choose_node(nodes: Iterable[dict], time_step: int) -> dict | None:
    candidates = []
    for node in nodes:
        try:
            created = int(node.get("created", 0) or 0)
        except (TypeError, ValueError):
            continue
        if created <= time_step:
            candidates.append(node)
    if not candidates:
        return None
    return max(candidates, key=lambda node: int(node.get("created", 0) or 0))


def _candidate_row(node: Mapping, text: str, time_step: int, rank: int, count: int) -> dict:
    node_type = _normalize(node.get("node_type")) or "memory"
    source = f"memory:{node_type}"
    try:
        raw_importance = float(node.get("importance", 0.0) or 0.0)
    except (TypeError, ValueError):
        raw_importance = 0.0
    importance = max(0.0, min(1.0, raw_importance / 100.0))
    created = int(node.get("created", 0) or 0)
    age = max(0, int(time_step) - created)
    recency = 1.0 / (1.0 + age / 8.0)
    return {
        "id": _candidate_id(source, text),
        "source": source,
        "text": text,
        "importance": round(importance, 6),
        "recency": round(recency, 6),
        "retrieval_score": round(_rank_proxy(rank, count), 6),
        "retrieval_rank": rank,
        "metadata_recovered": True,
        "stanford_node_id": node.get("node_id"),
        "stanford_created": created,
        "stanford_importance_raw": raw_importance,
    }


def build_exact_tape(
    artifact_root: str | Path,
    *,
    min_ticks: int = 12,
    artifact_run_id: int | None = None,
    artifact_sha256: str = "",
) -> dict:
    root = Path(artifact_root)
    jsonl = root / "replay" / "community_session.jsonl"
    if not jsonl.is_file():
        raise ValueError(f"missing artifact replay stream: {jsonl}")

    indexes = {name: _read_nodes(root, name) for name in ("Emily", "Olivia")}
    eligible_by_step: dict[int, dict] = {}
    rejected_turns = 0

    for turn in _turn_rows(jsonl):
        agent = str(turn.get("agent") or "").strip()
        if agent not in indexes:
            continue
        try:
            time_step = int(turn.get("time_step"))
        except (TypeError, ValueError):
            continue
        retrieved = turn.get("retrieved_memories")
        if not isinstance(retrieved, list) or not retrieved:
            continue
        texts = [_normalize(text) for text in retrieved if _normalize(text)]
        if not texts:
            continue

        candidates: list[dict] = []
        seen: set[str] = set()
        exact = True
        for rank, text in enumerate(texts, start=1):
            if text in seen:
                continue
            seen.add(text)
            node = _choose_node(indexes[agent].get(text, []), time_step)
            if node is None:
                exact = False
                break
            candidates.append(_candidate_row(node, text, time_step, rank, len(texts)))
        if not exact or not candidates:
            rejected_turns += 1
            continue

        eligible_by_step[time_step] = {
            "time_step": time_step,
            "agent": agent,
            "session_id": turn.get("_session_id"),
            "jsonl_line_index": int(turn.get("_line_index", 0)),
            "candidates": candidates,
        }

    if not eligible_by_step:
        raise ValueError("artifact contains no turns whose retrievals exactly match Stanford nodes")

    # Choose the newest longest contiguous block. This avoids mixing mutually
    # inconsistent historical branches that can coexist in an accumulated JSONL.
    steps = sorted(eligible_by_step)
    blocks: list[list[int]] = []
    current: list[int] = []
    for step in steps:
        if not current or step == current[-1] + 1:
            current.append(step)
        else:
            blocks.append(current)
            current = [step]
    if current:
        blocks.append(current)
    blocks.sort(key=lambda block: (len(block), block[-1]))
    chosen_steps = blocks[-1]
    if len(chosen_steps) < min_ticks:
        raise ValueError(
            f"newest best exact block has {len(chosen_steps)} ticks; need at least {min_ticks}"
        )

    ticks = [eligible_by_step[step] for step in chosen_steps]
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "source": "community_run_artifact_exact_stanford_join",
            "artifact_run_id": artifact_run_id,
            "artifact_sha256": artifact_sha256,
            "frozen": True,
            "read_only_reconstruction": True,
            "tick_count": len(ticks),
            "time_step_start": ticks[0]["time_step"],
            "time_step_end": ticks[-1]["time_step"],
            "rejected_nonexact_turns": rejected_turns,
            "importance_mode": "actual_stanford_node_importance",
            "recency_mode": "derived_from_actual_stanford_created_time",
            "retrieval_score_mode": "rank_proxy_from_recorded_stanford_retrieval_order",
            "exact_node_metadata": True,
            "llm_generation": "none_during_artifact_reconstruction",
        },
        "ticks": ticks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact-metadata EW tape from a Community artifact.")
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-ticks", type=int, default=12)
    parser.add_argument("--artifact-run-id", type=int, default=None)
    parser.add_argument("--artifact-sha256", default="")
    args = parser.parse_args()

    tape = build_exact_tape(
        args.artifact_root,
        min_ticks=args.min_ticks,
        artifact_run_id=args.artifact_run_id,
        artifact_sha256=args.artifact_sha256,
    )
    Path(args.out).write_text(json.dumps(tape, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(tape["metadata"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
