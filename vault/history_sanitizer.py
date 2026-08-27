from __future__ import annotations

import json
import re
from pathlib import Path

ENTITIES = {"sarah", "mara", "owen", "jules"}
MAX_HISTORY = 120
MAX_TEXT = 360
UNSUPPORTED_HOSTILITY = (
    r"\byour demands?\b",
    r"\bgive in to (?:you|your)\b",
    r"\byou (?:always|never)\b",
    r"\byou made me\b",
    r"\byou forced me\b",
    r"\byou're attacking me\b",
    r"\byou are attacking me\b",
    r"\byou're threatening me\b",
    r"\byou are threatening me\b",
)
META = ("inner_state", "regime_entropy", "mode_separation", "candidate_budget", "would_request_speech")


def _clean(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"').strip()
    return text[:MAX_TEXT].strip()


def acceptable_persisted_text(text: str) -> bool:
    text = _clean(text)
    low = text.lower()
    if len(text) < 12 or text[-1:] not in ".?!":
        return False
    if any(term in low for term in META):
        return False
    if any(re.search(pattern, low) for pattern in UNSUPPORTED_HOSTILITY):
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
    seen: set[str] = set()
    removed = 0
    for item in raw[-MAX_HISTORY * 2:]:
        if not isinstance(item, dict):
            removed += 1
            continue
        speaker = str(item.get("speaker") or "").lower()
        text = _clean(item.get("text"))
        item_id = str(item.get("id") or "").strip()[:160]
        if speaker not in ENTITIES or not acceptable_persisted_text(text):
            removed += 1
            continue
        if item_id and item_id in seen:
            removed += 1
            continue
        if item_id:
            seen.add(item_id)
        out.append({
            "id": item_id,
            "speaker": speaker,
            "text": text,
            "at": str(item.get("at") or "")[:100],
            "source_cycle": item.get("source_cycle"),
            "reason": str(item.get("reason") or "")[:80],
        })
    return out[-MAX_HISTORY:], {"removed": removed, "kept": len(out[-MAX_HISTORY:])}


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
