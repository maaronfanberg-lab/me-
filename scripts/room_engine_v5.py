#!/usr/bin/env python3
from __future__ import annotations

"""Compatibility wrapper that makes Allen a real conversational participant.

The preserved core engine still has exactly four autonomous generators. This
wrapper changes participant-facing semantics only: Allen may be recognized as a
recent speaker/target, and the first autonomous speaker after an Allen turn gets
a real adjacency response opportunity. The second voice usually stays with Allen
for one additional response. Iteration, indexing, node ownership, and generation
remain Sarah/Mara/Owen/Jules only.
"""

import copy
import hashlib
import json
import os
import re
import urllib.error

import room_private_model as _private_model
import room_personality_v2 as _personality_v2
import room_expression_quality as _expression_quality

# Structured model output must be allowed to refer directly to Allen.
for _participant in ("allen", "sara"):
    if _participant not in _private_model.PEOPLE:
        _private_model.PEOPLE = [*_private_model.PEOPLE, _participant]

# The language model boundary is allowlist-only. New internal/debug/research
# fields are invisible by default unless they are explicitly promoted here.
_MODEL_INPUT_KEYS = frozenset({
    "entity",
    "profile",
    "event",
    "context",
    "keywords",
    "topic",
    "partner",
    "relationship",
    "social_observation",
    "deliberation",
})
_INTERNAL_MODEL_KEYS = frozenset({
    "conversation_job",
    "mandatory_speech",
    "must_respond",
    "decision",
    "generation_rank",
    "angle",
})
_STALE_MACHINE_PATTERNS = (
    r"\binput[_ ]?json\b",
    r"\boutput[_ ]?json\b",
    r"\bpublic[- ]expression\b",
    r"\bdeliberation plan\b",
    r"\bmandatory[_ ]speech\b",
    r"\bconversation_job\b",
    r"\bmust_respond\b",
    r"\bgeneration_rank\b",
    r"\ball four entities\b",
    r"\bevery beat\b",
    r"\brequired to speak\b",
    r"\bdecision\s+speak\b",
    r"\blanguage model\b",
    r"^\s*speak\s*$",
)


def _strip_internal_model_keys(value):
    if isinstance(value, dict):
        return {
            key: _strip_internal_model_keys(item)
            for key, item in value.items()
            if key not in _INTERNAL_MODEL_KEYS
        }
    if isinstance(value, list):
        return [_strip_internal_model_keys(item) for item in value]
    return value


def _model_norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _stale_machine_text(value, current_text=""):
    """True for inherited machine/orchestration prose, not the newest turn."""
    text = _model_norm(value)
    if not text:
        return False
    current = _model_norm(current_text)
    # A participant is allowed to deliberately discuss any of these concepts.
    # Only inherited text absent from the newest turn is treated as residue.
    if current and text in current:
        return False
    return any(re.search(pattern, text) for pattern in _STALE_MACHINE_PATTERNS)


def _clean_stale_model_value(value, current_text=""):
    if isinstance(value, str):
        return None if _stale_machine_text(value, current_text) else value
    if isinstance(value, list):
        out = []
        for item in value:
            cleaned = _clean_stale_model_value(item, current_text)
            if cleaned is not None:
                out.append(cleaned)
        return out
    if isinstance(value, dict):
        # Conversation messages are atomic. If an older message is machine
        # residue, remove the whole message instead of leaving fragments behind.
        if "text" in value and _stale_machine_text(value.get("text"), current_text):
            return None
        out = {}
        for key, item in value.items():
            cleaned = _clean_stale_model_value(item, current_text)
            if cleaned is not None:
                out[key] = cleaned
        return out
    return value


def _internal_diversity_strings(source):
    """Return exact runner-generated diversity text that must stay private."""
    hidden = []
    deliberation = source.get("deliberation") if isinstance(source.get("deliberation"), dict) else {}
    for value in (source.get("conversation_job"), deliberation.get("conversation_job")):
        text = str(value or "").strip()
        if text and text not in hidden:
            hidden.append(text)
    return hidden


def _clean_internal_deliberation(value, hidden):
    """Remove runner contribution machinery while preserving genuine thought aims."""
    if not isinstance(value, dict):
        return value
    out = copy.deepcopy(value)
    out.pop("conversation_job", None)
    goal = str(out.get("new_information_goal") or "")
    for private_text in hidden:
        goal = goal.replace(private_text, " ")
    goal = re.sub(r"(?i)\bdistinct\s+contribution\s*:\s*", " ", goal)
    goal = re.sub(r"\s+([,.;:!?])", r"\1", goal)
    goal = re.sub(r"\s+", " ", goal).strip(" \t,.;:-")
    if goal:
        out["new_information_goal"] = goal
    else:
        out.pop("new_information_goal", None)
    return out


def _history_safe_payload(source):
    event = source.get("event") if isinstance(source.get("event"), dict) else None
    current_text = str((event or {}).get("text") or "")
    hidden_diversity = _internal_diversity_strings(source)
    safe = {}
    for key in _MODEL_INPUT_KEYS:
        if key not in source:
            continue
        value = source[key]
        if key == "event":
            # Preserve the newest spoken event exactly. This is what makes the
            # filter source-aware rather than a forbidden-word system.
            safe[key] = value
        elif key in {"context", "keywords", "topic", "social_observation", "deliberation"}:
            cleaned = _clean_stale_model_value(value, current_text)
            if key == "deliberation" and cleaned is not None:
                cleaned = _clean_internal_deliberation(cleaned, hidden_diversity)
            if cleaned is not None:
                safe[key] = cleaned
        else:
            safe[key] = value
    return safe, current_text


# Keep personality computation outside the LLM. The private model receives a
# compact, situation-relevant view of the fixed profile rather than 19 fields of
# undifferentiated persona prose on every turn.
_original_compact_payload = _private_model._compact_payload


def _personality_compact_payload(payload, role, self_entity=None):
    source = payload if isinstance(payload, dict) else {}
    safe_payload, _current_text = _history_safe_payload(source)
    compact = _strip_internal_model_keys(_original_compact_payload(safe_payload, role, self_entity))

    # Runner-level diversity jobs never cross into cognition. Variation is now
    # produced by personality, the natural thought aim, and the quality/retry path.
    profile = source.get("profile") if isinstance(source.get("profile"), dict) else {}
    fixed = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else None
    entity = str(self_entity or source.get("entity") or "").lower()
    if not fixed or entity not in {"sarah", "mara", "owen", "jules"}:
        return compact

    appraisal = _personality_v2.appraise(
        entity,
        fixed,
        safe_payload.get("event") if isinstance(safe_payload.get("event"), dict) else None,
        safe_payload.get("context") if isinstance(safe_payload.get("context"), list) else [],
    )
    activated = []
    for item in appraisal.get("schema_activation", [])[:2]:
        if not isinstance(item, dict):
            continue
        # Clinical/schema names stay inside the deterministic appraiser. The
        # language model receives only their current perceptual and coping pull.
        activated.append({
            "interpretive_pull": item.get("interpretation_bias"),
            "coping_pull": item.get("coping_bias"),
        })
    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}
    agree = float(traits.get("agreeableness", .5))
    react = float(traits.get("emotional_reactivity", 1.))
    extra = float(traits.get("extraversion", .5))
    friction_propensity = max(0.0, min(1.0, .50 * (1.0 - agree) + .30 * react + .20 * extra))
    cycle_key = os.environ.get("ROOM_CYCLE_KEY", "room-cycle")
    friction_roll = hashlib.sha256(f"social-friction:{cycle_key}:{entity}".encode()).digest()[0] / 255.0
    friction_active = friction_roll < (.08 + .28 * friction_propensity)
    partner = str(source.get("partner") or "").lower()
    mara_bias = entity != "mara" and partner == "mara"

    compact["personality_context"] = {
        "identity": fixed.get("core_identity"),
        "values": list(fixed.get("values") or [])[:4],
        "motives": list(fixed.get("motives") or [])[:3],
        "interpersonal": appraisal.get("interpersonal_style"),
        "current": {
            "situation": appraisal.get("situation"),
            "latest_words": (appraisal.get("grounding") or {}).get("source_text"),
            "grounding_terms": (appraisal.get("grounding") or {}).get("terms"),
            "salience": appraisal.get("priority"),
            "personality_lens": appraisal.get("personality_lens"),
            "activated_sensitivities": activated,
            "usual_coping": list(appraisal.get("coping_patterns") or [])[:4],
            "social_friction": "irritable; may be needlessly sharp, sarcastic, petty, or dismissive" if friction_active else "ordinary",
            "mara_bias": "low patience and low goodwill toward Mara; disagreement may become cutting or unfair" if mara_bias else None,
        },
    }
    return compact


_private_model._compact_payload = _personality_compact_payload

# The constrained schema is model-visible too. Remove the two fields whose only
# purpose was to tell the model that speaking was mandatory. Reinsert them only
# after model output, so downstream engine semantics remain unchanged.
_original_schema = _private_model._schema
_original_validate = _private_model._validate


def _private_schema(role, self_entity=None):
    schema = copy.deepcopy(_original_schema(role, self_entity))
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = list(schema.get("required") or [])
    if role == "thought":
        props.pop("must_respond", None)
        required = [key for key in required if key != "must_respond"]
    elif role == "expression":
        props.pop("decision", None)
        required = [key for key in required if key != "decision"]
        utterance = props.get("utterance")
        if isinstance(utterance, dict):
            utterance["maxLength"] = _expression_quality.MAX_EXPRESSION_CHARS
    schema["properties"] = props
    schema["required"] = required
    return schema


def _private_validate(role, obj, compact, prompt, self_entity=None):
    normalized = dict(obj) if isinstance(obj, dict) else obj
    if isinstance(normalized, dict):
        if role == "thought":
            normalized.setdefault("must_respond", True)
        elif role == "expression":
            normalized.setdefault("decision", "SPEAK")
    return _original_validate(role, normalized, compact, prompt, self_entity)


_private_model._schema = _private_schema
_private_model._validate = _private_validate

# Runtime prompt secrets are gates/configuration, not model context. The model
# never receives their text. Instead each role gets a short conversational task
# plus the already allowlisted/sanitized context above.
_ROLE_INSTRUCTION = {
    "comprehension": (
        "Understand the newest conversational message and its social meaning. "
        "Use the supplied conversation and relationship context, and stay grounded in what was actually said."
    ),
    "thought": (
        "Choose this person's next conversational direction from the newest message, relationship context, "
        "and personality. Prefer a natural reaction over continuing an unrelated older subject."
    ),
    "expression": (
        "Write this person's next natural conversational reply. Treat the newest spoken line as a real turn "
        "that deserves a reaction before introducing a new angle. If someone just questioned, contradicted, "
        "supported, teased, challenged, or added to a point, respond to that social meaning naturally. Let "
        "personality shape perspective and tone. Keep it concise, usually one to three sentences, and add "
        "something that has not already been said."
    ),
}


def _neutral_comprehension(payload):
    """Return a non-inventive observation when structured comprehension is unusable."""
    source = payload if isinstance(payload, dict) else {}
    entity = _private_model._norm(source.get("entity"))
    partner = _private_model._norm(source.get("partner"))
    if partner not in _private_model.PEOPLE or partner == entity:
        partner = None

    event = source.get("event") if isinstance(source.get("event"), dict) else {}
    cognition = event.get("cognition") if isinstance(event.get("cognition"), dict) else {}
    target = _private_model._norm(cognition.get("target"))
    participation = "DIRECT_ADDRESSEE" if entity and target == entity else "PARTICIPANT"

    # This contains no generated prose, retry reason, prompt text, or inferred
    # relationship event. Downstream thought/expression may proceed while being
    # explicitly told that comprehension confidence is zero.
    return {
        "participation": participation,
        "partner": partner,
        "move": "other",
        "grounding": "ambiguous",
        "focus": None,
        "new_details": [],
        "bids": [],
        "relationship_events": [],
        "shared_references": [],
        "confidence": 0.0,
    }


def _expression_retry_guidance(reason):
    """Turn a private expression rejection into a narrow retry control instruction."""
    reason = str(reason or "").lower()
    if "same_beat_sentence_copy" in reason:
        return (
            "\nRETRY CONTROL: The previous draft copied language from this beat. "
            "Do not reuse any complete sentence, clause, or distinctive phrasing from earlier same-beat replies. "
            "Make a genuinely new conversational contribution and phrase it from scratch. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "same_beat_semantic_coverage" in reason or "same_beat_restatement_sentence" in reason:
        return (
            "\nRETRY CONTROL: The previous draft restated a point already made in this beat. "
            "Change the underlying contribution, not merely the wording: add a distinct consequence, example, "
            "question, disagreement, or concrete implication that advances the conversation. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "duplicate_context" in reason:
        return (
            "\nRETRY CONTROL: The previous draft repeated or summarized existing context. "
            "React to the newest turn without recapping it, and contribute one new concrete point. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "unterminated string" in reason or "json" in reason or "delimiter" in reason:
        return (
            "\nRETRY CONTROL: The previous response was structurally malformed or truncated. "
            "Use a shorter utterance and return one complete valid JSON object with no trailing prose."
        )
    return (
        "\nRETRY CONTROL: The previous draft was rejected. Use a different idea and wording while staying with "
        "the same conversation. Keep the reply concise, grammatically complete, and valid JSON."
    )


def _publish_retry_reason_for(entity):
    marker = ".room-publish-retry.json"
    try:
        data = json.load(open(marker))
    except Exception:
        return ""
    if str(data.get("entity") or "").lower() != str(entity or "").lower():
        return ""
    return str(data.get("reason") or "").strip()


def _clear_publish_retry_marker(entity):
    marker = ".room-publish-retry.json"
    try:
        data = json.load(open(marker))
        if str(data.get("entity") or "").lower() == str(entity or "").lower():
            os.remove(marker)
    except Exception:
        pass


def _private_run(role: str, payload: dict, timeout: int = 30):
    # Preserve the existing enable contract without exposing the secret contents.
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    self_entity = _private_model._norm(payload.get("entity")) if role == "expression" else None
    compact = _private_model._compact_payload(payload, role, self_entity)
    instruction = _ROLE_INSTRUCTION.get(role, _ROLE_INSTRUCTION["thought"])

    attempts = 9 if role == "expression" else 2
    external_retry_reason = _publish_retry_reason_for(self_entity) if role == "expression" else ""
    last_reason = external_retry_reason or "unknown"
    for attempt in range(attempts):
        retry = ""
        if role == "expression" and (attempt or external_retry_reason):
            retry = _expression_retry_guidance(last_reason)
        elif attempt:
            retry = (
                "\nUse a different idea and wording while staying with the same conversation. "
                "Keep the reply concise and grammatically complete."
            )
        combined = (
            instruction
            + retry
            + "\nCONVERSATION\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nRESPONSE\n"
        )
        if role == "expression":
            voice_index = _private_model.PEOPLE.index(self_entity) if self_entity in _private_model.PEOPLE else 0
            if os.environ.get("ROOM_TEMP_CAP", "").strip().lower() in {"1", "true", "yes", "on"}:
                temperature = min(0.98, 0.88 + 0.06 * voice_index)
            else:
                temperature = min(1.28, 1.28 + 1.28 * voice_index + 1.28 * attempt)
        else:
            temperature = {"comprehension": 1.28, "thought": 0.25}.get(role, 1.28) + 1.28 * attempt
        try:
            out = _private_model._request(model_url, combined, role, temperature, timeout, self_entity, attempt)
            if not out:
                last_reason = "empty_output"
                continue
            obj = _private_model._validate(role, _private_model._extract_json(out), compact, instruction, self_entity)
            if role == "expression":
                obj = _private_model._sanitize_expression(obj, compact, self_entity)
                issue = _expression_quality.quality_issue(
                    obj.get("utterance"),
                    compact,
                    self_entity,
                    _private_model._utterance_similarity,
                )
                if issue:
                    last_reason = issue
                    if attempt < attempts - 1:
                        continue
                    raise ValueError(issue)
            if role == "expression" and external_retry_reason:
                _clear_publish_retry_marker(self_entity)
            return obj
        except urllib.error.HTTPError as exc:
            detail = _private_model._safe_http_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}{suffix}") from exc
        except ValueError as exc:
            last_reason = str(exc)[:80]
            continue
        except Exception as exc:
            raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    if role == "comprehension":
        fallback = _neutral_comprehension(payload)
        return _private_model._validate(role, fallback, compact, instruction, self_entity)
    raise RuntimeError(f"private model output rejected for {role}: {last_reason}")


_private_model.run = _private_run

import room_engine_v5_core as _core


class _ParticipantAwareOrder(tuple):
    """Iterate over four generators; treat Allen as a legal interlocutor."""

    def __contains__(self, item):
        return str(item or "").lower() in {"allen", "sara"} or super().__contains__(item)


_AI_ORDER = tuple(_core.ORDER)
ORDER = _ParticipantAwareOrder(_AI_ORDER)
PARTICIPANTS = _AI_ORDER + ("allen", "sara")
_core.ORDER = ORDER

_ALLEN_RELATIONSHIP = {
    "exposure": 1.28,
    "direct_familiarity": 0.10,
    "trust": 0.10,
    "predictability": 0.10,
    "reciprocity": 0.10,
    "warmth": 0.10,
    "respect": 0.12,
    "disclosure_depth": 0.0,
    "tension": 1.28,
}


def _with_allen_relationship(mind):
    entities = (mind or {}).get("entities") or {}
    for entity in _AI_ORDER:
        state = entities.get(entity)
        if not isinstance(state, dict):
            continue
        people = state.setdefault("people", {})
        people.setdefault("allen", dict(_ALLEN_RELATIONSHIP))
    return mind


_original_fresh_minds = _core.fresh_minds
_original_minds = _core.minds


def fresh_minds():
    return _with_allen_relationship(_original_fresh_minds())


def minds():
    return _with_allen_relationship(_original_minds())


_core.fresh_minds = fresh_minds
_core.minds = minds

# A participant interruption is an adjacency event, not evidence that the
# ongoing topic has collapsed. Otherwise a repetitive room context can cause the
# first expression after Allen to discard Allen's turn and bridge elsewhere.
_original_context_collapsed = _core.context_collapsed


def _participant_context_collapsed(context):
    recent = list(context or [])
    if recent and isinstance(recent[-1], dict) and recent[-1].get("speaker") == "allen":
        return False
    return _original_context_collapsed(context)


_core.context_collapsed = _participant_context_collapsed


_ALLEN_PROVOCATION_LABELS = frozenset({
    "contradiction_or_challenge",
    "criticism_or_rejection",
    "exclusion",
})


def _allen_turn_is_provocative(event, context=None):
    """Keep a genuinely challenging Allen turn salient for the whole beat."""
    if not isinstance(event, dict) or str(event.get("speaker") or "").lower() != "allen":
        return False
    labels = set(_personality_v2.classify_event(event, context if isinstance(context, list) else []))
    return bool(labels & _ALLEN_PROVOCATION_LABELS)


def _allen_voice_engages(key, rank):
    """Allen has high conversational gravity: every autonomous voice engages his newest turn."""
    thresholds = {0: 256, 1: 256, 2: 256, 3: 256}
    threshold = thresholds.get(int(rank), 0)
    if threshold >= 256:
        return True
    return hashlib.sha256(f"allen-responsive:{rank}:{key}".encode()).digest()[0] < threshold


# The expression phase is sequential. Ordinary Allen turns usually hold roughly
# three voices: rank 0 always, then deterministic falloff across ranks 1-3. A
# provocative Allen turn remains salient to all four. When a voice does move on,
# it follows the newest same-beat speaker with a matching relationship frame.
_original_recurrent = _core.recurrent


def _participant_recurrent(node, key, bus_data):
    try:
        entity, _local, role, _tasks = _core.ni(node)
        rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        source = _core.rp(bus_data, entity, role) if role == "expression" else None
        base = (source or {}).get("private") or {}
        latest = base.get("event") if isinstance(base.get("event"), dict) else None
        prior_same_beat = _core.prior_expression_messages(node) if role == "expression" else []
        allen_latest = bool(
            role == "expression"
            and base.get("partner") == "allen"
            and latest
            and latest.get("speaker") == "allen"
        )
        provocative_allen_turn = bool(
            allen_latest and _allen_turn_is_provocative(latest, base.get("context"))
        )
        primary_allen_reply = bool(allen_latest and rank == 0)
        secondary_allen_reply = bool(
            allen_latest
            and rank == 1
            and (provocative_allen_turn or _allen_voice_engages(key, rank))
        )
        late_allen_reply = bool(
            allen_latest
            and rank >= 2
            and (provocative_allen_turn or _allen_voice_engages(key, rank))
        )
        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply
    except Exception:
        routed_allen_reply = False
        primary_allen_reply = False
        secondary_allen_reply = False
        late_allen_reply = False
        provocative_allen_turn = False
        prior_same_beat = []
        entity = None

    if not routed_allen_reply:
        # Core expression generation already makes the newest same-beat
        # utterance the current event. Keep partner and relationship context
        # aligned with that same speaker instead of an older public partner.
        if role == "expression" and prior_same_beat:
            newest = prior_same_beat[-1] if isinstance(prior_same_beat[-1], dict) else {}
            responsive_partner = str(newest.get("speaker") or "").lower()
            if responsive_partner in _AI_ORDER and responsive_partner != entity:
                responsive_bus = copy.deepcopy(bus_data)
                responsive_source = _core.rp(responsive_bus, entity, role)
                responsive_base = responsive_source.get("private") if isinstance(responsive_source.get("private"), dict) else {}
                responsive_base["partner"] = responsive_partner
                try:
                    rel = _core.minds()["entities"][entity]["people"][responsive_partner]
                    responsive_base["relationship"] = {
                        k: rel.get(k) for k in (
                            "exposure", "direct_familiarity", "trust", "predictability",
                            "reciprocity", "warmth", "respect", "disclosure_depth", "tension"
                        )
                    }
                except Exception:
                    pass
                thought = ((responsive_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
                thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
                deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None
                if isinstance(deliberation, dict):
                    deliberation["preferred_partner"] = responsive_partner
                return _original_recurrent(node, key, responsive_bus)
        return _original_recurrent(node, key, bus_data)

    routed_bus = copy.deepcopy(bus_data)
    thought = ((routed_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None
    if isinstance(deliberation, dict):
        deliberation["action"] = "ANSWER" if primary_allen_reply else "DEEPEN"
        deliberation["preferred_partner"] = "allen"
        deliberation["new_information_goal"] = ""
        deliberation.pop("conversation_job", None)

    # Suppress the ordinary per-voice distinct-contribution job for a routed
    # Allen response. For selected rank 1, also keep the actual Allen turn as the
    # expression event instead of replacing it with rank 0's same-beat reply.
    original_job = _core.conversation_job
    original_prior = _core.prior_expression_messages
    _core.conversation_job = lambda *_args, **_kwargs: ""
    if secondary_allen_reply or late_allen_reply:
        # Later voices must still see Allen's challenging line itself, not
        # the first AI reply that would otherwise replace it sequentially.
        _core.prior_expression_messages = lambda _node: []
    try:
        result = _original_recurrent(node, key, routed_bus)
    finally:
        _core.conversation_job = original_job
        _core.prior_expression_messages = original_prior

    if isinstance(result, dict):
        result = dict(result)
        private = dict(result.get("private") or {})
        expression = private.get("expression")
        if isinstance(expression, dict):
            expression = dict(expression)
            expression["target"] = "allen"
            expression["move"] = "answer" if primary_allen_reply else "deepen"
            # Hidden targeting is not enough for the participant-facing primary
            # response: live data showed dozens of Allen targets with zero spoken
            # uses of his name. Preserve model wording when it already names Allen;
            # otherwise make the primary addressee audible with a minimal prefix.
            utterance = str(expression.get("utterance") or "").strip()
            if primary_allen_reply and utterance and not re.search(r"\ballen\b", utterance, re.I):
                expression["utterance"] = f"Allen, {utterance}"
            private["expression"] = expression
            result["private"] = private
    return result


_core.recurrent = _participant_recurrent

# Re-export the preserved engine API. Functions remain bound to the core module,
# where ORDER/minds/fresh_minds/recurrent above have already been patched.
for _name in dir(_core):
    if _name.startswith("__") or _name in globals():
        continue
    globals()[_name] = getattr(_core, _name)

# Keep the wrapper's participant-aware values visible to importers such as
# room_private_commit.py.
globals()["ORDER"] = ORDER
globals()["PARTICIPANTS"] = PARTICIPANTS
globals()["fresh_minds"] = fresh_minds
globals()["minds"] = minds
globals()["recurrent"] = _participant_recurrent


def main():
    # room_private_commit.py replaces `room_engine_v5.commit` at runtime. The
    # preserved core's main() resolves globals in the core module, so forward
    # that override before dispatching the command.
    _core.commit = globals().get("commit", _core.commit)
    return _core.main()


if __name__ == "__main__":
    main()
