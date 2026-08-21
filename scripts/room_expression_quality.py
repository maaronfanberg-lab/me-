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


def same_beat_issue(utterance: object, prior_turns: list[dict]) -> str | None:
    """Preserve existing checks, then reject high aggregate semantic reuse."""
    issue = _original_same_beat_issue(utterance, prior_turns)
    if issue:
        return issue
    text = str(utterance or "").strip()
    turns = [item for item in (prior_turns or []) if isinstance(item, dict)]
    if text and turns and _aggregate_same_beat_echo(text, turns):
        return "same_beat_semantic_coverage"
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
