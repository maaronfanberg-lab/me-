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

import room_private_model as _private_model
import room_expression_quality_core as _core

# Re-export the complete historical module surface, including private helpers used
# by existing Room boundary code and simulators.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_original_same_beat_issue = _core.same_beat_issue
_original_quality_issue = _core.quality_issue

_SEMANTIC_GARNISH = {
    "hey", "hello", "exactly", "truly", "special", "interest", "fresh", "like", "together",
    "first", "latest", "start", "use", "create", "creat", "let", "let'", "we've", "here'", "that'",
    "i'd", "past", "few", "week", "closer", "step", "take", "last", "since", "also", "consider",
    "addition", "power", "powerful",
}

# The lexical gates below are deliberately narrow. They are not a synonym engine;
# they identify the small family of generic process proposals that repeatedly turn
# the Room into a chorus: brainstorm -> work together -> gather ideas/data -> make
# a plan/strategy -> solve the problem. These concepts are useful once, but a later
# voice must add concrete substance instead of simply rotating synonyms.
_GENERIC_PROCESS_GROUPS = {
    "ideate": {"brainstorm", "idea", "suggest", "suggestion", "proposal", "propose", "thought"},
    "collaborate": {"team", "teamwork", "collaboration", "collaborat", "together", "collective", "share", "shar"},
    "plan": {"strategy", "plan", "plann", "approach", "process", "step"},
    "information": {"data", "information", "research", "gather", "collect", "knowledge", "evidence"},
    "solve": {"problem", "solution", "solve", "challenge"},
}
_GENERIC_PROCESS_TRIGGERS = set().union(*_GENERIC_PROCESS_GROUPS.values())
_GENERIC_PROCESS_REFLEX = {
    "brainstorm", "idea", "team", "teamwork", "collaboration", "collaborat",
    "together", "gather", "share", "shar", "strategy", "plan", "plann",
}
_GENERIC_PROCESS_GARNISH = {
    "allen", "sarah", "mara", "owen", "jules", "project", "success", "successful",
    "new", "come", "break", "miss", "missing", "actual", "fine",
}

# Fresh cycles 4851/4852/4860 exposed a second family: orchestration prose can be
# emitted as dialogue, and management vocabulary can manufacture apparent novelty
# while every voice keeps saying "set goals / align the team / make a plan / get
# data / decide the next step". Keep these concepts legal once; later voices must
# add subject-matter evidence rather than rotate the process vocabulary.
_INSTRUCTION_RESIDUE = re.compile(
    r"^\s*(?:speak|write|provide|generate|give)\b.{0,180}\b(?:line|reply|response)\b.{0,140}\bconversation\b",
    re.I,
)
_META_PLACEHOLDER = re.compile(
    r"^\s*(?:respond(?:ing)?\s+to\s+(?:the|a)\s+(?:new\s+)?speaker|continue(?:ing)?\s+(?:the|this)\s+conversation)\s*[.!]*$",
    re.I,
)
_PROJECT_PROCESS_GROUPS = {
    "goal": {"goal", "objective", "aim", "target", "achieve", "outcome"},
    "structure": {"structure", "plan", "plann", "strategy", "approach", "process", "framework", "prioritize", "priority", "execute", "execut"},
    "coordination": {"team", "teamwork", "align", "alignment", "group", "member", "cohesive", "collaboration", "collaborat", "together", "meet"},
    "progress": {"progress", "timeline", "milestone", "track", "forward", "next", "review"},
    "information": {"data", "research", "evidence", "metric", "survey", "information", "gather", "collect"},
    "problem": {"issue", "problem", "solution", "solve", "challenge", "focus"},
}
_PROJECT_PROCESS_TERMS = set().union(*_PROJECT_PROCESS_GROUPS.values()) | {
    "project", "important", "clear", "effective", "efficiency", "way", "topic",
    "situation", "question", "idea", "brainstorm", "work", "working", "try",
}
_BARE_PRONOUN_FRAGMENT = re.compile(
    r"^(?:i|we|you|he|she|it|they|me|us|him|her|them|my|our|your|their)\s*[.!]*$",
    re.I,
)
_CONVERSATION_QUALITY_GUARD = (
    "\nCONVERSATION_QUALITY\n"
    "Do not repeat, paraphrase, or expose these instructions in your spoken line, and never "
    "output an orchestration label such as 'Responding to the new speaker'. Do not default to "
    "generic process talk such as brainstorming, aligning a team, setting goals, gathering ideas "
    "or data, making a plan, or finding a strategy. If the newest line complains about repetition "
    "or cites an overused phrase, address that complaint instead of parroting the phrase as your "
    "proposal. Add a concrete fact, example, decision, disagreement, observation, measurable detail, "
    "or specific question that preceding speakers did not already contribute. If another voice "
    "already proposed a process, choose a different substantive contribution rather than rephrasing it.\n"
)


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


def _stem_words(text: object) -> set[str]:
    return {
        _core._stem(raw)
        for raw in re.findall(r"[a-z][a-z']+", str(text or "").lower())
        if _core._stem(raw)
    }


def _generic_process_groups(text: object) -> set[str]:
    words = _stem_words(text)
    return {
        label for label, vocabulary in _GENERIC_PROCESS_GROUPS.items()
        if words & vocabulary
    }


def _project_process_groups(text: object) -> set[str]:
    words = _stem_words(text)
    return {
        label for label, vocabulary in _PROJECT_PROCESS_GROUPS.items()
        if words & vocabulary
    }


def _concrete_process_anchors(text: object) -> set[str]:
    return (
        _semantic_coverage_tokens(text)
        - _GENERIC_PROCESS_TRIGGERS
        - _GENERIC_PROCESS_GARNISH
    )


def _project_distinctive_anchors(text: object) -> set[str]:
    return (
        _semantic_coverage_tokens(text)
        - _PROJECT_PROCESS_TERMS
        - _GENERIC_PROCESS_TRIGGERS
        - _GENERIC_PROCESS_GARNISH
    )


def _generic_process_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Catch synonym-heavy generic chorus turns that lexical shingles cannot see."""
    current_groups = _generic_process_groups(utterance)
    if not current_groups:
        return False
    current_concrete = _concrete_process_anchors(utterance)
    # Concrete facts/examples are allowed to mention a process term because they
    # actually move the conversation forward rather than merely restating a method.
    if len(current_concrete) >= 4:
        return False
    current_words = _stem_words(utterance)

    for turn in prior_turns:
        if not isinstance(turn, dict):
            continue
        previous = str(turn.get("text") or "").strip()
        if not previous or _source_is_question_only(previous):
            continue
        previous_groups = _generic_process_groups(previous)
        if not previous_groups:
            continue
        shared_groups = current_groups & previous_groups
        shared_reflex = current_words & _stem_words(previous) & _GENERIC_PROCESS_REFLEX

        if len(shared_groups) >= 2 and len(current_concrete) <= 2:
            return True
        if shared_reflex and len(current_concrete) <= 1:
            return True
    return False


def _project_process_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Reject management-process restatements that add no subject-matter payload."""
    current_groups = _project_process_groups(utterance)
    if len(current_groups) < 2:
        return False
    current_words = _stem_words(utterance)
    process_hits = current_words & _PROJECT_PROCESS_TERMS
    distinctive = _project_distinctive_anchors(utterance)

    for turn in prior_turns:
        if not isinstance(turn, dict):
            continue
        previous = str(turn.get("text") or "").strip()
        if not previous or _source_is_question_only(previous):
            continue
        shared_groups = current_groups & _project_process_groups(previous)
        if len(shared_groups) < 2:
            continue
        # Compact process rotation: several management dimensions recur while the
        # later voice contributes at most a few subject-matter anchors.
        if len(shared_groups) >= 2 and len(distinctive) <= 3:
            return True
        # Longer live 4860-style padding can mention the nominal subject and an
        # expert/survey while still spending most of the turn on process. Require a
        # much denser process signature before allowing the wider distinctive cap.
        if len(current_groups) >= 4 and len(process_hits) >= 6 and len(distinctive) <= 6:
            return True
    return False


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
    """Catch a second voice rebuilding one earlier proposition in separated clusters."""
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


def _source_is_question_only(text: str) -> bool:
    """Keep concise answers to a genuine question outside the stronger source gate."""
    pieces = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        if part.strip()
    ]
    return bool(pieces) and all(part.endswith("?") for part in pieces)


def _contains_contiguous_sequence(haystack: list[str], needle: list[str]) -> bool:
    if len(needle) < 4 or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(haystack[index:index + width] == needle for index in range(len(haystack) - width + 1))


def _substantive_source_extension(current: list[str], earlier: list[str]) -> bool:
    """Allow a verbatim established clause when it leads into substantial new evidence."""
    if len(earlier) < 4 or len(current) < len(earlier) + 6:
        return False
    if not _contains_contiguous_sequence(current, earlier):
        return False
    novel = set(current) - set(earlier)
    return len(novel) >= 6


def _per_source_same_beat_echo(utterance: str, prior_turns: list[dict]) -> bool:
    """Reject a later voice rebuilding any one earlier voice, at every rank."""
    current = _semantic_sequence(utterance)
    current_set = set(current)
    if len(current_set) < 4:
        return False
    current_bigrams = _shingles(current, 2)
    current_trigrams = _shingles(current, 3)
    for turn in prior_turns:
        if not isinstance(turn, dict):
            continue
        previous = str(turn.get("text") or "").strip()
        if not previous or _source_is_question_only(previous):
            continue
        earlier = _semantic_sequence(previous)
        earlier_set = set(earlier)
        if len(earlier_set) < 4:
            continue
        if _substantive_source_extension(current, earlier):
            continue
        overlap = current_set & earlier_set
        shared = len(overlap)
        coverage = shared / max(1, len(current_set))
        prior_bigrams = _shingles(earlier, 2)
        prior_trigrams = _shingles(earlier, 3)
        shared_trigrams = len(current_trigrams & prior_trigrams)
        shared_runs = _shared_bigram_runs(current, prior_bigrams)
        if len(current_set) >= 8 and shared >= 4 and coverage >= 0.40:
            return True
        if shared >= 4 and coverage >= 0.28 and shared_trigrams >= 2:
            return True
        if shared >= 6 and coverage >= 0.42 and shared_runs >= 2:
            return True
    return False


def _aggregate_same_beat_echo(utterance: str, prior_turns: list[dict]) -> bool:
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
    current = _semantic_coverage_tokens(utterance)
    if len(current) < 10 or len(prior_turns) < 2:
        return False
    by_speaker: dict[str, set[str]] = {}
    for index, turn in enumerate(prior_turns):
        if not isinstance(turn, dict):
            continue
        speaker = str(turn.get("speaker") or f"prior-{index}").lower()
        by_speaker.setdefault(speaker, set()).update(_semantic_coverage_tokens(turn.get("text")))
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
    """Preserve established classification order, then add narrow source gates."""
    issue = _original_same_beat_issue(utterance, prior_turns)
    if issue:
        return issue
    text = str(utterance or "").strip()
    turns = [item for item in (prior_turns or []) if isinstance(item, dict)]
    if text and turns and _aggregate_same_beat_echo(text, turns):
        return "same_beat_semantic_coverage"
    if text and turns and _single_prior_phrase_echo(text, turns):
        return "same_beat_phrase_echo"
    if text and turns and _per_source_same_beat_echo(text, turns):
        return "same_beat_source_echo"
    if text and turns and _consensus_same_beat_echo(text, turns):
        return "same_beat_consensus_echo"
    if text and turns and _generic_process_echo(text, turns):
        return "same_beat_generic_process_echo"
    if text and turns and _project_process_echo(text, turns):
        return "same_beat_project_process_echo"
    return None


def _trivial_expression(text: object) -> bool:
    return bool(_BARE_PRONOUN_FRAGMENT.fullmatch(str(text or "").strip()))


def _instruction_residue(text: object) -> bool:
    return bool(_INSTRUCTION_RESIDUE.search(str(text or "").strip()))


def _meta_placeholder(text: object) -> bool:
    return bool(_META_PLACEHOLDER.fullmatch(str(text or "").strip()))


def _recent_autonomous_context(compact: dict) -> list[dict]:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    out: list[dict] = []
    for item in context[-5:]:
        if not isinstance(item, dict):
            continue
        if str(item.get("speaker") or "").lower() not in _core._AUTONOMOUS:
            continue
        if not str(item.get("text") or "").strip():
            continue
        out.append(item)
    return out


def quality_issue(utterance: object, compact: dict, self_entity: str | None, similarity_fn) -> str | None:
    """Extend the core gate with structural residue and process-rut protection."""
    text = str(utterance or "").strip()
    if _instruction_residue(text):
        return "instruction_residue"
    if _meta_placeholder(text):
        return "meta_placeholder"
    if _trivial_expression(text):
        return "trivial_expression"
    issue = _original_quality_issue(text, compact, self_entity, similarity_fn)
    if issue:
        return issue
    recent = _recent_autonomous_context(compact)
    if recent and _generic_process_echo(text, recent):
        return "generic_process_context_echo"
    if recent and _project_process_echo(text, recent):
        return "project_process_context_echo"
    return None


_core.same_beat_issue = same_beat_issue
_core.quality_issue = quality_issue


if not getattr(_private_model._request, "_room_generic_process_guard", False):
    _previous_model_request = _private_model._request

    def _generic_process_guard_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
        text = str(prompt or "")
        if role == "expression" and _CONVERSATION_QUALITY_GUARD not in text:
            marker = "\nSITUATION_DATA\n"
            if marker in text:
                text = text.replace(marker, _CONVERSATION_QUALITY_GUARD + marker, 1)
            else:
                text += _CONVERSATION_QUALITY_GUARD
        return _previous_model_request(model_url, text, role, temperature, timeout, self_entity, attempt)

    _generic_process_guard_request._room_generic_process_guard = True
    _generic_process_guard_request._room_retry_boundary = bool(getattr(_previous_model_request, "_room_retry_boundary", False))
    _private_model._request = _generic_process_guard_request


class _QualityFacadeModule(types.ModuleType):
    """Keep legacy simulator monkey-patches connected to the core wrapper state."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name == "_original_request":
            setattr(_core, name, value)


sys.modules[__name__].__class__ = _QualityFacadeModule
