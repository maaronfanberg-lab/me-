#!/usr/bin/env python3
"""Memory hygiene for the Emily + Olivia Stanford runtime.

The local BitNet model can occasionally return parser scaffolding, malformed
reflection output, or a spoken line that accidentally contains serialized
memory text. None of those artifacts should become durable autobiographical
memory.

This module never generates, rewrites, or replaces memories. It removes only
malformed reflection nodes and demonstrably corrupted message-observation nodes,
while preserving clean observations and clean reflections.
"""
from __future__ import annotations

import re

_PROMPT_OR_FORMAT_MARKERS = (
    '"reflection"',
    "'reflection'",
    '"reasoning"',
    '"action"',
    "item 1:",
    "output format",
    "<commentblockmarker>",
    "what higher-level insight should",
    "what higher-level insights should",
)
_INTERROGATIVE_START = re.compile(
    r"^(?:what|why|how|when|where|who|which|would|could|should|can|do|does|did|is|are|am|was|were|will|have|has|had)\b",
    re.IGNORECASE,
)
_MESSAGE_OBSERVATION = re.compile(
    r"^(?:Emily|Olivia) observes a message from (?:Emily|Olivia):\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_FUSED_OBSERVATION = re.compile(
    r"\|\s*(?:Emily|Olivia)\s+observes(?:\s+a\s+message\s+from|\s+that)\b",
    re.IGNORECASE,
)
_INCOMPLETE_MESSAGE_END = re.compile(
    r"(?:[,;:]|\b(?:because|although|unless|until|while|when|if)\s*|\b(?:feel|felt|seem|seemed)\s+like\s*)$",
    re.IGNORECASE,
)


def is_clean_reflection_text(content: object) -> bool:
    """Return True only for a plausible natural-language reflection insight."""
    if not isinstance(content, str):
        return False
    text = content.strip()
    if not text:
        return False
    if text.startswith(("```", "{", "[", "<")):
        return False
    lowered = text.casefold()
    if any(marker in lowered for marker in _PROMPT_OR_FORMAT_MARKERS):
        return False
    if _FUSED_OBSERVATION.search(text):
        return False
    # Stanford reflection memory should contain an insight, not the model echoing
    # or inventing a focal-point question. Question-shaped nodes are prompt/model
    # scaffolding and become retrieval poison if persisted as autobiographical fact.
    if text.endswith("?") or _INTERROGATIVE_START.match(text):
        return False
    # Reflections are higher-level thoughts. Tiny fragments are almost always a
    # truncated parser/model failure, not a usable insight.
    if len(re.findall(r"\b[\w']+\b", text)) < 5:
        return False
    return True


def is_clean_observation_text(content: object) -> bool:
    """Reject only message observations that are provably serialization/cutoff debris.

    Presence/no-message observations and other normal Stanford observations are
    left alone. For addressed-message observations, a second serialized
    ``Emily/Olivia observes`` clause or a strong truncation suffix proves that
    the delivered model line was not a complete peer utterance.
    """
    if not isinstance(content, str):
        return False
    text = content.strip()
    if not text:
        return False
    match = _MESSAGE_OBSERVATION.match(text)
    if not match:
        return True
    message = match.group(1).strip()
    if not message:
        return False
    if _FUSED_OBSERVATION.search(message):
        return False
    if _INCOMPLETE_MESSAGE_END.search(message):
        return False
    return True


def sanitize_memory_stream(memory_stream) -> list[str]:
    """Remove malformed derived cognition and corrupted message observations.

    Returns removed contents as diagnostic evidence. Nothing is rewritten or
    replaced. Clean observation evidence is preserved; only observations that
    contain serialized peer-memory scaffolding or a strong cutoff marker are
    removed, along with malformed reflections.
    """
    original_nodes = list(memory_stream.seq_nodes)
    kept = []
    removed: list[str] = []
    old_to_new: dict[int, int] = {}

    for node in original_nodes:
        old_id = int(getattr(node, "node_id", len(kept)))
        node_type = getattr(node, "node_type", None)
        content = getattr(node, "content", None)
        invalid = (
            node_type == "reflection" and not is_clean_reflection_text(content)
        ) or (
            node_type == "observation" and not is_clean_observation_text(content)
        )
        if invalid:
            removed.append(str(content or "")[:500])
            continue
        old_to_new[old_id] = len(kept)
        kept.append(node)

    if not removed:
        return []

    for new_id, node in enumerate(kept):
        pointer = getattr(node, "pointer_id", None)
        if isinstance(pointer, list):
            node.pointer_id = [
                old_to_new[int(old_id)]
                for old_id in pointer
                if isinstance(old_id, int) and int(old_id) in old_to_new
            ]
        elif isinstance(pointer, int):
            node.pointer_id = old_to_new.get(pointer)
        node.node_id = new_id

    memory_stream.seq_nodes = kept
    memory_stream.id_to_node = {node.node_id: node for node in kept}

    kept_contents = {
        str(getattr(node, "content", ""))
        for node in kept
        if isinstance(getattr(node, "content", None), str)
    }
    memory_stream.embeddings = {
        content: embedding
        for content, embedding in dict(memory_stream.embeddings).items()
        if content in kept_contents
    }
    return removed
