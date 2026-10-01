from __future__ import annotations

"""Bounded consequences of observed speech, not inferred hidden intentions.

Activities are conversational invitations, not proof of completed outside work.
Only validated, published messages are observed by awake participants. No model
calls, invented memories, initial alliances, or history replay on waking.
"""

import re
import room_research_architecture as research
import room_social_v5 as social

VERSION = 1
MAX_ENCOUNTERS = 48
MAX_ACTIVITIES = 12
_INVITE = re.compile(r"\b(?:let['’]s|shall we|what if we|we could|would you both|want to)\b", re.I)
_ACCEPT = re.compile(r"\b(?:i['’]m in|count me in|i['’]ll (?:try|join|take|do|test|compare|design)|i will (?:try|join|take|test)|yes[, !]|agreed)\b", re.I)
_DECLINE = re.compile(r"\b(?:count me out|i (?:won['’]t|will not|don['’]t want to)|no thanks|not interested|i decline)\b", re.I)
_REVISE = re.compile(r"\b(?:i was wrong|i (?:misread|misunderstood)|my assumption was wrong|i changed my mind)\b", re.I)
_TASK_NOISE = {"let's", "shall", "experiment", "game", "try", "join", "design", "test", "build", "challenge", "count", "agreed"}
_SCAFFOLD = re.compile(r"\b(?:input_json|output_json|mandatory_speech|conversation_job|group_context|system prompt|hidden prompt|developer message|chain of thought|room_prompt_\w*)\b", re.I)


def enabled(config: dict) -> bool:
    return bool((config.get("group_dynamics") or {}).get("enabled"))


def _terms(text: str) -> set[str]:
    return set(social.words(text)) - set(social.PARTICIPANTS)


def unspecific_initiative(text: str) -> bool:
    """Recognise an empty announcement, not ordinary short answers or refusal."""
    if not re.search(r"\b(?:try something new|(?:explor\w*|try|suggest|propos\w*) (?:a |some )?(?:new |different )?(?:possibilit\w*|ideas?|things?|something)|new (?:possibilities|direction))\b", text, re.I):
        return False
    content = _terms(text) - {"open", "explore", "exploring", "exploration", "new", "different",
                              "possibility", "possibilities", "idea", "ideas", "try", "trying",
                              "propose", "proposing", "suggest", "suggesting", "direction", "directions"}
    return len(content) < 2


def _target(message: dict) -> str | None:
    return (message.get("cognition") or {}).get("target") or message.get("target")


def _encounter(message: dict, cycle: int) -> dict:
    return {
        "id": message["id"], "speaker": message["speaker"],
        "target": _target(message), "text": str(message["text"])[:300],
        "move": (message.get("cognition") or {}).get("move_type") or message.get("move"),
        "at": message.get("at"), "cycle": cycle,
    }


def _safe(message: dict) -> bool:
    return bool(message.get("id") and message.get("speaker") in social.PARTICIPANTS
                and str(message.get("text") or "").strip()
                and (message.get("speaker") == "allen" or not _SCAFFOLD.search(str(message.get("text"))))
                and not research.autonomous_text_issue(message))


def _personal(ent: dict) -> dict:
    data = ent.setdefault("group_dynamics", {})
    data.setdefault("version", VERSION)
    for key in ("encounters", "revisions", "activities"):
        data.setdefault(key, [])
    return data


def _relevant(message: dict, activity: dict) -> bool:
    # Generic procedural vocabulary alone is not a task reference.
    return bool(_terms(message.get("text", "")) & set(activity["terms"]))


def observe(minds: dict, state: dict, message: dict, cycle: int,
            awake: tuple[str, ...], config: dict) -> None:
    if not enabled(config) or not _safe(message):
        return
    group = state.setdefault("group_dynamics", {"version": VERSION, "activities": []})
    if message["id"] in group.get("observed_ids", []):
        return
    previous_id = group.get("last_event")
    activities = group.setdefault("activities", [])
    speaker, text = message["speaker"], str(message["text"])
    event = _encounter(message, cycle)
    # Persist only new observations. A waking character does not acquire the
    # transcript of conversations held while absent.
    for listener in awake:
        data = _personal(minds["entities"][listener])
        if any(item["id"] == event["id"] for item in data["encounters"]):
            continue
        if speaker == listener and _REVISE.search(text):
            grounds = [item for item in reversed(data["encounters"])
                       if item["speaker"] != speaker and item.get("target") == speaker
                       and _terms(item["text"]) & _terms(text)]
            if grounds:
                correction = {"statement": event, "in_response_to": grounds[0]["id"],
                              "status": "acknowledged_revision_not_verified_truth"}
                data["revisions"].append(correction)
                data["revisions"] = data["revisions"][-8:]
                peer = grounds[0]["speaker"]
                if peer in minds["entities"][listener].get("people", {}):
                    relation = minds["entities"][listener]["people"][peer]
                    relation["respect"] = social.approach(relation.get("respect", .12), .004)
        data["encounters"].append(dict(event))
        data["encounters"] = data["encounters"][-MAX_ENCOUNTERS:]

    for activity in activities:
        if activity["status"] not in {"proposed", "active"}:
            continue
        if cycle - activity["last_cycle"] > 48:
            activity["status"] = "expired"
            continue
        if speaker not in activity["participants"] or speaker == activity["owner"]:
            continue
        relevant = _relevant(message, activity) or (
            previous_id == activity["id"] and _target(message) == activity["owner"])
        if not relevant:
            continue
        participation = activity["responses"].get(speaker)
        if _DECLINE.search(text):
            activity["responses"][speaker] = {"status": "declined", "source": event["id"]}
            activity["contributions"].pop(speaker, None)
        elif _ACCEPT.search(text):
            activity["responses"][speaker] = {"status": "accepted", "source": event["id"]}
        elif participation and participation["status"] == "accepted" and event["move"] in {"answer", "deepen", "compare", "disclose"} and len(_terms(text)) >= 3:
            old = activity["contributions"].get(speaker)
            activity["contributions"][speaker] = {"source": event["id"], "text": text[:200]}
            if not old:
                # A witnessed follow-through changes the organiser's directional
                # relationship; simply being invited or accepting does not.
                owner = activity["owner"]
                if owner in awake:
                    relation = minds["entities"][owner]["people"].get(speaker)
                    if relation:
                        relation["reciprocity"] = social.approach(relation.get("reciprocity", .08), .008)
                        relation["respect"] = social.approach(relation.get("respect", .12), .004)
        else:
            continue
        activity["last_cycle"] = cycle
        statuses = [activity["responses"].get(person, {}).get("status")
                    for person in activity["participants"] if person != activity["owner"]]
        activity["status"] = "declined" if statuses and all(s == "declined" for s in statuses) else (
            "active" if "accepted" in statuses else "proposed")

    # A proposal requires a concrete task and two named, currently present people.
    # This is a conservative recogniser of explicit speech, not a sentiment model.
    named = [person for person in awake if person != speaker
             and re.search(r"\b" + re.escape(person) + r"\b", text, re.I)]
    terms = sorted(_terms(text) - _TASK_NOISE)
    open_count = sum(a["status"] in {"proposed", "active"} for a in activities)
    prior_cycle = max((a["created_cycle"] for a in activities if a["owner"] == speaker), default=-100)
    if speaker in awake and _INVITE.search(text) and len(named) >= 2 and len(terms) >= 3 and open_count < 2 and cycle - prior_cycle >= 8:
        activities.append({
            "id": event["id"], "owner": speaker, "proposal": text[:300],
            "participants": [speaker, *named[:3]], "terms": terms[:16],
            "status": "proposed", "responses": {}, "contributions": {},
            "created_cycle": cycle, "last_cycle": cycle,
        })
    # Closing is a public conversational decision, never certified task success.
    for activity in activities:
        if speaker == activity["owner"] and activity["status"] in {"proposed", "active"} and event["move"] == "close" and _relevant(message, activity):
            activity["status"] = "closed"
            activity["closure_source"] = event["id"]
    group["activities"] = activities[-MAX_ACTIVITIES:]
    group["last_event"] = event["id"]
    group["observed_ids"] = (list(group.get("observed_ids", [])) + [event["id"]])[-MAX_ENCOUNTERS:]
    for listener in awake:
        data = _personal(minds["entities"][listener])
        # Keep only activities this listener actually heard, not newly replayed
        # invitations from the interval when that participant was sleeping.
        known = {item["id"] for item in data["encounters"]} | {a["id"] for a in data["activities"]}
        data["activities"] = [a for a in group["activities"] if a["id"] in known][-4:]


def partner_bonus(minds: dict, entity: str, other: str, cycle: int) -> float:
    data = (minds.get("entities", {}).get(entity, {}).get("group_dynamics") or {})
    for activity in data.get("activities", []):
        if activity["status"] not in {"proposed", "active"} or cycle - activity["last_cycle"] > 48:
            continue
        if entity not in activity["participants"] or other not in activity["participants"]:
            continue
        if other == activity["owner"] and entity != other:
            response = activity["responses"].get(entity, {}).get("status")
            if response != "declined" and (response is None or entity not in activity["contributions"]):
                return .16
        if entity == activity["owner"] and activity["responses"].get(other, {}).get("status") == "accepted" and other not in activity["contributions"]:
            return .12
    return 0.


def model_context(minds: dict, entity: str, partner: str | None,
                  context: list[dict], awake: tuple[str, ...], config: dict) -> dict:
    if not enabled(config) or entity not in awake:
        return {}
    ent = minds.get("entities", {}).get(entity, {})
    data = ent.get("group_dynamics") or {}
    # Stored memories are private observations. Do not retrieve arbitrary public
    # history, particularly for someone returning from absence.
    candidates = list(data.get("encounters", []))
    for kind in ("room_memories", "self_history"):
        for item in ent.get(kind, []):
            speaker = item.get("speaker") or (entity if kind == "self_history" else item.get("reported_by"))
            record = {"id": item.get("source") or item.get("id"), "speaker": speaker,
                      "target": item.get("target"), "text": item.get("text"), "at": item.get("at")}
            if _safe(record):
                candidates.append(record)
    topic_words = _terms(" ".join(str(m.get("text") or "") for m in context[-3:]))
    recent_ids = {m.get("id") for m in context}
    seen, selected = set(), []
    ranked = sorted(enumerate(candidates), key=lambda pair: (
        3 * (pair[1].get("speaker") == partner or pair[1].get("target") == partner)
        + 2 * (pair[1].get("target") == entity)
        + min(3, len(_terms(pair[1].get("text", "")) & topic_words)), pair[0]), reverse=True)
    for _, item in ranked:
        if not _safe(item) or item["id"] in seen or item["id"] in recent_ids:
            continue
        if item.get("speaker") not in awake and item.get("speaker") != "allen":
            continue
        # No irrelevant callback merely because a long-term memory exists.
        if not (_terms(item["text"]) & topic_words or item.get("speaker") == partner or item.get("target") == partner):
            continue
        seen.add(item["id"])
        selected.append({"speaker": item["speaker"], "target": item.get("target"),
                         "text": item["text"][:180], "source": item["id"], "at": item.get("at"),
                         "status": "remembered_speech_not_verified_fact"})
        if len(selected) == 3:
            break
    peers = {other: {key: round(float(relation.get(key, 0)), 3)
                    for key in ("trust", "respect", "warmth", "tension", "reciprocity")}
             for other, relation in ent.get("people", {}).items()
             if other in awake and other != entity}
    last_cycle = max((item.get("cycle", 0) for item in data.get("encounters", [])), default=0)
    activities = [{"owner": a["owner"], "proposal": a["proposal"][:180],
                   "status": a["status"], "invited": a["participants"],
                   "responses": {p: r["status"] for p, r in a["responses"].items()},
                   "offered_work": {p: r["text"][:100] for p, r in a["contributions"].items()}}
                  for a in data.get("activities", []) if a["status"] in {"proposed", "active"}
                  and last_cycle - a["last_cycle"] <= 48][-2:]
    out = {"relationships": peers, "encounters": selected, "activities": activities}
    if entity == "jules" and not activities:
        available = [other for other in awake if other != entity]
        if len(available) >= 2:
            first = partner if partner in available else min(available, key=lambda person:
                ent.get("people", {}).get(person, {}).get("last_direct_cycle") or 0)
            # Offer a less-practised pairing, not a predetermined alliance.
            second = min((other for other in available if other != first), key=lambda person:
                sum(minds.get("entities", {}).get(a, {}).get("people", {}).get(b, {}).get("direct_turns", 0)
                    for a, b in ((first, person), (person, first))))
            out["possible_collaborators"] = [first, second]
        unfinished = next((item for item in reversed(data.get("encounters", []))
                           if item["speaker"] == entity and unspecific_initiative(item["text"])), None)
        if unfinished:
            out["unfinished_idea"] = {"said": unfinished["text"][:120],
                                      "missing": "a concrete subject and something specific to try"}
    if data.get("revisions"):
        out["last_revision"] = data["revisions"][-1]["statement"]["text"][:180]
    return out
