#!/usr/bin/env python3
"""Recover a frozen Endogenous Workspace tape from Git replay snapshots.

Continuous Community Runs publish ``community_session.json`` after each turn.
Even when the JSONL stream is missing or empty, Git therefore contains a
sequence of historical ``latest_turn`` snapshots. This recorder walks that
history and reconstructs a multi-turn candidate tape without calling an LLM,
loading a Stanford agent, sending dialogue, or writing any live state.

Historical Stanford importance/recency scalars are not committed with the
replay. We do not invent them. Every recovered candidate receives neutral
importance/recency constants and the observed Stanford retrieval order is kept
as an explicitly labelled rank proxy. The downstream trial must treat this as
proxy evidence, not as a reconstruction of unavailable internal scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Mapping

REPLAY_PATH = "experiments/emily-olivia-society/replay/community_session.json"
SCHEMA_VERSION = 1
NEUTRAL_IMPORTANCE = 0.5
NEUTRAL_RECENCY = 0.5


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _stable_id(agent: str, text: str) -> str:
    payload = f"history-retrieved:{agent}\n{text.strip()}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:20]


def _rank_proxy(rank: int, count: int) -> float:
    if count <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (count - 1)


def _extract_turn(payload: Mapping) -> dict | None:
    turn = payload.get("latest_turn")
    if not isinstance(turn, Mapping):
        return None
    retrieved = turn.get("retrieved_memories")
    if not isinstance(retrieved, list) or not any(str(x or "").strip() for x in retrieved):
        return None
    try:
        time_step = int(turn.get("time_step"))
    except (TypeError, ValueError):
        return None
    agent = str(turn.get("agent") or "").strip()
    if not agent:
        return None
    return {**dict(turn), "agent": agent, "time_step": time_step}


def _history_payloads(repo_root: Path, max_commits: int) -> list[tuple[str, dict]]:
    log = _git(
        repo_root,
        "log",
        f"--max-count={max_commits}",
        "--reverse",
        "--format=%H",
        "--",
        REPLAY_PATH,
    )
    out: list[tuple[str, dict]] = []
    for sha in [line.strip() for line in log.splitlines() if line.strip()]:
        proc = subprocess.run(
            ["git", "show", f"{sha}:{REPLAY_PATH}"],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append((sha, payload))
    return out


def reconstruct_history(
    snapshots: list[tuple[str, Mapping]],
    session_id: str | None = None,
) -> dict:
    sessions: dict[str, dict] = defaultdict(lambda: {"turns": {}, "commits": [], "last_index": -1})
    for index, (sha, payload) in enumerate(snapshots):
        sid = str(payload.get("session_id") or "").strip()
        if not sid:
            continue
        turn = _extract_turn(payload)
        if turn is None:
            continue
        key = (int(turn["time_step"]), str(turn["agent"]))
        sessions[sid]["turns"][key] = {"turn": turn, "commit": sha}
        sessions[sid]["commits"].append(sha)
        sessions[sid]["last_index"] = index

    if session_id:
        if session_id not in sessions:
            raise ValueError(f"session {session_id!r} was not found in replay history")
        chosen_id = session_id
    else:
        eligible = [
            (len(value["turns"]), int(value["last_index"]), sid)
            for sid, value in sessions.items()
            if value["turns"]
        ]
        if not eligible:
            raise ValueError("no replay session with retrieved turns was found in Git history")
        eligible.sort()
        chosen_id = eligible[-1][2]

    chosen = sessions[chosen_id]
    ordered = sorted(
        chosen["turns"].values(),
        key=lambda entry: (int(entry["turn"]["time_step"]), str(entry["turn"]["agent"])),
    )
    ticks: list[dict] = []
    for entry in ordered:
        turn = entry["turn"]
        retrieved = [str(x or "").strip() for x in turn.get("retrieved_memories", [])]
        retrieved = [text for text in retrieved if text]
        seen: set[str] = set()
        candidates: list[dict] = []
        for rank, text in enumerate(retrieved, start=1):
            if text in seen:
                continue
            seen.add(text)
            candidates.append(
                {
                    "id": _stable_id(str(turn["agent"]), text),
                    "source": "memory:history_replay_proxy",
                    "text": text,
                    "importance": NEUTRAL_IMPORTANCE,
                    "recency": NEUTRAL_RECENCY,
                    "retrieval_score": round(_rank_proxy(rank, len(retrieved)), 6),
                    "retrieval_rank": rank,
                    "metadata_recovered": False,
                }
            )
        if not candidates:
            continue
        observation = turn.get("observation")
        inbox = observation.get("inbox", []) if isinstance(observation, Mapping) else []
        inbound = ""
        if isinstance(inbox, list) and inbox and isinstance(inbox[-1], Mapping):
            inbound = str(inbox[-1].get("content") or "").strip()
        ticks.append(
            {
                "time_step": int(turn["time_step"]),
                "agent": str(turn["agent"]),
                "observation": inbound,
                "history_commit": entry["commit"],
                "candidates": candidates,
            }
        )

    unique_commits = list(dict.fromkeys(chosen["commits"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "source": "git_history_of_community_session_latest_turn",
            "source_replay_path": REPLAY_PATH,
            "session_id": chosen_id,
            "frozen": True,
            "read_only_reconstruction": True,
            "tick_count": len(ticks),
            "history_snapshot_count": len(unique_commits),
            "history_first_commit": unique_commits[0] if unique_commits else None,
            "history_last_commit": unique_commits[-1] if unique_commits else None,
            "retrieval_score_mode": "rank_proxy_from_recorded_stanford_retrieval_order",
            "importance_mode": f"neutral_constant_{NEUTRAL_IMPORTANCE}_historical_value_unavailable",
            "recency_mode": f"neutral_constant_{NEUTRAL_RECENCY}_historical_value_unavailable",
            "llm_generation": "none_during_history_reconstruction",
            "proxy_limitations_acknowledged": True,
        },
        "ticks": ticks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover a frozen EW tape from Git replay history.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--max-commits", type=int, default=500)
    parser.add_argument("--min-ticks", type=int, default=8)
    args = parser.parse_args()

    repo_root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    snapshots = _history_payloads(repo_root, max(1, args.max_commits))
    tape = reconstruct_history(snapshots, session_id=args.session_id)
    tick_count = int(tape["metadata"]["tick_count"])
    if tick_count < args.min_ticks:
        raise SystemExit(
            f"Recovered only {tick_count} unique retrieved turns; need at least {args.min_ticks}."
        )
    Path(args.out).write_text(json.dumps(tape, indent=2, sort_keys=True) + "\n")
    print(json.dumps(tape["metadata"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
