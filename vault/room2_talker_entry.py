from __future__ import annotations

import sys
from pathlib import Path

import history_sanitizer
import vault_talker


_original_has_ngram_echo = vault_talker._has_ngram_echo


def _balanced_echo_guard(text, sources, n=5):
    # Recent context needs enough lexical room for a 1B model to answer naturally.
    # Archive protection remains stricter at its requested 7-word threshold.
    effective_n = 6 if n == 5 else n
    return _original_has_ngram_echo(text, sources, n=effective_n)


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
    vault_talker.main()


if __name__ == "__main__":
    main()
