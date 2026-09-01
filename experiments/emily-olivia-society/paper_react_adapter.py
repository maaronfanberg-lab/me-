#!/usr/bin/env python3
"""Reaction stage adapted from the original Stanford Generative Agents planner.

Upstream research source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

The paper planner chooses a retrieved event, decides whether the persona should
chat/react, then creates the resulting action. Emily + Olivia have no Smallville
maze, path, or game objects, so this adapter preserves the cognitive boundary:
retrieve around the current social event -> select that event -> establish the
reaction mode -> let Stanford's interaction module generate the spoken action.
It never writes dialogue for the agents.
"""
from __future__ import annotations

_ORIGINAL_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"


def _clean_memory_nodes(nodes):
    out = []
    for node in nodes or []:
        content = str(getattr(node, "content", "") or "").strip()
        if content and content not in out:
            out.append(content)
    return out


def react_to_observation(agent, other_name: str, inbound: str, time_step: int) -> dict:
    """Retrieve context for the current event and select the paper-style reaction.

    In the original simulation `_should_react` may choose chat, wait, or keep the
    current plan depending on a retrieved event and spatial/activity state. In
    this dedicated two-person conversation an addressed inbound message is the
    social event, so the corresponding valid reaction is `chat with <person>`.
    Stanford still supplies the retrieved context and the utterance itself.
    """
    focal = (
        f"{other_name} said to {agent.name}: {inbound}\n"
        f"What memories and thoughts are relevant to how {agent.name} should react?"
    )
    retrieved = agent.brain.memory_stream.retrieve([focal], time_step=time_step, n_count=8)
    memories = _clean_memory_nodes(retrieved.get(focal, []))

    reaction = {
        "event": inbound,
        "source": other_name,
        "mode": f"chat with {other_name}",
        "retrieved": memories,
    }
    agent.brain.update_scratch(
        {
            "current_social_reaction": reaction["mode"],
            "current_social_event": inbound[:500],
            "reaction_research_source": _ORIGINAL_RESEARCH_COMMIT,
        }
    )
    return reaction


def reaction_context(reaction: dict) -> str:
    """Expose retrieved cognitive context, never a scripted conversational move."""
    mode = str(reaction.get("mode") or "").strip()
    memories = [str(x).strip() for x in reaction.get("retrieved", []) if str(x).strip()]
    parts = []
    if mode:
        parts.append(f"Current reaction selected by the social planner: {mode}.")
    if memories:
        parts.append("Relevant retrieved memories: " + " | ".join(memories[:6]))
    return " ".join(parts)
