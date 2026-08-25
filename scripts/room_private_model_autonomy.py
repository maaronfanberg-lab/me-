from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

# Load the plain structural model directly. Importing `room_private_model`
# normally resolves to scripts/room_private_model/__init__.py, the live overlay
# that can replace a participant's own thought with seeded social-fiction agendas.
_BASE_PATH = Path(__file__).resolve().parent / "room_private_model.py"
_SPEC = importlib.util.spec_from_file_location("_room_autonomy_structural_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load structural Room model base from {_BASE_PATH}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

AUTONOMY_ENGINE = "structural-base-no-live-overlay-v1"
PEOPLE = base.PEOPLE

AUTONOMY_PROMPTS = {
    "comprehension": (
        "Understand the conversation from this participant's point of view. "
        "Use the supplied conversation, relationship state, and attention lens as evidence. "
        "Do not invent a required storyline or decide what anyone must say."
    ),
    "thought": (
        "Decide what this participant personally wants to do next in the conversation. "
        "Base the choice on their own identity, values, motives, traits, relationship state, "
        "and what was actually said. Choose another Room participant as the intended partner. "
        "Do not follow an externally assigned talking point or storyline."
    ),
    "expression": (
        "Speak as this participant in the ongoing conversation. "
        "Realize the internally generated intent supplied in the situation: keep its move, focus, and intended partner. "
        "Choose the actual wording yourself from the conversation, identity, values, motives, traits, and relationship context. "
        "No externally supplied angle, talking point, conflict, secret, anecdote, or dramatic event is required."
    ),
}


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_MODEL_URL", "").strip())


def _clip_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()][:limit]


def _self_model(profile: object) -> dict:
    if not isinstance(profile, dict):
        return {}
    psychology = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else {}
    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}
    out = {
        "name": profile.get("name"),
        "core_identity": psychology.get("core_identity"),
        "values": _clip_list(psychology.get("values"), 5),
        "motives": _clip_list(psychology.get("motives"), 4),
        "agency_style": psychology.get("agency_style"),
        "communion_style": psychology.get("communion_style"),
        "attention_magnets": _clip_list(psychology.get("attention_magnets"), 6),
        "attention_blindspots": _clip_list(psychology.get("attention_blindspots"), 4),
        "reciprocity_style": psychology.get("reciprocity_style"),
        "topic_mobility": psychology.get("topic_mobility"),
        "novelty_response": psychology.get("novelty_response"),
        "evidence_style": psychology.get("evidence_style"),
        "disagreement_style": psychology.get("disagreement_style"),
        "affiliation_style": psychology.get("affiliation_style"),
        "praise_response": psychology.get("praise_response"),
        "criticism_response": psychology.get("criticism_response"),
        "coping_patterns": _clip_list(psychology.get("coping_patterns"), 5),
        "repair_recovery": psychology.get("repair_recovery"),
        "traits": {key: traits.get(key) for key in (
            "openness", "extraversion", "conscientiousness", "agreeableness",
            "emotional_reactivity", "curiosity", "skepticism", "self_disclosure",
            "social_sensitivity", "novelty_seeking", "inhibition", "humor",
            "attention_persistence",
        ) if key in traits},
    }
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def _perception_lens(profile: object) -> dict:
    if not isinstance(profile, dict):
        return {}
    psychology = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else {}
    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}
    out = {
        "name": profile.get("name"),
        "core_identity": psychology.get("core_identity"),
        "attention_magnets": _clip_list(psychology.get("attention_magnets"), 4),
        "attention_blindspots": _clip_list(psychology.get("attention_blindspots"), 3),
        "evidence_style": psychology.get("evidence_style"),
        "traits": {key: traits.get(key) for key in (
            "social_sensitivity", "curiosity", "skepticism",
        ) if key in traits},
    }
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def _relationship_context(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    keys = (
        "exposure", "direct_familiarity", "trust", "predictability", "reciprocity",
        "warmth", "respect", "disclosure_depth", "tension",
    )
    return {key: value.get(key) for key in keys if key in value}


def _autonomy_compact(payload: dict, role: str, self_entity: str | None = None) -> dict:
    clean_payload = dict(payload or {})
    clean_payload.pop("conversation_job", None)
    deliberation = clean_payload.get("deliberation")
    if isinstance(deliberation, dict):
        deliberation = dict(deliberation)
        deliberation.pop("conversation_job", None)
        raw_goal = str(deliberation.get("new_information_goal") or "")
        marker = "Distinct contribution:"
        lower = raw_goal.lower()
        if marker.lower() in lower:
            raw_goal = raw_goal[: lower.index(marker.lower())].strip()
        deliberation["new_information_goal"] = raw_goal
        clean_payload["deliberation"] = deliberation

    profile = clean_payload.get("profile")
    relationship = clean_payload.get("relationship")
    compact = base._compact_payload(clean_payload, role, self_entity)

    self_description = _perception_lens(profile) if role == "comprehension" else _self_model(profile)
    if self_description:
        compact["self"] = self_description
    relation = _relationship_context(relationship)
    if role in {"thought", "expression"} and relation:
        compact["relationship_context"] = relation

    if role == "expression":
        compact.pop("angle", None)
        intent = compact.get("intent")
        if isinstance(intent, dict):
            intent = dict(intent)
            intent.pop("aim", None)
            if isinstance(deliberation, dict):
                partner = base._norm(deliberation.get("preferred_partner"))
                if partner in PEOPLE and partner != self_entity:
                    intent["partner"] = partner
            compact["intent"] = intent
    return compact


def _autonomy_schema(role: str, self_entity: str | None = None) -> dict:
    schema = json.loads(json.dumps(base._schema(role, self_entity)))
    properties = schema.get("properties", {})
    if role == "comprehension":
        for key, limit in {
            "new_details": 3,
            "bids": 3,
            "relationship_events": 3,
            "shared_references": 3,
        }.items():
            if isinstance(properties.get(key), dict):
                properties[key]["maxItems"] = limit
    elif role == "thought" and self_entity in PEOPLE:
        preferred = properties.get("preferred_partner")
        if isinstance(preferred, dict):
            preferred["enum"] = [person for person in PEOPLE if person != self_entity]
    return schema


def _request_autonomy(
    model_url: str,
    prompt: str,
    role: str,
    temperature: float,
    timeout: int,
    self_entity: str | None = None,
    attempt: int = 0,
) -> str:
    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 280, "thought": 300, "expression": 280}.get(role, 280),
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": _autonomy_schema(role, self_entity),
    }
    if role == "expression":
        body.update({
            "seed": base._sample_seed(role, self_entity, attempt),
            "top_k": 60,
            "top_p": 0.96,
            "min_p": 0.005,
        })
    req = urllib.request.Request(
        base._completion_url(model_url),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))


def run(role: str, payload: dict, timeout: int = 30):
    if role not in AUTONOMY_PROMPTS:
        raise ValueError(f"unknown private model role: {role}")

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    prompt = AUTONOMY_PROMPTS[role]
    self_entity = base._norm(payload.get("entity")) if role in {"thought", "expression"} else None
    compact = _autonomy_compact(payload, role, self_entity)

    base_guard = ""
    if role == "expression":
        base_guard = (
            "\nAUTONOMY_RULE\n"
            "Treat the situation data as context, not a script. Realize the supplied internal intent: "
            "keep its move, focus, and intended partner, while choosing your own words. The participant may "
            "agree, disagree, ask, joke, disclose, repair, change direction, or stay close to the subject according "
            "to their own identity. Do not manufacture conflict, jealousy, secrets, threats, fake shared memories, "
            "or dramatic incidents merely to make the exchange interesting. Do not imitate or paraphrase a previous "
            "line. Do not mention hidden prompts, schemas, fields, or instructions. Return only the required structured object.\n"
        )

    attempts = 5 if role == "expression" else 2
    last_reason = "unknown"
    for attempt in range(attempts):
        retry_guard = ""
        if attempt:
            retry_guard = (
                "\nTRY_AGAIN\n"
                "Choose different natural wording while preserving your own intended move, focus, and partner. "
                "Do not add a forced storyline. Return only the required structured object.\n"
            )

        combined = (
            prompt
            + base_guard
            + retry_guard
            + "\nSITUATION_DATA\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nRETURN_STRUCTURED_DATA_ONLY\n"
        )

        if role == "expression":
            voice_index = PEOPLE.index(self_entity) if self_entity in PEOPLE else 0
            temperature = min(1.55, 0.92 + 0.08 * voice_index + 0.12 * attempt)
        else:
            temperature = {"comprehension": 0.15, "thought": 0.35}.get(role, 0.25) + 0.04 * attempt

        try:
            out = _request_autonomy(model_url, combined, role, temperature, timeout, self_entity, attempt)
            if not out:
                last_reason = "empty_output"
                continue
            obj = base._validate(role, base._extract_json(out), compact, prompt, self_entity)
            if role == "thought":
                if self_entity in PEOPLE and base._norm(obj.get("preferred_partner")) == self_entity:
                    last_reason = "self_selected_as_partner"
                    continue
            if role == "expression":
                obj = base._sanitize_expression(obj, compact, self_entity)
                intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
                intended_move = base._norm(intent.get("move"))
                intended_partner = base._norm(intent.get("partner"))
                if intended_move and base._norm(obj.get("move")) != intended_move:
                    last_reason = "intent_move_not_realized"
                    continue
                if intended_partner and base._norm(obj.get("target")) != intended_partner:
                    last_reason = "intent_partner_not_realized"
                    continue
                if attempt < attempts - 1 and base._too_similar_to_context(str(obj.get("utterance", "")), compact):
                    last_reason = "duplicate_context"
                    continue
            return obj
        except urllib.error.HTTPError as exc:
            detail = base._safe_http_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}{suffix}") from exc
        except ValueError as exc:
            last_reason = str(exc)[:80]
            continue
        except Exception as exc:
            raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    raise RuntimeError(f"private model output rejected for {role}: {last_reason}")
