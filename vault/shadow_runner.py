from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from decision import choose_candidates
from prompt_adapter import compact_state_text
from room_dynamics import ENTITIES, LATENT_BOUND, initial_state, project_observables, regime_logits, softmax, normalized_entropy, tick, l1_change

LEXICONS = (
    ("why", "how", "what", "wonder", "curious", "explore", "new", "novel"),
    ("angry", "upset", "wrong", "fight", "conflict", "stuck", "worse", "distrust"),
    ("new", "novel", "different", "surprise", "change", "strange", "weird"),
    ("love", "like", "appreciate", "together", "friend", "help", "care", "trust"),
    ("know", "sure", "clear", "certain", "understand", "right"),
    ("remember", "before", "again", "past", "used to", "last time"),
    ("maybe", "unclear", "unsure", "confused", "don't know", "not sure", "question"),
    ("keep", "continue", "again", "still", "persist", "finish", "return", "back"),
)
GENOME_KEYS = (
    "curiosity", "emotional_reactivity", "novelty_seeking", "social_sensitivity",
    "skepticism", "attention_persistence", "inhibition", "extraversion",
)
EVENT_HOMEOSTASIS = 0.96


def clamp(v: float) -> float:
    return max(-LATENT_BOUND, min(LATENT_BOUND, float(v)))


def parse_minute(value: object, fallback: float) -> float:
    text = str(value or "").strip()
    if not text:
        return fallback
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp() / 60.0
    except Exception:
        return fallback


def token_score(text: str, terms: tuple[str, ...]) -> float:
    low = text.lower()
    hits = sum(1 for term in terms if term in low)
    return min(1.0, hits / 2.0)


def semantic_event_delta(entity: str, speaker: str, text: str) -> list[float]:
    body = str(text or "")[:1200]
    s = [token_score(body, terms) for terms in LEXICONS]
    mention = 1.0 if re.search(rf"\b{re.escape(entity)}\b", body, flags=re.I) else 0.0
    question = 1.0 if "?" in body else 0.0
    self_speech = 1.0 if speaker == entity else 0.0
    return [
        0.055 * s[0] + 0.025 * s[2] + 0.015 * question - 0.020 * s[7],
        0.070 * s[1] - 0.040 * s[3],
        0.065 * s[2] - 0.020 * s[5],
        0.060 * s[3] + 0.020 * mention - 0.055 * s[1],
        0.055 * s[4] - 0.060 * s[6],
        0.050 * s[5] - 0.015 * s[2],
        0.060 * s[6] + 0.010 * mention - 0.040 * s[4],
        0.050 * s[7] + 0.015 * self_speech - 0.015 * s[2],
    ]


def seed_from_genome(state, genome: dict) -> None:
    vals = []
    for i, key in enumerate(GENOME_KEYS):
        try:
            trait = float(genome.get(key, 0.5))
        except Exception:
            trait = 0.5
        direction = -1.0 if key in {"skepticism", "inhibition"} else 1.0
        vals.append(clamp(state.latent[i] + direction * (trait - 0.5) * 0.9))
    state.latent = vals
    obs = project_observables(state.latent)
    state.regimes = softmax(regime_logits(obs))
    state.entropy = normalized_entropy(state.regimes)


def load_envelope(path: Path, feed: dict) -> dict:
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("version") == 3:
            return data
    generated = parse_minute(feed.get("generated_at"), 0.0)
    entities = {}
    minds = feed.get("minds", {}).get("entities", {}) or {}
    for entity in ENTITIES:
        state = initial_state(entity, generated)
        seed_from_genome(state, (minds.get(entity) or {}).get("genome", {}) or {})
        entities[entity] = state.__dict__
    return {"version": 3, "last_message_id": None, "entities": entities, "source_cycle": None, "decision_meta": {}}


def restore_state(data: dict):
    from room_dynamics import EntityState
    return EntityState(**data)


def run_shadow(feed: dict, envelope: dict) -> tuple[dict, dict]:
    conversation = list(feed.get("conversation") or [])
    last_id = envelope.get("last_message_id")
    start = 0
    if last_id:
        found = False
        for i, msg in enumerate(conversation):
            if msg.get("id") == last_id:
                start = i + 1
                found = True
                break
        if not found:
            start = max(0, len(conversation) - 16)
    else:
        start = max(0, len(conversation) - 40)
    new_messages = conversation[start:]
    now_minute = parse_minute(feed.get("generated_at"), 0.0)
    diagnostics, states = {}, {}

    for entity in ENTITIES:
        state = restore_state(envelope["entities"][entity])
        starting_regimes = list(state.regimes)
        for msg in new_messages:
            event_minute = parse_minute(msg.get("at"), state.minute)
            state, _ = tick(state, max(state.minute, event_minute), None)
            delta = semantic_event_delta(entity, str(msg.get("speaker") or "").lower(), str(msg.get("text") or ""))
            state.latent = [clamp(EVENT_HOMEOSTASIS * v + d) for v, d in zip(state.latent, delta)]
            obs = project_observables(state.latent)
            state.regimes = softmax(regime_logits(obs))
            state.entropy = normalized_entropy(state.regimes)
        state, diag = tick(state, max(state.minute, now_minute), None)
        cumulative_change = l1_change(starting_regimes, state.regimes)
        diag["regime_l1_change"] = cumulative_change
        diag["interesting"] = bool(cumulative_change >= 0.06)
        diag["dominant_regime"] = diag["regime_names"][max(range(4), key=lambda i: diag["regime_probabilities"][i])]
        diag["speech_requested"] = False
        states[entity], diagnostics[entity] = state.__dict__, diag

    state_obj = feed.get("state") or {}
    source_cycle = state_obj.get("cycle")
    candidates, decision_meta = choose_candidates(
        diagnostics, source_cycle, envelope.get("decision_meta"), len(new_messages)
    )
    semantic_summaries = {
        entity: compact_state_text(entity, diagnostics[entity], candidates[entity]) for entity in ENTITIES
    }
    last_message = new_messages[-1] if new_messages else (conversation[-1] if conversation else {})
    new_envelope = {
        "version": 3,
        "last_message_id": last_message.get("id") if last_message else last_id,
        "entities": states,
        "source_cycle": source_cycle,
        "decision_meta": decision_meta,
    }
    report = {
        "version": "room-vault-shadow-v3",
        "source_generated_at": feed.get("generated_at"),
        "source_cycle": source_cycle,
        "source_brain": (feed.get("brain") or {}).get("active"),
        "processed_messages": len(new_messages),
        "production_write_enabled": False,
        "llm_enabled": False,
        "speech_requested": False,
        "candidate_budget": decision_meta["global_candidate_budget"],
        "candidates": candidates,
        "semantic_summaries": semantic_summaries,
        "entities": diagnostics,
    }
    return new_envelope, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("feed")
    p.add_argument("--state", default="runtime/shadow-state.json")
    p.add_argument("--report", default="runtime/report.json")
    args = p.parse_args()
    feed = json.loads(Path(args.feed).read_text())
    state_path, report_path = Path(args.state), Path(args.report)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = load_envelope(state_path, feed)
    envelope, report = run_shadow(feed, envelope)
    state_path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
