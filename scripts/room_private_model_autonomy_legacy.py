from __future__ import annotations

import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

import room_research_architecture as _research

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

AUTONOMY_ENGINE = "structural-base-selective-context-provenance-v3"
PEOPLE = base.PEOPLE

AUTONOMY_PROMPTS = {
    "comprehension": (
        "Understand the conversation from this participant's point of view. "
        "Use the supplied conversation, relationship state, attention lens, and evidence_context as evidence. "
        "Treat observed speech as evidence that the speaker said something, not automatic proof that its proposition is true. "
        "Base your understanding only on details supported by the conversation."
    ),
    "thought": (
        "Decide what this participant personally wants to do next in the conversation. "
        "Use their own identity, values, motives, attention, relationship state, evidence_context, and what was actually said. "
        "Form this participant's own position rather than inferring a group consensus. "
        "A reported claim may be questioned, believed weakly, or left unresolved; it is not a witnessed event merely because someone said it. "
        "Choose among ANSWER, DEEPEN, DISCLOSE, COMPARE, DISAGREE, REPAIR, SUPPORT, CALLBACK, BRIDGE, or CLOSE. "
        "No move is preferred. SUPPORT is appropriate only when this participant actually wants to reinforce or affiliate. "
        "Choose another Room participant as the intended partner. Choose for yourself what matters next."
    ),
    "expression": (
        "Speak as this participant in an actual ongoing conversation. "
        "Where an internally generated intent exists, keep the participant's independently chosen action and partner. "
        "A personally addressed turn makes an answer, clarification, disagreement or refusal relevant. "
        "An open floor need not preserve the previous subject: the participant can respond, "
        "offer an initiative connected to their own genuine motives or relationships, "
        "or pursue a useful connection that interests them. These are opportunities, not commands. "
        "Choose the actual words yourself, without inventing group agreement or unsupported events. "
        "Use evidence_context to distinguish what was said from what was established. "
        "For interaction_project.kind=respond_or_repair, attend to the actual source "
        "utterance and choose your own appropriate response. "
        "If interaction_project.sequence.kind=unanswered_question_echo, another "
        "speaker already attempted a repair or echoed the question. Keep that "
        "sequence open and respond with an answer, clarification, disagreement, "
        "refusal, or a question about the precise misunderstanding. An utterance "
        "heard twice is not twice-confirmed understanding. "
        "For interaction_project.kind=respond_to_proposal, the source is an offer "
        "rather than an established agreement or criticism. You may accept, "
        "decline, clarify, or counteroffer in your own voice; do not attribute "
        "unspoken accusations to the person who made the offer. "
        "For interaction_project.kind=self_initiated_contribution, no answer is owed; "
        "start a concrete question, observation or idea from your established expertise "
        "and motives. Do not invent autobiographical events to support it."
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
            # Conversation initiation needs individual motives, not simply the
            # lexical content of whatever topic was most recently mentioned.
            # These are existing user-authored character properties, never
            # a fabricated topic or an instruction to avoid particular words.
            "motives": _clip_list(psychology.get("motives"), 3),
            "values": _clip_list(psychology.get("values"), 3),
            "attention_magnets": _clip_list(psychology.get("attention_magnets"), 3),
            "cognitive_style": psychology.get("cognitive_style"),
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
    # Smallville/AutoGen lesson: retrieval happens before prompt construction.
    # Each mind receives a bounded, scored subset rather than the same broadcast window.
    supplied = dict(payload or {})
    if role == "expression" and os.environ.get("ROOM_CONVERSATIONAL_FLOOR") == "1":
        from room_conversation_project import expression_project
        project = expression_project(
            entity=str(supplied.get("entity") or ""),
            latest=supplied.get("event"),
            context=list(supplied.get("context") or []),
            profile=supplied.get("profile"),
            private_self_state=supplied.get("private_self_state"),
        )
        supplied.update(project)
        if project["interaction_project"]["kind"] == "self_initiated_contribution":
            # Group memories are valuable for genuine replies and ongoing
            # projects. An unrequested initiative needs relationship knowledge,
            # not the three most recent quotations of a completed topic.
            # These quotations remain durably available to perception and
            # response projects, and are not deleted or forbidden.
            group = supplied.get("group_context")
            if isinstance(group, dict):
                supplied["group_context"] = {
                    key: group[key] for key in ("relationships", "possible_collaborators")
                    if key in group
                }
        # The durable topic index does not create a conversational debt.
        supplied["topic"] = {}
        supplied["keywords"] = []
    clean_payload = _research.select_context(supplied, role, limit=6)
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

    evidence = _research.evidence_context(clean_payload, self_entity, limit=6)
    if evidence:
        compact["evidence_context"] = evidence

    if role == "expression" and os.environ.get("ROOM_CONVERSATIONAL_FLOOR") == "1":
        # Infer only an opportunity to act, never agreement or a shared fact.
        # Publicly audible vocatives are better evidence than hidden target
        # metadata. Questions without named recipients remain open-floor bids.
        from room_conversational_floor import is_directed
        event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
        directly_addressed = bool(self_entity and is_directed(event, self_entity))
        last_text = str(event.get("text") or "").strip()
        current_project = compact.get("interaction_project")
        current_project = current_project if isinstance(current_project, dict) else {}
        initiative = current_project.get("kind") == "self_initiated_contribution"
        proposal = current_project.get("kind") == "respond_to_proposal"
        if initiative:
            compact["event"] = None
        compact["social_opportunity"] = {
            "action_due": ("self_initiated_contribution" if initiative
                           else "respond_to_proposal" if proposal
                           else "directed_response_or_repair" if directly_addressed
                           else "open_floor_response_or_repair"),
            "question_visible": last_text.endswith("?"),
            "prior_speaker": current_project.get("prior_speaker") if initiative else event.get("speaker"),
            "source_id": current_project.get("observed_source_id") if initiative
                         else (clean_payload.get("event") or {}).get("id")
                         if isinstance(clean_payload.get("event"), dict) else None,
        }

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


def _read_completion(req: urllib.request.Request, timeout: int) -> str:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))


def _request_autonomy(model_url: str, prompt: str, role: str, temperature: float, timeout: int,
                      self_entity: str | None = None, attempt: int = 0, intent: dict | None = None) -> str:
    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 200, "thought": 170, "expression": 180}.get(role, 180),
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
    if role == "thought":
        lock_path = Path(os.environ.get("ROOM_LLAMA_THOUGHT_LOCK", "/tmp/room-llama-thought.lock"))
        with lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            return _read_completion(req, timeout)
    return _read_completion(req, timeout)


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
        r"\bkeep\s+(?:the|your|its)\s+(?:chosen\s+)?move.{0,32}focus.{0,32}(?:intended\s+)?partner\b",
        r"\b(?:move|focus)\s*(?:,|and)\s*(?:focus|partner).{0,24}(?:partner|intact)\b",
        r"\bdo\s+not\s+(?:resolve|invent|copy).{0,48}\b(?:issue|conflict|speech|conversation)\b",
        r"\buse\s+only\s+details\s+supported\s+by\s+(?:what|the conversation)\b",
        r"\bbase\s+(?:the\s+)?reply\s+only\s+on\s+what\s+was\s+actually\s+said\b",
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

    social_floor = os.environ.get("ROOM_CONVERSATIONAL_FLOOR") == "1"
    base_guard = ""
    if role == "expression":
        base_guard = (
            "\nAUTONOMY_RULE\n"
            "Respond naturally to the current conversation. Keep the chosen move, focus, and intended partner while choosing your own words. "
            "Use only details supported by what was actually said. Do not invent unsupported conflict, jealousy, secrets, threats, shared memories, "
            "or dramatic incidents. Treat reported claims as reports unless independent evidence is present. " +
            ("Shared wording can be reused to answer, clarify, acknowledge, or emphasize a point. "
             "Prioritize the relevant conversational action over novelty.\n" if social_floor
             else "Avoid copying recent speech. Stay inside the conversation.\n")
        )

    attempts = 3 if role == "expression" else 2
    last_reason = "unknown"
    for attempt in range(attempts):
        retry_guard = ""
        if attempt:
            retry_guard = (
                "\nTRY_AGAIN\n" +
                ("Recheck the actual source utterance and the action it makes relevant. "
                 "Keep your own voice, stance and uncertainty.\n" if social_floor
                 else "Use fresh natural wording. Keep the same chosen move, focus, and partner. Base the reply only on what was actually said.\n")
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
                bare_words = _words(utterance)
                bare_move_labels = {
                    "acknowledge", "appreciate", "support", "repair", "answer",
                    "respond", "response", "disclose", "compare", "disagree",
                    "agree", "bridge", "close", "deepen", "callback",
                }
                if (
                    attempt < attempts - 1
                    and len(bare_words) == 1
                    and bare_words[0] in bare_move_labels
                ):
                    last_reason = "bare_move_label"
                    continue
                if not social_floor and len(utterance.split()) < max(1, int(min_words)):
                    last_reason = "utterance_too_short"
                    continue
                # In selected-floor mode "No.", "Really?" and "I agree."
                # are legitimate first-position responses. Structural and
                # hygiene checks still run; an absent model is not silence.
                if _public_meta_language(utterance, compact):
                    last_reason = "meta_language"
                    continue
                if not social_floor and (base._too_similar_to_context(utterance, compact) or _has_context_echo(utterance, compact)):
                    last_reason = "duplicate_context"
                    continue
            return obj
        except urllib.error.HTTPError as exc:
            detail = base._safe_http_detail(exc)
            suffix = f": {detail}" if detail else ""
            if role == "expression":
                print(f"Expression quarantined for {self_entity}: HTTP {exc.code}{suffix}")
                return None
            raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}{suffix}") from exc
        except ValueError as exc:
            last_reason = str(exc)[:80]
            continue
        except Exception as exc:
            if role == "expression":
                print(f"Expression quarantined for {self_entity}: {type(exc).__name__}")
                return None
            raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    if role == "expression":
        print(f"Expression quarantined for {self_entity}: {last_reason}")
        return None
    raise RuntimeError(f"private model output rejected for {role}: {last_reason}")