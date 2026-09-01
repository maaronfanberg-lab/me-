#!/usr/bin/env python3
"""Thin Emily + Olivia adapter around Stanford HCI genagents.

The live cognitive chain is intentionally research-shaped:
  observe -> remember -> retrieve -> reflect -> plan/react -> act

Stanford's GenerativeAgent and memory stream remain in charge of memory,
retrieval, reflection, and utterance generation. The original 2023 Generative
Agents planner supplies the planning/reaction structure adapted to this
maze-free two-person social space.

There are deliberately no canned replies, conversational-move prompts, topic-word
requirements, paraphrase recipes, or hand-written recovery dialogue here.
"""
from __future__ import annotations

import asyncio
import re

import community_cycle_base as _base
from paper_plan_adapter import planning_context
from paper_react_adapter import react_to_observation, reaction_context
from paper_reflection_adapter import maybe_reflect

CommunityAgent = _base.CommunityAgent
load_agents = _base.load_agents
observation_text = _base.observation_text
next_community_time_step = _base.next_community_time_step
latest_community_time_step = _base.latest_community_time_step

_CONTROL_SCAFFOLD = re.compile(
    r"(?:<\|(?:assistant|user|system|endoftext|im_start|im_end)[^>]*\|?>|"
    r"^\s*(?:SELF|PARTNER|Self-reply|Partner-reply|Answer|Example)\s*:|"
    r"\[Fill\s+in\])",
    re.IGNORECASE | re.MULTILINE,
)

_MEMORY_SCAFFOLD = re.compile(
    r"(?:<\|(?:assistant|user|system|endoftext|im_start|im_end)[^>]*\|?>|"
    r"(?:^|\n)\s*(?:SELF|PARTNER|Self-reply|Partner-reply|Answer|Example)\s*:|"
    r"\[Fill\s+in\])",
    re.IGNORECASE,
)


def _has_pathological_repetition(text: str) -> bool:
    words = _base._normalize_words(text)
    if len(words) < 8:
        return False
    for width in range(2, min(7, len(words) // 2 + 1)):
        counts: dict[tuple[str, ...], int] = {}
        for index in range(0, len(words) - width + 1):
            gram = tuple(words[index : index + width])
            counts[gram] = counts.get(gram, 0) + 1
        if counts and max(counts.values()) >= 3:
            return True
    if len(words) >= 14:
        counts: dict[str, int] = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1
        if max(counts.values(), default=0) >= max(5, len(words) // 3):
            return True
    return False


def _memory_is_contaminated(content: object) -> bool:
    text = str(content or "").strip()
    return bool(text and (_MEMORY_SCAFFOLD.search(text) or _has_pathological_repetition(text)))


def _is_usable_utterance(text: str, inbound: str = "", agent_name: str = "", other_name: str = "") -> bool:
    """Boundary validation only; it does not dictate Stanford's wording."""
    if not isinstance(text, str) or not text.strip():
        return False
    cleaned = _clean_boundary(text)
    if not cleaned or _has_pathological_repetition(cleaned):
        return False
    return _base._is_usable_utterance(cleaned, inbound, agent_name, other_name)


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


def _stanford_dialogue(dialogue_history, other: CommunityAgent, inbound: str) -> list[list[str]]:
    history = [
        [str(speaker).strip(), str(text).strip()]
        for speaker, text in (dialogue_history or [])
        if str(speaker).strip() and str(text).strip() and not _memory_is_contaminated(text)
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
        latest = max(latest, int(getattr(node, "created", 0) or 0), int(getattr(node, "last_retrieved", 0) or 0))
    return latest + 1


def _utterance_with_clean_retrieval(agent: CommunityAgent, dialogue: list[list[str]], context: str):
    """Run Stanford utterance while excluding only known poisoned memory nodes."""
    memory_stream = agent.brain.memory_stream
    original_retrieve = memory_stream.retrieve

    def clean_retrieve(*args, **kwargs):
        result = original_retrieve(*args, **kwargs)
        if not isinstance(result, dict):
            return result
        cleaned = {}
        for key, nodes in result.items():
            if not isinstance(nodes, list):
                cleaned[key] = nodes
                continue
            cleaned[key] = [node for node in nodes if not _memory_is_contaminated(getattr(node, "content", ""))]
        return cleaned

    memory_stream.retrieve = clean_retrieve
    try:
        return agent.brain.utterance(dialogue, context=context)
    finally:
        memory_stream.retrieve = original_retrieve


def choose_action(agent: CommunityAgent, observation: dict, other: CommunityAgent, dialogue_history=None) -> dict:
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    inbound = str(inbox[-1].get("content", "")).strip()
    if not inbound:
        return {"type": "wait", "reason": "empty_message"}
    if _memory_is_contaminated(inbound):
        raise RuntimeError(f"{agent.name} received contaminated dialogue and refused to feed it back into Stanford.")

    agent.brain.update_scratch({"first_name": agent.name, "last_name": ""})
    time_step = _agent_time_step(agent)

    # Stanford/paper chain: retrieve around the current event, allow accumulated
    # experience to become reflection, then combine broad plan + selected reaction
    # before Stanford interaction turns that private cognition into an action.
    reaction = react_to_observation(agent, other.name, inbound, time_step)
    maybe_reflect(agent, time_step)
    plan_context = planning_context(agent, other.name, time_step)

    dialogue = _stanford_dialogue(dialogue_history, other, inbound)
    context_parts = [
        f"{agent.name} and {other.name} are peers having a private conversation.",
        "They talk like two friends sharing ordinary thoughts, opinions, interests, and experiences.",
        "Respond as yourself based on your memories, current private state, and the conversation so far.",
    ]
    react_context = reaction_context(reaction)
    if react_context:
        context_parts.append(react_context)
    if plan_context:
        context_parts.append(plan_context)
    context = " ".join(context_parts)

    raw_text = _utterance_with_clean_retrieval(agent, dialogue, context)
    text = _clean_boundary(raw_text)

    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        retry_context = (
            f"{agent.name} and {other.name} are two friends continuing the same private conversation. "
            f"{other.name} just said: {inbound} "
            f"{agent.name} stays with that subject and answers from their own memories, opinions, and current state."
        )
        retry_raw = _utterance_with_clean_retrieval(agent, dialogue, retry_context)
        retry_text = _clean_boundary(retry_raw)
        if _is_usable_utterance(retry_text, inbound, agent.name, other.name):
            text = retry_text
        else:
            raw_preview = str(raw_text)[:700].replace("\n", "\\n")
            retry_preview = str(retry_raw)[:700].replace("\n", "\\n")
            clean_preview = str(retry_text)[:700].replace("\n", "\\n")
            raise RuntimeError(
                f"{agent.name} Stanford utterance rejected twice; first={raw_preview!r}; retry={retry_preview!r}; cleaned_retry={clean_preview!r}"
            )

    return {"type": "message", "recipient_id": other.agent_id, "content": text}


async def run_one_cycle() -> None:
    """Observe -> remember -> retrieve/reflect/plan/react -> act."""
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
            await social.send_message(agent.agent_id, int(action["recipient_id"]), str(action["content"]))
        agent.brain.save(str(agent.workspace))


if __name__ == "__main__":
    asyncio.run(run_one_cycle())
