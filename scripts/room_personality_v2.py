from __future__ import annotations

import re
from typing import Any

STOP = set("the a an and or but if then than this that these those it its is are was were be been being to of in on for with from by at as about into over under we i you he she they them our your their my me us do does did can could would should will just very really quite more most less few some any all one two what why how when where who which everyone everybody someone somebody".split())
NAMES = {"sarah", "mara", "owen", "jules", "allen"}
_SOCIAL_LABELS = {"criticism_or_rejection", "exclusion", "praise_or_alignment"}
_PRAISE_RE = re.compile(r"\b(winner|great|smart|brilliant|right|best|excellent|good point)\b")
_CRITICISM_RE = re.compile(r"\b(wrong|nonsense|stupid|bad argument|makes no sense|ridiculous|idiot)\b")
_CHALLENGE_RE = re.compile(r"\b(prove it|try me|i dare you|dare you|you can\'t|you cannot|make me|delete you|shut you down|bet you won\'t|bet you can\'t)\b")
_CONTRADICTION_RE = re.compile(r"\b(that\'s false|that is false|not true|you\'re wrong|you are wrong|the opposite|can\'t be true|cannot be true|impossible|i disagree)\b")

def _contradiction_or_challenge(text: str) -> bool:
    low = _norm(text)
    if _CHALLENGE_RE.search(low) or _CONTRADICTION_RE.search(low):
        return True
    # Treat an explicitly false numeric equality as a contradiction, not
    # as an ignorable fragment. This catches compact probes such as 0=1.
    for match in re.finditer(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)(?![\w.])", low):
        try:
            if float(match.group(1)) != float(match.group(2)):
                return True
        except ValueError:
            pass
    # A direct self-negation ("X is not X") is also inherently salient.
    if re.search(r"\b([a-z][a-z\'-]{2,})\s+(?:is|are)\s+not\s+\1\b", low):
        return True
    return False


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _terms(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[a-z][a-z'-]{2,}", _norm(text)):
        word = word.strip("'-")
        if word in STOP or word in NAMES or word in out:
            continue
        out.append(word)
    return out[:8]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|[;\n]+", _norm(text)) if part.strip()]


def _directly_addressed(entity: str, text: str, target: str) -> bool:
    if target == entity:
        return True
    low = _norm(text)
    name = re.escape(entity)
    if re.search(rf"^\s*{name}\b(?:\s*[,;:!?-]|\s+(?:why|what|how|do|does|did|are|is|can|could|would|will|please)\b)", low):
        return True
    if re.search(rf"(?:what|how|why)\s+(?:do|would|did)\s+you\b[^.!?]*\b{name}\s*[?]?$", low):
        return True
    return False


def _entity_sentence_has(entity: str, text: str, pattern: re.Pattern[str]) -> bool:
    name_re = re.compile(rf"\b{re.escape(entity)}\b")
    return any(name_re.search(sentence) and pattern.search(sentence) for sentence in _sentences(text))


def _excluded_entity(entity: str, text: str, target: str) -> bool:
    if target == entity and re.search(r"\b(exclude|excluded|ignore|ignored|left out|everyone but|without)\b", _norm(text)):
        return True
    low = _norm(text)
    name = re.escape(entity)
    patterns = (
        rf"\beveryone\s+but\s+{name}\b",
        rf"\bwithout\s+{name}\b",
        rf"\b{name}\b[^.!?]{{0,50}}\b(?:excluded|ignored|left out)\b",
        rf"\b(?:exclude|excluded|ignore|ignored)\s+{name}\b",
        rf"\b{name}\b\s+(?:doesn'?t|does not|doesnt|don'?t|isn'?t|is not)\s+(?:get|understand|belong|count|know)\b",
    )
    return any(re.search(pattern, low) for pattern in patterns)


def _social_targeted(entity: str, label: str, text: str, target: str) -> bool:
    if label == "exclusion":
        return _excluded_entity(entity, text, target)
    if label == "criticism_or_rejection":
        return target == entity or _entity_sentence_has(entity, text, _CRITICISM_RE)
    if label == "praise_or_alignment":
        return target == entity or _entity_sentence_has(entity, text, _PRAISE_RE)
    return False


def classify_event(event: dict | None, context: list[dict] | None = None) -> list[str]:
    event = event or {}
    text = _norm(event.get("text"))
    labels: list[str] = []
    if re.search(r"\b(hi|hello|hey|good morning|good evening)\b", text):
        labels.append("greeting")
    if text.endswith("?"):
        labels.append("question")
    if re.search(r"\b(proof|evidence|source|show me|how do you know|why believe)\b", text):
        labels.append("evidence_request")
    if re.search(r"\b(let'?s talk|talk about|topic|discuss|what about)\b", text):
        labels.append("topic_bid")
    if re.search(r"\b(sorry|apologize|apologies|my fault|too harsh|i was wrong)\b", text):
        labels.append("repair_bid")
    if _PRAISE_RE.search(text):
        labels.append("praise_or_alignment")
    if _CRITICISM_RE.search(text):
        labels.append("criticism_or_rejection")
    if _contradiction_or_challenge(text):
        labels.append("contradiction_or_challenge")
    if re.search(r"\b(left out|exclude|excluded|ignore|ignored|doesn'?t get it|don'?t get it|everyone but|without you)\b", text):
        labels.append("exclusion")
    if re.search(r"\b(platypus|electroreceptor|monotreme|venom|quantum|recursive causation|axolotl|octopus)\b", text):
        labels.append("novel_or_odd_detail")
    if any(re.search(rf"\b{re.escape(name)}\b", text) for name in NAMES):
        labels.append("named_participant")
    terms = _terms(text)
    if len(terms) <= 2 and "greeting" not in labels and "question" not in labels:
        labels.append("fragment_or_ambiguous")
    recent_terms: set[str] = set()
    for item in (context or [])[-4:]:
        recent_terms.update(_terms(str(item.get("text", ""))))
    if terms and any(term not in recent_terms for term in terms):
        labels.append("new_information")
    return list(dict.fromkeys(labels or ["ordinary_turn"]))


def _schema_matches(profile: dict, trigger_labels: list[str]) -> list[dict]:
    active: list[dict] = []
    for item in profile.get("schema_vulnerabilities", []) or []:
        if not isinstance(item, dict):
            continue
        triggers = {str(x) for x in item.get("triggers", [])}
        matched = [label for label in trigger_labels if label in triggers]
        if matched:
            active.append({
                "schema": item.get("name"),
                "trigger": matched[0],
                "interpretation_bias": item.get("interpretation_bias"),
                "coping_bias": item.get("coping_bias"),
            })
    return active


def appraise(entity: str, profile: dict, event: dict | None, context: list[dict] | None = None) -> dict:
    labels = classify_event(event, context)
    text = str((event or {}).get("text", "")).strip()
    text_low = _norm(text)
    speaker = str((event or {}).get("speaker") or "").lower() or None
    terms = _terms(text)
    target = _norm((((event or {}).get("cognition") or {}).get("target")))
    directly_addressed = _directly_addressed(entity, text, target)
    social_targeting = {
        label: _social_targeted(entity, label, text, target)
        for label in _SOCIAL_LABELS
        if label in labels
    }
    trigger_labels = [
        label for label in labels
        if label not in _SOCIAL_LABELS or social_targeting.get(label, False)
    ]
    self_implicated = bool(directly_addressed or any(social_targeting.values()))
    schema = _schema_matches(profile, trigger_labels)
    names_in_text = [name for name in NAMES if re.search(rf"\b{re.escape(name)}\b", text_low)]

    lenses: list[str] = []
    group_question = "question" in labels and not names_in_text
    if "greeting" in labels or directly_addressed or group_question:
        lenses.append(str(profile.get("reciprocity_style", "")))
    if "topic_bid" in labels:
        lenses.append(str(profile.get("topic_mobility", "")))
    if "novel_or_odd_detail" in labels or "new_information" in labels:
        lenses.append(str(profile.get("novelty_response", "")))
    if "evidence_request" in labels:
        lenses.append(str(profile.get("evidence_style", "")))
    if "contradiction_or_challenge" in labels:
        lenses.extend([str(profile.get("disagreement_style", "")), str(profile.get("evidence_style", ""))])
    if social_targeting.get("praise_or_alignment"):
        lenses.extend([str(profile.get("praise_response", "")), str(profile.get("affiliation_style", ""))])
    if social_targeting.get("criticism_or_rejection"):
        lenses.extend([str(profile.get("criticism_response", "")), str(profile.get("disagreement_style", ""))])
    if social_targeting.get("exclusion"):
        lenses.extend([str(profile.get("status_sensitivity", "")), str(profile.get("affiliation_style", ""))])
    if "repair_bid" in labels:
        lenses.extend([str(profile.get("repair_recovery", "")), str(profile.get("affiliation_style", ""))])
    if not lenses:
        lenses.extend([str(profile.get("attention_magnets", "")), str(profile.get("topic_mobility", ""))])

    priority = "ground_latest_turn" if any(
        label in labels
        for label in ("greeting", "question", "topic_bid", "evidence_request", "repair_bid", "contradiction_or_challenge")
    ) or directly_addressed else "integrate_latest_turn"
    if (
        "fragment_or_ambiguous" in labels
        and "question" not in labels
        and "contradiction_or_challenge" not in labels
    ):
        priority = "clarify_or_interpret_fragment"

    return {
        "entity": entity,
        "partner": speaker,
        "self_implicated": self_implicated,
        "directly_addressed": directly_addressed,
        "social_targeting": social_targeting,
        "situation": labels,
        "grounding": {"source_text": text[:500], "terms": terms},
        "priority": priority,
        "personality_lens": [x for x in lenses if x][:4],
        "interpersonal_style": {
            "agency": profile.get("agency_style"),
            "communion": profile.get("communion_style"),
        },
        "schema_activation": schema,
        "coping_patterns": profile.get("coping_patterns"),
    }
