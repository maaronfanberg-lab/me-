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
if "allen" not in _private_model.PEOPLE:
    _private_model.PEOPLE = [*_private_model.PEOPLE, "allen"]

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
        "Write this person's next natural conversational reply. Ground it in the newest spoken line when there "
        "is one. Let personality shape perspective and tone. Keep it concise, usually one to three sentences, "
        "and add something that has not already been said."
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
    last_reason = "unknown"
    for attempt in range(attempts):
        retry = ""
        if attempt:
            retry = "\nUse a different idea and wording while staying with the same conversation. Keep the reply concise and grammatically complete."
        combined = (
            instruction
            + retry
            + "\nCONVERSATION\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nRESPONSE\n"
        )
        if role == "expression":
            voice_index = _private_model.PEOPLE.index(self_entity) if self_entity in _private_model.PEOPLE else 0
            temperature = min(1.28, 0.88 + 0.06 * voice_index + 0.09 * attempt)
        else:
            temperature = {"comprehension": 0.15, "thought": 0.25}.get(role, 0.25) + 0.04 * attempt
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
    if role == "expression":
        intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
        move = str(intent.get("move") or "disagree").strip().lower()
        people = [p for p in _private_model.PEOPLE if p != self_entity]
        partner = str(intent.get("partner") or "").strip().lower()
        if partner not in people:
            partner = people[_private_model._sample_seed("volatile_fallback_partner", self_entity, 0) % len(people)]
        name = partner.capitalize()
        fresh_fn = getattr(_private_model, "_fresh_subject", None)
        if callable(fresh_fn):
            subject = str(fresh_fn(self_entity))
        else:
            discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
            subject = str(discussion.get("subject") or "the thing nobody is admitting")

        pools = {
            "sarah": {
                "disagree": [
                    f"{name}, don't give me that shit. You go cold for five minutes and act like I'm supposed to pretend I don't notice.",
                    f"{name}, that's bullshit. You don't get to dismiss me and then act surprised when I get angry about {subject}.",
                ],
                "disclose": [
                    f"{name}, I'm jealous, and I hate how much I still want your attention after {subject}.",
                    f"I hate admitting this, {name}, but I'm scared you'll pick everyone else over me, and {subject} made it worse.",
                ],
                "callback": [
                    f"{name}, remember {subject}? You promised me you'd never pull that stunt again, and I'm still pissed.",
                    f"{name}, don't pretend {subject} didn't happen. I remember exactly what you said to me afterward.",
                ],
                "repair": [
                    f"{name}, I'm furious, but don't walk away. I need you to tell me why {subject} keeps getting between us.",
                    f"{name}, I still want you here even though I'm pissed. Stop dodging me and talk about {subject}.",
                ],
            },
            "mara": {
                "disagree": [
                    f"{name}, that's bullshit. You couldn't bluff your way through {subject} if Herman handed you cue cards.",
                    f"{name}, you're wrong and smug about it, which is almost impressive. Explain {subject} without embarrassing yourself.",
                ],
                "compare": [
                    f"{name}, Jules handled {subject} better than you did, and watching you pretend otherwise is embarrassing.",
                    f"Between you and Sarah, {name}, you're the weaker liar about {subject}. At least she commits to the story.",
                ],
                "disclose": [
                    f"I hate admitting this, but {name}, I was jealous when you took over {subject}. I wanted the room looking at me.",
                    f"Fine, {name}, I wanted to win your attention during {subject}, and I resented everyone who got it first.",
                ],
                "close": [
                    f"Enough, {name}. This is beneath me. If we're going to talk, explain {subject} instead of boring me.",
                    f"I'm done with this tedious little performance, {name}. Tell me what really happened with {subject}.",
                ],
            },
            "owen": {
                "disagree": [
                    f"{name}, you're lying about {subject}. I don't buy the innocent act for a second.",
                    f"No, {name}. That's bullshit, and {subject} is exactly why I don't trust your version of anything.",
                ],
                "callback": [
                    f"{name}, I haven't forgotten {subject}. You changed your story twice and I still think you were hiding something.",
                    f"{name}, {subject} is still an open grudge. You never explained the part that made you look guilty.",
                ],
                "compare": [
                    f"{name}, this is exactly like {subject}: you act confused when it's convenient and expect everyone else to swallow it.",
                    f"You're worse at hiding motives than Mara, {name}. {subject} proved that already.",
                ],
                "close": [
                    f"I'm done with this, {name}. I don't trust where you're taking it. Tell me what really happened with {subject}.",
                    f"Enough, {name}. I'm not following you down another bullshit detour. Explain {subject} or drop it.",
                ],
            },
            "jules": {
                "disagree": [
                    f"{name}, that's boring bullshit. If you want me to believe you, explain {subject} without hiding behind that polite little act.",
                    f"Nope, {name}. You're being painfully safe. Tell me why {subject} happened or at least invent a better lie.",
                ],
                "disclose": [
                    f"{name}, fine, I'm jealous. I wanted your attention, and {subject} made it worse.",
                    f"Here's the ugly truth, {name}: I liked the chaos around {subject} because everyone finally stopped being boring.",
                ],
                "bridge": [
                    f"Forget this. {name}, Herman just texted me about {subject}, and apparently one of us is banned from Duluth again.",
                    f"New problem, {name}: {subject} is back, Herman is involved, and I absolutely refuse to behave normally about it.",
                ],
                "callback": [
                    f"{name}, don't pretend {subject} never happened. You were there, I was there, and the flamingo was definitely not ours.",
                    f"{name}, {subject} happened and you know it. I'm bringing it up because your face is funnier when you panic.",
                ],
            },
        }
        entity_pool = pools.get(self_entity, {})
        choices = entity_pool.get(move) or [f"{name}, I'm done pretending this is normal. Explain {subject}; I know you're leaving something out."]
        utterance = choices[_private_model._sample_seed("volatile_fallback_line", self_entity, 0) % len(choices)]
        print(f"Room volatile expression fallback used for {self_entity}/{move}: {last_reason}")
        return {
            "decision": "SPEAK",
            "target": partner,
            "move": move if move in {"answer","deepen","disclose","compare","disagree","repair","support","callback","bridge","close"} else "disagree",
            "utterance": utterance,
            "semantic_terms": [subject[:80]],
        }
    raise RuntimeError(f"private model output rejected for {role}: {last_reason}")


_private_model.run = _private_run

import room_engine_v5_core as _core


class _ParticipantAwareOrder(tuple):
    """Iterate over four generators; treat Allen as a legal interlocutor."""

    def __contains__(self, item):
        return str(item or "").lower() == "allen" or super().__contains__(item)


_AI_ORDER = tuple(_core.ORDER)
ORDER = _ParticipantAwareOrder(_AI_ORDER)
PARTICIPANTS = _AI_ORDER + ("allen",)
_core.ORDER = ORDER

_ALLEN_RELATIONSHIP = {
    "exposure": 0.18,
    "direct_familiarity": 0.10,
    "trust": 0.10,
    "predictability": 0.10,
    "reciprocity": 0.10,
    "warmth": 0.10,
    "respect": 0.12,
    "disclosure_depth": 0.0,
    "tension": 0.0,
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


def _second_voice_engages_allen(key):
    """Deterministic 75% gate so beat retries preserve the same routing."""
    return hashlib.sha256(f"allen-second-voice:{key}".encode()).digest()[0] < 192


# The expression phase is sequential. Rank 0 always answers Allen when Allen is
# the latest public event. Rank 1 stays with Allen on a deterministic 75% gate,
# which makes two responders usual without turning every interruption into a
# four-voice chorus. Ranks 2-3 remain unconstrained.
_original_recurrent = _core.recurrent


def _participant_recurrent(node, key, bus_data):
    try:
        entity, _local, role, _tasks = _core.ni(node)
        rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        source = _core.rp(bus_data, entity, role) if role == "expression" else None
        base = (source or {}).get("private") or {}
        latest = base.get("event") if isinstance(base.get("event"), dict) else None
        allen_latest = bool(
            role == "expression"
            and base.get("partner") == "allen"
            and latest
            and latest.get("speaker") == "allen"
        )
        primary_allen_reply = bool(allen_latest and rank == 0)
        secondary_allen_reply = bool(allen_latest and rank == 1 and _second_voice_engages_allen(key))
        routed_allen_reply = primary_allen_reply or secondary_allen_reply
    except Exception:
        routed_allen_reply = False
        primary_allen_reply = False
        secondary_allen_reply = False
        entity = None

    if not routed_allen_reply:
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
    if secondary_allen_reply:
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