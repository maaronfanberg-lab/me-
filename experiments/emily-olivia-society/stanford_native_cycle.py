#!/usr/bin/env python3
"""Thin Emily + Olivia adapter around Stanford HCI genagents.

The cognitive work belongs to Stanford's GenerativeAgent. Local code here only:
- translates our two-person social envelope into Stanford's dialogue shape;
- maintains the original Generative Agents paper's broad daily-plan state;
- calls GenerativeAgent.utterance(), which performs Stanford memory retrieval;
- applies a narrow output-boundary check so model/control scaffolding is never spoken.

There are deliberately no canned replies, conversational-move prompts, topic-word
requirements, paraphrase recipes, or hand-written recovery dialogue in this module.
"""
from __future__ import annotations

import asyncio
import re

import community_cycle_base as _base
from paper_plan_adapter import planning_context

CommunityAgent = _base.CommunityAgent
load_agents = _base.load_agents
observation_text = _base.observation_text
next_community_time_step = _base.next_community_time_step
latest_community_time_step = _base.latest_community_time_step

# Kept for compatibility with the replay verifier/first_exchange import surface.
_is_usable_utterance = _base._is_usable_utterance

_CONTROL_SCAFFOLD = re.compile(
    r"(?:<\|(?:assistant|user|system|endoftext|im_start|im_end)[^>]*\|?>|"
    r"(?im)^\s*(?:SELF|PARTNER|Self-reply|Answer|Example)\s*:|"
    r"\[Fill\s+in\])",
    re.IGNORECASE,
)


def _grounding_words(text: str, limit: int = 6) -> list[str]:
    """Compatibility helper only; not used to steer Stanford generation."""
    words: list[str] = []
    for word in _base._normalize_words(text):
        if word in _base._STOP_WORDS or word in {"emily", "olivia"} or len(word) <= 1:
            continue
        if word not in words:
            words.append(word)
        if len(words) >= max(1, limit):
            break
    return words


def _stanford_dialogue(
    dialogue_history: list[tuple[str, str]] | None,
    other: CommunityAgent,
    inbound: str,
) -> list[list[str]]:
    history = [
        [str(speaker).strip(), str(text).strip()]
        for speaker, text in (dialogue_history or [])
        if str(speaker).strip() and str(text).strip()
    ]
    if not history or history[-1] != [other.name, inbound.strip()]:
        history.append([other.name, inbound.strip()])
    # Stanford's own utterance code turns this dialogue into its retrieval anchor.
    return history[-20:]


def _clean_boundary(text: object) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = _base._unwrap_reply(text).strip()
    if _CONTROL_SCAFFOLD.search(cleaned):
        return ""
    return cleaned


def _agent_time_step(agent: CommunityAgent) -> int:
    latest = 0
    for node in agent.brain.memory_stream.seq_nodes:
        latest = max(
            latest,
            int(getattr(node, "created", 0) or 0),
            int(getattr(node, "last_retrieved", 0) or 0),
        )
    return latest + 1


def choose_action(
    agent: CommunityAgent,
    observation: dict,
    other: CommunityAgent,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> dict:
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    inbound = str(inbox[-1].get("content", "")).strip()
    if not inbound:
        return {"type": "wait", "reason": "empty_message"}

    # Stanford's get_fullname() requires both keys. We keep identity minimal.
    agent.brain.update_scratch({"first_name": agent.name, "last_name": ""})

    dialogue = _stanford_dialogue(dialogue_history, other, inbound)
    plan_context = planning_context(agent, other.name, _agent_time_step(agent))
    context_parts = [
        f"{agent.name} and {other.name} are peers having a private conversation.",
        "Respond as yourself based on your memories, current private state, and the conversation so far.",
    ]
    if plan_context:
        context_parts.append(plan_context)
    context = " ".join(context_parts)

    # This is Stanford's actual interaction path. interaction.utterance() builds the
    # Stanford prompt and retrieves relevant memories before generating the line.
    # The broad plan is cognitive context, never a required conversational move.
    text = _clean_boundary(agent.brain.utterance(dialogue, context=context))

    if not text or not _base._is_usable_utterance(
        text, inbound, agent.name, other.name
    ):
        raise RuntimeError(
            f"{agent.name} returned no grounded natural-language utterance."
        )

    return {
        "type": "message",
        "recipient_id": other.agent_id,
        "content": text,
    }


async def run_one_cycle() -> None:
    """Preserve the existing bounded social cycle, with Stanford choosing speech."""
    from controlled_social_space import ControlledSocialSpace

    agents = load_agents()
    social = ControlledSocialSpace([(a.agent_id, a.name) for a in agents])
    base_time_step = next_community_time_step(agents)

    for offset, agent in enumerate(agents):
        other = next(a for a in agents if a.agent_id != agent.agent_id)
        observation = await social.observe_social_space(agent.agent_id)
        memory = observation_text(agent, observation)
        agent.brain.remember(memory, time_step=base_time_step + offset)
        action = choose_action(agent, observation, other)
        if action["type"] == "message":
            await social.send_message(
                agent.agent_id, int(action["recipient_id"]), str(action["content"])
            )
        agent.brain.save(str(agent.workspace))


if __name__ == "__main__":
    asyncio.run(run_one_cycle())
