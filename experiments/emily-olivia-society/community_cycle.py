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
_TEMPLATE_JUNK = re.compile(
    r"(?:\{?\s*[\"']?utterance[\"']?\s*[:=]|\{?\s*fill\s+in\s*>|\[?\s*input\s*\]?:|return\s+only\s+the\s+words\s+you\s+would\s+say|end\s+of\s+dialogue\s+so\s+far)",
    re.IGNORECASE,
)
_ASSISTANTY_JUNK = re.compile(
    r"(?:how\s+can\s+i\s+(?:help|assist)\s+you|"
    r"if\s+you\s+have\s+any\s+(?:other\s+)?questions|"
    r"if\s+you\s+need\s+(?:any\s+)?(?:further\s+)?assistance|"
    r"feel\s+free\s+to\s+ask|"
    r"(?:i\s+am|i'm)\s+(?:here|happy)\s+to\s+(?:help|assist)|"
    r"i(?:'m|\s+am)\s+sorry[^.]{0,80}(?:can(?:not|'t)|unable)\s+(?:assist|help|fulfill)|"
    r"i\s+can(?:not|'t)\s+(?:assist|help|fulfill)(?:\s+with)?\s+(?:this|that|your)\s+request|"
    r"(?:our|the)\s+guidelines|"
    r"does\s+not\s+align\s+with\s+(?:our\s+)?(?:guidelines|policies)|"
    r"(?:i\s+am|i'm)\s+(?:currently\s+)?in\s+a\s+(?:two-person\s+)?community|"
    r"asking\s+about\s+my\s+last\s+update)",
    re.IGNORECASE,
)
_SPEAKER_LABEL = re.compile(r"(?im)^\s*(Emily|Olivia|User|Assistant|System)\s*:")
_REPLY_WRAPPER = re.compile(r"^\s*(?:<reply>\s*)?(.*?)(?:\s*</reply>)?\s*$", re.IGNORECASE | re.DOTALL)


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


def _unwrap_reply(text: str) -> str:
    match = _REPLY_WRAPPER.match(text.strip())
    return match.group(1).strip() if match else text.strip()


def _is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    cleaned = _unwrap_reply(text)
    if not cleaned or cleaned.startswith("GENERATION ERROR:") or len(cleaned) > MAX_UTTERANCE_CHARS:
        return False
    if _TEMPLATE_JUNK.search(cleaned) or _ASSISTANTY_JUNK.search(cleaned):
        return False
    if len(_SPEAKER_LABEL.findall(cleaned)) > 1:
        return False
    if sum(ch.isalnum() for ch in cleaned) < 3:
        return False
    if agent_name and other_name and re.search(
        rf"\b(?:i\s+am|i'm)\s+{re.escape(other_name)}\b",
        cleaned,
        re.IGNORECASE,
    ):
        return False
    if inbound:
        output_words = _normalize_words(cleaned)
        input_words = _normalize_words(inbound)
        if len(input_words) >= 5 and len(output_words) >= 5:
            common = len(set(output_words) & set(input_words))
            overlap = common / max(1, len(set(output_words)))
            if overlap > 0.85 and len(output_words) >= len(input_words):
                return False
    return True


def _chat_bitnet(agent: CommunityAgent, other: CommunityAgent, inbound: str, max_tokens: int) -> str:
    """Project neutral dialogue state into the current speaker's egocentric view."""
    system = (
        "This is a private peer-to-peer conversation, not a user-assistant support exchange. "
        f"CURRENT_SPEAKER={agent.name}. OTHER_PERSON={other.name}. "
        f"You are {agent.name}; never claim to be {other.name}. "
        "Stay in first-person perspective as CURRENT_SPEAKER. Do not offer customer-service help, "
        "mention policies or guidelines, describe the conversation system, or invent a fictional-character framing. "
        "Respond to OTHER_PERSON's latest words with one natural conversational turn. "
        "Output exactly <reply>your words</reply> and nothing else."
    )
    user = (
        f"OTHER_PERSON={other.name}\n"
        f"OTHER_LAST_MESSAGE={inbound}\n"
        f"CURRENT_SPEAKER={agent.name}\n"
        f"Write {agent.name}'s direct reply now."
    )
    return request_chat(system, user, max_tokens, 0.45)


def _direct_bitnet_reply(agent: CommunityAgent, other: CommunityAgent, inbound: str) -> str:
    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    attempts: list[str] = []
    for _ in range(4):
        text = _unwrap_reply(_chat_bitnet(agent, other, inbound, max_tokens))
        attempts.append(text)
        if _is_usable_utterance(text, inbound, agent.name, other.name):
            return text
    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(f"BitNet returned role-drifted or unusable dialogue after 4 grounded attempts: {previews}")


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
            f"CURRENT_SPEAKER={agent.name}. OTHER_PERSON={other.name}. "
            f"The latest message was written by {other.name}. "
            "This is peer conversation, not customer support. Stay yourself, answer the latest message directly, "
            "and never mirror the other person's identity or describe the conversation system."
        ),
    )
    text = _unwrap_reply(str(response))
    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        text = _direct_bitnet_reply(agent, other, inbound)
    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        raise RuntimeError(f"{agent.name} returned no grounded natural-language utterance.")
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
