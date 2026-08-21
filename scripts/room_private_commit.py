#!/usr/bin/env python3
from __future__ import annotations

"""Final Room publication boundary with phrase-level semantic novelty.

The PR #125 implementation is preserved byte-for-byte in
``room_private_commit_base``.  This entrypoint adds one final comparison over the
exact staged strings, then delegates every other behavior to that preserved
implementation.  Keeping the layer thin makes the live repair auditable and
prevents dialogue-quality work from perturbing state/memory publication logic.
"""

import re

import room_private_commit_base as _base


_original_validate_staged_quality = _base.validate_staged_quality


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


def _aggregate_staged_phrase_echo(text: str, prior: list[dict]) -> bool:
    """Detect a long paraphrase mosaic even when rhetorical padding adds tokens.

    Short replies are intentionally left to the existing sentence/short-echo
    rules.  This rule activates only for long turns and asks whether several
    ordered semantic phrases have already appeared in the same staged beat.
    That makes vocabulary garnish unable to dilute the denominator, while still
    allowing a concise answer to reuse the subject of the preceding turn.
    """
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

    # Against one earlier voice, require a dense phrase cluster. Against two or
    # more staged voices, four repeated semantic links plus one exact three-link
    # run is enough to expose a mosaic assembled from the existing proposition.
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


# The preserved private_commit resolves validate_staged_quality in its own module
# at call time. Patch that one symbol so the live commit path uses this final gate.
_base.validate_staged_quality = validate_staged_quality

# Public compatibility for importers and direct script execution.
c = _base.c
private_commit = _base.private_commit
c.commit = private_commit


def __getattr__(name: str):
    return getattr(_base, name)


if __name__ == "__main__":
    c.main()
