from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from decision import choose_candidates
from prompt_adapter import compact_state_text
from room_dynamics import (
    ENTITIES,
    LATENT_BOUND,
    EntityState,
    initial_state,
    l1_change,
    normalized_entropy,
    project_observables,
    regime_logits,
    softmax,
    tick,
)

STATE_VERSION = 4
MAX_TEXT_CHARS = 1200
MAX_NEW_MESSAGES = 200
RECENT_ID_LIMIT = 256
EVENT_HOMEOSTASIS = 0.96

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


def clamp(v: float) -> float:
    return max(-LATENT_BOUND, min(LATENT_BOUND, float(v)))


def finite_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def parse_cycle(value: object) -> int | None:
    try:
        cycle = int(value)
    except (TypeError, ValueError):
        return None
    return cycle if cycle >= 0 else None


def parse_minute(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        minute = dt.timestamp() / 60.0
        return minute if math.isfinite(minute) else None
    except Exception:
        return None


def _term_present(text: str, term: str) -> bool:
    # Word/phrase boundaries avoid accidental hits such as 'how' inside 'show'.
    pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def token_score(text: str, terms: tuple[str, ...]) -> float:
    hits = sum(1 for term in terms if _term_present(text, term))
    return min(1.0, hits / 2.0)


def semantic_event_delta(entity: str, speaker: str, text: str) -> list[float]:
    body = str(text or "")[:MAX_TEXT_CHARS]
    scores = [token_score(body, terms) for terms in LEXICONS]
    # Negated certainty should not simultaneously count as confidence.
    if _term_present(body, "not sure") or _term_present(body, "don't know"):
        scores[4] *= 0.25
    mention = 1.0 if re.search(rf"(?<!\w){re.escape(entity)}(?!\w)", body, flags=re.I) else 0.0
    question = 1.0 if "?" in body else 0.0
    # Deliberately no self-speech reward: otherwise an entity can amplify itself
    # merely because its own previous output is present in the feed.
    return [
        0.055 * scores[0] + 0.025 * scores[2] + 0.015 * question - 0.020 * scores[7],
        0.070 * scores[1] - 0.040 * scores[3],
        0.065 * scores[2] - 0.020 * scores[5],
        0.060 * scores[3] + 0.020 * mention - 0.055 * scores[1],
        0.055 * scores[4] - 0.060 * scores[6],
        0.050 * scores[5] - 0.015 * scores[2],
        0.060 * scores[6] + 0.010 * mention - 0.040 * scores[4],
        0.050 * scores[7] - 0.015 * scores[2],
    ]


def seed_from_genome(state: EntityState, genome: dict) -> None:
    vals = []
    genome = genome if isinstance(genome, dict) else {}
    for i, key in enumerate(GENOME_KEYS):
        trait = finite_float(genome.get(key, 0.5), 0.5)
        trait = max(0.0, min(1.0, trait))
        direction = -1.0 if key in {"skepticism", "inhibition"} else 1.0
        vals.append(clamp(state.latent[i] + direction * (trait - 0.5) * 0.9))
    state.latent = vals
    obs = project_observables(state.latent)
    state.regimes = softmax(regime_logits(obs))
    state.entropy = normalized_entropy(state.regimes)


def _state_valid(data: object, entity: str) -> bool:
    if not isinstance(data, dict) or data.get("entity") != entity:
        return False
    latent = data.get("latent")
    regimes = data.get("regimes")
    if not isinstance(latent, list) or len(latent) != 8:
        return False
    if not isinstance(regimes, list) or len(regimes) != 4:
        return False
    values = latent + regimes + [data.get("minute", 0.0), data.get("entropy", 0.0)]
    return all(math.isfinite(finite_float(v, float("nan"))) for v in values)


def _fresh_entity(feed: dict, entity: str, minute: float) -> EntityState:
    state = initial_state(entity, minute)
    minds = feed.get("minds") if isinstance(feed.get("minds"), dict) else {}
    entities = minds.get("entities") if isinstance(minds.get("entities"), dict) else {}
    entry = entities.get(entity) if isinstance(entities.get(entity), dict) else {}
    seed_from_genome(state, entry.get("genome") if isinstance(entry, dict) else {})
    return state


def _fresh_envelope(feed: dict) -> dict:
    generated = parse_minute(feed.get("generated_at")) or 0.0
    return {
        "version": STATE_VERSION,
        "last_message_id": None,
        "recent_message_ids": [],
        "entities": {entity: _fresh_entity(feed, entity, generated).__dict__ for entity in ENTITIES},
        "source_cycle": None,
        "decision_meta": {},
        "has_observed_feed": False,
        "recovery_count": 0,
    }


def load_envelope(path: Path, feed: dict) -> dict:
    fresh = _fresh_envelope(feed)
    if not path.exists():
        return fresh
    try:
        data = json.loads(path.read_text())
    except Exception:
        fresh["recovery_count"] = 1
        fresh["recovery_reason"] = "corrupt_state_json"
        return fresh
    if not isinstance(data, dict):
        fresh["recovery_count"] = 1
        fresh["recovery_reason"] = "invalid_state_root"
        return fresh

    # Migrate v3 in place rather than throwing away accumulated dynamics.
    version = data.get("version")
    if version not in {3, STATE_VERSION}:
        fresh["recovery_count"] = int(finite_float(data.get("recovery_count"), 0.0)) + 1
        fresh["recovery_reason"] = "unsupported_state_version"
        return fresh

    migrated = dict(data)
    migrated["version"] = STATE_VERSION
    migrated.setdefault("recent_message_ids", [])
    migrated.setdefault("decision_meta", {})
    migrated.setdefault("source_cycle", None)
    migrated.setdefault("has_observed_feed", bool(migrated.get("last_message_id")))
    migrated.setdefault("recovery_count", 0)
    if not isinstance(migrated.get("recent_message_ids"), list):
        migrated["recent_message_ids"] = []
    migrated["recent_message_ids"] = [str(x) for x in migrated["recent_message_ids"][-RECENT_ID_LIMIT:]]

    generated = parse_minute(feed.get("generated_at")) or 0.0
    entities = migrated.get("entities") if isinstance(migrated.get("entities"), dict) else {}
    recovered = 0
    for entity in ENTITIES:
        if not _state_valid(entities.get(entity), entity):
            entities[entity] = _fresh_entity(feed, entity, generated).__dict__
            recovered += 1
    migrated["entities"] = {entity: entities[entity] for entity in ENTITIES}
    if recovered:
        migrated["recovery_count"] = int(finite_float(migrated.get("recovery_count"), 0.0)) + recovered
        migrated["recovery_reason"] = "recovered_invalid_entities"
    return migrated


def restore_state(data: dict) -> EntityState:
    return EntityState(**data)


def _synthetic_id(msg: dict) -> str:
    canonical = json.dumps(
        {"speaker": msg.get("speaker"), "text": msg.get("text"), "at": msg.get("at")},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return "synthetic-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def sanitize_conversation(feed: dict) -> tuple[list[dict], dict]:
    anomalies = {
        "invalid_messages": 0,
        "synthetic_ids": 0,
        "duplicate_ids": 0,
        "truncated_texts": 0,
        "future_timestamps": 0,
        "out_of_order_timestamps": 0,
        "cursor_missing": False,
        "backlog_capped": 0,
        "clock_regressed": False,
        "cycle_regressed": False,
    }
    raw = feed.get("conversation")
    if not isinstance(raw, list):
        raw = []
        anomalies["invalid_messages"] += 1

    cleaned: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            anomalies["invalid_messages"] += 1
            continue
        text = str(item.get("text") or "")
        if len(text) > MAX_TEXT_CHARS:
            anomalies["truncated_texts"] += 1
            text = text[:MAX_TEXT_CHARS]
        msg = {
            "id": str(item.get("id") or "").strip(),
            "speaker": str(item.get("speaker") or "").strip().lower()[:64],
            "text": text,
            "at": item.get("at"),
        }
        if not msg["id"]:
            msg["id"] = _synthetic_id(msg)
            anomalies["synthetic_ids"] += 1
        cleaned.append(msg)

    # Keep the last occurrence of a duplicate id. The latest copy is closest to
    # the production feed's current truth and avoids replay ambiguity.
    seen: set[str] = set()
    deduped_reversed: list[dict] = []
    for msg in reversed(cleaned):
        if msg["id"] in seen:
            anomalies["duplicate_ids"] += 1
            continue
        seen.add(msg["id"])
        deduped_reversed.append(msg)
    return list(reversed(deduped_reversed)), anomalies


def _select_new_messages(conversation: list[dict], envelope: dict, anomalies: dict) -> list[dict]:
    last_id = envelope.get("last_message_id")
    recent = set(str(x) for x in (envelope.get("recent_message_ids") or []))
    if last_id:
        positions = [i for i, msg in enumerate(conversation) if msg.get("id") == last_id]
        if positions:
            candidates = conversation[positions[-1] + 1 :]
        else:
            anomalies["cursor_missing"] = True
            candidates = [msg for msg in conversation if msg.get("id") not in recent]
    else:
        candidates = conversation[-40:]

    if len(candidates) > MAX_NEW_MESSAGES:
        anomalies["backlog_capped"] = len(candidates) - MAX_NEW_MESSAGES
        candidates = candidates[-MAX_NEW_MESSAGES:]
    return candidates


def run_shadow(feed: dict, envelope: dict) -> tuple[dict, dict]:
    feed = feed if isinstance(feed, dict) else {}
    conversation, anomalies = sanitize_conversation(feed)
    new_messages = _select_new_messages(conversation, envelope, anomalies)

    source_cycle = parse_cycle((feed.get("state") or {}).get("cycle") if isinstance(feed.get("state"), dict) else None)
    previous_cycle = parse_cycle(envelope.get("source_cycle"))
    anomalies["cycle_regressed"] = (
        source_cycle is not None and previous_cycle is not None and source_cycle < previous_cycle
    )

    state_minutes = [finite_float(envelope["entities"][e].get("minute"), 0.0) for e in ENTITIES]
    prior_minute = max(state_minutes) if state_minutes else 0.0
    generated = parse_minute(feed.get("generated_at"))
    if generated is None:
        now_minute = prior_minute
    else:
        anomalies["clock_regressed"] = generated < prior_minute
        now_minute = max(prior_minute, generated)

    diagnostics: dict[str, dict] = {}
    states: dict[str, dict] = {}
    previous_event_minute: float | None = None

    for entity in ENTITIES:
        state = restore_state(envelope["entities"][entity])
        starting_regimes = list(state.regimes)
        for msg in new_messages:
            parsed_event_minute = parse_minute(msg.get("at"))
            if parsed_event_minute is None:
                event_minute = state.minute
            else:
                if parsed_event_minute > now_minute:
                    anomalies["future_timestamps"] += 1 if entity == ENTITIES[0] else 0
                    parsed_event_minute = now_minute
                if previous_event_minute is not None and parsed_event_minute < previous_event_minute and entity == ENTITIES[0]:
                    anomalies["out_of_order_timestamps"] += 1
                event_minute = max(state.minute, parsed_event_minute)
                if entity == ENTITIES[0]:
                    previous_event_minute = parsed_event_minute
            state, _ = tick(state, event_minute, None)
            delta = semantic_event_delta(entity, msg.get("speaker", ""), msg.get("text", ""))
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
        states[entity] = state.__dict__
        diagnostics[entity] = diag

    allow_candidates = bool(envelope.get("has_observed_feed")) and not anomalies["cycle_regressed"]
    candidates, decision_meta = choose_candidates(
        diagnostics,
        source_cycle,
        envelope.get("decision_meta"),
        len(new_messages),
        allow_candidates=allow_candidates,
    )
    semantic_summaries = {
        entity: compact_state_text(entity, diagnostics[entity], candidates[entity]) for entity in ENTITIES
    }

    last_message = new_messages[-1] if new_messages else (conversation[-1] if conversation else {})
    recent_ids = [str(x) for x in (envelope.get("recent_message_ids") or [])]
    recent_ids.extend(msg["id"] for msg in new_messages)
    recent_ids = list(dict.fromkeys(recent_ids))[-RECENT_ID_LIMIT:]

    health_status = "degraded" if any(
        [
            anomalies["invalid_messages"],
            anomalies["cursor_missing"],
            anomalies["backlog_capped"],
            anomalies["clock_regressed"],
            anomalies["cycle_regressed"],
            anomalies["future_timestamps"],
        ]
    ) else "ok"

    new_envelope = {
        "version": STATE_VERSION,
        "last_message_id": last_message.get("id") if last_message else envelope.get("last_message_id"),
        "recent_message_ids": recent_ids,
        "entities": states,
        "source_cycle": source_cycle if source_cycle is not None else previous_cycle,
        "decision_meta": decision_meta,
        "has_observed_feed": True,
        "recovery_count": int(finite_float(envelope.get("recovery_count"), 0.0)),
    }
    if envelope.get("recovery_reason"):
        new_envelope["recovery_reason"] = envelope.get("recovery_reason")

    report = {
        "version": "room-vault-shadow-v4",
        "source_generated_at": feed.get("generated_at"),
        "source_cycle": source_cycle,
        "source_brain": (feed.get("brain") or {}).get("active") if isinstance(feed.get("brain"), dict) else None,
        "processed_messages": len(new_messages),
        "production_write_enabled": False,
        "llm_enabled": False,
        "speech_requested": False,
        "candidate_budget": decision_meta["global_candidate_budget"],
        "candidate_selection_enabled": allow_candidates,
        "candidates": candidates,
        "semantic_summaries": semantic_summaries,
        "entities": diagnostics,
        "health": {
            "status": health_status,
            "anomalies": anomalies,
            "recovery_count": new_envelope["recovery_count"],
            "state_version": STATE_VERSION,
        },
    }
    return new_envelope, report


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text)
    os.replace(temp, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed")
    parser.add_argument("--state", default="runtime/shadow-state.json")
    parser.add_argument("--report", default="runtime/report.json")
    args = parser.parse_args()

    feed_path = Path(args.feed)
    try:
        feed = json.loads(feed_path.read_text())
    except Exception as exc:
        raise SystemExit(f"invalid feed JSON: {exc}")
    if not isinstance(feed, dict):
        raise SystemExit("invalid feed JSON: root must be an object")

    state_path = Path(args.state)
    report_path = Path(args.report)
    envelope = load_envelope(state_path, feed)
    envelope, report = run_shadow(feed, envelope)
    atomic_write_text(state_path, json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
