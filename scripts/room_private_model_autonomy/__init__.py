from __future__ import annotations

"""Narrow output guard layered over the current Room autonomy implementation.

This package intentionally loads the existing sibling module unchanged, then adds
one validation check at the public-expression boundary: generated speech must not
reuse distinctive wording from the non-dialogue self/configuration text supplied
for that turn. The check is exact-span based, not semantic, so it does not flatten
ordinary personality expression.
"""

import importlib.util
from pathlib import Path
import re


_IMPL_PATH = Path(__file__).resolve().parent.parent / "room_private_model_autonomy.py"
_SPEC = importlib.util.spec_from_file_location("_room_autonomy_file_impl", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load Room autonomy implementation from {_IMPL_PATH}")
_impl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_impl)

for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

AUTONOMY_ENGINE = "monolithic-single-pass-profile-span-guard-v11"
_ORIGINAL_PUBLIC_META_LANGUAGE = _impl._legacy._public_meta_language

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "hers", "him", "his", "i", "if", "in", "into", "is", "it",
    "its", "may", "me", "might", "my", "no", "not", "of", "on", "or", "our",
    "ours", "she", "should", "so", "than", "that", "the", "their", "theirs",
    "them", "they", "this", "those", "to", "us", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "yours",
}


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", str(value or "").lower())


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    return []


def _configuration_span_reused(utterance: str, compact: dict) -> bool:
    output = _words(utterance)
    if len(output) < 2:
        return False

    output_grams = {
        n: {tuple(output[i:i + n]) for i in range(len(output) - n + 1)}
        for n in (2, 3, 4, 5)
        if len(output) >= n
    }

    sources = _strings(compact.get("self"))
    sources.append(str(_impl.AUTONOMY_PROMPTS.get("expression") or ""))

    for source in sources:
        source_words = _words(source)

        for n in (5, 4, 3):
            if len(source_words) < n or n not in output_grams:
                continue
            for i in range(len(source_words) - n + 1):
                gram = tuple(source_words[i:i + n])
                content = [
                    word for word in gram
                    if word not in _STOPWORDS and len(word) >= 3
                ]
                if len(content) >= 3 and sum(len(word) for word in gram) >= 14 and gram in output_grams[n]:
                    return True

        if len(source_words) >= 2 and 2 in output_grams:
            for i in range(len(source_words) - 1):
                left, right = source_words[i], source_words[i + 1]
                if left in _STOPWORDS or right in _STOPWORDS:
                    continue
                if min(len(left), len(right)) < 4 or max(len(left), len(right)) < 10:
                    continue
                if (left, right) in output_grams[2]:
                    return True

    return False


def _public_meta_language(utterance: str, compact: dict) -> bool:
    if _ORIGINAL_PUBLIC_META_LANGUAGE(utterance, compact):
        return True
    return _configuration_span_reused(utterance, compact)


def run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
    # room_engine_v5 applies production wrappers to the imported autonomy module.
    # Mirror those live wrapper references into the sibling implementation before
    # delegating so the existing masking/copy-rejection path remains intact.
    _impl._request_autonomy = globals().get("_request_autonomy", _impl._request_autonomy)
    _impl._has_context_echo = globals().get("_has_context_echo", _impl._has_context_echo)
    _impl.AUTONOMY_ENGINE = AUTONOMY_ENGINE
    _impl._legacy._public_meta_language = _public_meta_language
    _impl._legacy.AUTONOMY_ENGINE = AUTONOMY_ENGINE
    return _impl.run(role, payload, timeout=timeout, min_words=min_words)
