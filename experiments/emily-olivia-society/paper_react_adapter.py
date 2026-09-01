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
reaction mode -> let the Stanford-derived act stage generate the spoken action.
It never writes dialogue for the agents.
"""
from __future__ import annotations

import re

from dialogue_attractor import content_tokens
from reflection_hygiene import is_clean_observation_text, is_clean_reflection_text
from retrieval_evidence import serialize_retrieval_evidence

_ORIGINAL_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_MESSAGE_OBSERVATION_PREFIX = re.compile(
    r"^(?:Emily|Olivia) observes a message from (?:Emily|Olivia):\s*",
    re.IGNORECASE,
)
_AMBIENT_NO_MESSAGE = re.compile(
    r"(?:observes\s+that\b[^.]{0,220}\bno\s+(?:new\s+)?addressed\s+messages?\b|"
    r"\bno\s+addressed\s+message\s+(?:is\s+)?pending\b)",
    re.IGNORECASE,
)


def _semantic_tokens(content: str) -> set[str]:
    text = _MESSAGE_OBSERVATION_PREFIX.sub("", str(content or "").strip())
    return set(content_tokens(text))


def _too_similar(candidate: set[str], selected: list[set[str]]) -> bool:
    if len(candidate) < 3:
        return False
    for prior in selected:
        if len(prior) < 3:
            continue
        shared = len(candidate & prior)
        if not shared:
            continue
        union = len(candidate | prior)
        jaccard = shared / max(1, union)
        containment = shared / max(1, min(len(candidate), len(prior)))
        if jaccard >= 0.70 or (min(len(candidate), len(prior)) >= 4 and containment >= 0.85):
            return True
    return False


def _clean_memory_nodes(nodes, *, include_ambient: bool):
    """Return the exact selected Stanford nodes after hygiene/diversity filtering."""
    out = []
    seen_content: set[str] = set()
    selected_tokens: list[set[str]] = []
    for node in nodes or []:
        content = str(getattr(node, "content", "") or "").strip()
        if not content:
            continue
        node_type = getattr(node, "node_type", None)
        if node_type == "reflection" and not is_clean_reflection_text(content):
            continue
        if node_type == "observation" and not is_clean_observation_text(content):
            continue
        if not include_ambient and node_type == "observation" and _AMBIENT_NO_MESSAGE.search(content):
            continue
        if content in seen_content:
            continue
        tokens = _semantic_tokens(content)
        if _too_similar(tokens, selected_tokens):
            continue
        out.append(node)
        seen_content.add(content)
        selected_tokens.append(tokens)
    return out


def _reaction(
    agent,
    other_name: str,
    event: str,
    focal: str,
    time_step: int,
    *,
    include_ambient: bool,
) -> dict:
    retrieved = agent.brain.memory_stream.retrieve([focal], time_step=time_step, n_count=16)
    selected_nodes = _clean_memory_nodes(retrieved.get(focal, []), include_ambient=include_ambient)
    memories = [str(getattr(node, "content", "") or "").strip() for node in selected_nodes]
    reaction = {
        "event": event,
        "source": other_name,
        "mode": f"chat with {other_name}",
        "retrieved": memories,
        "retrieved_evidence": serialize_retrieval_evidence(selected_nodes, time_step),
    }
    agent.brain.update_scratch(
        {
            "current_social_reaction": reaction["mode"],
            "current_social_event": event[:500],
            "reaction_research_source": _ORIGINAL_RESEARCH_COMMIT,
        }
    )
    return reaction


def react_to_observation(agent, other_name: str, inbound: str, time_step: int) -> dict:
    focal = (
        f"{other_name} said to {agent.name}: {inbound}\n"
        f"What memories and thoughts are relevant to how {agent.name} should react?"
    )
    return _reaction(
        agent,
        other_name,
        inbound,
        focal,
        time_step,
        include_ambient=False,
    )


def react_to_presence(agent, other_name: str, time_step: int) -> dict:
    """Select the paper-style reaction when a clean session has no inbox."""
    event = f"{other_name} is present in the private two-person community; no addressed message is pending."
    focal = (
        f"{agent.name} and {other_name} are present together with no addressed message pending. "
        f"What memories and thoughts are relevant to {agent.name}'s current social reaction?"
    )
    return _reaction(
        agent,
        other_name,
        event,
        focal,
        time_step,
        include_ambient=False,
    )


def reaction_context(reaction: dict) -> str:
    """Expose retrieved substance without leaking planner/control wording into speech."""
    memories = [str(x).strip() for x in reaction.get("retrieved", []) if str(x).strip()]
    if not memories:
        return ""
    return "Relevant retrieved memories: " + " | ".join(memories[:6])
