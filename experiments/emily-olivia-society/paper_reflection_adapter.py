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


def maybe_reflect(agent, time_step: int) -> bool:
    """Run Stanford reflection when enough new experience has accumulated.

    This mirrors the paper's importance-threshold trigger rather than reflecting
    every turn. The reflection itself is Stanford HCI GenerativeAgent.reflect(),
    which retrieves relevant memories and writes generated insights back into
    the memory stream.
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
    agent.brain.reflect(anchor, time_step=time_step)
    agent.brain.update_scratch({
        "reflection_last_step": time_step,
        "reflection_importance_threshold": threshold,
        "reflection_research_source": _RESEARCH_COMMIT,
    })
    agent.brain.save(str(agent.workspace))
    return True
