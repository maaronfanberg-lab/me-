#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
STANFORD = HERE / "vendor" / "stanford-genagents"
WORKSPACES = HERE / "workspaces"
MAX_UTTERANCE_CHARS = 12_000
MAX_UTTERANCE_WORDS = 52
MAX_ECP_TURNS = 10

_TEMPLATE_JUNK = re.compile(
    r"(?:\{?\s*[\"']?utterance[\"']?\s*[:=]|\{?\s*fill\s+in\s*>|\[?\s*input\s*\]?:|"
    r"(?im:^\s*(?:answer|example|self-reply|self|partner)\s*:)|"
    r"<\|(?:assistant|user|system|endoftext)?\|?>?|<\||"
    r"return\s+only\s+the\s+words\s+you\s+would\s+say|end\s+of\s+dialogue\s+so\s+far)",
    re.IGNORECASE,
)
_ASSISTANTY_JUNK = re.compile(
    r"(?:how\s+can\s+i\s+(?:help|assist)\s+you|"
    r"if\s+you\s+have\s+any\s+(?:other\s+)?questions|"
    r"if\s+you\s+need\s+(?:any\s+)?(?:further\s+)?assistance|"
    r"feel\s+free\s+to\s+ask|"
    r"(?:i\s+am|i'm)\s+(?:here|happy)\s+to\s+(?:help|assist|listen)|"
    r"i(?:'m|\s+am)\s+sorry[^.]{0,80}(?:can(?:not|'t)|unable)\s+(?:assist|help|fulfill)|"
    r"i\s+can(?:not|'t)\s+(?:assist|help|fulfill)(?:\s+with)?\s+(?:this|that|your)\s+request|"
    r"(?:our|the)\s+guidelines|"
    r"does\s+not\s+align\s+with\s+(?:our\s+)?(?:guidelines|policies)|"
    r"(?:i\s+am|i'm)\s+(?:currently\s+)?in\s+a\s+(?:two-person\s+)?community|"
    r"asking\s+about\s+my\s+last\s+update|"
    r"as\s+an\s+ai|"
    r"what\s+can\s+i\s+(?:help|assist)\s+you\s+with|"
    r"what\s+can\s+i\s+do\s+for\s+you|"
    r"please\s+provide(?:\s+me)?(?:\s+with)?(?:\s+the)?(?:\s+specific)?\s+(?:details|information)|"
    r"support\s+you\s+need)",
    re.IGNORECASE,
)
_SPEAKER_LABEL = re.compile(r"(?im)^\s*(Emily|Olivia|User|Assistant|System|SELF|PARTNER)\s*:")
_REPLY_WRAPPER = re.compile(
    r"^\s*(?:<reply>\s*)?(.*?)(?:\s*</reply>)?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ACKNOWLEDGEMENT = re.compile(
    r"\b(?:same here|me too|i agree|that makes sense|i get that|i understand|"
    r"sounds good|fair enough|absolutely|definitely|exactly)\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "about", "am", "an", "and", "are", "as", "at", "be", "been", "but",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "here", "hers", "him", "his", "i", "if", "in", "is", "it",
    "its", "me", "might", "my", "not", "of", "on", "or", "our", "ours", "she",
    "should", "so", "that", "the", "their", "theirs", "them", "then", "there",
    "they", "this", "to", "too", "us", "very", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "yours", "just", "really", "than",
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
        return (
            f"{agent.name} observes that the community contains Emily and Olivia "
            "and there are no new addressed messages."
        )
    latest = inbox[-1]
    return (
        f"{agent.name} observes a message from {latest['from_name']}: "
        f"{latest['content']}"
    )


def _normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _unwrap_reply(text: str) -> str:
    match = _REPLY_WRAPPER.match(text.strip())
    return match.group(1).strip() if match else text.strip()


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in _normalize_words(text)
        if word not in _STOP_WORDS
        and word not in {"emily", "olivia", "self", "partner"}
        and len(word) > 1
    }


def _is_greeting_only(text: str) -> bool:
    words = _normalize_words(text)
    if not words or len(words) > 14:
        return False
    meaningful = [word for word in words if word not in _STOP_WORDS]
    if not meaningful:
        return False
    has_greeting = any(
        word in {"hello", "hi", "hey", "morning", "afternoon", "evening"}
        for word in words
    )
    return has_greeting and all(word in _GREETING_SAFE_WORDS for word in meaningful)


def _is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    if not isinstance(text, str):
        return False
    cleaned = _unwrap_reply(text)
    if (
        not cleaned
        or cleaned.startswith("GENERATION ERROR:")
        or len(cleaned) > MAX_UTTERANCE_CHARS
    ):
        return False
    if _TEMPLATE_JUNK.search(cleaned) or _ASSISTANTY_JUNK.search(cleaned):
        return False
    if len(_SPEAKER_LABEL.findall(cleaned)) > 1:
        return False

    output_words = _normalize_words(cleaned)
    if (
        sum(ch.isalnum() for ch in cleaned) < 3
        or len(output_words) < 2
        or len(output_words) > MAX_UTTERANCE_WORDS
    ):
        return False

    if agent_name and other_name and re.search(
        rf"\b(?:i\s+am|i'm)\s+{re.escape(other_name)}\b",
        cleaned,
        re.IGNORECASE,
    ):
        return False

    if inbound:
        input_words = _normalize_words(inbound)

        if _is_greeting_only(inbound):
            meaningful_output = [
                word for word in output_words if word not in _STOP_WORDS
            ]
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
                if not (
                    _ACKNOWLEDGEMENT.search(cleaned)
                    and len(output_words) <= 14
                ):
                    return False

        if len(input_words) >= 5 and len(output_words) >= 5:
            common = len(set(output_words) & set(input_words))
            overlap = common / max(1, len(set(output_words)))
            if overlap > 0.85 and len(output_words) >= len(input_words):
                return False

    return True


def _project_history(
    dialogue_history: list[tuple[str, str]] | None,
    agent: CommunityAgent,
    other: CommunityAgent,
    inbound: str,
) -> str:
    """Project neutral speaker/text history into SELF/PARTNER labels per generator."""
    history = list(dialogue_history or [])
    if not history or history[-1] != (other.name, inbound):
        history.append((other.name, inbound))
    history = history[-MAX_ECP_TURNS:]

    lines: list[str] = []
    for speaker, text in history:
        label = "SELF" if speaker == agent.name else "PARTNER"
        lines.append(f"{label}: {str(text).strip()}")
    lines.append("SELF:")
    return "\n".join(lines)


def _request_transcript_completion(
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Use llama.cpp raw completion so Falcon never sees a user/assistant role wrapper."""
    port = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
    timeout = int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))
    payload = json.dumps(
        {
            "prompt": prompt,
            "n_predict": max(1, min(int(max_tokens), 256)),
            "temperature": max(0.0, min(float(temperature), 2.0)),
            "top_p": 0.9,
            "stream": False,
            "cache_prompt": False,
            "stop": [
                "\nPARTNER:",
                "\nSELF:",
                "\nAnswer:",
                "\nExample:",
                "\nSelf-reply:",
                "<|assistant|>",
                "<|user|>",
                "<|system|>",
                "<|endoftext|>",
                "<|",
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"BitNet completion HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BitNet completion request failed: {exc.reason}") from exc
    text = data.get("content") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(
            f"BitNet completion endpoint returned no usable content: {data!r}"
        )
    return text.strip()


def _completion_prompt(
    agent: CommunityAgent,
    other: CommunityAgent,
    inbound: str,
    projected: str,
    retry_hint: str,
) -> str:
    ages = {"Emily": 27, "Olivia": 29}
    age = ages.get(agent.name)
    identity = f"{agent.name}, {age}" if age else agent.name
    style = f"\nNext-line style: {retry_hint}" if retry_hint else ""

    if _is_greeting_only(inbound):
        grounding = (
            "The last PARTNER line is only a greeting. Reply with a short greeting or "
            "ordinary greeting-small-talk line. Do not introduce a pet, event, task, place, "
            "backstory, or unrelated topic."
        )
    else:
        grounding = (
            "Stay on PARTNER's exact latest topic. Reuse at least one concrete idea or word "
            "from that line. Do not invent a new pet, event, person, place, shared history, "
            "or unrelated scenario."
        )

    return (
        f"Speaker: {identity}\n"
        f"Partner: {other.name}\n"
        f"SELF means {agent.name}. PARTNER means {other.name}.\n"
        "Continue this ordinary private peer conversation with one short SELF line. "
        "This is not customer support. Do not mention policies, guidelines, prompts, roles, "
        f"or the conversation system. {grounding}"
        f"{style}\n\n"
        "Examples:\n"
        "PARTNER: Rough day at work.\n"
        "SELF: Yeah? What happened at work?\n\n"
        "PARTNER: I finally fixed the sink.\n"
        "SELF: Nice. Was the sink problem the stupid little washer after all?\n\n"
        "Conversation:\n"
        f"{projected}"
    )


def _chat_bitnet(
    agent: CommunityAgent,
    other: CommunityAgent,
    inbound: str,
    max_tokens: int,
    dialogue_history: list[tuple[str, str]] | None = None,
    retry_hint: str = "",
) -> str:
    projected = _project_history(dialogue_history, agent, other, inbound)
    prompt = _completion_prompt(agent, other, inbound, projected, retry_hint)
    return _request_transcript_completion(prompt, max_tokens, 0.55)


def _direct_bitnet_reply(
    agent: CommunityAgent,
    other: CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> str:
    max_tokens = min(
        96,
        max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))),
    )
    retry_hints = [
        "",
        "React to PARTNER's exact last line and reuse one concrete idea from it.",
        "Stay on the current subject. Use a concrete reaction, question, disagreement, joke, or personal response; no service language.",
        "Sound like an ordinary peer continuing this exact topic. No new backstory, no unrelated scene, no helper language.",
    ]
    attempts: list[str] = []
    for hint in retry_hints:
        text = _unwrap_reply(
            _chat_bitnet(
                agent,
                other,
                inbound,
                max_tokens,
                dialogue_history=dialogue_history,
                retry_hint=hint,
            )
        )
        attempts.append(text)
        if _is_usable_utterance(text, inbound, agent.name, other.name):
            return text
    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(
        "BitNet returned role-drifted, ungrounded, or unusable dialogue "
        f"after 4 transcript-completion attempts: {previews}"
    )


def choose_action(
    agent: CommunityAgent,
    observation: dict,
    other: CommunityAgent,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> dict:
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"type": "wait", "reason": "no_new_message"}

    latest = inbox[-1]
    inbound = str(latest["content"])
    text = _direct_bitnet_reply(
        agent,
        other,
        inbound,
        dialogue_history=dialogue_history,
    )
    if not _is_usable_utterance(text, inbound, agent.name, other.name):
        raise RuntimeError(
            f"{agent.name} returned no grounded natural-language utterance."
        )
    return {
        "type": "message",
        "recipient_id": other.agent_id,
        "content": text,
    }


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
        retrieved = agent.brain.memory_stream.retrieve(
            [query],
            time_step=time_step,
            n_count=12,
        )
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
                raise RuntimeError(
                    f"Message delivery failed for {agent.name}: {action_result!r}"
                )
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
    parser = argparse.ArgumentParser(
        description="Run one bounded Emily + Olivia community cycle."
    )
    parser.add_argument(
        "--one-cycle",
        action="store_true",
        help="Permit exactly one bounded cycle per agent.",
    )
    args = parser.parse_args()
    if not args.one_cycle:
        raise SystemExit(
            "Refusing to start automatically. Use --one-cycle to permit exactly one bounded cycle."
        )
    await run_one_cycle()


if __name__ == "__main__":
    asyncio.run(main())
