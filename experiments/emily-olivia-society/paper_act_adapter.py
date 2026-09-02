#!/usr/bin/env python3
"""Spoken-action adapter derived from the original Stanford Generative Agents code.

Upstream research source:
  joonspk-research/generative_agents
  commit fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4
  Apache-2.0

The original paper's conversation path generates the next line by ending the
prompt at ``<persona name>: "`` and completing that line. This adapter keeps
that research-derived boundary while using the current Community's Stanford HCI
memory/retrieval/reflection state.

There are no authored example replies or canned fallbacks. Rejected outputs are
resampled from the same research-derived prompt. Sampling state changes across
retries so a small local model cannot spend every retry reproducing one rejected
line.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import json
import os
import re
import secrets
import urllib.error
import urllib.request

import community_cycle_base as _base

_RESEARCH_COMMIT = "fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
_MAX_HISTORY_TURNS = 12
_MAX_UNIQUE_ACT_ATTEMPTS = 4
_MAX_COMPLETION_REQUESTS = 6

_PEER_META_DRIFT = re.compile(
    r"(?:generate\s+(?:the\s+)?dialogue|fictional\s+interaction|"
    r"noticed\s+the\s+conversation|communicat(?:e|ing)\s+effectively|"
    r"share\s+more\s+about\s+your\s+preferences|"
    r"preferred\s+(?:meal|food)\s+options|"
    r"ensure\s+(?:we(?:'re|\s+are)|that\s+we)\s+communicat)",
    re.IGNORECASE,
)
_ASSISTANT_SERVICE_DRIFT = re.compile(
    r"(?:how\s+can\s+i\s+(?:help|assist)\s+you(?:\s+today)?|"
    r"i(?:'d|\s+would)\s+be\s+happy\s+to\s+(?:help|assist)|"
    r"if\s+you\s+(?:have|need)\s+(?:any\s+)?(?:questions|assistance)|"
    r"feel\s+free\s+to\s+(?:ask|reach\s+out)|"
    r"how\s+may\s+i\s+(?:help|assist))",
    re.IGNORECASE,
)
_REFUSAL_TEMPLATE_DRIFT = re.compile(
    r"(?:i(?:'m|\s+am)\s+sorry[^.!?]{0,80}\b(?:can't|cannot|unable)\b|"
    r"\bi\s+(?:can't|cannot|am\s+unable\s+to)\s+(?:fulfill|comply\s+with|assist\s+with)\s+"
    r"(?:this|that|your)\s+(?:request|instruction))",
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
_VAGUE_REFERENTIAL_START = re.compile(
    r"^\s*(?:that(?:'s|\s+is)?|this(?:'s|\s+is)?|it(?:'s|\s+is)?)\b",
    re.IGNORECASE,
)
_REFERENCE_FILLER = {
    "that", "this", "it's", "thats", "that's", "is", "isnt", "isn't",
    "not", "really", "very", "just", "what", "your", "youre", "you're",
    "mine", "my", "the", "and", "but", "with", "from", "have", "has",
}
_INCOMPLETE_SPOKEN_END = re.compile(
    r"(?:[,;:]|\b(?:because|although|unless|until|while|when|if)\s*|"
    r"\b(?:feel|felt|seem|seemed)\s+like\s*)$",
    re.IGNORECASE,
)
_MEMORY_SERIALIZATION_LEAK = re.compile(
    r"(?:^|\|)\s*(?:Emily|Olivia)\s+observes(?:\s+a\s+message\s+from|\s+that)\b",
    re.IGNORECASE,
)
_PLAN_MARKER = "current broad-strokes plan:"
_RETRIEVED_MARKER = "relevant retrieved memories:"


def _identity(agent) -> str:
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
    return "\n".join(f"{speaker}: {text}" for speaker, text in history[-_MAX_HISTORY_TURNS:])


def _paper_prompt(agent, other, dialogue_history, inbound: str, cognitive_context: str) -> str:
    """Adapt the paper's generate_next_convo_line_v1 template."""
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
        f'{agent.name}: "'
    )


def _sampling_seed() -> int:
    """Return an explicit non-default llama.cpp seed for each request."""
    return 1 + secrets.randbelow(2_147_483_646)


def _request_completion(
    prompt: str,
    agent_name: str,
    other_name: str,
    *,
    request_index: int = 0,
    duplicate_pressure: int = 0,
    previous_hit_limit: bool = False,
) -> tuple[str, bool]:
    port = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
    timeout = int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "45"))
    base_tokens = min(128, max(24, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    extra_tokens = 16 * min(4, max(0, request_index)) if previous_hit_limit else 0
    max_tokens = min(128, base_tokens + extra_tokens)

    repeat_penalty = min(1.24, 1.08 + 0.03 * max(0, duplicate_pressure))
    temperature = min(1.15, 0.96 + 0.025 * min(5, request_index) + 0.03 * duplicate_pressure)

    payload = json.dumps(
        {
            "prompt": prompt,
            "n_predict": max_tokens,
            "seed": _sampling_seed(),
            "temperature": temperature,
            "top_k": 40,
            "top_p": 0.92,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": 96,
            "stream": False,
            "cache_prompt": False,
            "stop": [
                '"',
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
    hit_limit = bool(data.get("stopped_limit")) or str(data.get("stop_type", "")).strip().lower() == "limit"
    context_truncated = bool(data.get("truncated"))
    return text.strip(), bool(hit_limit or context_truncated)


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
    words = _base._normalize_words(text)
    if len(words) >= 4:
        return True
    if _base._is_greeting_only(text) or _base._ACKNOWLEDGEMENT.search(text):
        return True
    return bool(_SHORT_SPOKEN_CLAUSE.search(text))


def _looks_complete_spoken_turn(text: str) -> bool:
    cleaned = str(text or "").strip()
    return bool(cleaned and not _INCOMPLETE_SPOKEN_END.search(cleaned))


def _has_pathological_repetition(text: str) -> bool:
    words = _base._normalize_words(text)
    if len(words) < 8:
        return False
    for width in range(2, min(7, len(words) // 2 + 1)):
        counts: dict[tuple[str, ...], int] = {}
        for index in range(0, len(words) - width + 1):
            gram = tuple(words[index:index + width])
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
    if str(inbound or "").strip():
        return False
    if any(str(speaker).strip() and str(line).strip() for speaker, line in (dialogue_history or [])):
        return False
    return bool(_CONTEXT_DEPENDENT_OPENING.search(str(text or "")))


def _is_ungrounded_short_reference(text: str, inbound: str) -> bool:
    inbound = str(inbound or "").strip()
    if not inbound or not _VAGUE_REFERENTIAL_START.search(str(text or "")):
        return False
    output_words = _base._normalize_words(text)
    if len(output_words) > 6 or _base._ACKNOWLEDGEMENT.search(text):
        return False
    input_words = _base._normalize_words(inbound)
    output_content = {w for w in output_words if len(w) >= 4 and w not in _REFERENCE_FILLER}
    input_content = {w for w in input_words if len(w) >= 4 and w not in _REFERENCE_FILLER}
    return bool(output_content and not (output_content & input_content))


def _private_plan_items(cognitive_context: str) -> list[str]:
    context = str(cognitive_context or "")
    marker_index = context.casefold().find(_PLAN_MARKER)
    if marker_index < 0:
        return []
    tail = context[marker_index + len(_PLAN_MARKER):]
    return [item.strip(" .") for item in tail.split(";") if item.strip(" .")]


def _is_private_plan_echo(text: str, cognitive_context: str) -> bool:
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
            if (
                max(shared / max(1, len(output_set)), shared / max(1, len(plan_set))) >= 0.9
                and abs(len(output_words) - len(plan_words)) <= 5
            ):
                return True
    return False


def _is_retrieved_memory_echo(text: str, cognitive_context: str) -> bool:
    output_words = _base._normalize_words(text)
    if len(output_words) < 8:
        return False
    context = str(cognitive_context or "").strip()
    if not context:
        return False
    context_words = _base._normalize_words(context)
    width = len(output_words)
    if width <= len(context_words):
        for index in range(0, len(context_words) - width + 1):
            if context_words[index:index + width] == output_words:
                return True

    marker_index = context.casefold().find(_RETRIEVED_MARKER)
    if marker_index < 0:
        return False
    for item in context[marker_index + len(_RETRIEVED_MARKER):].split(" | "):
        memory_words = _base._normalize_words(item)
        smaller_len = min(len(output_words), len(memory_words))
        if smaller_len < 8:
            continue
        matcher = SequenceMatcher(None, output_words, memory_words, autojunk=False)
        if matcher.ratio() >= 0.82:
            return True
        if matcher.find_longest_match().size >= max(8, int(smaller_len * 0.72)):
            return True
    return False


def is_usable_spoken_action(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Validate output boundaries without prescribing what the agents say."""
    if not _base._is_usable_utterance(text, "", agent_name, other_name):
        return False
    if _CONTROL_SCAFFOLD.search(text) or _has_pathological_repetition(text):
        return False
    if _MEMORY_SERIALIZATION_LEAK.search(text):
        return False
    if _PEER_META_DRIFT.search(text):
        return False
    if _ASSISTANT_SERVICE_DRIFT.search(text):
        return False
    if _REFUSAL_TEMPLATE_DRIFT.search(text):
        return False
    if not _looks_complete_spoken_turn(text):
        return False
    if not _is_sentence_like_short_turn(text):
        return False

    inbound = str(inbound or "").strip()
    if not inbound:
        return True
    input_words = _base._normalize_words(inbound)
    output_words = _base._normalize_words(text)
    if not input_words or not output_words or input_words == output_words:
        return False
    if _is_ungrounded_short_reference(text, inbound):
        return False
    if len(input_words) >= 5 and len(output_words) >= 5:
        common = len(set(output_words) & set(input_words))
        overlap = common / max(1, len(set(output_words)))
        if overlap > 0.85 and len(output_words) >= len(input_words):
            return False
    return True


def _is_recent_echo(text: str, dialogue_history) -> bool:
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
        if matcher.find_longest_match().size >= max(8, int(smaller_len * 0.65)):
            return True
        if matcher.ratio() >= 0.78:
            return True
        prior_set = set(prior_words)
        shared = len(output_set & prior_set)
        smaller_unique = max(1, min(len(output_set), len(prior_set)))
        if shared / smaller_unique >= 0.88:
            return True
    return False


def _candidate_key(text: str) -> tuple[str, ...]:
    return tuple(_base._normalize_words(str(text or "")))


def generate_spoken_action(
    agent,
    other,
    dialogue_history=None,
    inbound: str = "",
    cognitive_context: str = "",
) -> str:
    """Generate one paper-derived spoken action with adaptive stochastic resampling."""
    prompt = _paper_prompt(agent, other, dialogue_history, inbound, cognitive_context)
    attempts: list[str] = []
    candidate_counts: dict[tuple[str, ...], int] = {}
    unique_attempts = 0
    duplicate_pressure = 0
    previous_hit_limit = False

    for request_index in range(_MAX_COMPLETION_REQUESTS):
        raw, hit_limit = _request_completion(
            prompt,
            agent.name,
            other.name,
            request_index=request_index,
            duplicate_pressure=duplicate_pressure,
            previous_hit_limit=previous_hit_limit,
        )
        previous_hit_limit = hit_limit
        text = _clean_line(raw, agent.name)
        attempts.append(text or str(raw).strip())

        key = _candidate_key(text)
        if key:
            seen = candidate_counts.get(key, 0)
            candidate_counts[key] = seen + 1
            if seen:
                duplicate_pressure = min(6, duplicate_pressure + 1)
                continue
            unique_attempts += 1

        if hit_limit:
            if unique_attempts >= _MAX_UNIQUE_ACT_ATTEMPTS:
                break
            continue

        if (
            is_usable_spoken_action(text, inbound, agent.name, other.name)
            and not _is_recent_echo(text, dialogue_history)
            and not _is_context_dependent_opening(text, inbound, dialogue_history)
            and not _is_private_plan_echo(text, cognitive_context)
            and not _is_retrieved_memory_echo(text, cognitive_context)
        ):
            return text

        if unique_attempts >= _MAX_UNIQUE_ACT_ATTEMPTS:
            break

    previews = " | ".join(repr(text[:220]) for text in attempts[-12:])
    raise RuntimeError(
        f"{agent.name} paper-derived Stanford act produced no usable spoken line after "
        f"{unique_attempts} unique samples / {len(attempts)} completion requests: {previews}"
    )


def research_source() -> str:
    return _RESEARCH_COMMIT
