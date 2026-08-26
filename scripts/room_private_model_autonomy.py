from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

# Load the plain structural model directly, bypassing the legacy live overlay.
_BASE_PATH = Path(__file__).resolve().parent / "room_private_model.py"
_SPEC = importlib.util.spec_from_file_location("_room_autonomy_structural_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load structural Room model base from {_BASE_PATH}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

# Allen is a real conversational participant even though only Sarah/Mara/Owen/Jules generate autonomously.
if "allen" not in base.PEOPLE:
    base.PEOPLE = [*base.PEOPLE, "allen"]

AUTONOMY_ENGINE = "structural-base-no-live-overlay-v2"
PEOPLE = base.PEOPLE

AUTONOMY_PROMPTS = {
    "comprehension": (
        "Understand the conversation from this participant's point of view. "
        "Use the supplied conversation, relationship state, and attention lens as evidence. "
        "Base your understanding only on details supported by the conversation."
    ),
    "thought": (
        "Decide what this participant personally wants to do next in the conversation. "
        "Use their own identity, values, motives, attention, relationship state, and what was actually said. "
        "Choose among ANSWER, DEEPEN, DISCLOSE, COMPARE, DISAGREE, REPAIR, SUPPORT, CALLBACK, BRIDGE, or CLOSE. "
        "No move is preferred. SUPPORT is appropriate only when this participant actually wants to reinforce or affiliate. "
        "Choose another Room participant as the intended partner. Choose for yourself what matters next."
    ),
    "expression": (
        "Speak as this participant in the ongoing conversation. "
        "Realize the internally generated intent supplied in the situation: keep its move, focus, and intended partner. "
        "Choose the actual wording yourself from the conversation and this participant's speaking identity. "
        "Use only details supported by the conversation and choose your own wording."
    ),
}


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_MODEL_URL", "").strip())


def _clip_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()][:limit]


def _profile_lens(profile: object, role: str) -> dict:
    if not isinstance(profile, dict):
        return {}
    psychology = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else {}
    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}

    if role == "comprehension":
        out = {
            "name": profile.get("name"),
            "core_identity": psychology.get("core_identity"),
            "attention_magnets": _clip_list(psychology.get("attention_magnets"), 4),
            "attention_blindspots": _clip_list(psychology.get("attention_blindspots"), 2),
            "evidence_style": psychology.get("evidence_style"),
            "traits": {key: traits.get(key) for key in (
                "social_sensitivity", "curiosity", "skepticism"
            ) if key in traits},
        }
    elif role == "thought":
        out = {
            "name": profile.get("name"),
            "core_identity": psychology.get("core_identity"),
            "values": _clip_list(psychology.get("values"), 4),
            "motives": _clip_list(psychology.get("motives"), 3),
            "attention_magnets": _clip_list(psychology.get("attention_magnets"), 4),
            "topic_mobility": psychology.get("topic_mobility"),
            "novelty_response": psychology.get("novelty_response"),
            "evidence_style": psychology.get("evidence_style"),
            "disagreement_style": psychology.get("disagreement_style"),
            "affiliation_style": psychology.get("affiliation_style"),
            "traits": {key: traits.get(key) for key in (
                "curiosity", "skepticism", "self_disclosure", "social_sensitivity",
                "novelty_seeking", "inhibition"
            ) if key in traits},
        }
    else:
        out = {
            "name": profile.get("name"),
            "core_identity": psychology.get("core_identity"),
            "agency_style": psychology.get("agency_style"),
            "communion_style": psychology.get("communion_style"),
            "reciprocity_style": psychology.get("reciprocity_style"),
            "disagreement_style": psychology.get("disagreement_style"),
            "affiliation_style": psychology.get("affiliation_style"),
            "novelty_response": psychology.get("novelty_response"),
            "traits": {key: traits.get(key) for key in (
                "extraversion", "self_disclosure", "social_sensitivity",
                "novelty_seeking", "inhibition", "humor"
            ) if key in traits},
        }
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def _relationship_context(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    keys = (
        "direct_familiarity", "trust", "reciprocity", "warmth", "respect",
        "disclosure_depth", "tension",
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

    self_description = _profile_lens(profile, role)
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


def _autonomy_schema(role: str, self_entity: str | None = None, intent: dict | None = None) -> dict:
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
    elif role == "expression" and isinstance(intent, dict):
        intended_move = base._norm(intent.get("move"))
        move_schema = properties.get("move")
        if intended_move and isinstance(move_schema, dict):
            allowed_moves = set(move_schema.get("enum") or [])
            if intended_move in allowed_moves:
                move_schema["enum"] = [intended_move]
        intended_partner = base._norm(intent.get("partner"))
        target_schema = properties.get("target")
        if intended_partner in PEOPLE and intended_partner != self_entity and isinstance(target_schema, dict):
            target_schema["enum"] = [intended_partner]
    return schema


def _request_autonomy(model_url: str, prompt: str, role: str, temperature: float, timeout: int,
                      self_entity: str | None = None, attempt: int = 0, intent: dict | None = None) -> str:
    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 300, "thought": 220, "expression": 180}.get(role, 180),
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": _autonomy_schema(role, self_entity, intent),
    }
    if role in {"thought", "expression"}:
        body.update({
            "seed": base._sample_seed(role, self_entity, attempt),
            "top_k": 60,
            "top_p": 0.95,
            "min_p": 0.007,
        })
    req = urllib.request.Request(
        base._completion_url(model_url),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _has_context_echo(utterance: str, compact: dict, n: int = 5) -> bool:
    output = _words(utterance)
    if len(output) < n:
        return False
    grams = {tuple(output[i:i + n]) for i in range(len(output) - n + 1)}
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    event = compact.get("event")
    sources = list(context[-5:])
    if event:
        sources.append(event)
    for item in sources:
        text = item.get("text") if isinstance(item, dict) else item
        incoming = _words(text)
        for i in range(max(0, len(incoming) - n + 1)):
            if tuple(incoming[i:i + n]) in grams:
                return True
    return False


def _public_meta_language(utterance: str, compact: dict) -> bool:
    """Reject ungrounded process/scaffold talk while allowing real subjects."""
    if base._contains_meta_language(utterance):
        return True
    low = base._norm(utterance)
    hard_patterns = (
        r"\b(?:prompt|schema|field)\s+(?:says|requires|expects|allows|forces|tells)\b",
        r"\b(?:output|generation|response)\s+(?:format|process|schema)\b",
        r"\b(?:return|output|generate)\s+(?:only\s+)?(?:json|structured\s+(?:data|object))\b",
    )
    if any(re.search(pattern, low) for pattern in hard_patterns):
        return True

    script_process = re.search(
        r"\b(?:focus|stick|follow|ignore|change|rewrite)\b.{0,28}\b(?:the\s+)?script\b",
        low,
    )
    if not script_process:
        return False

    sources = []
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    sources.extend(context[-5:])
    if compact.get("event"):
        sources.append(compact.get("event"))
    evidence = " ".join(
        str(item.get("text") or "") if isinstance(item, dict) else str(item or "")
        for item in sources
    ).lower()
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    evidence += " " + " ".join(str(v or "") for v in discussion.values()).lower()
    return not bool(re.search(r"\b(?:script|screenplay|screenwriter|screenwriting)\b", evidence))


def run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
    if role not in AUTONOMY_PROMPTS:
        raise ValueError(f"unknown private model role: {role}")

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    prompt = AUTONOMY_PROMPTS[role]
    self_entity = base._norm(payload.get("entity")) if role in {"thought", "expression"} else None
    compact = _autonomy_compact(payload, role, self_entity)
    compact_intent = compact.get("intent") if role == "expression" and isinstance(compact.get("intent"), dict) else None

    base_guard = ""
    if role == "expression":
        base_guard = (
            "\nAUTONOMY_RULE\n"
            "Respond naturally to the current conversation. Keep the chosen move, focus, and intended partner while choosing your own words. "
            "Use only details supported by what was actually said. Do not invent unsupported conflict, jealousy, secrets, threats, shared memories, "
            "or dramatic incidents. Avoid copying recent speech. Stay inside the conversation.\n"
        )

    attempts = 3 if role == "expression" else 2
    last_reason = "unknown"
    for attempt in range(attempts):
        retry_guard = ""
        if attempt:
            retry_guard = (
                "\nTRY_AGAIN\n"
                "Use fresh natural wording. Keep the same chosen move, focus, and partner. Base the reply only on what was actually said.\n"
            )

        combined = (
            prompt + base_guard + retry_guard + "\nSITUATION_DATA\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nRETURN_STRUCTURED_DATA_ONLY\n"
        )

        if role == "expression":
            voice_index = PEOPLE.index(self_entity) if self_entity in PEOPLE else 0
            temperature = min(1.35, 0.82 + 0.08 * voice_index + 0.10 * attempt)
        elif role == "thought":
            temperature = 0.72 + 0.06 * attempt
        else:
            temperature = 0.15 + 0.04 * attempt

        try:
            out = _request_autonomy(model_url, combined, role, temperature, timeout,
                                    self_entity, attempt, compact_intent)
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
                intent = compact_intent or {}
                intended_move = base._norm(intent.get("move"))
                intended_partner = base._norm(intent.get("partner"))
                if intended_move and base._norm(obj.get("move")) != intended_move:
                    last_reason = "intent_move_not_realized"
                    continue
                if intended_partner and base._norm(obj.get("target")) != intended_partner:
                    last_reason = "intent_partner_not_realized"
                    continue
                utterance = str(obj.get("utterance") or "").strip()
                if len(utterance.split()) < max(1, int(min_words)):
                    last_reason = "utterance_too_short"
                    continue
                if _public_meta_language(utterance, compact):
                    last_reason = "meta_language"
                    continue
                if base._too_similar_to_context(utterance, compact) or _has_context_echo(utterance, compact):
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
