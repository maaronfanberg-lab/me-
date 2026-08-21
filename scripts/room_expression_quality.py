from __future__ import annotations

"""Room expression-quality facade with live same-beat semantic coverage.

The proven pre-PR127 implementation lives in room_expression_quality_core. This
facade preserves that API exactly, then strengthens the shared same_beat_issue
boundary. Because both the five-attempt expression retry loop and the final
private commit call same_beat_issue, one predicate now protects both boundaries.
"""

import re
import sys
import types
from collections import Counter

import room_expression_quality_core as _core

# Re-export the complete historical module surface, including private helpers used
# by existing Room boundary code and simulators.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_original_same_beat_issue = _core.same_beat_issue

_SEMANTIC_GARNISH = {
    "hey", "hello", "exactly", "truly", "special", "interest", "fresh", "like", "together",
    "first", "latest", "start", "use", "create", "creat", "let", "let'", "we've", "here'", "that'",
    "i'd", "past", "few", "week", "closer", "step", "take", "last", "since", "also", "consider",
    "addition", "power", "powerful",
}


def _semantic_coverage_tokens(text: object) -> set[str]:
    """Return proposition-bearing anchors while ignoring conversational garnish."""
    normalized = re.sub(r"\btest\s+bed\b", "testbed", str(text or ""), flags=re.I)
    return {
        token for token in _core._anchor_tokens(normalized)
        if token not in _SEMANTIC_GARNISH
    }


def _semantic_sequence(text: object) -> list[str]:
    """Return ordered proposition-bearing anchors for phrase-cluster comparison."""
    normalized = re.sub(r"\btest\s+bed\b", "testbed", str(text or ""), flags=re.I)
    allowed = _semantic_coverage_tokens(normalized)
    out: list[str] = []
    for raw in re.findall(r"[a-z][a-z']+", normalized.lower()):
        word = _core._stem(raw)
        if word in allowed:
            out.append(word)
    return out


def _shingles(sequence: list[str], width: int) -> set[tuple[str, ...]]:
    if width <= 0 or len(sequence) < width:
        return set()
    return {
        tuple(sequence[index:index + width])
        for index in range(len(sequence) - width + 1)
    }


def _shared_bigram_runs(current: list[str], prior_bigrams: set[tuple[str, ...]]) -> int:
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


def _single_prior_phrase_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Catch a second voice rebuilding one earlier proposition in separated clusters.

    Live cycle 4793 showed a simpler failure than the multi-speaker consensus case:
    Owen reused Mara's research -> planning -> testing proposition with connector
    prose. Requiring multiple separated shared phrase clusters prevents a single
    quoted/reference clause from being mistaken for an echo when the reply then
    adds genuinely new evidence.
    """
    if len(prior_turns) != 1:
        return False
    previous = str((prior_turns[0] or {}).get("text") or "").strip()
    if not previous or "?" in previous:
        return False

    current = _semantic_sequence(utterance)
    earlier = _semantic_sequence(previous)
    if len(current) < 10 or len(earlier) < 8:
        return False

    prior_bigrams = _shingles(earlier, 2)
    prior_trigrams = _shingles(earlier, 3)
    shared_bigrams = len(_shingles(current, 2) & prior_bigrams)
    shared_trigrams = len(_shingles(current, 3) & prior_trigrams)
    shared_runs = _shared_bigram_runs(current, prior_bigrams)

    return shared_runs >= 2 and shared_bigrams >= 4 and shared_trigrams >= 2


def _aggregate_same_beat_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Detect a semantic mosaic assembled mostly from earlier same-beat content.

    The compact path retains PR125's high-coverage protection. The ten-anchor path
    catches longer live mosaics such as cycles 4783/4784: they add rhetorical
    framing, but reuse enough proposition-bearing material that the contribution is
    not genuinely new.
    """
    current = _semantic_coverage_tokens(utterance)
    if len(current) < 6 or not prior_turns:
        return False

    prior: set[str] = set()
    for turn in prior_turns:
        if isinstance(turn, dict):
            prior.update(_semantic_coverage_tokens(turn.get("text")))

    overlap = current & prior
    coverage = len(overlap) / max(1, len(current))
    if len(overlap) >= 8 and coverage >= 0.68:
        return True
    if len(overlap) >= 10 and coverage >= 0.50:
        return True
    return False


def _consensus_same_beat_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Detect a later voice rebuilding a semantic core earlier voices converged on.

    Exact phrase shingles miss a live failure where each earlier voice contributes
    part of the same proposition and the later voice recombines those anchors with
    new connective language. Count each prior speaker only once, then require both
    a multi-speaker consensus core and substantial aggregate borrowing. This keeps
    ordinary synthesis of two distinct facts legal because distinct facts do not
    create a repeated consensus core across prior voices.
    """
    current = _semantic_coverage_tokens(utterance)
    if len(current) < 10 or len(prior_turns) < 2:
        return False

    by_speaker: dict[str, set[str]] = {}
    for index, turn in enumerate(prior_turns):
        if not isinstance(turn, dict):
            continue
        speaker = str(turn.get("speaker") or f"prior-{index}").lower()
        by_speaker.setdefault(speaker, set()).update(
            _semantic_coverage_tokens(turn.get("text"))
        )
    if len(by_speaker) < 2:
        return False

    frequency: Counter[str] = Counter()
    aggregate: set[str] = set()
    for tokens in by_speaker.values():
        aggregate.update(tokens)
        frequency.update(tokens)

    borrowed = current & aggregate
    consensus = {token for token in current if frequency[token] >= 2}
    coverage = len(borrowed) / max(1, len(current))
    return len(consensus) >= 3 and len(borrowed) >= 7 and coverage >= 0.30


def same_beat_issue(utterance: object, prior_turns: list[dict]) -> str | None:
    """Preserve established classification order, then add the narrow phrase rule."""
    issue = _original_same_beat_issue(utterance, prior_turns)
    if issue:
        return issue
    text = str(utterance or "").strip()
    turns = [item for item in (prior_turns or []) if isinstance(item, dict)]
    # Preserve the pre-PR130 aggregate reason code for older live regressions such
    # as 4784. Only content that escaped the established aggregate boundary reaches
    # the new single-prior phrase-cluster classifier.
    if text and turns and _aggregate_same_beat_echo(text, turns):
        return "same_beat_semantic_coverage"
    if text and turns and _single_prior_phrase_echo(text, turns):
        return "same_beat_phrase_echo"
    if text and turns and _consensus_same_beat_echo(text, turns):
        return "same_beat_consensus_echo"
    return None


# quality_issue is a function defined in the core module, so its globals resolve
# there. Patch the core binding as well; this makes every existing caller inherit
# the strengthened predicate without duplicating retry or publication logic.
_core.same_beat_issue = same_beat_issue


class _QualityFacadeModule(types.ModuleType):
    """Keep legacy simulator monkey-patches connected to the core wrapper state."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name == "_original_request":
            setattr(_core, name, value)


# Existing retry/truncation simulations intentionally replace
# room_expression_quality._original_request. Preserve that public test seam even
# though the implementation body is now stored in the core module.
sys.modules[__name__].__class__ = _QualityFacadeModule
