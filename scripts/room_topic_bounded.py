#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import room_social_v5 as social

SCHEMA = 5
MAX_FACETS = 8
MAX_HISTORY = 8
MAX_RECENT_TERMS = 10
# update_topic is called twice around a published beat. Twenty updates therefore
# gives an episode roughly ten beats to develop before age alone forces a bridge.
MAX_EPISODE_UPDATES = 20
_AGE_BREAKOUT_SUBJECTS = (
    "volcanoes", "beekeeping", "coral reefs", "astronomy", "origami", "mushrooms",
    "architecture", "bird migration", "ceramics", "ocean currents", "mythology", "fossils",
    "urban trees", "caves", "lighthouses", "tea", "deserts", "constellations", "rivers",
    "insects", "textiles", "woodworking", "clouds", "maps", "islands", "orchards",
    "languages", "bridges", "tides", "seeds", "comets", "mountains", "shells",
    "fermentation", "railways", "museums", "wolves", "whales", "glassmaking", "geology",
    "folklore", "bicycles", "calligraphy", "wetlands", "penguins", "shipwrecks",
    "stargazing", "pottery", "butterflies", "waterfalls", "chess", "kites", "breadmaking",
    "mosaics", "orchids", "meteorites", "canoes", "castles", "spices", "snowflakes",
)


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _tokens(value: object) -> set[str]:
    return {word for word in social.words(value) if len(word) >= 3}


def _near(a: object, b: object) -> bool:
    left, right = _clean(a), _clean(b)
    if not left or not right:
        return False
    if left == right:
        return True
    a_tokens, b_tokens = _tokens(left), _tokens(right)
    if not a_tokens or not b_tokens:
        return left in right or right in left
    if len(left) >= 4 and len(right) >= 4 and (left in right or right in left):
        return True
    return len(a_tokens & b_tokens) / max(1, min(len(a_tokens), len(b_tokens))) >= 0.72


def _unique(values, limit: int) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _clean(value)
        if not text or not _tokens(text):
            continue
        if any(_near(text, prior) for prior in out):
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _persisted_live_vocabulary() -> list[str]:
    """Collect semantic terms from the persisted live Room, fail-soft when absent."""
    path = Path("room/feed.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return []
    vocabulary: list[str] = []
    state = payload.get("state") if isinstance(payload, dict) else {}
    topic = state.get("topic_episode") if isinstance(state, dict) else {}
    if isinstance(topic, dict):
        vocabulary.extend([topic.get("root"), topic.get("current_facet")])
        vocabulary.extend(list(topic.get("facets") or []))
        vocabulary.extend(list(topic.get("recent_terms") or []))
        vocabulary.extend(list(topic.get("visited_facets") or []))
        vocabulary.extend(list(topic.get("branch_history") or []))
    for message in list(payload.get("conversation") or []) if isinstance(payload, dict) else []:
        if not isinstance(message, dict):
            continue
        vocabulary.extend(_declared_terms(message))
    return _unique(vocabulary, 512)


def _age_breakout_terms(prior: dict, cycle: int) -> list[str]:
    vocabulary = [
        prior.get("root"), prior.get("current_facet"),
        *list(prior.get("facets") or []), *list(prior.get("recent_terms") or []),
        *list(prior.get("visited_facets") or []), *list(prior.get("branch_history") or []),
        *_persisted_live_vocabulary(),
    ]
    vocabulary = _unique(vocabulary, 512)
    start = int(cycle) % len(_AGE_BREAKOUT_SUBJECTS)
    for offset in range(len(_AGE_BREAKOUT_SUBJECTS)):
        candidate = _AGE_BREAKOUT_SUBJECTS[(start + offset) % len(_AGE_BREAKOUT_SUBJECTS)]
        if not any(_near(candidate, existing) for existing in vocabulary if existing):
            return [candidate]
    raise RuntimeError("no semantically fresh age-breakout subject remains")


def topic_template(cycle: int = 0) -> dict:
    return {
        "semantic_schema": SCHEMA,
        "id": f"topic-{int(cycle):06d}",
        "root": None,
        "current_facet": None,
        "facets": [],
        "visited_facets": [],
        "facet_index": 0,
        "unresolved": [],
        "examples": [],
        "disagreements": [],
        "shared_references": [],
        "participants": list(social.PARTICIPANTS),
        "turns": 0,
        "low_novelty_beats": 0,
        "recent_terms": [],
        "last_shift_cycle": int(cycle),
        "status": "forming",
        "bridge_pending": False,
        "bridge_reason": "",
        "branches": [],
        "branch_history": [],
        "focus_turns": 0,
        "last_branch_cycle": int(cycle),
        "last_semantic_progress_cycle": int(cycle),
        "last_stagnation_cycle": None,
        "escape_pressure": 0,
    }


def _flat_branches(root: str | None, facets: list[str], cycle: int, counts: Counter | None = None) -> list[dict]:
    counts = counts or Counter()
    out: list[dict] = []
    if root:
        out.append({"label": root, "parent": None, "depth": 0, "first_cycle": int(cycle), "last_cycle": int(cycle), "hits": max(1, int(counts.get(root, 1))), "status": "open"})
    for facet in facets:
        if root and _near(facet, root):
            continue
        out.append({"label": facet, "parent": root, "depth": 1, "first_cycle": int(cycle), "last_cycle": int(cycle), "hits": max(1, int(counts.get(facet, 1))), "status": "open"})
    return out[: 1 + MAX_FACETS]


def _declared_terms(message: dict) -> list[str]:
    cognition = (message or {}).get("cognition") or {}
    values = cognition.get("topic_terms")
    if isinstance(values, list) and values:
        return _unique(values, MAX_RECENT_TERMS)
    return _unique(social.words((message or {}).get("text", "")), MAX_RECENT_TERMS)


def topic_terms_from_messages(messages, limit: int = 12, episode_id: str | None = None) -> list[str]:
    counts: Counter = Counter()
    recency: dict[str, int] = {}
    serial = 0
    for message in list(messages or [])[-24:]:
        cognition = (message or {}).get("cognition") or {}
        if episode_id and cognition.get("topic_episode") != episode_id:
            continue
        for term in _declared_terms(message):
            counts[term] += 1
            recency[term] = serial
            serial += 1
    ranked = sorted(counts, key=lambda term: (-counts[term], -recency.get(term, -1), term))
    return ranked[:limit]


def _normalize(topic: dict | None, cycle: int) -> dict:
    source = dict(topic or {})
    root = _clean(source.get("root")) or None
    old_branches = source.get("branches") if isinstance(source.get("branches"), list) else []
    had_runaway_depth = any(int((branch or {}).get("depth", 0)) > 1 for branch in old_branches if isinstance(branch, dict))
    schema = int(source.get("semantic_schema", 0) or 0)
    if schema < SCHEMA or had_runaway_depth:
        candidates = [source.get("current_facet"), *list(source.get("recent_terms") or []), *list(source.get("visited_facets") or [])[-MAX_HISTORY:], *list(source.get("facets") or [])]
        facets = [term for term in _unique(candidates, MAX_FACETS + 1) if not (root and _near(term, root))][:MAX_FACETS]
        current = facets[0] if facets else root
        migrated = topic_template(cycle)
        migrated.update({
            "id": str(source.get("id") or migrated["id"]), "root": root, "current_facet": current,
            "facets": facets, "visited_facets": [current] if current else [], "facet_index": 0,
            "shared_references": list(source.get("shared_references") or [])[-4:], "unresolved": list(source.get("unresolved") or [])[-4:],
            "participants": list(social.PARTICIPANTS), "turns": int(source.get("turns", 0) or 0),
            "low_novelty_beats": 3 if had_runaway_depth else 0, "recent_terms": _unique(source.get("recent_terms") or [], MAX_RECENT_TERMS),
            "status": "ready_to_bridge" if had_runaway_depth else "active", "bridge_pending": bool(had_runaway_depth),
            "bridge_reason": "runaway_depth" if had_runaway_depth else "", "branch_history": [], "focus_turns": 0,
            "escape_pressure": 0, "last_shift_cycle": int(source.get("last_shift_cycle", cycle) or cycle), "last_branch_cycle": int(cycle),
        })
        migrated["branches"] = _flat_branches(root, facets, cycle)
        return migrated
    defaults = topic_template(cycle)
    defaults.update(source)
    defaults["semantic_schema"] = SCHEMA
    defaults["participants"] = list(social.PARTICIPANTS)
    defaults["bridge_pending"] = bool(defaults.get("bridge_pending", False))
    defaults["bridge_reason"] = str(defaults.get("bridge_reason") or "")
    defaults["root"] = root
    facets = [term for term in _unique(defaults.get("facets") or [], MAX_FACETS + 1) if not (root and _near(term, root))][:MAX_FACETS]
    defaults["facets"] = facets
    current = _clean(defaults.get("current_facet")) or None
    if current and root and _near(current, root):
        current = root
    if current and current != root and not any(_near(current, facet) for facet in facets):
        current = facets[0] if facets else root
    defaults["current_facet"] = current or (facets[0] if facets else root)
    defaults["visited_facets"] = _unique(defaults.get("visited_facets") or [], MAX_HISTORY)
    defaults["branch_history"] = _unique(defaults.get("branch_history") or [], MAX_HISTORY)
    defaults["recent_terms"] = _unique(defaults.get("recent_terms") or [], MAX_RECENT_TERMS)
    defaults["branches"] = _flat_branches(root, facets, cycle)
    if defaults["bridge_pending"]:
        defaults["status"] = "ready_to_bridge"
    return defaults


def new_topic_from_terms(terms, cycle: int, prior: dict | None = None) -> dict:
    source_terms = terms
    if prior and str(prior.get("bridge_reason") or "") == "episode_age":
        source_terms = _age_breakout_terms(prior, cycle)
    clean = _unique(source_terms, 1 + MAX_FACETS)
    topic = topic_template(cycle)
    if not clean:
        return topic
    root = clean[0]
    facets = [term for term in clean[1:] if not _near(term, root)][:MAX_FACETS]
    current = facets[0] if facets else root
    topic.update({"root": root, "current_facet": current, "facets": facets, "visited_facets": [current], "status": "active", "bridge_pending": False, "bridge_reason": "", "recent_terms": clean[:MAX_RECENT_TERMS]})
    if prior and prior.get("current_facet"):
        topic["shared_references"] = [_clean(prior.get("current_facet"))]
    topic["branches"] = _flat_branches(root, facets, cycle)
    return topic


def _outside_subject_shift(topic: dict, messages, cycle: int) -> dict | None:
    if not messages:
        return None
    latest = messages[-1]
    speaker = _clean((latest or {}).get("speaker"))
    if not speaker or speaker in social.ORDER:
        return None
    latest_terms = _declared_terms(latest)
    if not latest_terms:
        return None
    vocabulary = [topic.get("root"), topic.get("current_facet"), *list(topic.get("facets") or [])]
    novel = [term for term in latest_terms if not any(_near(term, existing) for existing in vocabulary if existing)]
    if not novel:
        return None
    primary = latest_terms[0]
    if any(_near(primary, existing) for existing in vocabulary if existing):
        primary = novel[0]
    rest = [term for term in latest_terms if not _near(term, primary)]
    return new_topic_from_terms([primary, *rest], cycle, topic)


def update_topic(topic: dict | None, messages, cycle: int) -> dict:
    current = _normalize(topic, cycle)
    shifted = _outside_subject_shift(current, list(messages or []), cycle)
    if shifted is not None:
        return shifted
    episode_id = current.get("id")
    terms = topic_terms_from_messages(messages, limit=MAX_RECENT_TERMS, episode_id=episode_id)
    if current.get("root") is None:
        return new_topic_from_terms(terms, cycle, current)
    root = current.get("root")
    was_bridge_pending = bool(current.get("bridge_pending", False))
    previous_terms = list(current.get("recent_terms") or [])
    novel = [term for term in terms if not any(_near(term, old) for old in [root, *current.get("facets", [])] if old)]
    facets = list(current.get("facets") or [])
    for term in novel:
        if root and _near(term, root):
            continue
        if not any(_near(term, existing) for existing in facets):
            facets.insert(0, term)
    for term in reversed(terms):
        if root and _near(term, root):
            continue
        if any(_near(term, existing) for existing in facets):
            match = next(existing for existing in facets if _near(term, existing))
            facets.remove(match)
            facets.insert(0, match)
    facets = facets[:MAX_FACETS]
    focus_turns = int(current.get("focus_turns", 0) or 0) + 1
    active = current.get("current_facet") or root
    if novel and focus_turns >= 2:
        active = novel[0]
        focus_turns = 0
    elif active != root and not any(_near(active, facet) for facet in facets):
        active = facets[0] if facets else root
    history = list(current.get("branch_history") or [])
    old_focus = current.get("current_facet")
    if old_focus and active and not _near(old_focus, active):
        history.append(_clean(old_focus))
    history = _unique(history, MAX_HISTORY)
    visited = list(current.get("visited_facets") or [])
    if active:
        visited.append(_clean(active))
    visited = _unique(reversed(visited), MAX_HISTORY)
    visited.reverse()
    # Semantic progress and stagnation use the same criterion as facet advancement.
    # Lexically different paraphrases of known facets are not progress. Because
    # update_topic runs twice around a beat, count at most once per cycle.
    prior_low_novelty = int(current.get("low_novelty_beats", 0) or 0)
    last_progress_cycle = int(current.get("last_semantic_progress_cycle", -1) or -1)
    last_stagnation_cycle = current.get("last_stagnation_cycle")
    if novel:
        low_novelty = 0
        last_progress_cycle = int(cycle)
        last_stagnation_cycle = None
    elif last_progress_cycle == int(cycle):
        low_novelty = prior_low_novelty
    elif last_stagnation_cycle == int(cycle) if last_stagnation_cycle is not None else False:
        low_novelty = prior_low_novelty
    else:
        low_novelty = prior_low_novelty + 1
        last_stagnation_cycle = int(cycle)
    next_turns = int(current.get("turns", 0) or 0) + 1
    age_exhausted = next_turns >= MAX_EPISODE_UPDATES
    low_novelty_exhausted = low_novelty >= 3
    bridge_pending = was_bridge_pending or age_exhausted or low_novelty_exhausted
    if age_exhausted:
        bridge_reason = "episode_age"
    elif was_bridge_pending:
        bridge_reason = str(current.get("bridge_reason") or "pending")
    elif low_novelty_exhausted:
        bridge_reason = "low_novelty"
    else:
        bridge_reason = ""
    status = "ready_to_bridge" if bridge_pending else "active"
    current.update({
        "semantic_schema": SCHEMA, "root": root, "current_facet": active, "facets": facets,
        "visited_facets": visited, "facet_index": max(0, len(visited) - 1), "branch_history": history,
        "focus_turns": focus_turns, "turns": next_turns, "recent_terms": terms[:MAX_RECENT_TERMS],
        "low_novelty_beats": low_novelty, "status": status, "bridge_pending": bridge_pending,
        "bridge_reason": bridge_reason, "escape_pressure": max(low_novelty, 3 if age_exhausted else 0),
        "last_branch_cycle": int(cycle), "last_semantic_progress_cycle": last_progress_cycle,
        "last_stagnation_cycle": last_stagnation_cycle, "participants": list(social.PARTICIPANTS),
    })
    counts = Counter(terms)
    current["branches"] = _flat_branches(root, facets, cycle, counts)
    return current


def should_shift_topic(topic: dict | None) -> bool:
    return bool(topic and (topic.get("bridge_pending") or topic.get("status") == "ready_to_bridge"))
