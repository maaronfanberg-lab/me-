#!/usr/bin/env python3
from __future__ import annotations

"""Select the lean autonomy-v2 model path only for the Llama Room brain."""

import copy
import json
import os
import re

import room_engine_v5_legacy as _legacy
import room_social_v5 as _social
import room_topic_bounded as _bounded_topic

LEGACY_RETRY_POLICY = 'attempts = 9 if role == "expression" else 2'
_AUTONOMOUS = set(_social.ORDER)
_SLEEPING_ENTITIES = {
    str(entity).strip().lower()
    for entity in (_legacy._core.CFG.get("sleeping_entities") or [])
    if str(entity).strip()
}
_AWAKE_AUTONOMOUS = _AUTONOMOUS - _SLEEPING_ENTITIES
_AWAKE_PARTICIPANTS = _AWAKE_AUTONOMOUS | {"allen"}


def _awake_choose_partner(entity, minds, topic, cycle):
    """Choose only among participants who are present in the Room right now."""
    scored = []
    for other in _social.ORDER:
        if other == entity or other in _SLEEPING_ENTITIES:
            continue
        relationship = minds["entities"][entity]["people"][other]
        strength = (
            .20 * relationship.get("direct_familiarity", 0)
            + .12 * relationship.get("trust", 0)
            + .10 * relationship.get("reciprocity", 0)
            + .08 * relationship.get("respect", 0)
            + .06 * relationship.get("warmth", 0)
            - .10 * relationship.get("tension", 0)
        )
        last = int(relationship.get("last_direct_cycle") or 0)
        gap = max(0, cycle - last)
        novelty = min(1., gap / 40.)
        recent = sum(
            1 for event in relationship.get("events", [])
            if int(event.get("cycle", -999999)) >= cycle - 24
        )
        saturation = min(.42, .045 * recent)
        jitter = _social.randomish(entity, other, cycle)
        scored.append((.18 + .55 * strength + .38 * novelty - saturation + jitter, other))
    if not scored:
        raise RuntimeError(f"no awake Room partner available for {entity}")
    return max(scored)[1]


# Sleeping entities remain in persisted topology/history, but are not present to
# awake agents while asleep.
_social.choose_partner = _awake_choose_partner
_legacy._core.choose_partner = _awake_choose_partner

_DISCOURSE_CUE_NOISE = {
    "despite", "although", "though", "however", "nevertheless", "nonetheless",
    "whereas", "therefore", "thus", "hence", "moreover", "furthermore",
    "instead", "otherwise", "anyway", "regardless", "meanwhile", "yet",
    "appreciate", "appreciates", "appreciated", "appreciating", "appreciation",
}
_CUE_STOPWORDS = {
    "about", "after", "again", "also", "because", "been", "before", "being", "between",
    "could", "does", "doing", "each", "from", "have", "here", "into", "just", "more",
    "most", "much", "only", "other", "ourselves", "should", "some", "still", "than", "that",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "very",
    "want", "what", "when", "where", "whether", "which", "while", "with", "without", "would",
    "your", "yourselves",
    "notice", "noticed", "noticing", "share", "shared", "sharing", "think", "thinking",
    "thought", "feel", "feels", "feeling", "felt", "seem", "seems", "seemed", "say", "said",
    "saying", "tell", "telling", "talk", "talked", "talking", "discuss", "discussed",
    "discussing", *_DISCOURSE_CUE_NOISE,
}
_TOPIC_SCAFFOLD = {
    "i", "i'm", "i've", "i'll", "i'd", "you", "you're", "you've", "you'll", "you'd",
    "we", "we're", "we've", "we'll", "we'd", "they", "they're", "they've", "they'll", "they'd",
}
_TOPIC_FILLER = {
    "hey", "hi", "hello", "sorry", "thanks", "thank", "please", "okay", "yeah", "yes", "no",
    "last", "happened", "happen", "help", "stuck", "honey", "today", "tonight", "yesterday",
    "tomorrow", "really", "just", "maybe", "probably", "actually", "well",
    "notice", "noticed", "noticing", "share", "shared", "sharing", "think", "thinking",
    "thought", "feel", "feels", "feeling", "felt", "seem", "seems", "seemed", "say", "said",
    "saying", "tell", "telling", "talk", "talked", "talking", "discuss", "discussed",
    "discussing", *_DISCOURSE_CUE_NOISE,
}
_TOPIC_SOCIAL_MOVE_TERMS = {
    "support", "supporting", "supported", "repair", "repairing", "repaired",
    "disagree", "disagreeing", "disagreement", "agree", "agreeing", "agreement",
    "answer", "answering", "answered", "callback", "compare", "comparing", "compared",
    "disclose", "disclosing", "disclosed", "bridge", "bridging", "close", "closing", "closed",
    "ask", "asking", "asked", "question", "questioning", "respond", "responding", "response",
    "apologize", "apologizing", "apology", "reassure", "reassuring",
}
_TOPIC_STATE_TERMS = {
    "glad", "happy", "sad", "sorry", "sure", "unsure", "worried", "worry", "worrying",
    "grateful", "thankful", "overwhelmed", "upset", "angry", "afraid", "scared", "nervous",
    "confused", "comfortable", "uncomfortable", "honest", "open", "okay", "fine",
    "tough", "hard", "difficult", "easy", "rough", "need", "needs", "needed", "needing",
    "want", "wants", "wanted", "wanting",
}


def _semantic_cues(value: object, limit: int = 6) -> list[str]:
    cues: list[str] = []
    for word in re.findall(r"[a-z0-9']+", str(value or "").lower()):
        if len(word) < 4 or word in _CUE_STOPWORDS or word in _TOPIC_SOCIAL_MOVE_TERMS or word in _TOPIC_STATE_TERMS or word in cues:
            continue
        cues.append(word)
        if len(cues) >= limit:
            break
    return cues


def _message_episode(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    cognition = message.get("cognition")
    return str(cognition.get("topic_episode") or "").strip() if isinstance(cognition, dict) else ""


def _poisoned_autonomous_event(message: object) -> bool:
    """Quarantine old model collapse without ever suppressing Allen's input."""
    if not isinstance(message, dict):
        return False
    speaker = str(message.get("speaker") or "").strip().lower()
    if speaker not in _AUTONOMOUS:
        return False
    words = re.findall(r"[a-z0-9']+", str(message.get("text") or "").lower())
    if not words:
        return True
    nonsemantic = _DISCOURSE_CUE_NOISE | _TOPIC_FILLER | _TOPIC_SOCIAL_MOVE_TERMS | _TOPIC_STATE_TERMS
    if all(word in nonsemantic for word in words):
        return True
    counts = {word: words.count(word) for word in set(words)}
    peak = max(counts.values(), default=0)
    return len(words) >= 3 and peak >= 3 and peak / len(words) >= 0.40


def _sanitize_topic_for_model(topic: object) -> dict:
    """Never let a persisted bad facet become model input before commit-time normalization."""
    if not isinstance(topic, dict):
        return {}
    clean = dict(topic)
    root = str(clean.get("root") or "").strip().lower()
    if root and not _bounded_topic._valid_term(root):
        root = ""
    facet = str(clean.get("current_facet") or "").strip().lower()
    if facet and not _bounded_topic._valid_term(facet):
        facet = root
    clean["root"] = root or None
    clean["current_facet"] = facet or root or None
    for key in ("facets", "visited_facets", "recent_terms", "shared_references"):
        values = clean.get(key) if isinstance(clean.get(key), list) else []
        clean[key] = [str(value).strip().lower() for value in values if _bounded_topic._valid_term(value)][:10]
    return clean


def _episode_scoped_payload(payload: dict) -> dict:
    scoped = dict(payload or {})
    topic = _sanitize_topic_for_model(scoped.get("topic"))
    if topic:
        scoped["topic"] = topic
    episode_id = str(topic.get("id") or "").strip() if isinstance(topic, dict) else ""
    if not episode_id:
        return scoped
    context = scoped.get("context")
    if isinstance(context, list):
        scoped["context"] = [
            item for item in context
            if _message_episode(item) == episode_id and not _poisoned_autonomous_event(item)
        ]
    event = scoped.get("event")
    if event is not None and (_message_episode(event) != episode_id or _poisoned_autonomous_event(event)):
        scoped["event"] = None
    return scoped


def _rewrite_prompt_data(prompt: str, transform) -> str:
    marker = "\nSITUATION_DATA\n"
    end_marker = "\nRETURN_STRUCTURED_DATA_ONLY\n"
    if marker not in prompt or end_marker not in prompt:
        return prompt
    before, rest = prompt.split(marker, 1)
    raw, after = rest.split(end_marker, 1)
    try:
        data = json.loads(raw)
    except Exception:
        return prompt
    if not isinstance(data, dict):
        return prompt
    transformed = transform(data)
    return before + marker + json.dumps(transformed, ensure_ascii=False, separators=(",", ":")) + end_marker + after


def _mask_private_context(prompt: str) -> str:
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            data["context"] = [{
                "speaker": item.get("speaker") if isinstance(item, dict) else None,
                "target": item.get("target") if isinstance(item, dict) else None,
                "cues": _semantic_cues(item.get("text") if isinstance(item, dict) else item, limit=5),
            } for item in context]
        return data
    return _rewrite_prompt_data(prompt, transform)


def _mask_expression_transcript(prompt: str) -> str:
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            data["context"] = [{
                "speaker": item.get("speaker") if isinstance(item, dict) else None,
                "target": item.get("target") if isinstance(item, dict) else None,
                "cues": _semantic_cues(item.get("text") if isinstance(item, dict) else item),
            } for item in context]
        event = data.get("event")
        if isinstance(event, dict):
            data["event"] = {
                "speaker": event.get("speaker"), "target": event.get("target"),
                "text": str(event.get("text") or "")[:420], "cues": _semantic_cues(event.get("text")),
            }
        elif event:
            data["event"] = {"speaker": None, "target": None, "cues": _semantic_cues(event)}
        return data
    return _rewrite_prompt_data(prompt, transform)


def _remember_rejected(autonomy, utterance: object) -> None:
    text = str(utterance or "").strip()
    rejected = getattr(autonomy, "_production_rejected_wordings", [])
    if text and text not in rejected:
        rejected.append(text)
    autonomy._production_rejected_wordings = rejected[-3:]


def _sanitize_declared_topic_terms(message: object) -> list[str]:
    cognition = (message or {}).get("cognition") if isinstance(message, dict) else {}
    cognition = cognition if isinstance(cognition, dict) else {}
    values = cognition.get("topic_terms")
    raw_values = values if isinstance(values, list) and values else [str((message or {}).get("text", ""))]
    out: list[str] = []
    participant_names = set(_social.PARTICIPANTS)
    for value in raw_values:
        raw = re.sub(r"\s+", " ", str(value or "").strip().lower())
        if not raw:
            continue
        raw_words = re.findall(r"[a-z][a-z'-]{1,}", raw)
        candidates = _social.words(raw) if (bool(raw_words and raw_words[0] in _TOPIC_SCAFFOLD) or len(raw_words) > 4) else [raw]
        for candidate in candidates:
            candidate = str(candidate or "").strip().lower()
            if (not candidate or candidate in participant_names or candidate in _TOPIC_SCAFFOLD or
                    candidate in _TOPIC_FILLER or candidate in _TOPIC_SOCIAL_MOVE_TERMS or
                    candidate in _TOPIC_STATE_TERMS or not _bounded_topic._valid_term(candidate)):
                continue
            if candidate not in out:
                out.append(candidate)
            if len(out) >= 8:
                return out
    return out


def _llama_model_run(role: str, payload: dict, timeout: int = 30):
    entity = str(payload.get("entity") or "").strip().lower()
    if entity in _SLEEPING_ENTITIES:
        return None
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    import room_private_model_autonomy as autonomy
    autonomy._production_rejected_wordings = []
    payload = _episode_scoped_payload(payload)

    if not hasattr(autonomy, "_production_original_request_autonomy"):
        autonomy._production_original_request_autonomy = autonomy._request_autonomy
        def _production_request_autonomy(model_url, prompt, request_role, temperature, request_timeout,
                                         self_entity=None, attempt=0, intent=None):
            if request_role in {"comprehension", "thought"}:
                prompt = _mask_private_context(prompt)
            elif request_role == "expression":
                prompt = _mask_expression_transcript(prompt)
            rejected = [str(item or "").strip() for item in getattr(autonomy, "_production_rejected_wordings", []) if str(item or "").strip()]
            if request_role == "expression" and attempt > 0 and rejected:
                prompt += ("\nREJECTED_WORDING\nPrevious attempts copied recent speech too closely. Rewrite from scratch while preserving "
                           "the same internal intent. Do not repeat, lightly edit, or closely paraphrase any rejected sentence below. "
                           "Use a different sentence structure and different phrasing.\n" +
                           "\n".join(f"- {item}" for item in rejected[-3:]) + "\nEND_REJECTED_WORDING\n")
            return autonomy._production_original_request_autonomy(model_url, prompt, request_role, temperature, request_timeout, self_entity, attempt, intent)
        autonomy._request_autonomy = _production_request_autonomy

    if not hasattr(autonomy, "_production_original_context_echo"):
        autonomy._production_original_context_echo = autonomy._has_context_echo
        def _production_context_echo(utterance, compact, n=5):
            matched = autonomy._production_original_context_echo(utterance, compact, n=max(8, int(n)))
            if matched:
                _remember_rejected(autonomy, utterance)
            return bool(matched)
        autonomy._has_context_echo = _production_context_echo

    if not hasattr(autonomy.base, "_production_original_too_similar"):
        autonomy.base._production_original_too_similar = autonomy.base._too_similar_to_context
        def _production_too_similar(utterance, compact):
            matched = autonomy.base._production_original_too_similar(utterance, compact)
            if matched:
                _remember_rejected(autonomy, utterance)
            return bool(matched)
        autonomy.base._too_similar_to_context = _production_too_similar

    effective_timeout = min(int(timeout), 10) if role in {"comprehension", "thought"} else timeout
    try:
        return autonomy.run(role, payload, timeout=effective_timeout, min_words=1 if role == "expression" else 5)
    except Exception as exc:
        if role == "thought":
            entity = str(payload.get("entity") or "unknown")
            print(f"Thought fail-soft for {entity}: {type(exc).__name__}: {str(exc)[:120]}")
            return None
        raise


def _coherent_recurrent(node, key, bus_data):
    entity, _local, role, _tasks = _legacy._core.ni(node)
    if role != "expression":
        return _LLAMA_ORIGINAL_RECURRENT(node, key, bus_data)
    routed = copy.deepcopy(bus_data)
    source_part = _legacy._core.rp(routed, entity, role)
    base = source_part.get("private") if isinstance(source_part.get("private"), dict) else {}
    prior = list(_legacy._core.prior_expression_messages(node))
    thought = ((routed.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None
    participants = set(_AWAKE_PARTICIPANTS)
    planned = str((deliberation or {}).get("preferred_partner") or base.get("partner") or "").lower()
    live_partner = planned if planned in participants and planned != entity else None
    live_event = None
    directly_addressed = False
    for message in reversed(prior):
        cognition = message.get("cognition") if isinstance(message, dict) else {}
        target = str(cognition.get("target") or "").lower() if isinstance(cognition, dict) else ""
        speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
        if target == entity and speaker in participants and speaker != entity and not _poisoned_autonomous_event(message):
            live_event, live_partner, directly_addressed = message, speaker, True
            break
    if live_event is None and live_partner:
        for message in reversed(prior):
            if str(message.get("speaker") or "").lower() == live_partner and not _poisoned_autonomous_event(message):
                live_event = message
                break
    if live_event is None and prior:
        for candidate in reversed(prior):
            speaker = str(candidate.get("speaker") or "").lower() if isinstance(candidate, dict) else ""
            if speaker in participants and speaker != entity and not _poisoned_autonomous_event(candidate):
                live_event, live_partner = candidate, speaker
                break
    if live_event is None or not live_partner:
        return _LLAMA_ORIGINAL_RECURRENT(node, key, routed)

    base["event"] = live_event
    base["partner"] = live_partner
    mind = _legacy._core.minds()
    relationship = (((mind.get("entities") or {}).get(entity) or {}).get("people") or {}).get(live_partner) or {}
    base["relationship"] = {field: relationship.get(field) for field in (
        "exposure", "direct_familiarity", "trust", "predictability", "reciprocity",
        "warmth", "respect", "disclosure_depth", "tension") if field in relationship}
    source_part["private"] = base

    if isinstance(deliberation, dict):
        deliberation["preferred_partner"] = live_partner
        text = str(live_event.get("text") or "").rstrip()
        if directly_addressed:
            deliberation["action"] = "ANSWER" if text.endswith("?") else "DEEPEN"
            deliberation["new_information_goal"] = "Respond to the specific message just addressed to you. Acknowledge its concrete point before adding one relevant thought."
            deliberation.pop("conversation_job", None)
        else:
            deliberation["new_information_goal"] = "Pick up the latest speaker's concrete point before adding your own relevant thought. Do not start a separate conversation while another turn is active."

    ordered = [item for item in prior if item is not live_event and not _poisoned_autonomous_event(item)] + [live_event]
    original_prior = _legacy._core.prior_expression_messages
    _legacy._core.prior_expression_messages = lambda _node: ordered
    try:
        return _LLAMA_ORIGINAL_RECURRENT(node, key, routed)
    finally:
        _legacy._core.prior_expression_messages = original_prior


if os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":
    _social._declared_terms = _sanitize_declared_topic_terms
    _bounded_topic._declared_terms = _sanitize_declared_topic_terms
    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run
    _LLAMA_ORIGINAL_RECURRENT = _legacy._core.recurrent
    _legacy._core.recurrent = _coherent_recurrent
    _legacy.recurrent = _coherent_recurrent

for _name in dir(_legacy):
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = getattr(_legacy, _name)


def main():
    if "commit" in globals():
        _legacy.commit = globals()["commit"]
    return _legacy.main()


if __name__ == "__main__":
    main()
