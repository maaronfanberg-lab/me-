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

from difflib import SequenceMatcher
import json
import os
import re
import urllib.error
import urllib.request

import community_cycle_base as _base

_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_MAX_HISTORY_TURNS = 12
_MAX_ACT_ATTEMPTS = 8
_PEER_META_DRIFT = re.compile(
    r"(?:generate\s+(?:the\s+)?dialogue|fictional\s+interaction|"
    r"noticed\s+the\s+conversation|communicat(?:e|ing)\s+effectively|"
    r"share\s+more\s+about\s+your\s+preferences|"
    r"preferred\s+(?:meal|food)\s+options|"
    r"ensure\s+(?:we(?:'re|\s+are)|that\s+we)\s+communicat)",
    re.IGNORECASE,
)
_SHORT_SPOKEN_CLAUSE = re.compile(
    r"\b(?:i(?:'m|'d|'ll|'ve)|you(?:'re|'d|'ll|'ve)|we(?:'re|'d|'ll|'ve)|"
    r"it(?:'s|'d|'ll)|that(?:'s|'d)|this(?:'s|'d)|they(?:'re|'d|'ll|'ve)|"
    r"he(?:'s|'d|'ll)|she(?:'s|'d|'ll)|can't|don't|didn't|won't|wouldn't|"
    r"couldn't|shouldn't|isn't|aren't|wasn't|weren't)\b",
    re.IGNORECASE,
)
_CONTROL_SCAFFOLD = re.compile(
    r"(?:<\|(?:assistant|user|system|endoftext|im_start|im_end)[^>]*\|?>|"
    r"^\s*(?:SELF|PARTNER|Self-reply|Partner-reply|Answer|Example)\s*:|"
    r"\[Fill\s+in\])",
    re.IGNORECASE | re.MULTILINE,
)
_CONTEXT_DEPENDENT_OPENING = re.compile(
    r"^\s*(?:yeah|yep|yes|right|exactly|sure|okay|ok|"
    r"i\s+(?:know|understand|agree)|same\s+here|me\s+too|so\s+do\s+i|"
    r"that(?:'s|\s+is)\s+(?:true|right))\b",
    re.IGNORECASE,
)
_PLAN_MARKER = "current broad-strokes plan:"


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
    if not isinstance(text, str):
        raise RuntimeError(f"BitNet paper-act completion returned malformed content: {data!r}")
    return text.strip()


def _clean_line(raw: object, agent_name: str) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.strip().lstrip('"').strip()
    if not text:
        return ""
    text = text.split('"', 1)[0].strip()
    text = text.splitlines()[0].strip() if text.splitlines() else ""
    text = re.sub(rf"^\s*{re.escape(agent_name)}\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return _base._unwrap_reply(text).strip()


def _is_sentence_like_short_turn(text: str) -> bool:
    """Permit genuine terse speech while rejecting bare topic labels."""
    words = _base._normalize_words(text)
    if len(words) >= 4:
        return True
    if _base._is_greeting_only(text) or _base._ACKNOWLEDGEMENT.search(text):
        return True
    return bool(_SHORT_SPOKEN_CLAUSE.search(text))


def _has_pathological_repetition(text: str) -> bool:
    """Mirror the outer runtime's repetition safety check inside resampling."""
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


def _is_context_dependent_opening(text: str, inbound: str, dialogue_history) -> bool:
    """Reject answer-like first lines when there is nothing yet to answer."""
    if str(inbound or "").strip():
        return False
    if any(str(speaker).strip() and str(line).strip() for speaker, line in (dialogue_history or [])):
        return False
    return bool(_CONTEXT_DEPENDENT_OPENING.search(str(text or "")))


def _private_plan_items(cognitive_context: str) -> list[str]:
    """Extract private daily-plan clauses only for leak detection, never steering."""
    context = str(cognitive_context or "")
    lowered = context.casefold()
    marker_index = lowered.find(_PLAN_MARKER)
    if marker_index < 0:
        return []
    tail = context[marker_index + len(_PLAN_MARKER) :]
    return [item.strip(" .") for item in tail.split(";") if item.strip(" .")]


def _is_private_plan_echo(text: str, cognitive_context: str) -> bool:
    """Keep private plan steps from leaking verbatim or near-verbatim into speech."""
    output_words = _base._normalize_words(text)
    if len(output_words) < 3:
        return False
    output_set = set(output_words)
    for item in _private_plan_items(cognitive_context):
        plan_words = _base._normalize_words(item)
        if not plan_words:
            continue
        if output_words == plan_words:
            return True
        if len(output_words) >= 4 and len(plan_words) >= 4:
            plan_set = set(plan_words)
            shared = len(output_set & plan_set)
            output_coverage = shared / max(1, len(output_set))
            plan_coverage = shared / max(1, len(plan_set))
            if max(output_coverage, plan_coverage) >= 0.9 and abs(len(output_words) - len(plan_words)) <= 5:
                return True
    return False


def is_usable_spoken_action(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Validate a paper-derived line without dictating its vocabulary."""
    if not _base._is_usable_utterance(text, "", agent_name, other_name):
        return False
    if _CONTROL_SCAFFOLD.search(text) or _has_pathological_repetition(text):
        return False
    if _PEER_META_DRIFT.search(text):
        return False
    if not _is_sentence_like_short_turn(text):
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


def _is_recent_echo(text: str, dialogue_history) -> bool:
    """Reject exact, subset, and long-sequence copies of recent dialogue.

    This is a diversity boundary, not a topic or vocabulary requirement. A
    small local model can otherwise shorten the previous speaker's sentence by
    one clause on every turn and pass a literal exact-match check forever.
    """
    output_words = _base._normalize_words(text)
    if not output_words:
        return True
    output_set = set(output_words)
    for _speaker, prior in list(dialogue_history or [])[-_MAX_HISTORY_TURNS:]:
        prior_words = _base._normalize_words(str(prior))
        if not prior_words:
            continue
        if output_words == prior_words:
            return True

        smaller_len = min(len(output_words), len(prior_words))
        if smaller_len < 8:
            continue

        matcher = SequenceMatcher(None, output_words, prior_words, autojunk=False)
        longest = matcher.find_longest_match().size
        if longest >= max(8, int(smaller_len * 0.65)):
            return True
        if matcher.ratio() >= 0.78:
            return True

        prior_set = set(prior_words)
        shared = len(output_set & prior_set)
        smaller_unique = max(1, min(len(output_set), len(prior_set)))
        if shared / smaller_unique >= 0.88:
            return True
    return False


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
    for _ in range(_MAX_ACT_ATTEMPTS):
        raw = _request_completion(prompt, agent.name, other.name)
        text = _clean_line(raw, agent.name)
        attempts.append(text or str(raw).strip())
        if (
            is_usable_spoken_action(text, inbound, agent.name, other.name)
            and not _is_recent_echo(text, dialogue_history)
            and not _is_context_dependent_opening(text, inbound, dialogue_history)
            and not _is_private_plan_echo(text, cognitive_context)
        ):
            return text

    previews = " | ".join(repr(text[:220]) for text in attempts)
    raise RuntimeError(
        f"{agent.name} paper-derived Stanford act produced no usable spoken line after "
        f"{_MAX_ACT_ATTEMPTS} same-prompt attempts: {previews}"
    )


def research_source() -> str:
    return _RESEARCH_COMMIT
