#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACES = HERE / "workspaces"
REPLAY_DIR = HERE / "replay"
EVIDENCE = REPLAY_DIR / "checkpoint_sanitization.json"

SERVICE_PATTERNS = (
    "how can i help you",
    "how can i assist",
    "need assistance",
    "assist you further",
    "feel free to ask",
    "can't fulfill this request",
    "cannot fulfill this request",
    "can't comply with",
    "cannot comply with",
    "as an ai",
    "as a language model",
)

_WORD_RE = re.compile(r"[a-z']+")
_RUT_IGNORE = {
    "a", "about", "after", "again", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "better", "both", "but", "by", "can", "could",
    "day", "did", "do", "does", "doing", "don't", "dont", "each", "emily", "few", "for", "from",
    "further", "good", "great", "had", "has", "have", "having", "he", "her", "here", "hers", "him",
    "his", "how", "i", "i'm", "i've", "if", "in", "into", "is", "it", "it's", "its", "just", "know",
    "little", "made", "make", "makes", "me", "more", "most", "much", "my", "nice", "no", "nor", "not",
    "now", "of", "off", "olivia", "on", "once", "one", "only", "or", "other", "our", "out", "over",
    "own", "really", "same", "she", "should", "small", "so", "some", "something", "such", "sure", "than",
    "that", "that's", "the", "their", "them", "then", "there", "there's", "these", "they", "thing", "things",
    "think", "this", "those", "though", "through", "to", "too", "under", "until", "up", "very", "was", "way",
    "we", "well", "were", "what", "what's", "when", "where", "which", "while", "who", "why", "will", "with",
    "would", "you", "you're", "your", "yeah",
}


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _message_body(content: str) -> str:
    marker = ": "
    if marker in content and " observes a message from " in content:
        return content.split(marker, 1)[1]
    return content


def _content_terms(content: str) -> set[str]:
    return {
        word
        for word in _WORD_RE.findall(_message_body(content).lower())
        if len(word) >= 4 and word not in _RUT_IGNORE
    }


def _service_poison(content: str) -> bool:
    lowered = content.lower()
    return any(pattern in lowered for pattern in SERVICE_PATTERNS)


def _malformed_reflection(node: dict) -> bool:
    if node.get("node_type") != "reflection":
        return False
    content = str(node.get("content", "")).lstrip()
    return content.startswith("```") or '"reflection"' in content[:200]


def _rut_node_ids(nodes: list[dict]) -> tuple[set[int], list[str]]:
    observations = [node for node in nodes if node.get("node_type") == "observation"]
    recent = observations[-4:]
    if len(recent) < 3:
        return set(), []
    term_sets = [_content_terms(str(node.get("content", ""))) for node in recent]
    counts = Counter(term for terms in term_sets for term in terms)
    dominant = sorted(term for term, count in counts.items() if count >= 3)
    if not dominant:
        return set(), []

    # Quarantine a dominant-word cluster only when the lines themselves are terse. This
    # protects substantive focused conversations while removing short attractor loops.
    remove: set[int] = set()
    accepted_terms: list[str] = []
    for term in dominant:
        members = [
            (node, terms)
            for node, terms in zip(recent, term_sets)
            if term in terms
        ]
        if len(members) < 3:
            continue
        average_terms = sum(len(terms) for _, terms in members) / len(members)
        if average_terms > 4.5:
            continue
        accepted_terms.append(term)
        remove.update(int(node.get("node_id", -1)) for node, _ in members)
    remove.discard(-1)
    return remove, accepted_terms


def sanitize_agent(agent: str) -> dict:
    root = WORKSPACES / agent / "memory_stream"
    nodes_path = root / "nodes.json"
    embeddings_path = root / "embeddings.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    embeddings = json.loads(embeddings_path.read_text(encoding="utf-8"))
    if not isinstance(nodes, list) or not isinstance(embeddings, dict):
        raise RuntimeError(f"Unexpected Stanford memory schema for {agent}.")

    max_time_before = 0
    for node in nodes:
        max_time_before = max(
            max_time_before,
            int(node.get("created", 0) or 0),
            int(node.get("last_retrieved", 0) or 0),
        )

    remove_reasons: dict[int, list[str]] = {}
    for node in nodes:
        node_id = int(node.get("node_id", -1))
        content = str(node.get("content", ""))
        reasons: list[str] = []
        if _service_poison(content):
            reasons.append("service_or_refusal_language")
        if _malformed_reflection(node):
            reasons.append("malformed_reflection_payload")
        if reasons:
            remove_reasons[node_id] = reasons

    # If an early legacy epoch is clearly poisoned, quarantine the whole epoch rather than
    # leaving adjacent generic lines generated by the same bad prompt regime.
    poisoned_early_times = [
        int(node.get("created", 0) or 0)
        for node in nodes
        if int(node.get("node_id", -1)) in remove_reasons
        and int(node.get("created", 0) or 0) <= 10
    ]
    if poisoned_early_times:
        legacy_cutoff = max(poisoned_early_times)
        for node in nodes:
            node_id = int(node.get("node_id", -1))
            if int(node.get("created", 0) or 0) <= legacy_cutoff:
                remove_reasons.setdefault(node_id, []).append("legacy_poisoned_epoch")
    else:
        legacy_cutoff = None

    remaining_for_rut = [
        node for node in nodes if int(node.get("node_id", -1)) not in remove_reasons
    ]
    rut_ids, rut_terms = _rut_node_ids(remaining_for_rut)
    for node_id in rut_ids:
        remove_reasons.setdefault(node_id, []).append("lexical_attractor_rut")

    removed_ids = set(remove_reasons)
    kept = [node for node in nodes if int(node.get("node_id", -1)) not in removed_ids]
    old_to_new: dict[int, int] = {}
    for new_id, node in enumerate(kept):
        old_to_new[int(node.get("node_id", new_id))] = new_id

    sanitized: list[dict] = []
    for new_id, raw in enumerate(kept):
        node = dict(raw)
        node["node_id"] = new_id
        pointer = node.get("pointer_id")
        if isinstance(pointer, list):
            node["pointer_id"] = [
                old_to_new[int(old)] for old in pointer if int(old) in old_to_new
            ]
        sanitized.append(node)

    kept_contents = {str(node.get("content", "")) for node in sanitized}
    sanitized_embeddings = {
        content: vector for content, vector in embeddings.items() if content in kept_contents
    }
    missing_embeddings = [
        content for content in kept_contents if content not in sanitized_embeddings
    ]
    if missing_embeddings:
        raise RuntimeError(
            f"Sanitization would leave {agent} nodes without embeddings: {missing_embeddings[:2]!r}"
        )

    _atomic_json(nodes_path, sanitized)
    _atomic_json(embeddings_path, sanitized_embeddings)
    return {
        "agent": agent,
        "before_nodes": len(nodes),
        "after_nodes": len(sanitized),
        "removed_nodes": len(nodes) - len(sanitized),
        "removed": [
            {"old_node_id": node_id, "reasons": remove_reasons[node_id]}
            for node_id in sorted(remove_reasons)
        ],
        "legacy_cutoff": legacy_cutoff,
        "rut_terms": rut_terms,
        "max_time_before": max_time_before,
    }


def main() -> None:
    restore_path = REPLAY_DIR / "checkpoint_restore.json"
    if not restore_path.is_file():
        return
    restore = json.loads(restore_path.read_text(encoding="utf-8"))
    if restore.get("restored") is not True:
        return
    source_run_id = restore.get("source_run_id")
    if EVIDENCE.is_file():
        try:
            existing = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if (
            existing.get("version") == 1
            and existing.get("source_run_id") == source_run_id
            and existing.get("completed") is True
        ):
            return
    if not WORKSPACES.is_dir():
        raise RuntimeError("Checkpoint restore says restored=true but workspaces are missing.")
    reports = [sanitize_agent(agent) for agent in ("emily", "olivia")]
    time_floor = max((report["max_time_before"] for report in reports), default=0)
    payload = {
        "mode": "checkpoint_sanitization",
        "version": 1,
        "source_run_id": source_run_id,
        "completed": True,
        "time_floor": time_floor,
        "agents": reports,
    }
    _atomic_json(EVIDENCE, payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
