#!/usr/bin/env python3
"""Planning adapter derived from the original Stanford Generative Agents code.

Upstream source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

This keeps the paper's persistent broad-strokes planning idea and `daily_req`
scratch convention while omitting Smallville-specific map and game machinery.
In this isolated two-person community, a plan must be grounded in actual memory
or reflection. Unknown biography is not replaced with invented errands, places,
or activities, because those synthetic plan details can become conversational
attractors rather than genuine continuity.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable

from dialogue_attractor import content_tokens
from reflection_hygiene import is_clean_observation_text, is_clean_reflection_text

_ORIGINAL_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_NUMBERED_ITEM = re.compile(r"(?:^|\n|\s)(?:\d{1,2})[.)]\s*([^\n]+?)(?=(?:\s+\d{1,2}[.)]\s)|\n|$)")
_MESSAGE_PREFIX = re.compile(
    r"^(?:Emily|Olivia) observes a message from (?:Emily|Olivia|Alex):\s*",
    re.IGNORECASE,
)
_NO_MESSAGE = re.compile(r"\bno\s+(?:new\s+)?addressed\s+messages?\b", re.IGNORECASE)
_GREETING_ONLY = re.compile(
    r"^\s*(?:(?:oh|well)[,! ]+)?(?:good\s+(?:morning|afternoon|evening)|hi|hello|hey)"
    r"(?:\s+(?:there|again|emily|olivia))?[!,. ]*$",
    re.IGNORECASE,
)


def _payload(text: str) -> str:
    return _MESSAGE_PREFIX.sub("", str(text or "").strip()).strip()


def _substantive_memory(node) -> bool:
    content = str(getattr(node, "content", "") or "").strip()
    if not content:
        return False
    node_type = getattr(node, "node_type", None)
    if node_type == "reflection":
        return is_clean_reflection_text(content)
    if node_type == "observation":
        if not is_clean_observation_text(content) or _NO_MESSAGE.search(content):
            return False
        payload = _payload(content)
        if _GREETING_ONLY.match(payload):
            return False
        return len(set(content_tokens(payload))) >= 2
    return len(set(content_tokens(content))) >= 2


def _memory_context(agent, time_step: int, other_name: str) -> list[str]:
    """Use Stanford retrieval, retaining only grounded substantive plan evidence."""
    focal = (
        f"What genuinely matters to {agent.name} now, based on remembered experiences, "
        f"reflections, and the ongoing interaction with {other_name}?"
    )
    retrieved = agent.brain.memory_stream.retrieve([focal], time_step=time_step, n_count=16)
    selected: list[str] = []
    seen: set[str] = set()
    for node in retrieved.get(focal, []):
        if not _substantive_memory(node):
            continue
        content = str(getattr(node, "content", "") or "").strip()
        if content in seen:
            continue
        seen.add(content)
        selected.append(content)
        if len(selected) >= 10:
            break
    return selected


def _paper_style_prompt(agent, memories: Iterable[str], now: _dt.datetime) -> str:
    """Adapt the paper's broad-strokes planning prompt without fabricated life facts."""
    scratch = dict(agent.brain.scratch)
    first_name = str(scratch.get("first_name") or agent.name)
    age = scratch.get("age")
    identity = f"{first_name} is {age} years old." if age else f"This person is {first_name}."
    memory_lines = [str(x).strip() for x in memories if str(x).strip()]
    observed = "\n".join(f"- {line}" for line in memory_lines[-10:])
    date_str = now.strftime("%A %B %d, %Y")

    return (
        f"{identity}\n"
        "Grounded memories and reflections:\n"
        f"{observed}\n\n"
        f"Today is {date_str}. Form a short private broad-strokes plan for {first_name} "
        "using only goals, concerns, interests, unfinished matters, or intentions that are "
        "actually supported by the memories above. Do not invent errands, locations, jobs, "
        "relationships, hobbies, purchases, appointments, or shared history. If the memories "
        "do not support a meaningful plan yet, answer exactly NONE. Otherwise give a short "
        "numbered list. This is private planning state, not dialogue."
    )


def _parse_plan(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text or text.casefold() == "none":
        return []
    matches = [m.group(1).strip(" ,.;") for m in _NUMBERED_ITEM.finditer(text)]
    if not matches:
        matches = [
            re.sub(r"^[-*]\s*", "", line).strip(" ,.;")
            for line in text.splitlines()
            if line.strip() and line.strip().casefold() != "none"
        ]
    clean: list[str] = []
    for item in matches:
        if not item or len(item) > 240:
            continue
        lowered = item.lower()
        if any(marker in lowered for marker in ("<|", "answer:", "example:", "self:", "partner:")):
            continue
        if item not in clean:
            clean.append(item)
        if len(clean) >= 6:
            break
    return clean


def ensure_daily_plan(agent, other_name: str, time_step: int) -> list[str]:
    """Create/persist grounded paper-style planning state once per local day."""
    now = _dt.datetime.now().astimezone()
    date_key = now.date().isoformat()
    scratch = agent.brain.scratch
    existing = scratch.get("daily_req")
    profile = scratch.get("daily_plan_profile")
    if (
        scratch.get("daily_plan_date") == date_key
        and profile == "grounded-two-person-v1"
        and isinstance(existing, list)
    ):
        return [str(x) for x in existing if str(x).strip()]

    memories = _memory_context(agent, time_step, other_name)
    if not memories:
        plan: list[str] = []
    else:
        prompt = _paper_style_prompt(agent, memories, now)
        from simulation_engine.gpt_structure import gpt_request

        raw = gpt_request(prompt, model="community-bitnet", max_tokens=192)
        if isinstance(raw, str) and raw.startswith("GENERATION ERROR:"):
            plan = []
        else:
            plan = _parse_plan(raw)

    agent.brain.update_scratch(
        {
            "daily_plan_date": date_key,
            "daily_req": plan,
            "daily_plan_profile": "grounded-two-person-v1",
            "daily_plan_research_source": _ORIGINAL_RESEARCH_COMMIT,
        }
    )
    agent.brain.save(str(agent.workspace))
    return plan


def planning_context(agent, other_name: str, time_step: int) -> str:
    """Return private grounded plan state as context, never as required dialogue."""
    plan = ensure_daily_plan(agent, other_name, time_step)
    if not plan:
        return ""
    return "Current private broad-strokes plan: " + "; ".join(plan[:5])
