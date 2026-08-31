#!/usr/bin/env python3
"""Daily planning adapter derived from the original Stanford Generative Agents code.

Upstream source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

This intentionally keeps the paper's broad-strokes daily-plan idea and its
`daily_req` scratch convention, while omitting Smallville-specific map,
spatial-memory, and game-object machinery that does not exist in this isolated
two-person community.

The speech generator does not get hand-written conversational moves here.  The
plan is private cognitive state.  Stanford's own GenerativeAgent.utterance()
can then speak from that state and from retrieved memories.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable


_ORIGINAL_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_NUMBERED_ITEM = re.compile(r"(?:^|\n|\s)(?:\d{1,2})[.)]\s*([^\n]+?)(?=(?:\s+\d{1,2}[.)]\s)|\n|$)")


def _memory_context(agent, time_step: int, other_name: str) -> list[str]:
    """Use Stanford genagents' recency/relevance/importance retrieval directly."""
    focal = (
        f"What matters to {agent.name} today, what {agent.name} has been doing, "
        f"and the current interaction with {other_name}"
    )
    retrieved = agent.brain.memory_stream.retrieve(
        [focal], time_step=time_step, n_count=12
    )
    return [node.content for node in retrieved.get(focal, [])]


def _paper_style_prompt(agent, memories: Iterable[str], now: _dt.datetime) -> str:
    """Adapt the original daily_planning_v6 prompt to the smaller environment.

    Original prompt shape:
      identity/commonset
      lifestyle
      current date
      broad-strokes numbered plan with times

    We intentionally do not fabricate a job, home, relationships, or location.
    """
    scratch = dict(agent.brain.scratch)
    first_name = str(scratch.get("first_name") or agent.name)
    age = scratch.get("age")
    identity = f"{first_name} is {age} years old." if age else f"This person is {first_name}."
    memory_lines = [str(x).strip() for x in memories if str(x).strip()]
    observed = "\n".join(f"- {line}" for line in memory_lines[-12:]) or "- No additional observations yet."
    date_str = now.strftime("%A %B %d, %Y")

    # Closely follows the original paper's daily_planning_v6 broad-strokes
    # formulation, replacing Smallville identity/lifestyle fields with facts
    # actually present in this agent's Stanford memory/scratch state.
    return (
        f"{identity}\n"
        "Relevant observations and memories:\n"
        f"{observed}\n\n"
        f"Today is {date_str}. Here is {first_name}'s plan today in broad-strokes "
        "with the time of day (for example, have lunch at 12:00 pm): 1) "
        "Give a short numbered plan for the rest of the day. Use only the identity, "
        "observations, and memories above as personal facts. If details are unknown, "
        "choose ordinary low-stakes activities without inventing a job, relationship, "
        "specific place, pet, or shared history."
    )


def _parse_plan(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    matches = [m.group(1).strip(" ,.;") for m in _NUMBERED_ITEM.finditer(text)]
    if not matches:
        # BitNet occasionally returns one item per line without numbering.
        matches = [
            re.sub(r"^[-*]\s*", "", line).strip(" ,.;")
            for line in text.splitlines()
            if line.strip()
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
        if len(clean) >= 8:
            break
    return clean


def ensure_daily_plan(agent, other_name: str, time_step: int) -> list[str]:
    """Create/persist the paper-style daily_req once per local calendar day."""
    now = _dt.datetime.now().astimezone()
    date_key = now.date().isoformat()
    scratch = agent.brain.scratch
    existing = scratch.get("daily_req")
    if scratch.get("daily_plan_date") == date_key and isinstance(existing, list) and existing:
        return [str(x) for x in existing if str(x).strip()]

    memories = _memory_context(agent, time_step, other_name)
    prompt = _paper_style_prompt(agent, memories, now)

    # Stanford's gpt_structure is patched by patch_stanford_local.py so this
    # remains local BitNet generation while preserving the research runtime.
    from simulation_engine.gpt_structure import gpt_request

    raw = gpt_request(prompt, model="community-bitnet", max_tokens=256)
    if isinstance(raw, str) and raw.startswith("GENERATION ERROR:"):
        return []
    plan = _parse_plan(raw)
    if not plan:
        return []

    agent.brain.update_scratch(
        {
            "daily_plan_date": date_key,
            "daily_req": plan,
            "daily_plan_research_source": _ORIGINAL_RESEARCH_COMMIT,
        }
    )
    agent.brain.save(str(agent.workspace))
    return plan


def planning_context(agent, other_name: str, time_step: int) -> str:
    """Return private plan state as context, not as a required dialogue script."""
    plan = ensure_daily_plan(agent, other_name, time_step)
    if not plan:
        return ""
    return "Current broad-strokes plan: " + "; ".join(plan[:5])
