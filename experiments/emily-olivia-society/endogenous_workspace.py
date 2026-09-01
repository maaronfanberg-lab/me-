#!/usr/bin/env python3
"""Endogenous attention workspace for the Emily + Olivia Stanford runtime.

This is an experimental cognitive mechanism, not a consciousness claim.
It adds two timescales of explicit state around the existing Stanford chain:

* fast activation: deterministic competition among currently observed/retrieved
  representations during one pulse;
* slow traces: decaying salience history stored in Stanford scratch state and
  carried across pulses/runs by the existing brain.save() mechanism.

Only text that already exists as an observation or Stanford memory may enter the
broadcast. The module never generates inner monologue, autobiographical facts,
or dialogue. A caller may give an ignited broadcast to existing cognition as
additional context, or may run a private pulse with no speech at all.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Iterable, Mapping

ENV_FLAG = "COMMUNITY_ENDOGENOUS_WORKSPACE"
STATE_KEY = "endogenous_workspace_v1"
STATE_VERSION = 1
DEFAULT_THRESHOLD = 0.58
MAX_CANDIDATES = 16
MAX_SLOW_TRACES = 64
MAX_BROADCAST_ITEMS = 2
MAX_BROADCAST_CHARS = 700

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source: str
    text: str
    importance: float
    recency: float


@dataclass(frozen=True)
class PulseResult:
    enabled: bool
    broadcast_context: str
    diagnostics: dict


def feature_enabled(value: str | None = None) -> bool:
    """Return whether the experimental workspace is enabled.

    Default is OFF so the live Community Run remains backward compatible until
    an explicit experiment enables it.
    """
    raw = os.environ.get(ENV_FLAG, "0") if value is None else value
    return str(raw).strip().casefold() in _TRUE_VALUES


def _clamp01(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _normalize_text(text: object) -> str:
    return _WS.sub(" ", str(text or "").strip())


def _candidate_id(source: str, text: str) -> str:
    payload = f"{source}\n{_normalize_text(text)}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:20]


def observation_candidate(text: object) -> Candidate | None:
    cleaned = _normalize_text(text)
    if not cleaned:
        return None
    return Candidate(
        candidate_id=_candidate_id("observation", cleaned),
        source="observation",
        text=cleaned,
        importance=0.35,
        recency=1.0,
    )


def memory_candidate(node: object, time_step: int) -> Candidate | None:
    cleaned = _normalize_text(getattr(node, "content", ""))
    if not cleaned or cleaned.startswith("GENERATION ERROR:") or "<|" in cleaned:
        return None

    raw_importance = getattr(node, "importance", 0.0)
    try:
        importance = float(raw_importance)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(raw_importance))
        importance = float(match.group(0)) if match else 0.0
    importance = _clamp01(importance / 100.0)

    try:
        created = int(getattr(node, "created", 0) or 0)
    except (TypeError, ValueError):
        created = 0
    age = max(0, int(time_step) - created)
    recency = 1.0 / (1.0 + age / 8.0)

    node_type = _normalize_text(getattr(node, "node_type", "memory")) or "memory"
    source = f"memory:{node_type}"
    return Candidate(
        candidate_id=_candidate_id(source, cleaned),
        source=source,
        text=cleaned,
        importance=importance,
        recency=_clamp01(recency),
    )


def _empty_state() -> dict:
    return {"version": STATE_VERSION, "pulse_count": 0, "slow": {}}


def _sanitize_state(state: object) -> dict:
    if not isinstance(state, Mapping) or state.get("version") != STATE_VERSION:
        return _empty_state()
    try:
        pulse_count = max(0, int(state.get("pulse_count", 0)))
    except (TypeError, ValueError):
        pulse_count = 0

    slow: dict[str, dict] = {}
    raw_slow = state.get("slow", {})
    if isinstance(raw_slow, Mapping):
        for key, value in raw_slow.items():
            if not isinstance(key, str) or not isinstance(value, Mapping):
                continue
            strength = _clamp01(value.get("strength", 0.0))
            try:
                seen = max(0, int(value.get("seen", 0)))
                last_seen = max(0, int(value.get("last_seen", 0)))
            except (TypeError, ValueError):
                continue
            source = _normalize_text(value.get("source", "memory")) or "memory"
            slow[key] = {
                "strength": strength,
                "seen": seen,
                "last_seen": last_seen,
                "source": source,
            }
    return {"version": STATE_VERSION, "pulse_count": pulse_count, "slow": slow}


def _source_bias(source: str) -> float:
    if source == "observation":
        return 1.0
    if source.startswith("memory:reflection"):
        return 0.65
    if source.startswith("memory:"):
        return 0.50
    return 0.40


def score_candidate(candidate: Candidate, slow_strength: float) -> float:
    """Deterministic fast activation from current evidence plus slow trace."""
    return _clamp01(
        0.42 * _clamp01(candidate.importance)
        + 0.28 * _clamp01(candidate.recency)
        + 0.20 * _clamp01(slow_strength)
        + 0.10 * _source_bias(candidate.source)
    )


def run_pulse(
    candidates: Iterable[Candidate],
    prior_state: object,
    time_step: int,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[dict, str, dict]:
    """Run one deterministic competition/ignition pulse.

    Returns (new_state, broadcast_context, diagnostics). Diagnostics contain no
    representation text, only ids/sources/scores and timing/state metadata.
    """
    threshold = _clamp01(threshold, DEFAULT_THRESHOLD)
    state = _sanitize_state(prior_state)
    slow = dict(state["slow"])

    # Slow traces decay even when they are not currently retrieved.
    decayed: dict[str, dict] = {}
    for key, trace in slow.items():
        strength = _clamp01(trace.get("strength", 0.0)) * 0.94
        if strength < 0.015:
            continue
        decayed[key] = {
            "strength": strength,
            "seen": int(trace.get("seen", 0)),
            "last_seen": int(trace.get("last_seen", 0)),
            "source": str(trace.get("source", "memory")),
        }
    slow = decayed

    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        if not isinstance(candidate, Candidate) or not candidate.text.strip():
            continue
        existing = unique.get(candidate.candidate_id)
        if existing is None or (candidate.importance, candidate.recency) > (
            existing.importance,
            existing.recency,
        ):
            unique[candidate.candidate_id] = candidate
        if len(unique) >= MAX_CANDIDATES:
            break

    rows: list[dict] = []
    by_id = unique
    for candidate in by_id.values():
        trace = slow.get(candidate.candidate_id, {})
        slow_before = _clamp01(trace.get("strength", 0.0))
        score = score_candidate(candidate, slow_before)
        slow_after = _clamp01(0.75 * slow_before + 0.25 * score)
        slow[candidate.candidate_id] = {
            "strength": slow_after,
            "seen": int(trace.get("seen", 0)) + 1,
            "last_seen": max(0, int(time_step)),
            "source": candidate.source,
        }
        rows.append(
            {
                "id": candidate.candidate_id,
                "source": candidate.source,
                "score": round(score, 6),
                "slow_before": round(slow_before, 6),
                "slow_after": round(slow_after, 6),
            }
        )

    rows.sort(key=lambda row: (-row["score"], row["id"]))
    selected_rows = [row for row in rows if row["score"] >= threshold][:MAX_BROADCAST_ITEMS]

    # State carries ids and numeric traces only. It intentionally stores no text.
    if len(slow) > MAX_SLOW_TRACES:
        ranked_traces = sorted(
            slow.items(),
            key=lambda item: (
                float(item[1].get("strength", 0.0)),
                int(item[1].get("last_seen", 0)),
                item[0],
            ),
            reverse=True,
        )[:MAX_SLOW_TRACES]
        slow = dict(ranked_traces)

    new_state = {
        "version": STATE_VERSION,
        "pulse_count": int(state["pulse_count"]) + 1,
        "slow": slow,
    }

    selected_texts = [by_id[row["id"]].text for row in selected_rows if row["id"] in by_id]
    broadcast = ""
    if selected_texts:
        joined = " | ".join(selected_texts)
        joined = joined[:MAX_BROADCAST_CHARS].rstrip()
        broadcast = "Workspace broadcast from existing observations/memories only: " + joined

    diagnostics = {
        "enabled": True,
        "version": STATE_VERSION,
        "pulse": new_state["pulse_count"],
        "time_step": max(0, int(time_step)),
        "candidate_count": len(rows),
        "threshold": threshold,
        "ignited": bool(selected_rows),
        "selected": selected_rows,
        "top": rows[:5],
        "slow_trace_count": len(slow),
    }
    return new_state, broadcast, diagnostics


def _retrieve_memory_candidates(agent: object, other_name: str, time_step: int) -> list[Candidate]:
    focal = f"What currently matters to {agent.name} in relation to {other_name}"
    retrieved = agent.brain.memory_stream.retrieve([focal], time_step=time_step, n_count=12)
    nodes = retrieved.get(focal, []) if isinstance(retrieved, Mapping) else []
    out: list[Candidate] = []
    for node in nodes:
        candidate = memory_candidate(node, time_step)
        if candidate is not None:
            out.append(candidate)
    return out


def pulse_agent(
    agent: object,
    other_name: str,
    time_step: int,
    observed_text: object = "",
) -> PulseResult:
    """Run one workspace pulse against an agent's real Stanford memory stream."""
    if not feature_enabled():
        return PulseResult(False, "", {"enabled": False, "version": STATE_VERSION})

    candidates: list[Candidate] = []
    observed = observation_candidate(observed_text)
    if observed is not None:
        candidates.append(observed)
    candidates.extend(_retrieve_memory_candidates(agent, str(other_name), int(time_step)))

    prior = getattr(agent.brain, "scratch", {}).get(STATE_KEY, _empty_state())
    new_state, broadcast, diagnostics = run_pulse(candidates, prior, int(time_step))
    agent.brain.update_scratch({STATE_KEY: new_state})
    return PulseResult(True, broadcast, diagnostics)
