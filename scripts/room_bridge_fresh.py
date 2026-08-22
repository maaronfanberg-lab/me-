#!/usr/bin/env python3
from __future__ import annotations

import room_topic_bounded as bounded

def _clean(value: object) -> str:
    return bounded._clean(value)

def previous_vocabulary(topic: dict | None, messages) -> list[str]:
    """Full exact-normalized vocabulary accumulated within one live episode."""
    current = dict(topic or {})
    episode_id = str(current.get('id') or '')
    out: list[str] = []
    def add(value):
        text = _clean(value)
        if text and text not in out:
            out.append(text)
    for value in list(current.get('previous_vocabulary') or []): add(value)
    for value in [current.get('root'), current.get('current_facet'), *list(current.get('facets') or []), *list(current.get('recent_terms') or []), *list(current.get('visited_facets') or []), *list(current.get('branch_history') or [])]: add(value)
    for message in list(messages or []):
        if not isinstance(message, dict):
            continue
        cognition = message.get('cognition') if isinstance(message.get('cognition'), dict) else {}
        if episode_id and str(cognition.get('topic_episode') or '') != episode_id:
            continue
        for value in bounded._declared_terms(message): add(value)
    return out

def with_previous_vocabulary(topic: dict | None, messages) -> dict:
    out = dict(topic or {})
    out['previous_vocabulary'] = previous_vocabulary(out, messages)
    return out

def is_fresh(candidate: object, vocabulary) -> bool:
    text = _clean(candidate)
    return bool(text) and not any(bounded._near(text, old) for old in list(vocabulary or []) if _clean(old))

def bridge_seed_terms(engine, key: str, vocabulary, declared_terms=()) -> list[str]:
    """Breakout subject is always the root; exhausted-turn terms may only add fresh facets."""
    prior = list(vocabulary or [])
    subjects = tuple(getattr(engine, 'BREAKOUT_SUBJECTS', ()) or ())
    if not subjects:
        raise RuntimeError('breakout subject pool unavailable')
    root = None
    for attempt in range(len(subjects)):
        candidate = engine.breakout_subject(key, attempt)
        if is_fresh(candidate, prior):
            root = _clean(candidate)
            break
    if not root:
        raise RuntimeError('no breakout subject survives _near against previous_vocabulary')
    terms = [root]
    for value in list(declared_terms or []):
        text = _clean(value)
        if not text or not is_fresh(text, prior):
            continue
        if any(bounded._near(text, selected) for selected in terms):
            continue
        terms.append(text)
        if len(terms) >= 8:
            break
    return terms
