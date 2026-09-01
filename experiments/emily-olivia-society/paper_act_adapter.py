#!/usr/bin/env python3
"""Spoken-action adapter derived from the original Stanford Generative Agents code.

Upstream research source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

The original paper's conversation path generates the next line by ending the
prompt at ``<persona name>: \"`` and completing that line. That shape is a much
better fit for the small local Falcon model than the later Stanford HCI JSON
utterance prompt, which can drift into self-description instead of dialogue.

This adapter keeps the paper's next-line completion boundary while using the
current Community's Stanford HCI memory/retrieval/reflection state. It contains
no authored example dialogue, conversational-move recipes, or fallback replies.
Retries resample the same research-derived prompt and fail closed if the model
never produces a usable line.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

import community_cycle_base as _base

_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_MAX_HISTORY_TURNS = 12


def _identity(agent) -> str:
    """Use only factual scratch identity; never invent a biography."""
    scratch = dict(agent.brain.scratch)
    name = str(scratch.get("first_name") or agent.name).strip() or agent.name
    age = scratch.get("age")
    try:
        age_value = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_value = None
    if age_value and age_value > 0:
        return f"{name} is {age_value} years old."
    return f"This person's name is {name}."


def _history_text(dialogue_history, other_name: str, inbound: str) -> str:
    history = [
        (str(speaker).strip(), str(text).strip())
        for speaker, text in (dialogue_history or [])
        if str(speaker).strip() and str(text).strip()
    ]
    inbound = str(inbound or "").strip()
    if inbound and (not history or history[-1] != (other_name, inbound)):
        history.append((other_name, inbound))
    history = history[-_MAX_HISTORY_TURNS:]
    return "\n".join(f"{speaker}: {text}" for speaker, text in history)


def _paper_prompt(agent, other, dialogue_history, inbound: str, cognitive_context: str) -> str:
    """Adapt the paper's generate_next_convo_line_v1 template to this runtime.

    Original source shape at the pinned commit:
      basic persona information
      conversation transcript
      note containing the retrieved summary
      <persona name>: "
    """
    history = _history_text(dialogue_history, other.name, inbound)
    context = str(cognitive_context or "").strip()
    if not context:
        context = "No additional retrieved information is available."
    transcript = history + ("\n" if history else "")
    return (
        f"Here is some basic information about {agent.name}.\n"
        f"{_identity(agent)}\n\n"
        "===\n"
        f"Following is a conversation between {agent.name} and {other.name}.\n\n"
        f"{transcript}\n"
        f"(Note -- This is the only information that {agent.name} has: {context})\n\n"
        f"{agent.name}: \""
    )


def _request_completion(prompt: str, agent_name: str, other_name: str) -> str:
    port = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
    timeout = int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))
    max_tokens = min(128, max(24, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    payload = json.dumps(
        {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": 1.0,
            "top_p": 0.9,
            "stream": False,
            "cache_prompt": False,
            "stop": [
                "\"",
                f"\n{agent_name}:",
                f"\n{other_name}:",
                "<|assistant|>",
                "<|user|>",
                "<|system|>",
                "<|endoftext|>",
                "<|",
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"BitNet paper-act completion HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BitNet paper-act completion request failed: {exc.reason}") from exc

    text = data.get("content") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"BitNet paper-act completion returned no content: {data!r}")
    return text.strip()


def _clean_line(raw: object, agent_name: str) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.strip().lstrip('"').strip()
    if not text:
        return ""
    # The paper's own clean-up takes text only up to the next quote. Do the same,
    # then keep only the completed spoken line if the model emits extra text.
    text = text.split('"', 1)[0].strip()
    text = text.splitlines()[0].strip() if text.splitlines() else ""
    text = re.sub(rf"^\s*{re.escape(agent_name)}\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return _base._unwrap_reply(text).strip()


def is_usable_spoken_action(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Validate a paper-derived line without dictating its vocabulary.

    The older local dialogue gate required an output to reuse a literal content
    word from the inbound message. That is useful for a tightly steered fallback
    generator but wrong for the paper's transcript-completion act: a natural
    reply can be semantically relevant with zero lexical overlap. Keep the
    structural, role-drift, length, and service-language checks by validating
    with an empty inbound, then independently reject direct/near-direct echoes.
    """
    if not _base._is_usable_utterance(text, "", agent_name, other_name):
        return False
    inbound = str(inbound or "").strip()
    if not inbound:
        return True

    input_words = _base._normalize_words(inbound)
    output_words = _base._normalize_words(text)
    if not input_words or not output_words:
        return False
    if input_words == output_words:
        return False

    if len(input_words) >= 5 and len(output_words) >= 5:
        common = len(set(output_words) & set(input_words))
        overlap = common / max(1, len(set(output_words)))
        if overlap > 0.85 and len(output_words) >= len(input_words):
            return False
    return True


def generate_spoken_action(
    agent,
    other,
    dialogue_history=None,
    inbound: str = "",
    cognitive_context: str = "",
) -> str:
    """Generate one spoken action with the paper's next-line completion shape."""
    prompt = _paper_prompt(agent, other, dialogue_history, inbound, cognitive_context)
    attempts: list[str] = []
    for _ in range(5):
        raw = _request_completion(prompt, agent.name, other.name)
        text = _clean_line(raw, agent.name)
        attempts.append(text or str(raw).strip())
        if is_usable_spoken_action(text, inbound, agent.name, other.name):
            return text

    previews = " | ".join(repr(text[:220]) for text in attempts)
    raise RuntimeError(
        f"{agent.name} paper-derived Stanford act produced no usable spoken line after 5 same-prompt attempts: {previews}"
    )


def research_source() -> str:
    return _RESEARCH_COMMIT
