#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import Counter

import room_social_v5 as social

SCHEMA = 9
MAX_FACETS = 8
MAX_HISTORY = 8
MAX_RECENT_TERMS = 10
MAX_EPISODE_UPDATES = 7
MIN_FACET_SUPPORT = 2
MIN_ROOT_SUPPORT = 2

_TOPIC_NOISE = {
    "hey", "hi", "hello", "okay", "ok", "sorry", "thanks", "thank", "please",
    "last", "happened", "help", "helping", "stuck", "thing", "things", "really",
    "maybe", "probably", "actually", "well", "just", "again", "today", "tonight",
    "sarah", "mara", "owen", "jules", "allen",
    # Discourse mechanics, social moves, generic state, and evaluative language
    # can shape a turn but are not durable subject matter. Keep persistence
    # aligned with the production expression/topic guards.
    "notice", "noticed", "noticing", "share", "shared", "sharing",
    "think", "thinking", "thought", "feel", "feels", "feeling", "felt",
    "seem", "seems", "seemed", "say", "said", "saying", "tell", "telling",
    "talk", "talked", "talking", "discuss", "discussed", "discussing",
    "listen", "listens", "listened", "listening", "focus", "focuses", "focused", "focusing",
    "interested", "explore", "explores", "explored", "exploring",
    "support", "supporting", "supported", "repair", "repairing", "repaired",
    "reassure", "reassuring", "reassurance", "agree", "agreeing", "agreement",
    "disagree", "disagreeing", "disagreement", "answer", "answering", "answered",
    "callback", "compare", "comparing", "compared", "disclose", "disclosing",
    "disclosed", "bridge", "bridging", "ask", "asking", "asked",
    "question", "questioning", "respond", "responding", "response",
    "apologize", "apologizing", "apology",
    "glad", "happy", "sad", "sure", "unsure", "worried", "worry", "worrying",
    "grateful", "thankful", "overwhelmed", "upset", "angry", "afraid",
    "scared", "nervous", "confused", "comfortable", "uncomfortable",
    "honest", "open", "fine", "need", "needs", "needed", "needing",
    "want", "wants", "wanted", "wanting",
    "tough", "hard", "difficult", "easy", "rough",
    "get", "gets", "got", "getting", "leave", "leaves", "left", "leaving",
    "convince", "convinces", "convinced", "convincing",
    # Meta-conversational stance nouns repeatedly became fake persistent subjects.
    # They may occur naturally in speech, but the object of the stance is the topic,
    # not the fact that somebody has a position, perspective, issue, or direction.
    "position", "positions", "stance", "stances", "perspective", "perspectives",
    "importance", "important", "clarify", "clarifies", "clarified", "clarifying", "clarity",
    "direction", "directions", "account", "accounts", "issue", "issues", "problem", "problems",
    "conversation", "conversations", "discussion", "discussions", "subject", "subjects",
    # Pragmatic/discourse connectives organize clauses; they are not what the
    # Room is talking about. Treat the whole family generically rather than
    # banning the single canary word that exposed the bug.
    "despite", "although", "though", "however", "nevertheless", "nonetheless",
    "whereas", "therefore", "thus", "hence", "moreover", "furthermore",
    "instead", "otherwise", "anyway", "regardless", "meanwhile", "yet",
    # Evaluative stance verbs can become lexical attractors without naming a
    # concrete subject. Keep the object of the stance, not the stance verb.
    "appreciate", "appreciates", "appreciated", "appreciating", "appreciation",
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _stem(word: str) -> str:
    word = str(word or "").strip().lower()
    if len(word) > 5 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 4 and word.endswith("es"):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s"):
        word = word[:-1]
    return word


def _tokens(value: object) -> set[str]:
    out: set[str] = set()
    for word in social.words(value):
        stem = _stem(word)
        if len(stem) >= 3 and stem not in _TOPIC_NOISE:
            out.add(stem)
    return out


def _valid_term(value: object) -> bool:
    text = _clean(value)
    if not text:
        return False
    if text in _TOPIC_NOISE or text in social.PARTICIPANTS:
        return False
    return bool(_tokens(text))


def _near(a: object, b: object) -> bool:
    left, right = _clean(a), _clean(b)
    if not left or not right:
        return False
    if left == right:
        return True
    a_tokens, b_tokens = _tokens(left), _tokens(right)
    if not a_tokens or not b_tokens:
        return False
    if len(left) >= 4 and len(right) >= 4 and (left in right or right in left):
        return True
    if len(a_tokens) == 1 and len(b_tokens) == 1:
        aw, bw = next(iter(a_tokens)), next(iter(b_tokens))
        common = 0
        for ac, bc in zip(aw, bw):
            if ac != bc:
                break
            common += 1
        if common >= 6 and common / max(1, min(len(aw), len(bw))) >= 0.80:
            return True
    return len(a_tokens & b_tokens) / max(1, min(len(a_tokens), len(b_tokens))) >= 0.72


def _unique(values, limit: int) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _clean(value)
        if not _valid_term(text):
            continue
        if any(_near(text, prior) for prior in out):
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


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
        "branches": [],
        "branch_history": [],
        "focus_turns": 0,
        "last_branch_cycle": int(cycle),
        "escape_pressure": 0,
        "retired_terms": [],
        "retired_until_cycle": 0,
    }


def _flat_branches(root: str | None, facets: list[str], cycle: int, counts: Counter | None = None) -> list[dict]:
    counts = counts or Counter()
    out: list[dict] = []
    if root and _valid_term(root):
        out.append({
            "label": root,
            "parent": None,
            "depth": 0,
            "first_cycle": int(cycle),
            "last_cycle": int(cycle),
            "hits": max(1, int(counts.get(root, 1))),
            "status": "open",
        })
    for facet in facets:
        if not _valid_term(facet):
            continue
        if root and _near(facet, root):
            continue
        out.append({
            "label": facet,
            "parent": root,
            "depth": 1,
            "first_cycle": int(cycle),
            "last_cycle": int(cycle),
            "hits": max(1, int(counts.get(facet, 1))),
            "status": "open",
        })
    return out[: 1 + MAX_FACETS]


def _declared_terms(message: dict) -> list[str]:
    cognition = (message or {}).get("cognition") or {}
    values = cognition.get("topic_terms")
    if isinstance(values, list) and values:
        return _unique(values, MAX_RECENT_TERMS)
    return _unique(social.words((message or {}).get("text", "")), MAX_RECENT_TERMS)


def topic_terms_from_messages(messages, limit: int = 12, episode_id: str | None = None, min_support: int = 1) -> list[str]:
    groups: list[dict] = []
    serial = 0
    for message in list(messages or [])[-24:]:
        cognition = (message or {}).get("cognition") or {}
        if episode_id and cognition.get("topic_episode") != episode_id:
            continue
        touched: set[int] = set()
        for term in _declared_terms(message):
            group_index = next((i for i, group in enumerate(groups) if _near(term, group["label"])), None)
            if group_index is None:
                groups.append({"label": term, "support": 0, "recency": serial})
                group_index = len(groups) - 1
            group = groups[group_index]
            if group_index not in touched:
                group["support"] += 1
                touched.add(group_index)
            group["recency"] = serial
            serial += 1
    threshold = max(1, int(min_support))
    ranked = sorted(
        (group for group in groups if int(group["support"]) >= threshold),
        key=lambda group: (-int(group["support"]), -int(group["recency"]), str(group["label"])),
    )
    return [str(group["label"]) for group in ranked[:limit]]


def _normalize(topic: dict | None, cycle: int) -> dict:
    source = dict(topic or {})
    root = _clean(source.get("root")) or None
    if root and not _valid_term(root):
        root = None
    old_branches = source.get("branches") if isinstance(source.get("branches"), list) else []
    had_runaway_depth = any(int((branch or {}).get("depth", 0)) > 1 for branch in old_branches if isinstance(branch, dict))
    schema = int(source.get("semantic_schema", 0) or 0)

    if schema < SCHEMA or had_runaway_depth:
        schema_upgrade = schema < SCHEMA
        if schema_upgrade:
            root = None
        candidates = [] if schema_upgrade else [
            source.get("current_facet"),
            *list(source.get("recent_terms") or []),
            *list(source.get("visited_facets") or [])[-MAX_HISTORY:],
            *list(source.get("facets") or []),
        ]
        facets = [term for term in _unique(candidates, MAX_FACETS + 1) if not (root and _near(term, root))][:MAX_FACETS]
        current = root if schema_upgrade else (facets[0] if facets else root)
        migrated = topic_template(cycle)
        migrated.update({
            "id": str(source.get("id") or migrated["id"]),
            "root": root,
            "current_facet": current,
            "facets": facets,
            "visited_facets": [current] if current else [],
            "facet_index": 0,
            "shared_references": _unique(source.get("shared_references") or [], 4),
            "unresolved": list(source.get("unresolved") or [])[-4:],
            "participants": list(social.PARTICIPANTS),
            "turns": int(source.get("turns", 0) or 0),
            "low_novelty_beats": 3 if had_runaway_depth else int(source.get("low_novelty_beats", 0) or 0),
            "recent_terms": [root] if schema_upgrade and root else _unique(source.get("recent_terms") or [], MAX_RECENT_TERMS),
            "status": "ready_to_bridge" if had_runaway_depth else "active",
            "bridge_pending": bool(had_runaway_depth),
            "branch_history": [] if schema_upgrade else _unique(source.get("branch_history") or [], MAX_HISTORY),
            "focus_turns": 0 if schema_upgrade else int(source.get("focus_turns", 0) or 0),
            "escape_pressure": int(source.get("escape_pressure", 0) or 0),
            "last_shift_cycle": int(source.get("last_shift_cycle", cycle) or cycle),
            "last_branch_cycle": int(cycle),
            "retired_terms": _unique(source.get("retired_terms") or [], MAX_HISTORY),
            "retired_until_cycle": int(source.get("retired_until_cycle", 0) or 0),
        })
        migrated["branches"] = _flat_branches(root, facets, cycle)
        return migrated

    defaults = topic_template(cycle)
    defaults.update(source)
    defaults["semantic_schema"] = SCHEMA
    defaults["participants"] = list(social.PARTICIPANTS)
    defaults["bridge_pending"] = bool(defaults.get("bridge_pending", False))
    defaults["root"] = root
    defaults["retired_terms"] = _unique(defaults.get("retired_terms") or [], MAX_HISTORY)
    defaults["retired_until_cycle"] = int(defaults.get("retired_until_cycle", 0) or 0)
    facets = [term for term in _unique(defaults.get("facets") or [], MAX_FACETS + 1) if not (root and _near(term, root))][:MAX_FACETS]
    defaults["facets"] = facets
    current = _clean(defaults.get("current_facet")) or None
    if current and not _valid_term(current):
        current = None
    if current and root and _near(current, root):
        current = root
    if current and current != root and not any(_near(current, facet) for facet in facets):
        current = facets[0] if facets else root
    defaults["current_facet"] = current or (facets[0] if facets else root)
    live_labels = [label for label in [root, *facets] if label]
    visited = [
        term for term in _unique(defaults.get("visited_facets") or [], MAX_HISTORY)
        if any(_near(term, live) for live in live_labels)
    ]
    current_live = defaults.get("current_facet")
    if current_live and not any(_near(current_live, term) for term in visited):
        visited.append(_clean(current_live))
    defaults["visited_facets"] = _unique(visited, MAX_HISTORY)
    defaults["branch_history"] = [
        term for term in _unique(defaults.get("branch_history") or [], MAX_HISTORY)
        if any(_near(term, facet) for facet in facets)
    ]
    defaults["recent_terms"] = _unique(defaults.get("recent_terms") or [], MAX_RECENT_TERMS)
    defaults["shared_references"] = _unique(defaults.get("shared_references") or [], 4)
    defaults["branches"] = _flat_branches(root, facets, cycle)
    if defaults["bridge_pending"]:
        defaults["status"] = "ready_to_bridge"
    return defaults


def new_topic_from_terms(terms, cycle: int, prior: dict | None = None) -> dict:
    clean = _unique(terms, 1 + MAX_FACETS)
    topic = topic_template(cycle)
    if not clean:
        return topic
    root = clean[0]
    facets = []
    topic.update({
        "root": root,
        "current_facet": root,
        "facets": facets,
        "visited_facets": [root],
        "status": "active",
        "bridge_pending": False,
        "recent_terms": clean[:MAX_RECENT_TERMS],
    })
    if prior and prior.get("current_facet") and _valid_term(prior.get("current_facet")):
        topic["shared_references"] = [_clean(prior.get("current_facet"))]
        retired = [prior.get("root"), prior.get("current_facet"), *list(prior.get("facets") or [])]
        topic["retired_terms"] = _unique(retired, MAX_HISTORY)
        topic["retired_until_cycle"] = int(cycle) + 4
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
    min_support = MIN_ROOT_SUPPORT if current.get("root") is None else MIN_FACET_SUPPORT
    terms = topic_terms_from_messages(messages, limit=MAX_RECENT_TERMS, episode_id=episode_id, min_support=min_support)
    retired = list(current.get("retired_terms") or []) if int(cycle) <= int(current.get("retired_until_cycle", 0) or 0) else []
    if retired:
        terms = [term for term in terms if not any(_near(term, old) for old in retired)]
    if current.get("root") is None:
        return new_topic_from_terms(terms, cycle, current)

    root = current.get("root")
    bridge_pending = bool(current.get("bridge_pending", False))
    previous_terms = list(current.get("recent_terms") or [])

    supported_non_root = [term for term in terms if not (root and _near(term, root))]
    facets = [
        facet for facet in list(current.get("facets") or [])
        if any(_near(facet, term) for term in supported_non_root)
    ]
    novel = [term for term in supported_non_root if not any(_near(term, old) for old in facets)]
    for term in novel:
        if not any(_near(term, existing) for existing in facets):
            facets.insert(0, term)
    for term in reversed(supported_non_root):
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
    history = [
        term for term in _unique(history, MAX_HISTORY)
        if any(_near(term, facet) for facet in facets)
    ]

    live_labels = [label for label in [root, *facets] if label]
    visited = [
        term for term in list(current.get("visited_facets") or [])
        if any(_near(term, live) for live in live_labels)
    ]
    if active:
        visited.append(_clean(active))
    visited = _unique(reversed(visited), MAX_HISTORY)
    visited.reverse()

    meaningful = [term for term in terms if not any(_near(term, old) for old in previous_terms)]
    low_novelty = 0 if meaningful else int(current.get("low_novelty_beats", 0) or 0) + 1
    next_turns = int(current.get("turns", 0) or 0) + 1
    hard_escape = next_turns >= MAX_EPISODE_UPDATES
    bridge_pending = bridge_pending or hard_escape
    status = "ready_to_bridge" if bridge_pending or low_novelty >= 2 else "active"

    current.update({
        "semantic_schema": SCHEMA,
        "root": root,
        "current_facet": active,
        "facets": facets,
        "visited_facets": visited,
        "facet_index": max(0, len(visited) - 1),
        "branch_history": history,
        "focus_turns": focus_turns,
        "turns": next_turns,
        "recent_terms": terms[:MAX_RECENT_TERMS],
        "low_novelty_beats": low_novelty,
        "status": status,
        "bridge_pending": bridge_pending,
        "escape_pressure": low_novelty,
        "last_branch_cycle": int(cycle),
        "participants": list(social.PARTICIPANTS),
    })
    counts = Counter(terms)
    current["branches"] = _flat_branches(root, facets, cycle, counts)
    return current


def should_shift_topic(topic: dict | None) -> bool:
    return bool(topic and (topic.get("bridge_pending") or topic.get("status") == "ready_to_bridge"))
