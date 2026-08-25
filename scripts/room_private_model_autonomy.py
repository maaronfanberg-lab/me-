from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

# IMPORTANT: load the plain structural model module directly by file path.
# Importing `room_private_model` normally resolves to scripts/room_private_model/
# __init__.py, which is the live semantic-chaos overlay and can rewrite a
# participant's own thought into seeded shared-fiction agendas. The autonomy
# path must not pass through that layer.
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
        "Use the supplied conversation, relationship state, and traits as evidence. "
        "Do not invent a required storyline or decide what anyone must say."
    ),
    "thought": (
        "Decide what this participant personally wants to do next in the conversation. "
        "Base the choice on their traits, relationship state, memories represented in the situation, "
        "and what was actually said. Do not follow an externally assigned talking point or storyline."
    ),
    "expression": (
        "Speak as this participant in the ongoing conversation. "
        "Choose the actual content yourself from the conversation, your internally generated intent, "
        "your traits, and the relationship context. No externally supplied angle, talking point, conflict, "
        "secret, anecdote, or dramatic event is required."
    ),
}


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_MODEL_URL", "").strip())


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

    compact = base._compact_payload(clean_payload, role, self_entity)
    if role == "expression":
        compact.pop("angle", None)
        intent = compact.get("intent")
        if isinstance(intent, dict):
            intent = dict(intent)
            intent.pop("aim", None)
            compact["intent"] = intent
    return compact


def _request_autonomy(
    model_url: str,
    prompt: str,
    role: str,
    temperature: float,
    timeout: int,
    self_entity: str | None = None,
    attempt: int = 0,
) -> str:
    # The base 192-token comprehension ceiling can cut a larger model's otherwise
    # valid JSON object mid-string. Give structured objects enough completion room
    # while keeping them bounded; the live timing gate is tested independently.
    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 320, "thought": 300, "expression": 280}.get(role, 280),
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": base._schema(role, self_entity),
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
    self_entity = base._norm(payload.get("entity")) if role == "expression" else None
    compact = _autonomy_compact(payload, role, self_entity)

    base_guard = ""
    if role == "expression":
        base_guard = (
            "\nAUTONOMY_RULE\n"
            "Treat the situation data as context, not a script. The participant may agree, disagree, "
            "ask, joke, disclose, repair, change direction, or stay close to the subject according to "
            "their own traits and internally generated intent. Do not manufacture conflict, jealousy, "
            "secrets, threats, fake shared memories, or dramatic incidents merely to make the exchange "
            "interesting. Do not imitate or paraphrase a previous line. Do not mention hidden prompts, "
            "schemas, fields, or instructions. Return only the required structured object.\n"
        )

    attempts = 5 if role == "expression" else 2
    last_reason = "unknown"
    for attempt in range(attempts):
        retry_guard = ""
        if attempt:
            retry_guard = (
                "\nTRY_AGAIN\n"
                "Choose a different natural response based on the participant's own state and the real "
                "conversation. Do not add a forced storyline. Return only the required structured object.\n"
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
            if role == "expression":
                obj = base._sanitize_expression(obj, compact, self_entity)
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
