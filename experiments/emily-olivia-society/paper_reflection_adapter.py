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

_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_DEFAULT_THRESHOLD = 12
_EMPTY_EMBEDDING_ERROR = "Input text must be a non-empty string."


def _latest_nodes(agent, count: int = 12):
    nodes = list(agent.brain.memory_stream.seq_nodes)
    return nodes[-max(1, count):]


def _importance(node) -> float:
    for attr in ("poignancy", "importance"):
        value = getattr(node, attr, None)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    # genagents memories do not expose the paper's scratch counter directly.
    # Treat each new observation as one unit so reflection remains periodic.
    return 1.0


def _reflection_count(agent) -> int:
    return sum(
        1
        for node in agent.brain.memory_stream.seq_nodes
        if getattr(node, "node_type", None) == "reflection"
    )


def maybe_reflect(agent, time_step: int) -> bool:
    """Run Stanford reflection when enough new experience has accumulated.

    This mirrors the paper's importance-threshold trigger rather than reflecting
    every turn. Reflection uses Stanford HCI MemoryStream directly with named
    arguments so the timestep cannot be confused with reflection_count.

    Small local models can occasionally return an empty item inside an otherwise
    valid reflection list. Stanford rejects that item at the embedding boundary.
    We preserve any valid reflections already written, discard the blank failure,
    and let conversation continue rather than inventing substitute reflection text.
    """
    scratch = agent.brain.scratch
    last_step = int(scratch.get("reflection_last_step", 0) or 0)
    threshold = float(scratch.get("reflection_importance_threshold", _DEFAULT_THRESHOLD))

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
        # A blank generated item is never inserted because embedding rejects it.
        # Valid items generated before it remain in the stream and are preserved.

    after_reflections = _reflection_count(agent)
    agent.brain.update_scratch({
        "reflection_last_step": time_step,
        "reflection_importance_threshold": threshold,
        "reflection_research_source": _RESEARCH_COMMIT,
    })
    agent.brain.save(str(agent.workspace))
    return after_reflections > before_reflections
