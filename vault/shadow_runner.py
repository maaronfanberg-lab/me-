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

STATE_VERSION = 5
MAX_TEXT_CHARS = 1200
MAX_NEW_MESSAGES = 200
RECENT_ID_LIMIT = 2048
BOOTSTRAP_MESSAGES = 40
EVENT_HOMEOSTASIS = 0.96
SELF_EVENT_SCALE = 0.35

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
    except (TypeError, ValueError, OverflowError):
        return None
    return cycle if 0 <= cycle <= 10**12 else None


def parse_minute(value: object) -> float | None:
    text = str(value or "").strip()[:100]
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
    pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def token_score(text: str, terms: tuple[str, ...]) -> float:
    hits = sum(1 for term in terms if _term_present(text, term))
    return min(1.0, hits / 2.0)


def semantic_event_delta(entity: str, speaker: str, text: str) -> list[float]:
    body = str(text or "")[:MAX_TEXT_CHARS]
    scores = [token_score(body, terms) for terms in LEXICONS]
    if _term_present(body, "not sure") or _term_present(body, "don't know"):
        scores[4] *= 0.25
    mention = 1.0 if re.search(rf"(?<!\w){re.escape(entity)}(?!\w)", body, flags=re.I) else 0.0
    question = 1.0 if "?" in body else 0.0
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


def _repair_entity(feed: dict, entity: str, data: object, fallback_minute: float) -> tuple[dict, bool]:
    if not isinstance(data, dict) or str(data.get("entity")) != entity:
        return _fresh_entity(feed, entity, fallback_minute).__dict__, True
    latent = data.get("latent")
    minute = finite_float(data.get("minute"), float("nan"))
    if not isinstance(latent, list) or len(latent) != 8 or not math.isfinite(minute):
        return _fresh_entity(feed, entity, fallback_minute).__dict__, True
    cleaned = [finite_float(v, float("nan")) for v in latent]
    if not all(math.isfinite(v) for v in cleaned):
        return _fresh_entity(feed, entity, fallback_minute).__dict__, True
    cleaned = [clamp(v) for v in cleaned]
    obs = project_observables(cleaned)
    regimes = softmax(regime_logits(obs))
    state = EntityState(
        version=1,
        entity=entity,
        minute=max(0.0, minute),
        latent=cleaned,
        regimes=regimes,
        entropy=normalized_entropy(regimes),
        last_event_hash=str(data.get("last_event_hash"))[:64] if data.get("last_event_hash") else None,
    )
    return state.__dict__, False


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
    if data.get("version") not in {3, 4, STATE_VERSION}:
        fresh["recovery_count"] = min(10**6, int(finite_float(data.get("recovery_count"), 0.0)) + 1)
        fresh["recovery_reason"] = "unsupported_state_version"
        return fresh

    migrated = dict(data)
    migrated["version"] = STATE_VERSION
    migrated.setdefault("recent_message_ids", [])
    migrated.setdefault("decision_meta", {})
    migrated.setdefault("source_cycle", None)
    migrated.setdefault("has_observed_feed", bool(migrated.get("last_message_id")))
    migrated["recovery_count"] = min(10**6, max(0, int(finite_float(migrated.get("recovery_count"), 0.0))))
    ids = migrated.get("recent_message_ids") if isinstance(migrated.get("recent_message_ids"), list) else []
    migrated["recent_message_ids"] = [str(x)[:160] for x in ids[-RECENT_ID_LIMIT:] if str(x)]

    generated = parse_minute(feed.get("generated_at")) or 0.0
    entities = migrated.get("entities") if isinstance(migrated.get("entities"), dict) else {}
    recovered = 0
    repaired: dict[str, dict] = {}
    for entity in ENTITIES:
        repaired[entity], did_recover = _repair_entity(feed, entity, entities.get(entity), generated)
        recovered += int(did_recover)
    migrated["entities"] = repaired
    if recovered:
        migrated["recovery_count"] = min(10**6, migrated["recovery_count"] + recovered)
        migrated["recovery_reason"] = "recovered_invalid_entities"
    elif data.get("version") != STATE_VERSION:
        migrated["recovery_reason"] = "migrated_state_v5"
    return migrated


def restore_state(data: dict) -> EntityState:
    return EntityState(
        version=1,
        entity=str(data["entity"]),
        minute=float(data["minute"]),
        latent=[float(v) for v in data["latent"]],
        regimes=[float(v) for v in data["regimes"]],
        entropy=float(data["entropy"]),
        last_event_hash=data.get("last_event_hash"),
    )


def _synthetic_id(msg: dict) -> str:
    canonical = json.dumps({"speaker": msg.get("speaker"), "text": msg.get("text"), "at": msg.get("at")},
                           sort_keys=True, ensure_ascii=False, default=str)
    return "synthetic-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def sanitize_conversation(feed: dict) -> tuple[list[dict], dict]:
    anomalies = {
        "invalid_messages": 0, "synthetic_ids": 0, "duplicate_ids": 0, "truncated_texts": 0,
        "future_timestamps": 0, "out_of_order_timestamps": 0, "cursor_missing": False,
        "backlog_capped": 0, "clock_regressed": False, "cycle_regressed": False,
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
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if not text:
            anomalies["invalid_messages"] += 1
            continue
        if len(text) > MAX_TEXT_CHARS:
            anomalies["truncated_texts"] += 1
            text = text[:MAX_TEXT_CHARS]
        msg = {
            "id": str(item.get("id") or "").strip()[:160],
            "speaker": str(item.get("speaker") or "unknown").strip().lower()[:64] or "unknown",
            "text": text,
            "at": str(item.get("at") or "")[:100],
        }
        if not msg["id"]:
            msg["id"] = _synthetic_id(msg)
            anomalies["synthetic_ids"] += 1
        cleaned.append(msg)
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
    recent = set(str(x) for x in (envelope.get("recent_message_ids") or []))
    last_id = str(envelope.get("last_message_id") or "")
    ids = {str(msg.get("id")) for msg in conversation}
    if last_id and last_id not in ids:
        anomalies["cursor_missing"] = True
    if not bool(envelope.get("has_observed_feed")):
        candidates = conversation[-BOOTSTRAP_MESSAGES:]
    else:
        candidates = [msg for msg in conversation if str(msg.get("id")) not in recent]
    if len(candidates) > MAX_NEW_MESSAGES:
        anomalies["backlog_capped"] = len(candidates) - MAX_NEW_MESSAGES
        candidates = candidates[-MAX_NEW_MESSAGES:]
    return candidates


def run_shadow(feed: dict, envelope: dict) -> tuple[dict, dict]:
    feed = feed if isinstance(feed, dict) else {}
    envelope = envelope if isinstance(envelope, dict) else _fresh_envelope(feed)
    conversation, anomalies = sanitize_conversation(feed)
    new_messages = _select_new_messages(conversation, envelope, anomalies)

    source_cycle = parse_cycle((feed.get("state") or {}).get("cycle") if isinstance(feed.get("state"), dict) else None)
    previous_cycle = parse_cycle(envelope.get("source_cycle"))
    anomalies["cycle_regressed"] = source_cycle is not None and previous_cycle is not None and source_cycle < previous_cycle

    state_minutes = [finite_float((envelope.get("entities") or {}).get(e, {}).get("minute"), 0.0) for e in ENTITIES]
    prior_minute = max(state_minutes) if state_minutes else 0.0
    generated = parse_minute(feed.get("generated_at"))
    if generated is None:
        now_minute = prior_minute
    else:
        anomalies["clock_regressed"] = generated < prior_minute
        now_minute = max(prior_minute, generated)

    diagnostics: dict[str, dict] = {}
    states: dict[str, dict] = {}
    first_entity_event_minute: float | None = None

    for entity in ENTITIES:
        state = restore_state(envelope["entities"][entity])
        starting_regimes = list(state.regimes)
        for msg in new_messages:
            parsed_event_minute = parse_minute(msg.get("at"))
            if parsed_event_minute is None:
                event_minute = state.minute
            else:
                if parsed_event_minute > now_minute:
                    if entity == ENTITIES[0]:
                        anomalies["future_timestamps"] += 1
                    parsed_event_minute = now_minute
                if entity == ENTITIES[0]:
                    if first_entity_event_minute is not None and parsed_event_minute < first_entity_event_minute:
                        anomalies["out_of_order_timestamps"] += 1
                    first_entity_event_minute = parsed_event_minute
                event_minute = max(state.minute, parsed_event_minute)
            state, _ = tick(state, event_minute, None)
            delta = semantic_event_delta(entity, msg.get("speaker", ""), msg.get("text", ""))
            if str(msg.get("speaker") or "").lower() == entity:
                delta = [SELF_EVENT_SCALE * d for d in delta]
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
        diagnostics, source_cycle, envelope.get("decision_meta"), len(new_messages), allow_candidates=allow_candidates
    )
    semantic_summaries = {
        entity: compact_state_text(entity, diagnostics[entity], candidates[entity]) for entity in ENTITIES
    }

    all_ids = [str(msg.get("id")) for msg in conversation if msg.get("id")]
    recent_ids = list(dict.fromkeys(all_ids))[-RECENT_ID_LIMIT:]
    last_message = conversation[-1] if conversation else {}
    health_status = "degraded" if any(bool(v) for v in anomalies.values()) else "ok"

    new_envelope = {
        "version": STATE_VERSION,
        "last_message_id": last_message.get("id") if last_message else envelope.get("last_message_id"),
        "recent_message_ids": recent_ids,
        "entities": states,
        "source_cycle": source_cycle if source_cycle is not None else previous_cycle,
        "decision_meta": decision_meta,
        "has_observed_feed": True,
        "recovery_count": min(10**6, max(0, int(finite_float(envelope.get("recovery_count"), 0.0)))),
    }
    if envelope.get("recovery_reason"):
        new_envelope["recovery_reason"] = str(envelope.get("recovery_reason"))[:100]

    report = {
        "version": "room-2-shadow-v5",
        "source_generated_at": feed.get("generated_at"),
        "production_generated_at": feed.get("production_generated_at"),
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
