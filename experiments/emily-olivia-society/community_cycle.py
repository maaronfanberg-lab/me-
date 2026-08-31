#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from bitnet_server import request_chat

HERE = Path(__file__).resolve().parent
STANFORD = HERE / "vendor" / "stanford-genagents"
WORKSPACES = HERE / "workspaces"
MAX_UTTERANCE_CHARS = 12_000
MAX_UTTERANCE_WORDS = 52
_TEMPLATE_JUNK = re.compile(
    r"(?:\{?\s*[\"']?utterance[\"']?\s*[:=]|\{?\s*fill\s+in\s*>|\[?\s*input\s*\]?:|return\s+only\s+the\s+words\s+you\s+would\s+say|end\s+of\s+dialogue\s+so\s+far)",
    re.IGNORECASE,
)
_GENERIC_ASSISTANT_JUNK = re.compile(
    r"(?:\bhow can i (?:assist|help)(?: you)?(?: today)?\b|"
    r"\bi(?:'m| am) here to (?:assist|help)\b|"
    r"\bi can (?:assist|help) you\b|"
    r"\bwhat can i (?:assist|help) you with\b|"
    r"\bwhat can i do for you\b|"
    r"\bplease provide (?:me )?(?:with )?(?:the )?(?:specific )?(?:details|information)\b|"
    r"\bassist with any (?:information|support)\b|"
    r"\bsupport you need\b|"
    r"\bas an ai\b)",
    re.IGNORECASE,
)
_SPEAKER_LABEL = re.compile(r"(?im)^\s*(Emily|Olivia|User|Assistant|System)\s*:")
_ACKNOWLEDGEMENT = re.compile(
    r"\b(?:same here|me too|i agree|that makes sense|i get that|i understand|sounds good|fair enough|absolutely|definitely|exactly)\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "about", "am", "an", "and", "are", "as", "at", "be", "been", "but",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "here", "hers", "him", "his", "i", "if", "in", "is", "it",
    "its", "me", "might", "my", "not", "of", "on", "or", "our", "ours", "she",
    "should", "so", "that", "the", "their", "theirs", "them", "then", "there",
    "they", "this", "to", "too", "us", "very", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you", "your",
    "yours", "just", "really", "than",
}
_GREETING_SAFE_WORDS = {
    "hello", "hi", "hey", "morning", "afternoon", "evening", "emily", "olivia",
    "good", "great", "nice", "glad", "hear", "hearing", "see", "seeing", "meet",
    "meeting", "back", "doing", "going", "well", "today", "thanks", "thank", "how",
    "up", "fine", "okay", "ok", "likewise", "welcome",
}


@dataclass
class CommunityAgent:
    agent_id: int
    name: str
    workspace: Path
    brain: object


def load_specs() -> list[dict]:
    raw = json.loads((HERE / "agents.json").read_text(encoding="utf-8"))
    specs = raw.get("agents", [])
    if len(specs) != 2:
        raise RuntimeError("Emily + Olivia Community requires exactly two agents.")
    ids = [int(spec["id"]) for spec in specs]
    names = [str(spec["profile"]["name"]).strip() for spec in specs]
    if len(set(ids)) != 2 or any(agent_id <= 0 for agent_id in ids):
        raise RuntimeError("Community agent IDs must be two distinct positive integers.")
    if len(set(names)) != 2 or any(not name for name in names):
        raise RuntimeError("Community agent names must be two distinct non-empty strings.")
    return specs


def ensure_stanford_importable() -> None:
    if not STANFORD.exists():
        raise SystemExit("Run ./bootstrap_upstreams.sh first.")
    sys.path.insert(0, str(STANFORD))


def load_agents() -> list[CommunityAgent]:
    ensure_stanford_importable()
    from genagents.genagents import GenerativeAgent

    out: list[CommunityAgent] = []
    for spec in load_specs():
        agent_id = int(spec["id"])
        name = str(spec["profile"]["name"]).strip()
        workspace = WORKSPACES / name.lower()
        if not (workspace / "scratch.json").exists():
            raise SystemExit("Run .venv-stanford/bin/python init_cognition.py first.")
        out.append(
            CommunityAgent(
                agent_id=agent_id,
                name=name,
                workspace=workspace,
                brain=GenerativeAgent(str(workspace)),
            )
        )
    return out


def latest_community_time_step(agents: list[CommunityAgent]) -> int:
    latest = 0
    for agent in agents:
        for node in agent.brain.memory_stream.seq_nodes:
            latest = max(
                latest,
                int(getattr(node, "created", 0) or 0),
                int(getattr(node, "last_retrieved", 0) or 0),
            )
    return latest


def next_community_time_step(agents: list[CommunityAgent]) -> int:
    return latest_community_time_step(agents) + 1


def observation_text(agent: CommunityAgent, observation: dict) -> str:
    inbox = observation.get("inbox", [])
    if not inbox:
        return f"{agent.name} observes that the community contains Emily and Olivia and there are no new addressed messages."
    latest = inbox[-1]
    return f"{agent.name} observes a message from {latest['from_name']}: {latest['content']}"


def _normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in _normalize_words(text)
        if word not in _STOP_WORDS and word not in {"emily", "olivia"} and len(word) > 1
    }


def _is_greeting_only(text: str) -> bool:
    words = _normalize_words(text)
    if not words or len(words) > 14:
        return False
    meaningful = [word for word in words if word not in _STOP_WORDS]
    if not meaningful:
        return False
    has_greeting = any(word in {"hello", "hi", "hey", "morning", "afternoon", "evening"} for word in words)
    return has_greeting and all(word in _GREETING_SAFE_WORDS for word in meaningful)


def _is_usable_utterance(text: str, inbound: str = "") -> bool:
    if not isinstance(text, str):
        return False
    cleaned = text.strip()
    if not cleaned or cleaned.startswith("GENERATION ERROR:") or len(cleaned) > MAX_UTTERANCE_CHARS:
        return False
    if _TEMPLATE_JUNK.search(cleaned) or _GENERIC_ASSISTANT_JUNK.search(cleaned):
        return False
    if len(_SPEAKER_LABEL.findall(cleaned)) > 1:
        return False
    output_words = _normalize_words(cleaned)
    if sum(ch.isalnum() for ch in cleaned) < 3 or len(output_words) < 2 or len(output_words) > MAX_UTTERANCE_WORDS:
        return False

    if inbound:
        input_words = _normalize_words(inbound)

        if _is_greeting_only(inbound):
            meaningful_output = [word for word in output_words if word not in _STOP_WORDS]
            has_greeting = any(
                word in {"hello", "hi", "hey", "morning", "afternoon", "evening"}
                for word in output_words
            )
            if not has_greeting:
                return False
            if any(word not in _GREETING_SAFE_WORDS for word in meaningful_output):
                return False
        else:
            input_content = _content_words(inbound)
            output_content = _content_words(cleaned)
            if input_content and not (input_content & output_content):
                if not (_ACKNOWLEDGEMENT.search(cleaned) and len(output_words) <= 14):
                    return False

        if len(input_words) >= 5 and len(output_words) >= 5:
            common = len(set(output_words) & set(input_words))
            overlap = common / max(1, len(set(output_words)))
            if overlap > 0.85 and len(output_words) >= len(input_words):
                return False
    return True


def _chat_bitnet(agent: CommunityAgent, other: CommunityAgent, inbound: str, max_tokens: int) -> str:
    """Use llama-server chat with strict grounding to the addressed message."""
    if _is_greeting_only(inbound):
        grounding = (
            "The message is only a greeting. Return a short greeting or ordinary greeting-small-talk response. "
            "Do not introduce a pet, event, task, place, backstory, or unrelated topic."
        )
    else:
        grounding = (
            "Stay grounded in the exact message. Carry forward at least one meaningful idea or word from it. "
            "Do not invent a new pet, event, person, place, shared history, or unrelated scenario."
        )
    system = (
        f"You are {agent.name}, one participant in a private two-person conversation with {other.name}. "
        "You are not a customer-service assistant, support agent, or generic helper. "
        f"The latest message was written by {other.name}; answer that exact message. {grounding} "
        "Use one or two natural sentences. Never offer generic assistance, ask what help is needed, repeat the prompt, "
        "repeat role labels, or reproduce the other person's whole message."
    )
    user = f"{other.name} just said: {inbound}\n\nReply directly to {other.name}."
    return request_chat(system, user, max_tokens, 0.45)


def _direct_bitnet_reply(agent: CommunityAgent, other: CommunityAgent, inbound: str) -> str:
    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    attempts: list[str] = []
    for _ in range(3):
        text = _chat_bitnet(agent, other, inbound, max_tokens).strip()
        attempts.append(text)
        if _is_usable_utterance(text, inbound):
            return text
    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(f"BitNet returned unusable dialogue after 3 grounded attempts: {previews}")


def choose_action(agent: CommunityAgent, observation: dict, other: CommunityAgent) -> dict:
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    latest = inbox[-1]
    inbound = str(latest["content"])
    dialogue = [[latest["from_name"], inbound]]
    response = agent.brain.utterance(
        dialogue,
        context=(
            f"You are {agent.name}. You are in a two-person community with {other.name}. "
            "Respond naturally and specifically to the addressed message without inventing a different scenario."
        ),
    )
    text = str(response).strip()
    if not _is_usable_utterance(text, inbound):
        text = _direct_bitnet_reply(agent, other, inbound)
    if not _is_usable_utterance(text, inbound):
        raise RuntimeError(f"{agent.name} returned no usable grounded natural-language utterance.")
    return {"type": "message", "recipient_id": other.agent_id, "content": text}


async def run_one_cycle() -> None:
    from controlled_social_space import ControlledSocialSpace

    agents = load_agents()
    pairs = [(agent.agent_id, agent.name) for agent in agents]
    social = ControlledSocialSpace(pairs)
    base_time_step = next_community_time_step(agents)
    cycle_log: list[dict] = []

    for offset, agent in enumerate(agents):
        other = next(a for a in agents if a.agent_id != agent.agent_id)
        time_step = base_time_step + offset
        observation = await social.observe_social_space(agent.agent_id)
        memory = observation_text(agent, observation)
        agent.brain.remember(memory, time_step=time_step)
        query = f"Current interaction with {other.name}"
        retrieved = agent.brain.memory_stream.retrieve([query], time_step=time_step, n_count=12)
        relevant = [node.content for node in retrieved.get(query, [])]
        action = choose_action(agent, observation, other)
        action_result = None
        if action["type"] == "message":
            action_result = await social.send_message(
                agent.agent_id,
                int(action["recipient_id"]),
                str(action["content"]),
            )
            if not action_result.get("success"):
                raise RuntimeError(f"Message delivery failed for {agent.name}: {action_result!r}")
        agent.brain.save(str(agent.workspace))
        cycle_log.append(
            {
                "agent": agent.name,
                "time_step": time_step,
                "observation": observation,
                "retrieved_memories": relevant,
                "action": action,
                "action_result": action_result,
            }
        )

    print(json.dumps({"start_time_step": base_time_step, "cycles": cycle_log}, indent=2))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded Emily + Olivia community cycle.")
    parser.add_argument("--one-cycle", action="store_true", help="Permit exactly one bounded cycle per agent.")
    args = parser.parse_args()
    if not args.one_cycle:
        raise SystemExit("Refusing to start automatically. Use --one-cycle to permit exactly one bounded cycle.")
    await run_one_cycle()


if __name__ == "__main__":
    asyncio.run(main())
