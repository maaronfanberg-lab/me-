#!/usr/bin/env python3
"""Reflection adapter following the original Generative Agents architecture.

Upstream research source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

The paper implementation triggers reflection after accumulated importance,
creates focal points, retrieves memories around those focal points, and stores
higher-level thoughts. In this smaller environment we preserve that structure
while delegating retrieval and reflection storage to Stanford HCI genagents.
"""
from __future__ import annotations

from reflection_generation import install_natural_reflection_parser
from reflection_hygiene import sanitize_memory_stream

_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
# The original Generative Agents implementation uses an importance trigger of
# 150 with individual event poignancy scored on a 1-10 scale.
_DEFAULT_THRESHOLD = 150.0
_LEGACY_LOW_THRESHOLD_MAX = 20.0
_EMPTY_EMBEDDING_ERROR = "Input text must be a non-empty string."


def _latest_nodes(agent, count: int = 12):
    nodes = list(agent.brain.memory_stream.seq_nodes)
    return nodes[-max(1, count):]


def _importance(node) -> float:
    """Return paper-scale (0-10) importance for a Stanford memory node."""
    for attr in ("poignancy", "importance"):
        value = getattr(node, attr, None)
        try:
            if value is not None:
                score = max(0.0, float(value))
                # Stanford HCI/local patches may represent poignancy on 0-100.
                # Normalize that larger scale before comparing with the paper's
                # 150-point cumulative reflection trigger.
                if score > 10.0:
                    score /= 10.0
                return min(10.0, score)
        except (TypeError, ValueError):
            pass
    # If a node exposes no score at all, count it as one mundane experience.
    return 1.0


def _reflection_count(agent) -> int:
    return sum(
        1
        for node in agent.brain.memory_stream.seq_nodes
        if getattr(node, "node_type", None) == "reflection"
    )


def maybe_reflect(agent, time_step: int) -> bool:
    """Run Stanford reflection after paper-scale accumulated importance.

    This mirrors the paper's importance-threshold trigger rather than reflecting
    every turn. Reflection uses Stanford HCI MemoryStream directly with named
    arguments so the timestep cannot be confused with reflection_count.

    Earlier Community builds persisted a threshold of 12, which was mismatched
    to Stanford's larger poignancy scale and could cause reflection after a
    single observation. Treat that legacy low value as a migration marker and
    restore the paper-scale threshold of 150. Blank or malformed reflection
    output is removed rather than becoming durable memory; no substitute insight
    or authored fallback is invented.
    """
    scratch = agent.brain.scratch
    last_step = int(scratch.get("reflection_last_step", 0) or 0)
    try:
        threshold = float(
            scratch.get("reflection_importance_threshold", _DEFAULT_THRESHOLD)
        )
    except (TypeError, ValueError):
        threshold = _DEFAULT_THRESHOLD
    if threshold <= _LEGACY_LOW_THRESHOLD_MAX:
        threshold = _DEFAULT_THRESHOLD

    fresh = [
        node for node in _latest_nodes(agent, 24)
        if int(getattr(node, "created", 0) or 0) > last_step
    ]
    accumulated = sum(_importance(node) for node in fresh)
    if not fresh or accumulated < threshold:
        return False

    anchor_parts = [str(getattr(node, "content", "")).strip() for node in fresh[-8:]]
    anchor_parts = [part for part in anchor_parts if part]
    if not anchor_parts:
        return False

    anchor = (
        f"What higher-level insight should {agent.name} draw from these recent experiences? "
        + " | ".join(anchor_parts)
    )
    before_reflections = _reflection_count(agent)
    total_memories = len(list(agent.brain.memory_stream.seq_nodes))
    install_natural_reflection_parser()
    try:
        agent.brain.memory_stream.reflect(
            anchor=anchor,
            reflection_count=3,
            retrieval_count=min(12, max(1, total_memories)),
            time_step=time_step,
        )
    except ValueError as exc:
        if str(exc) != _EMPTY_EMBEDDING_ERROR:
            raise
        # Stanford can append a malformed node immediately before its embedding
        # boundary rejects it. The hygiene pass below removes that partial node.

    sanitize_memory_stream(agent.brain.memory_stream)
    after_reflections = _reflection_count(agent)
    agent.brain.update_scratch({
        "reflection_last_step": time_step,
        "reflection_importance_threshold": threshold,
        "reflection_research_source": _RESEARCH_COMMIT,
    })
    agent.brain.save(str(agent.workspace))
    return after_reflections > before_reflections
