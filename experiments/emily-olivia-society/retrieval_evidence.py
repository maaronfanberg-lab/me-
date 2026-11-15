#!/usr/bin/env python3
"""Read-only serialization of Stanford retrieval metadata for replay evidence.

This module never changes a memory node and never emits memory text. It records
only rank, stable content hash, node identity/type, importance, and timestamps
already present on retrieved Stanford nodes so future offline experiments do not
have to reconstruct those values from a later checkpoint.
"""
from __future__ import annotations

import hashlib
import math
import re


def _content_hash(text: object) -> str:
    normalized = " ".join(str(text or "").strip().split())
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:20]


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    number = float(match.group(0))
    return number if math.isfinite(number) else None


def serialize_retrieval_evidence(nodes, time_step: int) -> list[dict]:
    evidence: list[dict] = []
    for rank, node in enumerate(list(nodes or []), start=1):
        created = _numeric(getattr(node, "created", None))
        last_retrieved = _numeric(getattr(node, "last_retrieved", None))
        importance = _numeric(getattr(node, "importance", None))
        row = {
            "retrieval_rank": rank,
            "content_hash": _content_hash(getattr(node, "content", "")),
            "stanford_node_id": getattr(node, "node_id", None),
            "stanford_node_type": str(getattr(node, "node_type", "") or ""),
            "stanford_importance_raw": importance,
            "stanford_created": int(created) if created is not None else None,
            "stanford_last_retrieved": int(last_retrieved) if last_retrieved is not None else None,
            "observed_time_step": int(time_step),
        }
        evidence.append(row)
    return evidence
