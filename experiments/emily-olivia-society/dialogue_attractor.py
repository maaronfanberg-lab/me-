#!/usr/bin/env python3
"""Generic refractory and grounding guards for Emily + Olivia.

These checks never write dialogue or prescribe a topic. They only reject
structurally bad model samples so the same Stanford-derived prompt can be
sampled again.
"""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re

_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)
_TEMPLATE_BLANK = re.compile(
    r"(?:_{2,}|\[\s*(?:blank|fill|insert)[^\]]*\]|\{\{[^}]*\}\}|<blank>)",
    re.IGNORECASE,
)
_TRAILING_CUTOFF = re.compile(r"(?:\.{3,}|…|--+|[,;:])\s*$")
_DANGLING_DETERMINER = re.compile(r"\b(?:the|a|an)\s*$", re.IGNORECASE)
_GREETING_START = re.compile(r"^\s*(?:oh[\s,!]+)?(?:hi|hello|hey)\b", re.IGNORECASE)
_FIRST_PERSON_MARKER = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|my)\b", re.IGNORECASE)
_FINITE_SHORT_CLAUSE = re.compile(
    r"\b(?:am|is|are|was|were|have|has|had|do|does|did|can|could|will|would|"
    r"should|may|might|must|love|loves|like|likes|want|wants|need|needs|know|knows|"
    r"think|thinks|feel|feels|say|says|tell|tells|mean|means|go|goes|come|comes|"
    r"i'm|i've|i'll|i'd|you're|you've|you'll|you'd|we're|we've|we'll|we'd|"
    r"they're|they've|they'll|they'd|it's|that's|can't|don't|doesn't|didn't|won't|"
    r"wouldn't|couldn't|shouldn't|isn't|aren't|wasn't|weren't)\b",
    re.IGNORECASE,
)
_CONCRETE_AUTOBIOGRAPHY = re.compile(
    r"(?:\bi\s+(?:went|visited|travelled|traveled|moved|worked|lived|studied|"
    r"bought|owned|made|built|created)\b|"
    r"\bi(?:'ve|\s+have)\s+(?:got|bought|owned|made|built|created|visited|"
    r"worked|lived|studied)\b|"
    r"\bi\s+(?:just\s+)?got\s+(?:a|an|the)\b|"
    r"\bmy\s+(?:sister|brother|mother|mom|father|dad|parent|parents|husband|"
    r"wife|partner|boyfriend|girlfriend|child|children|son|daughter|boss|"
    r"coworker|roommate|house|home|apartment|car|computer|job|office|school)\b|"
    r"\b(?:last\s+(?:night|week|weekend|month|year)|"
    r"for\s+(?:(?:a|an|one|two|three|several|many|\d+)\s+)?(?:days|weeks|months|years)|"
    r"\d+\s+years?\s+ago)\b)",
    re.IGNORECASE,
)
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had", "has",
    "have", "having", "he", "her", "hers", "him", "his", "how", "i", "if", "in",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours", "she", "so",
    "that", "the", "their", "theirs", "them", "they", "this", "to", "us", "was",
    "we", "were", "what", "when", "where", "which", "who", "why", "will", "with",
    "would", "should", "you", "your", "yours", "emily", "olivia", "hey", "hi",
    "hello", "yeah", "yes", "okay", "ok", "thanks", "thank", "sorry", "please",
    "oh", "uh", "well", "just", "really", "very",
}
_CANONICAL_DROP = {"emily", "olivia", "oh", "well", "okay", "ok", "hey", "hi", "hello", "please"}
_SOCIAL_RESET_FILLER = {
    "oh", "hi", "hello", "hey", "im", "i'm", "i", "am", "here", "happy", "glad",
    "good", "great", "to", "be", "see", "you", "again", "okay", "ok", "well",
    "emily", "olivia",
}
_IRREGULAR = {"making": "make", "taking": "take", "having": "have", "giving": "give", "using": "use", "moving": "move", "going": "go", "doing": "do"}


def _root(word: str) -> str:
    word = word.lower().strip("'")
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if word.endswith("ies") and len(word) >= 6:
        return word[:-3] + "y"
    if word.endswith("ed") and len(word) >= 6:
        base = word[:-2]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if word.endswith("ing") and len(word) >= 7 and not word.endswith("thing"):
        base = word[:-3]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if word.endswith("s") and not word.endswith("ss") and len(word) >= 6:
        return word[:-1]
    return word


def normalized_words(text: str) -> tuple[str, ...]:
    return tuple(raw.lower() for raw in _WORD_RE.findall(str(text or "")))


def canonical_words(text: str) -> tuple[str, ...]:
    return tuple(word for word in normalized_words(text) if word not in _CANONICAL_DROP)


def content_tokens(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(str(text or "")):
        rooted = _root(raw)
        if rooted in _STOP or len(rooted) < 3:
            continue
        tokens.append(rooted)
    return tuple(tokens)


def _pairs(tokens: tuple[str, ...]) -> set[tuple[str, str]]:
    return {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1) if tokens[i] != tokens[i + 1]}


def _is_bare_short_fragment(text: str) -> bool:
    words = normalized_words(text)
    if not 4 <= len(words) <= 7:
        return False
    cleaned = str(text or "").strip()
    if re.search(r"[?!.]\s*$", cleaned):
        return False
    return not bool(_FINITE_SHORT_CLAUSE.search(cleaned))


def _is_short_subset_echo(text: str, histories: list[str]) -> bool:
    candidate = canonical_words(text)
    if not 3 <= len(candidate) <= 10:
        return False
    candidate_set = set(candidate)
    for prior in histories:
        previous = canonical_words(prior)
        if len(previous) < 3:
            continue
        width = len(candidate)
        if width <= len(previous):
            for i in range(len(previous) - width + 1):
                if previous[i : i + width] == candidate:
                    return True
        if len(candidate_set & set(previous)) / max(1, len(candidate_set)) >= 0.90 and len(candidate) <= len(previous) + 2:
            return True
    return False


def _is_cosmetic_echo(text: str, histories: list[str]) -> bool:
    candidate = canonical_words(text)
    if len(candidate) < 3:
        return False
    for prior in histories:
        previous = canonical_words(prior)
        if len(previous) < 3:
            continue
        if candidate == previous:
            return True
        if min(len(candidate), len(previous)) <= 10 and SequenceMatcher(None, candidate, previous, autojunk=False).ratio() >= 0.88:
            return True
    return False


def _is_long_refractory_echo(text: str, histories: list[str]) -> bool:
    candidate = normalized_words(text)
    if len(candidate) < 4:
        return False
    for prior in histories:
        previous = normalized_words(prior)
        if len(previous) < 4:
            continue
        smaller = min(len(candidate), len(previous))
        matcher = SequenceMatcher(None, candidate, previous, autojunk=False)
        if matcher.ratio() >= 0.82 or matcher.find_longest_match().size >= max(4, int(smaller * 0.76)):
            return True
    return False


def _is_repeated_question_stem(text: str, histories: list[str]) -> bool:
    if "?" not in str(text or ""):
        return False
    candidate = canonical_words(text)
    if len(candidate) < 3:
        return False
    for prior in histories:
        if "?" not in prior:
            continue
        previous = canonical_words(prior)
        if len(previous) < 3:
            continue
        smaller = min(len(candidate), len(previous))
        matcher = SequenceMatcher(None, candidate, previous, autojunk=False)
        if matcher.ratio() >= 0.80 or matcher.find_longest_match().size >= max(3, int(smaller * 0.80)):
            return True
    return False


def _is_social_reset(text: str, dialogue_history) -> bool:
    history = list(dialogue_history or [])
    if len(history) < 4 or not _GREETING_START.search(str(text or "")):
        return False
    substance = [word for word in normalized_words(text) if word not in _SOCIAL_RESET_FILLER]
    return len(substance) <= 1


def _recurring_content_blocker(text: str, histories: list[str]) -> str | None:
    candidate = content_tokens(text)
    tokenized = [tokens for tokens in (content_tokens(prior) for prior in histories) if tokens]
    if not candidate or len(tokenized) < 2:
        return None
    token_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    for tokens in tokenized:
        token_counts.update(set(tokens))
        pair_counts.update(_pairs(tokens))
    if len(set(candidate)) == 1 and token_counts[candidate[0]] >= 4:
        return "single_token_attractor"
    if any(pair_counts[pair] >= 2 for pair in _pairs(candidate)):
        return "recurring_pair_attractor"
    candidate_set = set(candidate)
    hot = {token for token, count in token_counts.items() if count >= 3}
    shared = candidate_set & hot
    if len(shared) >= 2 and len(shared) / max(1, len(candidate_set)) >= 0.60:
        return "hot_topic_cluster"
    return None


def _is_role_swapped_fact(text: str, dialogue_history, agent_name: str) -> bool:
    if not agent_name or not _FIRST_PERSON_MARKER.search(str(text or "")):
        return False
    candidate = set(content_tokens(text))
    if len(candidate) < 2:
        return False
    own_support = False
    peer_match = False
    for speaker, prior in list(dialogue_history or [])[-48:]:
        prior_tokens = set(content_tokens(str(prior)))
        if len(prior_tokens) < 2:
            continue
        containment = len(candidate & prior_tokens) / max(1, min(len(candidate), len(prior_tokens)))
        if containment < 0.80:
            continue
        if str(speaker).strip() == agent_name:
            own_support = True
        else:
            peer_match = True
    return peer_match and not own_support


def _is_unsupported_concrete_biography(text: str, dialogue_history, inbound: str, cognitive_context: str) -> bool:
    candidate = set(content_tokens(text))
    if len(candidate) < 2 or not _CONCRETE_AUTOBIOGRAPHY.search(str(text or "")):
        return False
    support_text = " ".join([str(inbound or ""), str(cognitive_context or "")] + [str(prior) for _speaker, prior in list(dialogue_history or [])[-8:]])
    support = set(content_tokens(support_text))
    return not bool(candidate & support)


def candidate_dialogue_blocker(text: str, dialogue_history, *, inbound: str = "", cognitive_context: str = "", agent_name: str = "", history_limit: int = 48) -> str | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "empty_candidate"
    if _TEMPLATE_BLANK.search(cleaned):
        return "template_blank_residue"
    if _TRAILING_CUTOFF.search(cleaned) or _DANGLING_DETERMINER.search(cleaned):
        return "unfinished_cutoff"
    if _is_bare_short_fragment(cleaned):
        return "bare_short_fragment"
    history_rows = list(dialogue_history or [])[-max(1, history_limit):]
    histories = [str(prior).strip() for _speaker, prior in history_rows if str(prior).strip()]
    if _is_short_subset_echo(cleaned, histories):
        return "short_subset_echo"
    if _is_cosmetic_echo(cleaned, histories):
        return "cosmetic_echo"
    if _is_long_refractory_echo(cleaned, histories):
        return "long_refractory_echo"
    if _is_repeated_question_stem(cleaned, histories):
        return "repeated_question_stem"
    if _is_social_reset(cleaned, history_rows):
        return "mid_conversation_social_reset"
    recurring = _recurring_content_blocker(cleaned, histories[-24:])
    if recurring:
        return recurring
    if _is_role_swapped_fact(cleaned, history_rows, agent_name):
        return "role_swapped_personal_fact"
    if _is_unsupported_concrete_biography(cleaned, history_rows, inbound, cognitive_context):
        return "unsupported_concrete_biography"
    return None


def candidate_repeats_recurring_attractor(text: str, dialogue_history, history_limit: int = 48) -> bool:
    return candidate_dialogue_blocker(text, dialogue_history, history_limit=history_limit) is not None


def detect_recurring_content_attractor(messages: list[str]) -> dict | None:
    tokenized = [tokens for tokens in (content_tokens(text) for text in messages) if tokens]
    if len(tokenized) < 4:
        return None
    token_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    for tokens in tokenized:
        token_counts.update(set(tokens))
        pair_counts.update(_pairs(tokens))
    recurring_pairs = sorted(((pair, count) for pair, count in pair_counts.items() if count >= 3), key=lambda x: (-x[1], x[0]))
    recurring_tokens = sorted(((token, count) for token, count in token_counts.items() if count >= 6), key=lambda x: (-x[1], x[0]))
    if recurring_pairs and (recurring_pairs[0][1] >= 5 or len(recurring_pairs) >= 2):
        return {"reason": "recurring_content_attractor", "count": recurring_pairs[0][1], "phrase": " ".join(recurring_pairs[0][0]), "recurring_pairs": [{"phrase": " ".join(pair), "count": count} for pair, count in recurring_pairs[:5]]}
    if recurring_tokens:
        return {"reason": "recurring_single_token_attractor", "count": recurring_tokens[0][1], "phrase": recurring_tokens[0][0], "recurring_pairs": []}
    return None
