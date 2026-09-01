#!/usr/bin/env python3
"""Reflection-memory hygiene for the Emily + Olivia Stanford runtime.

The local BitNet model occasionally returns parser scaffolding or malformed JSON
where Stanford expects one natural-language reflection string. Such output is
not cognition and must never become durable autobiographical memory.

This module does not generate, rewrite, or replace memories. It only removes
malformed reflection nodes while preserving observations and clean reflections.
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


def sanitize_memory_stream(memory_stream) -> list[str]:
    """Remove malformed reflection nodes and rebuild Stanford's indices.

    Returns the removed reflection contents as diagnostic evidence. No new
    content is generated and observation nodes are never removed here.
    """
    original_nodes = list(memory_stream.seq_nodes)
    kept = []
    removed: list[str] = []
    old_to_new: dict[int, int] = {}

    for node in original_nodes:
        old_id = int(getattr(node, "node_id", len(kept)))
        if getattr(node, "node_type", None) == "reflection" and not is_clean_reflection_text(
            getattr(node, "content", None)
        ):
            removed.append(str(getattr(node, "content", ""))[:500])
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
