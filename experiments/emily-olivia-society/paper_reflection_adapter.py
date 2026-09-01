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
_DEFAULT_THRESHOLD = 150.0
_LEGACY_LOW_THRESHOLD_MAX = 20.0
_EMPTY_EMBEDDING_ERROR = "Input text must be a non-empty string."
_MAX_REFLECTION_ATTEMPTS = 8


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
                if score > 10.0:
                    score /= 10.0
                return min(10.0, score)
        except (TypeError, ValueError):
            pass
    return 1.0


def _reflection_count(agent) -> int:
    return sum(
        1
        for node in agent.brain.memory_stream.seq_nodes
        if getattr(node, "node_type", None) == "reflection"
    )


def maybe_reflect(agent, time_step: int) -> bool:
    """Run Stanford reflection after paper-scale accumulated importance.

    Natural declarative model output is parsed by the guarded local reflection
    adapter, while malformed, structured, prompt-shaped, or question-shaped
    output is still removed by memory hygiene. When a stochastic pass yields no
    clean insight, resample the same Stanford request at the same logical
    timestep. The reflection watermark advances only after a clean reflection
    survives, so one bad local-model draw cannot suppress future reflection.
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
        f"Higher-level understanding for {agent.name} based on these recent experiences: "
        + " | ".join(anchor_parts)
    )
    before_reflections = _reflection_count(agent)
    total_memories = len(list(agent.brain.memory_stream.seq_nodes))
    install_natural_reflection_parser()
    succeeded = False

    for _attempt in range(_MAX_REFLECTION_ATTEMPTS):
        try:
            agent.brain.memory_stream.reflect(
                anchor=anchor,
                reflection_count=1,
                retrieval_count=min(12, max(1, total_memories)),
                time_step=time_step,
            )
        except ValueError as exc:
            if str(exc) != _EMPTY_EMBEDDING_ERROR:
                raise
        finally:
            sanitize_memory_stream(agent.brain.memory_stream)

        if _reflection_count(agent) > before_reflections:
            succeeded = True
            break

    scratch_update = {
        "reflection_importance_threshold": threshold,
        "reflection_research_source": _RESEARCH_COMMIT,
    }
    if succeeded:
        scratch_update["reflection_last_step"] = time_step
    agent.brain.update_scratch(scratch_update)
    agent.brain.save(str(agent.workspace))
    return succeeded
