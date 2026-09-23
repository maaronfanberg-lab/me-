#!/usr/bin/env python3
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

import room_engine_v5 as c
import room_expression_quality as _expression_quality
import room_social_v5 as _social
import room_topic_bounded as _bounded_topic
import room_private_self_state as _private_self_state
import room_research_architecture as _research

for _topic_name in (
    "topic_template",
    "topic_terms_from_messages",
    "update_topic",
    "new_topic_from_terms",
    "should_shift_topic",
):
    _topic_fn = getattr(_bounded_topic, _topic_name)
    setattr(c, _topic_name, _topic_fn)
    setattr(_social, _topic_name, _topic_fn)

ALLOWED_MOVES = {
    "answer", "deepen", "disclose", "compare", "disagree",
    "repair", "support", "callback", "bridge", "close",
}
PRIVACY_MARKERS = (
    "system prompt", "hidden prompt", "developer message",
    "internal instructions", "chain of thought", "room_prompt_",
)
CONTROL_SENTINELS = {
    "rejected_wording", "try_again", "return_structured_data_only",
    "end_rejected_wording", "response", "conversation",
}
CONTEXT_SCOPE_VERSION = 1

SLEEPING_ENTITIES = frozenset(
    str(entity).strip().lower()
    for entity in (c._core.CFG.get("sleeping_entities") or [])
    if str(entity).strip()
)
AWAKE_ORDER = tuple(entity for entity in c.ORDER if entity not in SLEEPING_ENTITIES)
if not AWAKE_ORDER:
    raise RuntimeError("Room has no awake autonomous participants")


def _restore_sleeping_minds(minds: dict, snapshots: dict[str, dict]) -> None:
    entities = minds.setdefault("entities", {})
    for entity, snapshot in snapshots.items():
        entities[entity] = copy.deepcopy(snapshot)


def _prune_absent_live_models(state: dict, entity: str) -> dict:
    state = dict(state or {})
    models = state.get("models_of_others")
    if isinstance(models, dict):
        state["models_of_others"] = {
            other: value
            for other, value in models.items()
            if other in AWAKE_ORDER and other != entity
        }
    return state


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def infected_text(value) -> bool:
    text = norm(value)
    if not text:
        return True
    return any(marker in text for marker in PRIVACY_MARKERS)


def bad_term(value) -> bool:
    text = norm(value)
    if not text or len(text) > 80:
        return True
    if any(marker in text for marker in PRIVACY_MARKERS):
        return True
    return False


def clean_topic(topic: dict) -> dict:
    topic = dict(topic or {})
    for key in ("facets", "visited_facets", "recent_terms", "shared_references", "unresolved"):
        vals = topic.get(key)
        if isinstance(vals, list):
            cleaned = []
            for value in vals:
                s = norm(value)
                if not bad_term(s) and s not in cleaned:
                    cleaned.append(s)
            topic[key] = cleaned
    root = norm(topic.get("root"))
    facet = norm(topic.get("current_facet"))
    topic["root"] = None if bad_term(root) else root
    if bad_term(facet):
        choices = [x for x in topic.get("facets", []) if not bad_term(x)]
        topic["current_facet"] = topic.get("root") or (choices[0] if choices else None)
    else:
        topic["current_facet"] = facet
    return topic


def semantic_values(expr: dict) -> list:
    return expr.get("semantic_terms") if isinstance(expr, dict) and isinstance(expr.get("semantic_terms"), list) else []


def grounded(text: str, terms: list[str]) -> bool:
    words = set(re.findall(r"[a-z][a-z'-]{2,}", norm(text)))
    for term in terms:
        significant = [word for word in re.findall(r"[a-z][a-z'-]{2,}", norm(term)) if len(word) >= 4]
        if any(word in words for word in significant):
            return True
    return False


def clean_terms(expr: dict, topic: dict, text: str) -> list[str]:
    out: list[str] = []
    for value in semantic_values(expr):
        s = norm(value)
        if not bad_term(s) and grounded(text, [s]) and s not in out:
            out.append(s)
    for value in (topic.get("root"), topic.get("current_facet")):
        s = norm(value)
        if not bad_term(s) and grounded(text, [s]) and s not in out:
            out.append(s)
    if not out:
        for value in c.toks(text)[:4]:
            s = norm(value)
            if not bad_term(s) and s not in out:
                out.append(s)
    return out[:4]


def seed_topic(expressions: dict, order: list[str], cycle: int, prior: dict) -> dict:
    terms: list[str] = []
    for entity in order:
        expr = expressions.get(entity, {})
        text = c.model_text(expr) or ""
        local: list[str] = []
        for value in semantic_values(expr):
            s = norm(value)
            if not bad_term(s) and grounded(text, [s]) and s not in local:
                local.append(s)
        if not local:
            local.extend(norm(value) for value in c.toks(text)[:4] if not bad_term(value))
        for value in local:
            if value and value not in terms:
                terms.append(value)
    if not terms:
        raise RuntimeError("private Room clean start produced no publishable grounded semantic terms")
    seeded = clean_topic(c.new_topic_from_terms(terms[:8], cycle, prior))
    if not seeded.get("root"):
        raise RuntimeError("private Room clean start could not establish a subject")
    return seeded


def context_scope_reset(topic: dict, key: str, cycle: int) -> dict:
    prior_root = norm((topic or {}).get("root"))
    subject = c.breakout_subject(f"{key}:context-scope")
    if prior_root and norm(subject) == prior_root:
        alternate = c.breakout_subject(f"{key}:context-scope:alternate")
        if alternate:
            subject = alternate
    candidate = clean_topic(c.new_topic_from_terms([subject], cycle, None))
    if not candidate.get("root"):
        raise RuntimeError("context-scope migration could not establish a clean subject")
    return candidate


def _publication_degenerate(text: str) -> str | None:
    raw = str(text or "").strip()
    low = norm(raw)
    if low in CONTROL_SENTINELS:
        return "control_sentinel"
    if raw in {"{", "}", "[", "]"}:
        return "structured_debris"
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        return "structured_debris"
    if re.search(r"\b([a-z][a-z']{2,})(?:\s+\1){2,}\b", low, re.I):
        return "token_loop"
    words = re.findall(r"[a-z0-9']+", low)
    if len(words) >= 3:
        counts: dict[str, int] = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1
        peak = max(counts.values(), default=0)
        if peak >= 3 and peak / len(words) >= 0.34:
            return "dominant_token"
    return None


def validate_public_expression(entity: str, text: str, terms: list[str], context: list[dict]) -> None:
    if infected_text(text):
        raise RuntimeError(f"private Room privacy leak blocked for {entity}")
    deterministic_issue = _publication_degenerate(text)
    if deterministic_issue:
        raise RuntimeError(f"private Room publish quarantine for {entity}: {deterministic_issue}")
    hygiene_issue = _research.autonomous_text_issue({"speaker": entity, "text": text})
    if hygiene_issue:
        raise RuntimeError(f"private Room publish quarantine for {entity}: {hygiene_issue}")
    compact = {
        "context": list(context or [])[-8:],
        "event": (list(context or [])[-1] if context else None),
        "discussion": {},
    }
    issue = _expression_quality.quality_issue(text, compact, entity, c._sim)
    if issue:
        raise RuntimeError(f"private Room publish quarantine for {entity}: {issue}")


def private_commit(parts: list[dict], key: str):
    S = c.state()
    M = c.minds()
    sleeping_snapshots = {
        entity: copy.deepcopy(M["entities"][entity])
        for entity in SLEEPING_ENTITIES
        if entity in M.get("entities", {})
    }
    T = c.tree()
    V = c.conv()
    prev = c.event()
    cycle = int(S.get("cycle", 0)) + 1
    context_scope_migration = int(S.get("context_scope_version", 0) or 0) < CONTEXT_SCOPE_VERSION
    topic = clean_topic(S.get("topic_episode") or {})
    if topic.get("root"):
        topic = clean_topic(c.update_topic(topic, V[-24:], cycle))

    q = prev if c.isq(prev) and topic.get("root") else None
    order, E = c.order4(parts, prev, cycle)
    awake_order = [entity for entity in order if entity in AWAKE_ORDER]
    beat = f"beat-{c.BOOT}-{cycle:06d}"

    # A failed expression belongs to that agent, not to the whole Room. Preserve
    # the hard quality boundary, but quarantine the failed candidate and allow
    # independently valid peers to publish.
    expressions: dict[str, dict] = {}
    quarantined: list[str] = []
    for entity in AWAKE_ORDER:
        expr = (E[entity].get("private") or {}).get("expression")
        if not isinstance(expr, dict):
            quarantined.append(f"{entity}:missing_expression")
            continue
        if not semantic_values(expr):
            quarantined.append(f"{entity}:missing_semantic_fields")
            continue
        expressions[entity] = expr

    if not expressions:
        print("All Room expressions quarantined before publication; skipping beat without state mutation")
        return

    valid_order = [entity for entity in awake_order if entity in expressions]
    if not topic.get("root"):
        topic = seed_topic(expressions, valid_order, cycle, topic)

    qtarget = c.target(q) if q and c.target(q) in AWAKE_ORDER else None
    plans = c.plan_actions(awake_order, qtarget, M, topic, cycle)
    staged: list[tuple[str, str, str, str, list[str]]] = []

    # Candidate N is checked against accepted candidates 1..N-1. Any invalid
    # candidate is dropped locally and never reaches history, memory, or topic state.
    for entity in valid_order:
        expr = expressions[entity]
        text = c.model_text(expr)
        if not text:
            quarantined.append(f"{entity}:invalid_model_text")
            continue

        terms = clean_terms(expr, topic, text)
        if not terms:
            terms = [norm(value) for value in c.toks(text)[:2] if not bad_term(value)]
        if not terms:
            terms = [norm(topic.get("root")) or "conversation"]
        validation_context = list(V[-8:]) + [
            {"speaker": speaker, "text": staged_text, "cognition": {"target": target}}
            for speaker, _move, target, staged_text, _terms in staged
        ]
        try:
            validate_public_expression(entity, text, terms, validation_context)
        except RuntimeError as exc:
            quarantined.append(f"{entity}:{str(exc)[:100]}")
            continue

        planned = plans[entity]
        move = norm(expr.get("move") or planned["action"])
        if move not in ALLOWED_MOVES:
            move = planned["action"] if planned["action"] in ALLOWED_MOVES else "deepen"
        target = norm(expr.get("target") or planned["target"])
        if target not in AWAKE_ORDER or target == entity:
            target = planned["target"]
        if target not in AWAKE_ORDER or target == entity:
            target = next(other for other in AWAKE_ORDER if other != entity)
        staged.append((entity, move, target, text, terms))

    if not staged:
        print("All Room expressions quarantined at final publication gate; skipping beat without state mutation")
        if quarantined:
            print("Room quarantine:", " | ".join(quarantined))
        return

    spoken: list[dict] = []
    answer_msg = None
    for entity, move, target, text, terms in staged:
        parent = (q or answer_msg or prev or {}).get("discourse_id")
        msg, node = c.emit(entity, move, target, parent, None, text, beat, len(spoken), topic, terms)
        c.record(V, T, M, msg, node, cycle)
        spoken.append(msg)
        if move == "answer":
            answer_msg = msg

    speakers = [m["speaker"] for m in spoken]

    # Sleeping participants are absent from the live social field and their
    # private state is frozen while they nap: no new heard memories, relationship
    # observations, attention updates, or private-self updates.
    _restore_sleeping_minds(M, sleeping_snapshots)

    # Migrate legacy memory non-destructively and label new memories by what was
    # actually observed. Hearing a proposition is not the same thing as witnessing it.
    _research.annotate_memory_provenance(M)
    _restore_sleeping_minds(M, sleeping_snapshots)

    previous_vocabulary = {
        norm(x)
        for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))
        if not bad_term(x)
    }
    topic = clean_topic(c.update_topic(topic, spoken, cycle))
    if not topic.get("root") or bad_term(topic.get("root")):
        topic = seed_topic(expressions, valid_order, cycle, topic)

    if context_scope_migration:
        topic = context_scope_reset(topic, key, cycle)
    elif c.should_shift_topic(topic):
        forced_breakout = bool(topic.get("bridge_pending"))
        if forced_breakout:
            candidate_terms = [c.breakout_subject(key)]
        else:
            declared = c.topic_terms_from_messages(spoken, limit=12, episode_id=topic.get("id"))
            novel = [norm(x) for x in declared if not bad_term(x) and norm(x) not in previous_vocabulary]
            candidate_terms = novel or [c.breakout_subject(key)]
        prior = None if forced_breakout else topic
        candidate = clean_topic(c.new_topic_from_terms(candidate_terms, cycle, prior))
        if candidate.get("root") and not bad_term(candidate.get("root")):
            topic = candidate

    topic["participants"] = list(AWAKE_ORDER) + ["allen"]
    S["topic_episode"] = topic
    S["context_scope_version"] = CONTEXT_SCOPE_VERSION

    part_index = {(part.get("entity"), part.get("role")): part for part in parts}
    for entity in AWAKE_ORDER:
        comprehension_part = part_index.get((entity, "comprehension"), {})
        comprehension_private = comprehension_part.get("private") if isinstance(comprehension_part.get("private"), dict) else {}
        comprehension_source = comprehension_private.get("source") if isinstance(comprehension_private.get("source"), dict) else {}
        perception = comprehension_source.get("social_observation") if isinstance(comprehension_source.get("social_observation"), dict) else {}
        thought_part = part_index.get((entity, "thought"), {})
        thought_private = thought_part.get("private") if isinstance(thought_part.get("private"), dict) else {}
        deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else {}

        latest_event = comprehension_source.get("event") if isinstance(comprehension_source.get("event"), dict) else prev
        perception, deliberation = _research.guard_private_self_inputs(perception, deliberation, latest_event)

        prior_private_self = M["entities"][entity].get("private_self_state")
        updated_private_self = _private_self_state.update(
            prior_private_self, c.P[entity], entity, AWAKE_ORDER, perception, deliberation, V, cycle
        )
        M["entities"][entity]["private_self_state"] = _prune_absent_live_models(updated_private_self, entity)

    for entity in AWAKE_ORDER:
        M["entities"][entity]["medium"] = {
            "topics": [
                x for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))[:8]
                if x and not bad_term(x)
            ],
            "branch_interest": round(c.clamp(.4 * c.trait(entity, "curiosity") + .4 * c.trait(entity, "attention_persistence")), 3),
        }

    T["nodes"] = T.get("nodes", [])[-1200:]
    T["roots"] = T.get("roots", [])[-300:]
    V = V[-1000:]
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    S.update({
        "version": c.VERSION,
        "boot_id": c.BOOT,
        "cycle": cycle,
        "last_run": stamp,
        "messages": len(V),
        "last_public_event": spoken[-1]["id"],
        "last_speaker": spoken[-1]["speaker"],
        "last_beat_id": beat,
        "beat_contributors": speakers,
        "beat_message_count": len(spoken),
        "silence_cycles": 0,
        "sleeping_entities": sorted(SLEEPING_ENTITIES),
        "note": "research-informed v5: selective agent context; provenance-tagged memory; guarded private beliefs; per-agent quality+privacy quarantine",
    })

    c.audit_invariants(M, topic)
    _restore_sleeping_minds(M, sleeping_snapshots)
    c.save(c.ROOM / "conversation.json", V)
    c.save(c.ROOM / "discourse.json", T)
    c.save(c.ROOM / "cognitive_state.json", M)
    c.save(c.ROOM / "state.json", S)

    cm = {"schema": 5, "entities": {}}
    for entity in c.ORDER:
        ent = M["entities"][entity]
        cm["entities"][entity] = {
            "name": c.N[entity],
            "status": "sleeping" if entity in SLEEPING_ENTITIES else "awake",
            "profile": c.P[entity],
            "genome": c.P[entity]["traits"],
            "development": {
                "turns": cycle,
                "spoken": ent.get("spoken", 0),
                "silences": ent.get("silences", 0),
                "topic_weights": {t: 1 for t in M["entities"][entity]["medium"]["topics"] if t},
                "relationships": {
                    other: {
                        k: v for k, v in ent["people"][other].items()
                        if k in {"exposure", "direct_familiarity", "trust", "predictability", "reciprocity", "warmth", "respect", "disclosure_depth", "tension", "direct_turns", "repair_successes"}
                    }
                    for other in ent.get("people", {})
                },
            },
            "memory": [_research.memory_public_slice(x) for x in ent.get("room_memories", [])[-12:]],
        }

    live = {
        "generated_at": stamp,
        "architecture_version": c.VERSION,
        "boot_id": c.BOOT,
        "minds": cm,
        "profiles": c.P,
        "state": S,
        "conversation": V,
        "discourse": T,
        "topic_episode": topic,
        "network": {
            "compute_nodes": 12,
            "entities": len(c.ORDER),
            "awake_entities": len(AWAKE_ORDER),
            "sleeping_entities": sorted(SLEEPING_ENTITIES),
            "sleeping_visibility": "hidden_from_awake_participants",
            "nodes_per_entity": 3,
            "tasks_per_node": 4,
            "active_processes": 48,
            "voting": False,
            "public_bus": True,
            "private_scope": "agent-specific selective retrieval",
            "beat_output": f"{len(spoken)} validated contribution(s); invalid candidates quarantined per agent",
            "private_pipeline": "selective evidence->perception->deliberation->expression",
            "public_fallback": False,
            "history_generation": c.BOOT,
            "contamination_gate": True,
            "privacy_gate": True,
            "memory_provenance": True,
            "reported_claims_are_facts": False,
            "per_agent_expression_quarantine": True,
        },
    }
    c.save(c.ROOM / "live.json", live)
    c.save(c.ROOT / "society" / "live.json", live)
    if quarantined:
        print("Room quarantine:", " | ".join(quarantined))
    print("Room private beat", cycle, ":", ", ".join(c.N[e] for e in speakers), "subject=", topic.get("root"))


c.commit = private_commit

if __name__ == "__main__":
    c.main()