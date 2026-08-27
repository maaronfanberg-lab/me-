from __future__ import annotations

import copy
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import history_sanitizer
import room2_firewall_adapter
import room2_guardrails
import vault_talker

_original_has_ngram_echo = vault_talker._has_ngram_echo
_original_quality_check = vault_talker.quality_check
_original_request = vault_talker._request

BOILERPLATE = (
    "grateful for the opportunity",
    "appreciating the opportunity",
    "opportunity to share my perspective",
    "opportunity to engage",
    "meaningful conversations with you",
    "taking measures, you know that",
    "grateful for these moments",
    "moments of connection",
)
GENERIC_SENTIMENT = re.compile(
    r"\b(?:i(?:'m| am)\s+)?(?:grateful|thankful|appreciative)\b.{0,45}\b(?:moment|moments|connection|conversation|opportunity)\b",
    re.I,
)
FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "because", "if", "when", "while", "that", "this", "these",
    "to", "of", "for", "with", "from", "in", "on", "at", "is", "are", "was", "were", "be", "been",
    "my", "our", "your", "it", "its", "i", "i'm", "i've", "i'd", "me", "we", "you",
}


def _balanced_echo_guard(text, sources, n=5):
    effective_n = 7 if n == 5 else (9 if n >= 7 else n)
    return _original_has_ngram_echo(text, sources, n=effective_n)


def _compact_text(value: object, limit: int = 6) -> str:
    """Keep ordered concepts while removing source sentence structure."""
    words = re.findall(r"[a-z0-9']+", str(value or "").lower())
    out: list[str] = []
    for word in words:
        if len(word) < 4 or word in vault_talker.STOPWORDS:
            continue
        if word not in out:
            out.append(word)
        if len(out) >= limit:
            break
    return " ".join(out)


def _compact_request(model_url: str, payload: dict, entity: str, attempt: int, cycle: int) -> str:
    # Preserve ideas but remove copyable syntax. A complete cue sentence encourages grammatical output
    # better than handing a tiny model a naked keyword pile.
    compact = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    for key in ("CONTEXT", "ROOM2"):
        items = compact.get(key) if isinstance(compact.get(key), list) else []
        reduced = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cue = _compact_text(item.get("text"))
            if cue:
                concepts = ", ".join(cue.split())
                reduced.append({
                    "speaker": str(item.get("speaker") or "")[:40],
                    "text": f"Topic cues: {concepts}.",
                })
        compact[key] = reduced
    return _original_request(model_url, compact, entity, attempt, cycle)


def _looks_telegraphic(text: str) -> bool:
    words = re.findall(r"[a-z0-9']+", str(text or "").lower())
    if len(words) < 7:
        return True
    # Several tiny comma-separated noun/verb chunks are characteristic of the 1B model collapsing
    # its keyword cues into word salad rather than forming a sentence.
    chunks = [c.strip() for c in str(text or "").rstrip(".?!").split(",")]
    if len(chunks) >= 3 and sum(len(re.findall(r"[a-z0-9']+", c.lower())) <= 3 for c in chunks) >= 2:
        return True
    function_count = sum(w in FUNCTION_WORDS for w in words)
    if len(words) >= 8 and function_count / len(words) < 0.18:
        return True
    return False


def _hardened_quality_check(text, entity, recent, live_context, archive):
    accepted, reason = _original_quality_check(text, entity, recent, live_context, archive)
    if not accepted:
        return accepted, reason
    grounding = list(live_context) + list(recent[-6:])
    low = str(text or "").lower()
    grounding_text = " ".join(str(x.get("text") or "") for x in grounding if isinstance(x, dict)).lower()
    if any(p in low and p not in grounding_text for p in BOILERPLATE) or GENERIC_SENTIMENT.search(low):
        return False, "generic_boilerplate"
    if _looks_telegraphic(text):
        return False, "telegraphic_syntax"
    if len(re.findall(r"[.!?](?:\s|$)", str(text or ""))) > 1:
        return False, "multiple_sentences"
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
    if len(argv) < 4:
        return {"removed": 0, "kept": 0}
    path = Path(argv[3])
    value = vault_talker._load(path, [])
    clean, stats = history_sanitizer.sanitize_history(value)
    vault_talker._atomic_json(path, clean)
    return stats


def _arg_value(flag: str) -> str | None:
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except Exception:
        return None


def _postflight() -> None:
    feed_path = Path(sys.argv[1])
    report_path = Path(sys.argv[2])
    history_path = Path(sys.argv[3])
    result_arg = _arg_value("--result")
    if not result_arg:
        raise SystemExit("missing --result")
    result_path = Path(result_arg)
    clean, stats = history_sanitizer.sanitize_history(vault_talker._load(history_path, []))
    vault_talker._atomic_json(history_path, clean)
    sanitizer_path = history_path.parent / "sanitizer-report.json"
    vault_talker._atomic_json(sanitizer_path, stats)
    report = vault_talker._load(report_path, {})
    heartbeat = {
        "version": "room-2-heartbeat-v3",
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": os.environ.get("ROOM2_RUN_ID"),
        "source_cycle": report.get("source_cycle"),
        "health": (report.get("health") or {}).get("status") if isinstance(report.get("health"), dict) else None,
        "conversation_size": len(clean),
        "llm_active": True,
        "feedback_loop": True,
        "sanitizer_removed": int(stats.get("removed") or 0),
    }
    heartbeat_path = history_path.parent / "heartbeat.json"
    vault_talker._atomic_json(heartbeat_path, heartbeat)
    firewall = room2_firewall_adapter.validate(
        vault_talker._load(feed_path, {}), report, clean,
        vault_talker._load(result_path, {}), stats, heartbeat,
    )
    vault_talker._atomic_json(history_path.parent / "firewall-report.json", firewall)
    if not firewall.get("ok"):
        raise SystemExit("ROOM 2 runtime firewall: " + ",".join(firewall.get("failures", [])[:20]))


def main() -> None:
    stats = sanitize_history_argument(sys.argv)
    if stats.get("removed"):
        print(f"ROOM 2 quarantined {stats['removed']} persisted utterance(s).")
    vault_talker._has_ngram_echo = _balanced_echo_guard
    vault_talker._request = _compact_request
    vault_talker.quality_check = _hardened_quality_check
    vault_talker.main()
    _postflight()


if __name__ == "__main__":
    main()
