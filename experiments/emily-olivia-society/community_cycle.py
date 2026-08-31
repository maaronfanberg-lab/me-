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
_SPEAKER_LABEL = re.compile(r"(?im)^\s*(Emily|Olivia|User|Assistant|System)\s*:")


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


def _is_usable_utterance(text: str, inbound: str = "") -> bool:
    cleaned = text.strip()
    if not cleaned or cleaned.startswith("GENERATION ERROR:") or len(cleaned) > MAX_UTTERANCE_CHARS:
        return False
    if _TEMPLATE_JUNK.search(cleaned):
        return False
    if len(_SPEAKER_LABEL.findall(cleaned)) > 1:
        return False
    if sum(ch.isalnum() for ch in cleaned) < 3:
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
    """Use llama-server's chat endpoint so the GGUF's own template serializes dialogue."""
    system = (
        f"You are {agent.name}. You are speaking privately with {other.name}. "
        "Reply naturally and briefly to the other person. Do not repeat the prompt, "
        "instructions, role labels, or the other person's whole message."
    )
    return request_chat(system, inbound, max_tokens, 0.6)


def _direct_bitnet_reply(agent: CommunityAgent, other: CommunityAgent, inbound: str) -> str:
    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    text = _chat_bitnet(agent, other, inbound, max_tokens)
    if not _is_usable_utterance(text, inbound):
        raise RuntimeError(f"BitNet returned template-like, echoed, or unusable dialogue: {text[:240]!r}")
    return text


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
            "Respond naturally to the addressed message."
        ),
    )
    text = str(response).strip()
    if not _is_usable_utterance(text, inbound):
        text = _direct_bitnet_reply(agent, other, inbound)
    if not _is_usable_utterance(text, inbound):
        raise RuntimeError(f"{agent.name} returned no usable natural-language utterance.")
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
