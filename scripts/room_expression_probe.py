#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from room_private_model import run

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
CFG = json.loads((ROOM / "config.json").read_text())
PROFILES = CFG["p"]
ORDER = ["sarah", "mara", "owen", "jules"]
JOBS = {
    "sarah": "Add one concrete example or specific observation that has not already been stated.",
    "mara": "Test or challenge one claim with a reason, exception, or piece of evidence.",
    "owen": "Add a personal or social implication, preference, or consequence that changes the angle.",
    "jules": "Make a comparison or unexpected connection that introduces a genuinely new direction.",
}
OUT = ROOM / "expression-diversity-diagnostic.json"


def norm(text: str) -> str:
    return re.sub(r"\W+", " ", str(text or "").lower()).strip()


def jaccard(a: str, b: str) -> float:
    left, right = set(norm(a).split()), set(norm(b).split())
    return len(left & right) / max(1, len(left | right))


def main() -> int:
    os.environ["ROOM_CYCLE_KEY"] = "focused-expression-diversity-probe"
    context = []
    outputs = []
    error = None
    for entity in ORDER:
        payload = {
            "entity": entity,
            "profile": PROFILES[entity],
            "conversation_job": JOBS[entity],
            "deliberation": {
                "action": "BRIDGE",
                "focus": "weather",
                "new_information_goal": JOBS[entity],
            },
            "event": context[-1] if context else None,
            "context": list(context),
            "topic": {
                "root": "weather",
                "current_facet": "weather",
                "facets": [],
                "shared_references": [],
                "unresolved": [],
            },
            "partner": ORDER[(ORDER.index(entity) + 1) % len(ORDER)],
            "relationship": {},
            "mandatory_speech": True,
        }
        try:
            result = run("expression", payload, timeout=45)
            text = str((result or {}).get("utterance") or "").strip()
            outputs.append({
                "speaker": entity,
                "text": text,
                "target": (result or {}).get("target"),
                "move": (result or {}).get("move"),
                "semantic_terms": (result or {}).get("semantic_terms", []),
            })
            context.append({"speaker": entity, "text": text, "cognition": {"target": (result or {}).get("target")}})
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:240]}"
            break

    texts = [item["text"] for item in outputs if item.get("text")]
    unique = len(set(map(norm, texts)))
    pair_scores = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            pair_scores.append(jaccard(texts[i], texts[j]))
    diagnostic = {
        "status": "accepted" if error is None and len(outputs) == 4 else "failed",
        "error": error,
        "voices": len(outputs),
        "unique_exact": unique,
        "max_pair_similarity": round(max(pair_scores or [0.0]), 3),
        "diversity_pass": error is None and len(outputs) == 4 and unique == 4 and max(pair_scores or [0.0]) < 0.9,
        "outputs": outputs,
    }
    OUT.write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
