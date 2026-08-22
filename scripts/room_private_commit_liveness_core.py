#!/usr/bin/env python3
from __future__ import annotations

"""Final Room publication boundary with phrase-level semantic novelty.

The PR #125 implementation is preserved byte-for-byte in
``room_private_commit_base``. This entrypoint adds final quality and bridge
selection guards, then delegates every other behavior to that preserved
implementation.
"""

import re
import sys

import room_private_commit_base as _base


QUALITY_REJECTION_EXIT = 42
_original_validate_staged_quality = _base.validate_staged_quality
_original_new_topic_from_terms = _base.c.new_topic_from_terms


def quality_rejection_exit_code(error: BaseException) -> int | None:
    """Classify only an intentional same-beat publication rejection."""
    if isinstance(error, RuntimeError) and "private Room same-beat echo blocked" in str(error):
        return QUALITY_REJECTION_EXIT
    return None


def _publish_semantic_sequence(text: object) -> list[str]:
    """Return ordered proposition-bearing anchors from exact staged speech."""
    normalized = re.sub(r"\btest\s+bed\b", "testbed", str(text or ""), flags=re.I)
    allowed = _base._publish_semantic_tokens(normalized)
    sequence: list[str] = []
    for raw in re.findall(r"[a-z][a-z']+", normalized.lower()):
        word = _base._quality._stem(raw)
        if word in allowed:
            sequence.append(word)
    return sequence


def _shingles(sequence: list[str], width: int) -> set[tuple[str, ...]]:
    if width <= 0 or len(sequence) < width:
        return set()
    return {
        tuple(sequence[index:index + width])
        for index in range(len(sequence) - width + 1)
    }


def _shared_bigram_runs(
    current: list[str], prior_bigrams: set[tuple[str, ...]]
) -> int:
    """Count separated runs of already-used semantic bigrams in current speech."""
    positions = [
        index
        for index in range(max(0, len(current) - 1))
        if tuple(current[index:index + 2]) in prior_bigrams
    ]
    if not positions:
        return 0
    runs = 1
    for previous, current_index in zip(positions, positions[1:]):
        if current_index != previous + 1:
            runs += 1
    return runs


def _aggregate_staged_phrase_echo(text: str, prior: list[dict]) -> bool:
    """Detect a long paraphrase mosaic even when rhetorical padding adds tokens."""
    if not prior:
        return False
    current = _publish_semantic_sequence(text)
    if len(current) < 16:
        return False

    current_bigrams = _shingles(current, 2)
    current_trigrams = _shingles(current, 3)
    prior_bigrams: set[tuple[str, ...]] = set()
    prior_trigrams: set[tuple[str, ...]] = set()
    for turn in prior:
        sequence = _publish_semantic_sequence(turn.get("text"))
        prior_bigrams.update(_shingles(sequence, 2))
        prior_trigrams.update(_shingles(sequence, 3))

    shared_bigrams = len(current_bigrams & prior_bigrams)
    shared_trigrams = len(current_trigrams & prior_trigrams)
    shared_runs = _shared_bigram_runs(current, prior_bigrams)

    if shared_runs < 2:
        return False
    if shared_bigrams >= 6 and shared_trigrams >= 2:
        return True
    if len(prior) >= 2 and shared_bigrams >= 4 and shared_trigrams >= 1:
        return True
    return False


def validate_staged_quality(staged: list[tuple[str, str, str, str, list[str]]]) -> None:
    """Run the established gates, then reject phrase-level same-beat mosaics."""
    _original_validate_staged_quality(staged)
    prior: list[dict] = []
    for entity, _move, target, text, _terms in staged:
        if _aggregate_staged_phrase_echo(text, prior):
            raise RuntimeError(
                f"private Room same-beat echo blocked for {entity}: semantic_phrase_mosaic"
            )
        prior.append({
            "speaker": entity,
            "text": text,
            "cognition": {"target": target},
        })


def _remember_vocabulary(out: list[str], value: object) -> None:
    text = _base.norm(value)
    if not text:
        return
    if text in out:
        out.remove(text)
    out.append(text)


def episode_previous_vocabulary(prior: dict, minds: dict | None = None) -> list[str]:
    """Build the episode's accumulated vocabulary from the live cognitive store."""
    prior = dict(prior or {})
    episode_id = str(prior.get("id") or "")
    store = minds if isinstance(minds, dict) else _base.c.minds()
    out: list[str] = []

    for key in (
        "root", "current_facet", "facets", "visited_facets", "recent_terms",
        "shared_references", "branch_history",
    ):
        values = prior.get(key)
        if isinstance(values, list):
            for value in values:
                _remember_vocabulary(out, value)
        else:
            _remember_vocabulary(out, values)
    for branch in prior.get("branches") or []:
        if isinstance(branch, dict):
            _remember_vocabulary(out, branch.get("label"))

    entities = store.get("entities") if isinstance(store.get("entities"), dict) else {}
    for entity in _base.c.ORDER:
        mind = entities.get(entity) if isinstance(entities.get(entity), dict) else {}
        medium = mind.get("medium") if isinstance(mind.get("medium"), dict) else {}
        for value in medium.get("topics") or []:
            _remember_vocabulary(out, value)
        for bucket in ("room_memories", "self_history"):
            for item in mind.get(bucket) or []:
                if not isinstance(item, dict) or str(item.get("topic_episode") or "") != episode_id:
                    continue
                cognition = item.get("cognition") if isinstance(item.get("cognition"), dict) else {}
                for value in cognition.get("topic_terms") or []:
                    _remember_vocabulary(out, value)
                for value in _base.c.toks(item.get("text", "")):
                    _remember_vocabulary(out, value)
    return out


def _near_vocabulary(candidate: object, vocabulary: list[str]) -> bool:
    return any(
        _base._bounded_topic._near(candidate, existing)
        for existing in vocabulary
        if existing
    )


def _safe_bridge_seed(terms, cycle: int, prior: dict) -> list[str]:
    """Prefer a true breakout; accept exhausted-episode terms only if genuinely far."""
    vocabulary = episode_previous_vocabulary(prior)
    bridge_key = f"bridge:{prior.get('id')}:{int(cycle)}"

    breakout = _base.c.breakout_subject(bridge_key)
    if breakout and not _near_vocabulary(breakout, vocabulary):
        return [_base.norm(breakout)]

    safe_generated = []
    for value in list(terms or []):
        text = _base.norm(value)
        if text and not _near_vocabulary(text, vocabulary) and text not in safe_generated:
            safe_generated.append(text)
    if safe_generated:
        return safe_generated

    # breakout_subject() remains the default path. If its deterministic pick is
    # contaminated by the live history, search the same breakout pool rather than
    # silently recycling an exhausted-episode term.
    for value in getattr(_base.c, "BREAKOUT_SUBJECTS", ()):
        text = _base.norm(value)
        if text and not _near_vocabulary(text, vocabulary):
            return [text]

    raise RuntimeError("private Room bridge has no seed outside accumulated live vocabulary")


def _bridge_safe_new_topic_from_terms(terms, cycle: int, prior: dict | None = None) -> dict:
    if prior and _base.c.should_shift_topic(prior):
        safe_terms = _safe_bridge_seed(terms, cycle, prior)
        # The bounded topic module has a legacy episode-age override that checks
        # only the small current topic surface. Clear only that selector hint so
        # the already-vetted live-vocabulary seed is preserved.
        safe_prior = dict(prior)
        safe_prior["bridge_reason"] = ""
        return _original_new_topic_from_terms(safe_terms, cycle, safe_prior)
    return _original_new_topic_from_terms(terms, cycle, prior)


# The preserved private_commit resolves these symbols through its module globals
# at call time, so patch only the final boundaries used by the live commit path.
_base.validate_staged_quality = validate_staged_quality
_base.c.new_topic_from_terms = _bridge_safe_new_topic_from_terms

# Public compatibility for importers and direct script execution.
c = _base.c
private_commit = _base.private_commit
c.commit = private_commit


def __getattr__(name: str):
    return getattr(_base, name)


def _run_cli() -> None:
    try:
        c.main()
    except RuntimeError as exc:
        code = quality_rejection_exit_code(exc)
        if code is None:
            raise
        print(f"ROOM PUBLISH QUALITY REJECTION: {exc}", file=sys.stderr)
        raise SystemExit(code) from None


if __name__ == "__main__":
    _run_cli()
