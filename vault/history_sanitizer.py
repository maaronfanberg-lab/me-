from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import room2_guardrails

ENTITIES = {"sarah", "mara", "owen", "jules"}
MAX_HISTORY = 120
MAX_TEXT = 360
VALID_REASONS = {
    "latent_candidate", "latent_candidate_fair", "bounded_idle_turn", "bounded_idle_fair",
}
META = ("inner_state", "regime_entropy", "mode_separation", "candidate_budget", "would_request_speech")
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


def _clean(value: object) -> str:
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip()
    return text[:MAX_TEXT].strip()


def _safe_cycle(value: object) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 10**9 else None


def _safe_time(value: object) -> str | None:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if dt > now.replace(microsecond=0) and (dt - now).total_seconds() > 300:
            return None
        if dt.year < 2020 or dt.year > 2100:
            return None
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _stable_id(speaker: str, text: str, at: str | None) -> str:
    raw = f"{speaker}|{text}|{at or ''}".encode("utf-8")
    return "room2-recovered-" + hashlib.sha256(raw).hexdigest()[:20]


def _normalized_text(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _looks_telegraphic(text: str) -> bool:
    words = re.findall(r"[a-z0-9']+", str(text or "").lower())
    chunks = [c.strip() for c in str(text or "").rstrip(".?!").split(",")]
    if len(chunks) >= 3 and sum(len(re.findall(r"[a-z0-9']+", c.lower())) <= 3 for c in chunks) >= 2:
        return True
    function_count = sum(w in FUNCTION_WORDS for w in words)
    return len(words) >= 8 and function_count / len(words) < 0.18


def acceptable_persisted_text(text: str) -> bool:
    text = _clean(text)
    low = text.lower()
    if len(text) < 12 or text[-1:] not in ".?!":
        return False
    if any(term in low for term in META):
        return False
    if any(term in low for term in BOILERPLATE) or GENERIC_SENTIMENT.search(low):
        return False
    if _looks_telegraphic(text):
        return False
    if len(re.findall(r"[.!?](?:\s|$)", text)) > 1:
        return False
    if room2_guardrails.has_unsupported_accusation(text):
        return False
    if room2_guardrails.excessive_second_person(text):
        return False
    if room2_guardrails.malformed_identity_claim(text):
        return False
    words = re.findall(r"[a-z0-9']+", low)
    if not 7 <= len(words) <= 48:
        return False
    if len(set(words)) / max(1, len(words)) < 0.58:
        return False
    return True


def sanitize_history(value: object) -> tuple[list[dict], dict]:
    raw = value if isinstance(value, list) else []
    out: list[dict] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    stats = {
        "removed": 0, "kept": 0, "recovered_ids": 0, "bad_timestamps": 0,
        "duplicate_ids": 0, "duplicate_text": 0, "bad_cycles": 0, "bad_reasons": 0,
    }
    for item in raw[-MAX_HISTORY * 2:]:
        if not isinstance(item, dict):
            stats["removed"] += 1
            continue
        speaker = str(item.get("speaker") or "").lower().strip()
        text = _clean(item.get("text"))
        if speaker not in ENTITIES or not acceptable_persisted_text(text):
            stats["removed"] += 1
            continue
        at = _safe_time(item.get("at"))
        if at is None:
            stats["bad_timestamps"] += 1
            stats["removed"] += 1
            continue
        cycle = _safe_cycle(item.get("source_cycle"))
        if item.get("source_cycle") is not None and cycle is None:
            stats["bad_cycles"] += 1
        item_id = str(item.get("id") or "").strip()[:160]
        if not item_id:
            item_id = _stable_id(speaker, text, at)
            stats["recovered_ids"] += 1
        if item_id in seen_ids:
            stats["duplicate_ids"] += 1
            stats["removed"] += 1
            continue
        normalized = _normalized_text(text)
        if normalized in seen_text:
            stats["duplicate_text"] += 1
            stats["removed"] += 1
            continue
        reason = str(item.get("reason") or "").strip()[:80]
        if reason not in VALID_REASONS:
            if reason:
                stats["bad_reasons"] += 1
            reason = "bounded_idle_turn"
        seen_ids.add(item_id)
        seen_text.add(normalized)
        out.append({
            "id": item_id,
            "speaker": speaker,
            "text": text,
            "at": at,
            "source_cycle": cycle,
            "reason": reason,
        })
    out.sort(key=lambda x: x["at"])
    out = out[-MAX_HISTORY:]
    stats["kept"] = len(out)
    return out, stats


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("history")
    parser.add_argument("--report")
    args = parser.parse_args()
    path = Path(args.history)
    try:
        value = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        value = []
    clean, stats = sanitize_history(value)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)
    if args.report:
        Path(args.report).write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
