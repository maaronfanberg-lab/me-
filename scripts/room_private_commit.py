#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timezone

import room_engine_v5 as c
import room_expression_quality as _quality
import room_social_v5 as _social
import room_topic_bounded as _bounded_topic

# Topic state is a bounded working-conversation episode. Keep the relationship
# machinery in room_social_v5, but replace its recursive topic functions at the
# commit boundary so old depth-N state is flattened before it can be published
# again. Patch both exports because tests/importers may hold either module.
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

# At the irreversible publication boundary, presentation garnish must not count
# as a genuinely new proposition. These are deliberately narrow discourse and
# evaluative tokens that the live 4777 echo used to manufacture false novelty.
_PUBLISH_GARNISH = {
    "hey", "exactly", "truly", "special", "interest", "fresh", "like",
    "together", "first", "latest", "start", "use", "create", "creat",
    "let", "let'", "we've", "here'", "that'", "i'd", "past", "few", "week",
    "closer", "step", "take", "last", "since", "also", "consider",
    "addition", "power", "powerful",
}


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def infected_text(value) -> bool:
    """Only genuine privacy leakage blocks publication.

    Dialogue-quality/meta/scaffold language is intentionally tolerated so the
    Room keeps running instead of quarantining itself.
    """
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
    """Return only semantic terms supported by the actual public sentence."""
    out: list[str] = []
    for value in semantic_values(expr):
        s = norm(value)
        if not bad_term(s) and grounded(text, [s]) and s not in out:
            out.append(s)
    # Existing topic labels may remain only when the speaker actually used them.
    for value in (topic.get("root"), topic.get("current_facet")):
        s = norm(value)
        if not bad_term(s) and grounded(text, [s]) and s not in out:
            out.append(s)
    # A model may emit poor semantic metadata while speaking a useful new idea.
    # Derive a bounded fallback from the sentence itself rather than stale state.
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


def validate_public_expression(entity: str, text: str, terms: list[str]) -> None:
    # Keep the hard privacy boundary, but do not quarantine for dialogue quality.
    if infected_text(text):
        raise RuntimeError(f"private Room privacy leak blocked for {entity}")


def _publish_semantic_tokens(text: object) -> set[str]:
    """Return proposition-bearing anchors for exact staged speech.

    Normalize a common split compound and remove discourse/evaluative garnish so
    respacing or stylistic flourishes cannot masquerade as semantic novelty.
    """
    normalized = re.sub(r"\btest\s+bed\b", "testbed", str(text or ""), flags=re.I)
    return {
        token for token in _quality._anchor_tokens(normalized)
        if token not in _PUBLISH_GARNISH
    }


def _aggregate_staged_echo(text: str, prior: list[dict]) -> bool:
    """Detect a multi-sentence paraphrase mosaic across already-staged voices."""
    if not prior:
        return False
    current = _publish_semantic_tokens(text)
    if len(current) < 6:
        return False
    earlier: set[str] = set()
    for turn in prior:
        earlier.update(_publish_semantic_tokens(turn.get("text")))
    overlap = current & earlier
    coverage = len(overlap) / max(1, len(current))
    # One earlier turn can already establish a proposition. Later turns get a
    # slightly broader aggregate test because they can remix two earlier voices.
    if len(overlap) >= 8 and coverage >= 0.68:
        return True
    if len(prior) >= 2 and len(overlap) >= 10 and coverage >= 0.60:
        return True
    return False


def validate_staged_quality(staged: list[tuple[str, str, str, str, list[str]]]) -> None:
    """Block cross-voice semantic echoes at the final publication boundary."""
    prior: list[dict] = []
    for entity, _move, target, text, _terms in staged:
        issue = _quality.same_beat_issue(text, prior)
        if issue:
            raise RuntimeError(f"private Room same-beat echo blocked for {entity}: {issue}")
        if _aggregate_staged_echo(text, prior):
            raise RuntimeError(f"private Room same-beat echo blocked for {entity}: semantic_coverage")
        prior.append({
            "speaker": entity,
            "text": text,
            "cognition": {"target": target},
        })


def private_commit(parts: list[dict], key: str):
    S = c.state()
    M = c.minds()
    T = c.tree()
    V = c.conv()
    prev = c.event()
    cycle = int(S.get("cycle", 0)) + 1
    topic = clean_topic(S.get("topic_episode") or {})
    if topic.get("root"):
        topic = clean_topic(c.update_topic(topic, V[-24:], cycle))

    q = prev if c.isq(prev) and topic.get("root") else None
    order, E = c.order4(parts, prev, cycle)
    beat = f"beat-{c.BOOT}-{cycle:06d}"

    expressions = {}
    for entity in c.ORDER:
        expr = (E[entity].get("private") or {}).get("expression")
        if not isinstance(expr, dict):
            raise RuntimeError(f"private Room requires model expression for {entity}; no public fallback is permitted")
        if not semantic_values(expr):
            raise RuntimeError(f"private Room expression lacks semantic fields for {entity}")
        expressions[entity] = expr

    if not topic.get("root"):
        topic = seed_topic(expressions, order, cycle, topic)

    plans = c.plan_actions(order, c.target(q) if q else None, M, topic, cycle)
    staged: list[tuple[str, str, str, str, list[str]]] = []

    # Nothing touches memory until all four public turns pass the privacy gate.
    for entity in order:
        expr = expressions[entity]
        text = c.model_text(expr)
        if not text:
            raise RuntimeError(f"private Room expression invalid for {entity}; no public fallback is permitted")

        terms = clean_terms(expr, topic, text)
        if not terms:
            terms = [norm(value) for value in c.toks(text)[:2] if not bad_term(value)]
        if not terms:
            terms = [norm(topic.get("root")) or "conversation"]
        validate_public_expression(entity, text, terms)

        planned = plans[entity]
        move = norm(expr.get("move") or planned["action"])
        if move not in ALLOWED_MOVES:
            move = planned["action"] if planned["action"] in ALLOWED_MOVES else "deepen"
        target = norm(expr.get("target") or planned["target"])
        if target not in c.ORDER or target == entity:
            target = planned["target"]
        if target not in c.ORDER or target == entity:
            target = next(other for other in c.ORDER if other != entity)
        staged.append((entity, move, target, text, terms))

    # This is the final quality boundary: compare the exact four strings that are
    # about to be published. It cannot be bypassed by lossy prompt context, retry
    # mutation, or temporary room_parts state.
    validate_staged_quality(staged)

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
    if len(spoken) != 4 or set(speakers) != set(c.ORDER):
        raise RuntimeError(f"v5 mandatory speech invariant failed: {speakers}")

    previous_vocabulary = {
        norm(x)
        for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))
        if not bad_term(x)
    }
    topic = clean_topic(c.update_topic(topic, spoken, cycle))
    if not topic.get("root") or bad_term(topic.get("root")):
        topic = seed_topic(expressions, order, cycle, topic)

    if c.should_shift_topic(topic):
        declared = c.topic_terms_from_messages(spoken, limit=12, episode_id=topic.get("id"))
        novel = [norm(x) for x in declared if not bad_term(x) and norm(x) not in previous_vocabulary]
        candidate_terms = novel or [c.breakout_subject(key)]
        candidate = clean_topic(c.new_topic_from_terms(candidate_terms, cycle, topic))
        if candidate.get("root") and not bad_term(candidate.get("root")):
            topic = candidate

    S["topic_episode"] = topic
    for entity in c.ORDER:
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
        "beat_message_count": 4,
        "silence_cycles": 0,
        "note": "research-informed v5 private model active; four mandatory unique speakers; bounded topic episodes; no public fallback; privacy gate retained",
    })

    c.audit_invariants(M, topic)
    c.save(c.ROOM / "conversation.json", V)
    c.save(c.ROOM / "discourse.json", T)
    c.save(c.ROOM / "cognitive_state.json", M)
    c.save(c.ROOM / "state.json", S)

    cm = {"schema": 5, "entities": {}}
    for entity in c.ORDER:
        ent = M["entities"][entity]
        cm["entities"][entity] = {
            "name": c.N[entity],
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
            "memory": [{"text": x.get("text", "")} for x in ent.get("room_memories", [])[-12:]],
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
            "entities": 4,
            "nodes_per_entity": 3,
            "tasks_per_node": 4,
            "active_processes": 48,
            "voting": False,
            "public_bus": True,
            "private_scope": "same_entity",
            "beat_output": "4 mandatory unique speakers",
            "private_pipeline": "perception->deliberation->expression",
            "public_fallback": False,
            "history_generation": c.BOOT,
            "contamination_gate": False,
            "privacy_gate": True,
        },
    }
    c.save(c.ROOM / "live.json", live)
    c.save(c.ROOT / "society" / "live.json", live)
    print("Room private beat", cycle, ":", ", ".join(c.N[e] for e in speakers), "subject=", topic.get("root"))


c.commit = private_commit

if __name__ == "__main__":
    c.main()
