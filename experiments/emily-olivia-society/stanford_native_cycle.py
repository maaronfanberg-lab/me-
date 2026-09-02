#!/usr/bin/env python3
"""Emily + Olivia Stanford-chain adapter.

The live cognitive chain is intentionally research-shaped:
  observe -> remember -> retrieve -> reflect -> plan/react -> act

Stanford HCI genagents owns persistent memory, retrieval, and reflection. The
original 2023 Generative Agents source supplies the map-free planning/reaction
structure and the spoken next-line act boundary. There are deliberately no
canned replies, conversational-move prompts, topic-word requirements,
paraphrase recipes, or hand-written recovery dialogue here.
"""
from __future__ import annotations

import asyncio
import re

import community_cycle_base as _base
from dialogue_attractor import candidate_dialogue_blocker
from paper_act_adapter import (
    generate_spoken_action,
    is_usable_spoken_action,
    research_source as act_research_source,
)
from paper_plan_adapter import planning_context
from paper_react_adapter import react_to_observation, react_to_presence, reaction_context
from paper_reflection_adapter import maybe_reflect

CommunityAgent = _base.CommunityAgent
load_agents = _base.load_agents
observation_text = _base.observation_text
next_community_time_step = _base.next_community_time_step
latest_community_time_step = _base.latest_community_time_step

_MAX_ATTRACTOR_RESAMPLES = 1
_INNER_EXHAUSTION_MARKER = "paper-derived Stanford act produced no usable spoken line after"
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
_HARD_DIALOGUE_BLOCKERS = {
    "empty_candidate",
    "template_blank_residue",
    "unfinished_cutoff",
    "role_swapped_personal_fact",
    "unsupported_concrete_biography",
}


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


def _clean_boundary(text: object, agent_name: str = "") -> str:
    if not isinstance(text, str):
        return ""
    cleaned = _base._unwrap_reply(text).strip()
    if agent_name:
        self_prefix = re.compile(rf"^\s*{re.escape(agent_name)}\s*:\s*", re.IGNORECASE)
        match = self_prefix.match(cleaned)
        if match:
            cleaned = cleaned[match.end() :].strip()
            if self_prefix.match(cleaned):
                return ""
    if _CONTROL_SCAFFOLD.search(cleaned):
        return ""
    return cleaned


def _is_usable_utterance(text: str, inbound: str = "", agent_name: str = "", other_name: str = "") -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    cleaned = _clean_boundary(text, agent_name)
    if not cleaned or _has_pathological_repetition(cleaned):
        return False
    return is_usable_spoken_action(cleaned, inbound, agent_name, other_name)


def _grounding_words(text: str, limit: int = 6) -> list[str]:
    words: list[str] = []
    for word in _base._normalize_words(text):
        if word in _base._STOP_WORDS or word in {"emily", "olivia"} or len(word) <= 1:
            continue
        if word not in words:
            words.append(word)
        if len(words) >= max(1, limit):
            break
    return words


def _cognitive_context(reaction: dict, plan_context: str) -> str:
    """Expose retrieved substance plus the existing private Stanford plan."""
    parts = [reaction_context(reaction).strip(), str(plan_context or "").strip()]
    return "\n".join(part for part in parts if part)


def _is_exact_same_speaker_repeat(text: str, dialogue_history, agent_name: str) -> bool:
    """Reject only literal same-speaker loops, not ordinary topical repetition.

    Stanford's iterative chat permits natural reuse of greetings, fragments, and
    topics. What it does not require us to preserve is a local sampler emitting
    the exact same line for the same persona over and over. Keep this check
    deliberately narrow so it cannot become another stylistic dialogue filter.
    """
    candidate = tuple(_base._normalize_words(str(text or "")))
    if not candidate:
        return False
    for speaker, prior in reversed(list(dialogue_history or [])[-12:]):
        if str(speaker).strip() != agent_name:
            continue
        if tuple(_base._normalize_words(str(prior))) == candidate:
            return True
    return False


def _generate_non_attractor_spoken_action(
    agent: CommunityAgent,
    other: CommunityAgent,
    dialogue_history,
    inbound: str,
    cognitive_context: str,
) -> str:
    rejected: list[str] = []
    for _attempt in range(_MAX_ATTRACTOR_RESAMPLES):
        try:
            text = generate_spoken_action(
                agent,
                other,
                dialogue_history=dialogue_history,
                inbound=inbound,
                cognitive_context=cognitive_context,
            )
        except RuntimeError as exc:
            if _INNER_EXHAUSTION_MARKER not in str(exc):
                raise
            rejected.append(f"inner_sampler_exhaustion: {str(exc)[:220]}")
            continue

        if _is_exact_same_speaker_repeat(text, dialogue_history, agent.name):
            rejected.append(f"exact_same_speaker_repeat: {text}")
            continue

        blocker = candidate_dialogue_blocker(
            text,
            dialogue_history,
            inbound=inbound,
            cognitive_context=cognitive_context,
            agent_name=agent.name,
        )
        # Stanford's original iterative chat lets ordinary conversational
        # repetition, fragments, greetings, and topic reuse pass through. Keep
        # only boundary/integrity blockers here; stylistic refractory signals
        # remain useful for diagnostics but must not stop the live toy.
        if blocker not in _HARD_DIALOGUE_BLOCKERS:
            return text
        rejected.append(f"{blocker}: {text}")
    previews = " | ".join(repr(item[:240]) for item in rejected)
    raise RuntimeError(
        f"{agent.name} repeatedly hit structural dialogue blockers after "
        f"{_MAX_ATTRACTOR_RESAMPLES} paper-derived resamples: {previews}"
    )


def choose_action(agent: CommunityAgent, observation: dict, other: CommunityAgent, dialogue_history=None) -> dict:
    """Complete retrieve/reflect/plan/react and emit one paper-derived spoken act."""
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    inbound = str(inbox[-1].get("content", "")).strip()
    if not inbound:
        return {"type": "wait", "reason": "empty_message"}
    if _memory_is_contaminated(inbound):
        raise RuntimeError(f"{agent.name} received contaminated dialogue and refused to feed it back into Stanford.")

    agent.brain.update_scratch({"first_name": agent.name, "last_name": ""})
    time_step = max(
        int(getattr(node, "created", 0) or 0)
        for node in (list(agent.brain.memory_stream.seq_nodes) or [type("N", (), {"created": 0})()])
    ) + 1

    reaction = react_to_observation(agent, other.name, inbound, time_step)
    reflected = maybe_reflect(agent, time_step)
    plan_context = planning_context(agent, other.name, time_step)
    cognitive_context = _cognitive_context(reaction, plan_context)
    text = _generate_non_attractor_spoken_action(
        agent,
        other,
        dialogue_history=dialogue_history,
        inbound=inbound,
        cognitive_context=cognitive_context,
    )
    text = _clean_boundary(text, agent.name)
    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        raise RuntimeError(f"{agent.name} paper-derived Stanford act failed the dialogue boundary.")

    return {
        "type": "message",
        "recipient_id": other.agent_id,
        "content": text,
        "retrieved_memories": list(reaction.get("retrieved", [])),
        "retrieved_memory_evidence": list(reaction.get("retrieved_evidence", [])),
        "cognition": {
            "reaction": reaction.get("mode"),
            "reflected": reflected,
            "plan_present": bool(plan_context),
            "act_research_source": act_research_source(),
        },
    }


def choose_opening_action(
    agent: CommunityAgent,
    observation: dict,
    other: CommunityAgent,
    time_step: int,
    dialogue_history=None,
) -> dict:
    """Run the full chain for a clean session and autonomously create its first act."""
    inbox = observation.get("inbox", [])
    if inbox:
        raise RuntimeError("Autonomous opening requires a clean inbox.")

    memory = observation_text(agent, observation)
    agent.brain.remember(memory, time_step=time_step)

    reaction = react_to_presence(agent, other.name, time_step)
    reflected = maybe_reflect(agent, time_step)
    plan_context = planning_context(agent, other.name, time_step)
    cognitive_context = _cognitive_context(reaction, plan_context)
    text = _generate_non_attractor_spoken_action(
        agent,
        other,
        dialogue_history=dialogue_history,
        inbound="",
        cognitive_context=cognitive_context,
    )
    text = _clean_boundary(text, agent.name)
    if not _is_usable_utterance(text, "", agent.name, other.name):
        raise RuntimeError(f"{agent.name} autonomous paper-derived opening failed the dialogue boundary.")

    return {
        "type": "message",
        "recipient_id": other.agent_id,
        "content": text,
        "observation_memory": memory,
        "retrieved_memories": list(reaction.get("retrieved", [])),
        "retrieved_memory_evidence": list(reaction.get("retrieved_evidence", [])),
        "cognition": {
            "reaction": reaction.get("mode"),
            "reflected": reflected,
            "plan_present": bool(plan_context),
            "act_research_source": act_research_source(),
        },
    }


async def run_one_cycle() -> None:
    from controlled_social_space import ControlledSocialSpace

    agents = load_agents()
    social = ControlledSocialSpace([(a.agent_id, a.name) for a in agents])
    base_time_step = next_community_time_step(agents)

    for offset, agent in enumerate(agents):
        other = next(a for a in agents if a.agent_id != agent.agent_id)
        observation = await social.observe_social_space(agent.agent_id)
        if not observation.get("inbox") and offset == 0:
            action = choose_opening_action(agent, observation, other, base_time_step + offset)
        else:
            memory = observation_text(agent, observation)
            agent.brain.remember(memory, time_step=base_time_step + offset)
            action = choose_action(agent, observation, other)
        if action["type"] == "message":
            await social.send_message(agent.agent_id, int(action["recipient_id"]), str(action["content"]))
        agent.brain.save(str(agent.workspace))


if __name__ == "__main__":
    asyncio.run(run_one_cycle())