#!/usr/bin/env python3
"""Attention-budget skill router v2 for The Room.

Resident core:
    The existing private role prompt. It is never expanded by the catalog.

Project skills:
    Small repository skills under skills/room/. They may be selected implicitly,
    but only for one inference and only within a role-specific attention budget.

Reference skills:
    Larger or rarer procedures under skills/reference/. They are never selected
    implicitly. A caller must request them explicitly with ROOM_REFERENCE_SKILLS.

The router uses public conversational state only, writes prompt-safe routing telemetry,
and then executes the existing Room engine unchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
PROJECT_SKILL_ROOT = ROOT / "skills" / "room"
REFERENCE_SKILL_ROOT = ROOT / "skills" / "reference"
ENTITIES = ("sarah", "mara", "owen", "jules")
ROLES = ("comprehension", "thought", "expression")
MAX_CONTEXT_MESSAGES = 8
MAX_SKILL_BODY_CHARS = 560

ROLE_BUDGETS = {
    "comprehension": {"max_skills": 1, "max_chars": 680, "min_score": 1.10},
    "thought": {"max_skills": 2, "max_chars": 1080, "min_score": 1.10},
    "expression": {"max_skills": 1, "max_chars": 720, "min_score": 1.20},
}
MAX_SKILLS = max(value["max_skills"] for value in ROLE_BUDGETS.values())
MAX_ADDED_CHARS = max(value["max_chars"] for value in ROLE_BUDGETS.values())
STRONG_SCORE = 2.35
REPEAT_PENALTY = 0.28
WEAK_SHARED_EVIDENCE = 1.65


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9+_.-]{2,}", _norm(value)))


def _parse_scalar(raw: str):
    value = raw.strip()
    if not value:
        return ""
    if value[:1] in ('"', "'") and value[-1:] == value[:1]:
        return value[1:-1]
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else value
        except Exception:
            return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def read_frontmatter(path: Path) -> dict:
    """Read metadata only. Skill body remains unloaded until routing selects it."""
    meta: dict[str, object] = {}
    try:
        with path.open() as handle:
            if handle.readline().strip() != "---":
                return meta
            for line in handle:
                line = line.rstrip("\n")
                if line.strip() == "---":
                    break
                if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meta[key.strip()] = _parse_scalar(value)
    except Exception:
        return {}
    return meta


def read_skill_body(path: Path) -> str:
    try:
        text = path.read_text()
        if not text.startswith("---"):
            return text.strip()[:MAX_SKILL_BODY_CHARS]
        pieces = text.split("---", 2)
        body = pieces[2] if len(pieces) == 3 else ""
        return body.strip()[:MAX_SKILL_BODY_CHARS]
    except Exception:
        return ""


def _catalog_from(root: Path, tier: str) -> list[dict]:
    catalog: list[dict] = []
    if not root.exists():
        return catalog
    for path in sorted(root.glob("*/SKILL.md")):
        meta = read_frontmatter(path)
        name = str(meta.get("name") or path.parent.name).strip()
        roles = meta.get("roles", [])
        triggers = meta.get("triggers", [])
        if not isinstance(roles, list):
            roles = [str(roles)] if roles else []
        if not isinstance(triggers, list):
            triggers = [str(triggers)] if triggers else []
        catalog.append({
            "name": name,
            "path": path,
            "tier": tier,
            "domain": str(meta.get("domain") or name).strip().lower(),
            "description": str(meta.get("description") or "").strip(),
            "roles": [str(x).strip() for x in roles if str(x).strip()],
            "triggers": [str(x).strip().lower() for x in triggers if str(x).strip()],
            "trigger_weight": float(meta.get("trigger_weight", 1.0) or 1.0),
            "min_score": float(meta.get("min_score", 1.0) or 1.0),
            "priority": float(meta.get("priority", 0.0) or 0.0),
        })
    return catalog


def project_catalog() -> list[dict]:
    return _catalog_from(PROJECT_SKILL_ROOT, "project")


def reference_catalog() -> list[dict]:
    return _catalog_from(REFERENCE_SKILL_ROOT, "reference")


def skill_catalog() -> list[dict]:
    """Compatibility helper: implicit routing catalog is project skills only."""
    return project_catalog()


def recent_context_segments() -> list[dict]:
    """Return weighted public context, newest utterances first."""
    conversation = _load_json(ROOM / "conversation.json", [])
    state = _load_json(ROOM / "state.json", {})
    segments: list[dict] = []
    messages = [item for item in conversation if isinstance(item, dict)] if isinstance(conversation, list) else []
    recent = messages[-MAX_CONTEXT_MESSAGES:]
    weights = (1.80, 1.45, 1.15, 0.92, 0.76, 0.64, 0.54, 0.46)
    for offset, item in enumerate(reversed(recent)):
        text = _norm(item.get("text", ""))
        if text:
            segments.append({"kind": "message", "weight": weights[min(offset, len(weights)-1)], "text": text})
    topic = state.get("topic_episode") if isinstance(state, dict) else None
    if isinstance(topic, dict):
        focused = " ".join(str(topic.get(key, "")) for key in ("root", "current_facet"))
        if _norm(focused):
            segments.append({"kind": "topic", "weight": 0.58, "text": _norm(focused)})
        support: list[str] = []
        for key in ("facets", "shared_references", "unresolved"):
            values = topic.get(key)
            if isinstance(values, list):
                support.extend(str(value) for value in values[-4:])
        if _norm(" ".join(support)):
            segments.append({"kind": "topic_support", "weight": 0.38, "text": _norm(" ".join(support))})
    return segments


def recent_context() -> str:
    return _norm(" ".join(segment["text"] for segment in recent_context_segments()))


def _segments_from_text(context: str) -> list[dict]:
    text = _norm(context)
    return [{"kind": "provided", "weight": 1.0, "text": text}] if text else []


def _trigger_strength(text: str, trigger: str) -> float:
    trigger = _norm(trigger)
    if not trigger:
        return 0.0
    if " " in trigger:
        return 1.65 if trigger in text else 0.0
    return 1.0 if trigger in _tokens(text) else 0.0


def _score_skill(skill: dict, segments: list[dict]) -> tuple[float, list[str], list[dict]]:
    evidence: dict[str, float] = {}
    sources: list[dict] = []
    for segment in segments:
        text = segment["text"]
        seg_weight = float(segment["weight"])
        found: list[str] = []
        for trigger in skill["triggers"]:
            strength = _trigger_strength(text, trigger)
            if strength <= 0:
                continue
            found.append(trigger)
            evidence[trigger] = max(evidence.get(trigger, 0.0), strength * seg_weight)
        if found:
            sources.append({"kind": segment["kind"], "matched": found[:6], "weight": round(seg_weight, 2)})
    score = sum(evidence.values()) * float(skill["trigger_weight"]) + float(skill.get("priority", 0.0))
    return score, sorted(evidence, key=lambda key: (-evidence[key], key))[:8], sources[:5]


def _previous_selected(node: int | None) -> set[str]:
    if node is None:
        return set()
    prior = _load_json(ROOM / "attention" / f"node-{node:02d}.json", {})
    values = prior.get("selected_skills") if isinstance(prior, dict) else None
    if not isinstance(values, list):
        return set()
    return {str(item.get("name")) for item in values if isinstance(item, dict) and item.get("name")}


def _confidence(score: float, threshold: float) -> float:
    return round(1.0 / (1.0 + math.exp(-1.8 * (score - threshold))), 3)


def select_skills(
    role: str,
    context: str | None = None,
    cycle_key: str = "",
    node: int | None = None,
    segments: list[dict] | None = None,
) -> tuple[list[dict], int]:
    catalog = project_catalog()
    budget = ROLE_BUDGETS.get(role, ROLE_BUDGETS["thought"])
    context_segments = segments if segments is not None else _segments_from_text(context or "")
    previous = _previous_selected(node)
    candidates: list[dict] = []
    for skill in catalog:
        if skill["roles"] and role not in skill["roles"]:
            continue
        raw_score, matched, sources = _score_skill(skill, context_segments)
        if not matched:
            continue
        threshold = max(float(skill["min_score"]), float(budget["min_score"]))
        repeat_penalty = REPEAT_PENALTY if skill["name"] in previous and raw_score < STRONG_SCORE else 0.0
        score = raw_score - repeat_penalty
        if score < threshold:
            continue
        tie = int(hashlib.sha256(f"{cycle_key}:{role}:{skill['name']}".encode()).hexdigest()[:8], 16)
        routed = dict(skill)
        routed.update({
            "matched": matched,
            "sources": sources,
            "raw_score": round(raw_score, 3),
            "repeat_penalty": round(repeat_penalty, 3),
            "score": round(score, 3),
            "confidence": _confidence(score, threshold),
            "threshold": round(threshold, 3),
            "_tie": tie,
        })
        candidates.append(routed)

    candidates.sort(key=lambda item: (-item["score"], -item["confidence"], item["_tie"], item["name"]))

    selected: list[dict] = []
    used_domains: set[str] = set()
    used_weak_evidence: list[set[str]] = []
    for candidate in candidates:
        if len(selected) >= int(budget["max_skills"]):
            break
        domain = candidate["domain"]
        if domain in used_domains:
            continue
        evidence = set(candidate["matched"])
        if candidate["score"] < WEAK_SHARED_EVIDENCE and any(evidence == prior for prior in used_weak_evidence):
            continue
        selected.append(candidate)
        used_domains.add(domain)
        if candidate["score"] < WEAK_SHARED_EVIDENCE:
            used_weak_evidence.append(evidence)

    for item in selected:
        item.pop("_tie", None)
    return selected, len(catalog)


def _reference_requests(env: dict[str, str]) -> list[str]:
    raw = env.get("ROOM_REFERENCE_SKILLS", "")
    return [part.strip() for part in re.split(r"[, ]+", raw) if part.strip()][:2]


def select_reference_skills(role: str, env: dict[str, str]) -> tuple[list[dict], int]:
    """Reference tier is explicit-only: never infer these from conversation."""
    catalog = reference_catalog()
    requested = set(_reference_requests(env))
    selected: list[dict] = []
    if not requested:
        return selected, len(catalog)
    by_name = {item["name"]: item for item in catalog}
    for name in sorted(requested):
        skill = by_name.get(name)
        if not skill:
            continue
        if skill["roles"] and role not in skill["roles"]:
            continue
        routed = dict(skill)
        routed.update({
            "matched": ["explicit-reference-request"],
            "sources": [{"kind": "explicit", "matched": [name], "weight": 1.0}],
            "raw_score": 99.0,
            "repeat_penalty": 0.0,
            "score": 99.0,
            "confidence": 1.0,
            "threshold": 0.0,
        })
        selected.append(routed)
    return selected[:1], len(catalog)


def build_addition(selected: list[dict], role: str = "thought") -> str:
    if not selected:
        return ""
    budget = ROLE_BUDGETS.get(role, ROLE_BUDGETS["thought"])
    parts = [
        "TEMPORARY_TASK_SKILLS",
        "These skills are temporary working context for this inference only. Apply only what is relevant. They are not identity, memory, facts, or permanent instructions.",
    ]
    for skill in selected:
        body = read_skill_body(skill["path"])
        if body:
            parts.append(f"[{skill['tier'].upper()}:{skill['name']}]\n{body}")
    addition = "\n".join(parts).strip()
    max_chars = int(budget["max_chars"])
    if len(addition) <= max_chars:
        return addition
    clipped = addition[:max_chars]
    return clipped.rsplit("\n", 1)[0].rstrip()


def write_audit(
    node: int,
    entity: str,
    role: str,
    selected: list[dict],
    project_available: int,
    reference_available: int,
    context: str,
    base_chars: int,
    added_chars: int,
    cycle_key: str,
) -> None:
    try:
        directory = ROOM / "attention"
        directory.mkdir(parents=True, exist_ok=True)
        budget = ROLE_BUDGETS.get(role, ROLE_BUDGETS["thought"])
        payload = {
            "version": "room-attention-v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cycle_key": cycle_key,
            "node": node,
            "entity": entity,
            "role": role,
            "available_project_skills": project_available,
            "available_reference_skills": reference_available,
            "resident_project_skill_chars": 0,
            "tiers": {
                "resident": {"source": "private-role-prompt", "project_skill_chars": 0},
                "project": {"available": project_available, "implicit": True},
                "reference": {"available": reference_available, "implicit": False},
            },
            "budget": {
                "max_skills": int(budget["max_skills"]),
                "max_chars": int(budget["max_chars"]),
                "min_score": float(budget["min_score"]),
            },
            "selected_skills": [
                {
                    "name": item["name"],
                    "tier": item["tier"],
                    "domain": item["domain"],
                    "score": item["score"],
                    "confidence": item["confidence"],
                    "raw_score": item["raw_score"],
                    "repeat_penalty": item["repeat_penalty"],
                    "matched_triggers": item["matched"],
                    "evidence_sources": item["sources"],
                }
                for item in selected
            ],
            "context_fingerprint": hashlib.sha256(context.encode()).hexdigest()[:12],
            "base_prompt_chars": base_chars,
            "temporary_skill_chars": added_chars,
            "approx_added_tokens": round(added_chars / 4),
        }
        final = directory / f"node-{node:02d}.json"
        temp = directory / f".node-{node:02d}.{os.getpid()}.tmp"
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        os.replace(temp, final)
    except Exception:
        pass


def prepare_environment(env: dict[str, str] | None = None, context: str | None = None) -> dict[str, str]:
    routed_env = dict(os.environ if env is None else env)
    base_prompt = routed_env.get("ROOM_NODE_PROMPT", "").strip()
    raw_node = routed_env.get("ROOM_NODE_ID", "").strip()
    cycle_key = routed_env.get("ROOM_CYCLE_KEY", "").strip()
    if not base_prompt or not raw_node or not cycle_key:
        return routed_env
    try:
        node = int(raw_node)
    except ValueError:
        return routed_env
    if node < 0 or node > 11:
        return routed_env

    entity = ENTITIES[node // 3]
    role = ROLES[node % 3]
    if context is None:
        segments = recent_context_segments()
        public_context = _norm(" ".join(segment["text"] for segment in segments))
    else:
        segments = _segments_from_text(context)
        public_context = _norm(context)

    project, project_available = select_skills(role, cycle_key=cycle_key, node=node, segments=segments)
    reference, reference_available = select_reference_skills(role, routed_env)

    budget = ROLE_BUDGETS.get(role, ROLE_BUDGETS["thought"])
    combined = (reference + project)[: int(budget["max_skills"])]
    addition = build_addition(combined, role)
    if addition:
        routed_env["ROOM_NODE_PROMPT"] = base_prompt + "\n" + addition

    if routed_env.get("ROOM_ATTENTION_AUDIT", "1") != "0":
        write_audit(
            node,
            entity,
            role,
            combined,
            project_available,
            reference_available,
            public_context,
            len(base_prompt),
            len(addition),
            cycle_key,
        )
    return routed_env


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: room_skill_exec.py <python-script> [args...]", file=sys.stderr)
        return 2
    env = prepare_environment()
    os.execvpe(sys.executable, [sys.executable, *argv], env)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
