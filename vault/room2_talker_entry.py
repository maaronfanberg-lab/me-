from __future__ import annotations

import sys
from pathlib import Path

import history_sanitizer
import room2_guardrails
import vault_talker

_original_has_ngram_echo = vault_talker._has_ngram_echo
_original_quality_check = vault_talker.quality_check


def _balanced_echo_guard(text, sources, n=5):
    # Recent context: reject six-word copying. Full archive: require eight words.
    # This protects originality without making ordinary English impossible for a 1B model.
    effective_n = 6 if n == 5 else (8 if n >= 7 else n)
    return _original_has_ngram_echo(text, sources, n=effective_n)


def _hardened_quality_check(text, entity, recent, live_context, archive):
    accepted, reason = _original_quality_check(text, entity, recent, live_context, archive)
    if not accepted:
        return accepted, reason
    grounding = list(live_context) + list(recent[-6:])
    if room2_guardrails.has_unsupported_accusation(text):
        return False, "unsupported_accusation"
    if room2_guardrails.excessive_second_person(text):
        return False, "second_person_excess"
    if room2_guardrails.malformed_identity_claim(text):
        return False, "identity_claim"
    if room2_guardrails.weak_grounding(text, grounding):
        return False, "weak_grounding"
    if room2_guardrails.semantic_repeat(text, recent):
        return False, "semantic_repeat"
    if room2_guardrails.repetitive_opening(text, recent):
        return False, "repetitive_opening"
    return True, "ok"


def sanitize_history_argument(argv: list[str]) -> dict:
    # CLI contract: feed report history --model-url ... --result ...
    if len(argv) < 4:
        return {"removed": 0, "kept": 0}
    path = Path(argv[3])
    value = vault_talker._load(path, [])
    clean, stats = history_sanitizer.sanitize_history(value)
    vault_talker._atomic_json(path, clean)
    return stats


def main() -> None:
    stats = sanitize_history_argument(sys.argv)
    if stats.get("removed"):
        print(f"ROOM 2 quarantined {stats['removed']} persisted utterance(s).")
    vault_talker._has_ngram_echo = _balanced_echo_guard
    vault_talker.quality_check = _hardened_quality_check
    vault_talker.main()


if __name__ == "__main__":
    main()
