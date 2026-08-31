#!/usr/bin/env python3
"""Thin Emily + Olivia adapter around Stanford HCI genagents.

The cognitive work belongs to Stanford's GenerativeAgent. Local code here only:
- translates our two-person social envelope into Stanford's dialogue shape;
- maintains the original Generative Agents paper's broad daily-plan state;
- periodically reflects after accumulated experience, as in the paper;
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
from paper_reflection_adapter import maybe_reflect

CommunityAgent = _base.CommunityAgent
load_agents = _base.load_agents
observation_text = _base.observation_text
next_community_time_step = _base.next_community_time_step
latest_community_time_step = _base.latest_community_time_step

_CONTROL_SCAFFOLD = re.compile(
    r"(?:<\|(?:assistant|user|system|endoftext|im_start|im_end)[^>]*\|?>|"
    r"^\s*(?:SELF|PARTNER|Self-reply|Answer|Example)\s*:|"
    r"\[Fill\s+in\])",
    re.IGNORECASE | re.MULTILINE,
)


def _is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Validate the output boundary without steering Stanford's wording.

    The legacy validator required a reply to repeat a content word from the
    incoming message. That was a local conversational heuristic, not part of
    Stanford's architecture, and rejected natural indirect answers. Keep the
    safety/format/role checks but let Stanford retrieval and cognition decide
    what the response actually says.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    cleaned = _clean_boundary(text)
    if not cleaned:
        return False
    # Passing an empty inbound intentionally disables the old lexical-overlap
    # and greeting-shape steering while retaining junk, role, and size checks.
    return _base._is_usable_utterance(cleaned, "", agent_name, other_name)


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

    agent.brain.update_scratch({"first_name": agent.name, "last_name": ""})
    time_step = _agent_time_step(agent)

    # Paper order: accumulated observations can produce reflection before the
    # next act. Reflections become memories, so Stanford retrieval can use them
    # naturally when producing the action rather than us scripting the reply.
    maybe_reflect(agent, time_step)

    dialogue = _stanford_dialogue(dialogue_history, other, inbound)
    plan_context = planning_context(agent, other.name, time_step)
    context_parts = [
        f"{agent.name} and {other.name} are peers having a private conversation.",
        "Respond as yourself based on your memories, current private state, and the conversation so far.",
    ]
    if plan_context:
        context_parts.append(plan_context)
    context = " ".join(context_parts)

    text = _clean_boundary(agent.brain.utterance(dialogue, context=context))

    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        raise RuntimeError(
            f"{agent.name} returned no natural-language utterance that passed the output boundary."
        )

    return {
        "type": "message",
        "recipient_id": other.agent_id,
        "content": text,
    }


async def run_one_cycle() -> None:
    """Preserve the bounded social envelope; Stanford drives cognition/speech."""
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
