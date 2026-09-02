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
_GREETING_ONLY = re.compile(
    r"^\s*(?:(?:oh|well)[,! ]+)?(?:good\s+(?:morning|afternoon|evening)|hi|hello|hey)"
    r"(?:\s+(?:there|again|emily|olivia))?[!,. ]*$",
    re.IGNORECASE,
)
_ACK_ONLY = re.compile(
    r"^\s*(?:yes|yeah|yep|okay|ok|sure|right|exactly|thanks|thank\s+you|same\s+here)"
    r"[!,. ]*$",
    re.IGNORECASE,
)


def _observation_payload(content: str) -> str:
    return _MESSAGE_OBSERVATION_PREFIX.sub("", str(content or "").strip()).strip()


def _semantic_tokens(content: str) -> set[str]:
    return set(content_tokens(_observation_payload(content)))


def _is_low_information_social_memory(node) -> bool:
    """Identify social phatic observations without deleting them from memory.

    These memories remain available as a fail-open fallback. They are simply
    ranked behind substantive observations and reflections so a fresh greeting
    cannot monopolize Stanford retrieval forever.
    """
    if getattr(node, "node_type", None) != "observation":
        return False
    text = _observation_payload(str(getattr(node, "content", "") or ""))
    if not text:
        return True
    return bool(_GREETING_ONLY.match(text) or _ACK_ONLY.match(text))


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
    """Return selected Stanford nodes with substantive material preferred.

    Hygiene and semantic diversity remain hard selection criteria. Phatic social
    memories are soft-ranked rather than rejected, preserving liveness when the
    memory stream genuinely contains nothing richer yet.
    """
    substantive = []
    phatic = []
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
        seen_content.add(content)
        selected_tokens.append(tokens)
        if _is_low_information_social_memory(node):
            phatic.append(node)
        else:
            substantive.append(node)

    return substantive + phatic


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

    # Alex is a direct side-channel, not a third member of Emily + Olivia's
    # autonomous dialogue. A live replay showed Olivia answering Alex with
    # "Hello, Emily" because peer memories were retrieved into the Alex turn.
    # Keep the Stanford retrieval stage, but scope external-turn retrieval to
    # memories that actually mention that external interlocutor. With no such
    # memory yet, the current Alex message itself remains the grounding event.
    external_turn = str(other_name or "").strip().casefold() not in {"emily", "olivia"}
    if external_turn:
        source_token = str(other_name or "").strip().casefold()
        selected_nodes = [
            node for node in selected_nodes
            if source_token and source_token in str(getattr(node, "content", "") or "").casefold()
        ]

    memories = [str(getattr(node, "content", "") or "").strip() for node in selected_nodes]
    reaction = {
        "event": event,
        "source": other_name,
        "mode": f"chat with {other_name}",
        "retrieved": memories,
        "retrieved_evidence": serialize_retrieval_evidence(selected_nodes, time_step),
    }

    # Do not persist an external speaker's verbatim event into the pair's scratch
    # state. The direct reply still uses the full current event and Stanford act,
    # but Emily/Olivia peer cognition resumes with its own social state intact.
    if not external_turn:
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
        f"What memories, reflections, and unfinished conversational substance are relevant "
        f"to how {agent.name} should react now, beyond merely repeating the latest social greeting?"
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
        f"What memories, reflections, and ongoing interests are relevant to {agent.name}'s current social reaction?"
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
    """Carry Stanford's current-event grounding plus retrieved substance into act.

    ``agent_chat_v2`` supplies each utterance generator with the personas' actual
    current actions before asking what to say next. In this map-free adapter the
    selected social event is that current-action equivalent, so it must not be
    dropped merely because retrieval returned no older memories.
    """
    parts: list[str] = []
    event = str(reaction.get("event", "") or "").strip()
    if event:
        parts.append("Current observed social event: " + event)
    memories = [str(x).strip() for x in reaction.get("retrieved", []) if str(x).strip()]
    if memories:
        parts.append("Relevant retrieved memories: " + " | ".join(memories[:6]))
    return "\n".join(parts)
