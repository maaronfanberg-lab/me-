from __future__ import annotations

import json
import os
import urllib.error

import room_private_model as base

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

    # The legacy engine may attach a rotating conversation job to the payload and
    # append it to new_information_goal. It is useful for anti-repetition, but it
    # also tells the speaker what contribution to make. Strip that external
    # assignment before inference while preserving the participant's own thought.
    clean_payload.pop("conversation_job", None)
    deliberation = clean_payload.get("deliberation")
    if isinstance(deliberation, dict):
        deliberation = dict(deliberation)
        deliberation.pop("conversation_job", None)
        raw_goal = str(deliberation.get("new_information_goal") or "")
        marker = "Distinct contribution:"
        if marker.lower() in raw_goal.lower():
            lower = raw_goal.lower()
            raw_goal = raw_goal[: lower.index(marker.lower())].strip()
        deliberation["new_information_goal"] = raw_goal
        clean_payload["deliberation"] = deliberation

    compact = base._compact_payload(clean_payload, role, self_entity)
    if role == "expression":
        compact.pop("angle", None)
        intent = compact.get("intent")
        if isinstance(intent, dict):
            # Keep move/focus chosen by the participant's thought node, but do not
            # hand expression a sentence-level content assignment.
            intent = dict(intent)
            intent.pop("aim", None)
            compact["intent"] = intent
    return compact


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
            out = base._request(model_url, combined, role, temperature, timeout, self_entity, attempt)
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
