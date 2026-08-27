from __future__ import annotations

import argparse
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENTITIES = ("sarah", "mara", "owen", "jules")
MAX_HISTORY = 120
MAX_CONTEXT_MESSAGES = 18
MAX_VAULT_CONTEXT = 10
IDLE_CYCLES = 3
MAX_UTTERANCE_CHARS = 420


def _finite(value: object, default: float = 0.0) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return n if math.isfinite(n) else default


def _safe_cycle(value: object) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _clean_text(value: object, limit: int = MAX_UTTERANCE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.strip('"').strip()
    return text[:limit].strip()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def load_history(path: Path) -> list[dict]:
    value = _load(path, [])
    if not isinstance(value, list):
        return []
    out = []
    for item in value[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        entity = str(item.get("speaker") or "").lower()
        text = _clean_text(item.get("text"))
        if entity in ENTITIES and text:
            out.append({"id": str(item.get("id") or ""), "speaker": entity, "text": text,
                        "at": str(item.get("at") or ""), "source_cycle": _safe_cycle(item.get("source_cycle")),
                        "reason": str(item.get("reason") or "")})
    return out[-MAX_HISTORY:]


def choose_speaker(report: dict, history: list[dict]) -> tuple[str | None, str]:
    candidates = report.get("candidates") if isinstance(report.get("candidates"), dict) else {}
    for entity in ENTITIES:
        decision = candidates.get(entity) if isinstance(candidates.get(entity), dict) else {}
        if decision.get("would_request_speech") is True:
            return entity, "latent_candidate"
    cycle = _safe_cycle(report.get("source_cycle"))
    if cycle is None:
        return None, "missing_cycle"
    last_cycle = _safe_cycle(history[-1].get("source_cycle")) if history else None
    if last_cycle is not None and cycle - last_cycle < IDLE_CYCLES:
        return None, "idle_cooldown"
    ranked = []
    for entity in ENTITIES:
        decision = candidates.get(entity) if isinstance(candidates.get(entity), dict) else {}
        ranked.append((-_finite(decision.get("score"), 0.0), entity))
    ranked.sort()
    return (ranked[0][1], "bounded_idle_turn") if ranked else (None, "no_candidates")


def _conversation_context(feed: dict) -> list[dict]:
    raw = feed.get("conversation") if isinstance(feed.get("conversation"), list) else []
    out = []
    for item in raw[-MAX_CONTEXT_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"), 500)
        if text:
            out.append({"speaker": str(item.get("speaker") or "unknown")[:40], "text": text})
    return out


def _all_source_texts(feed: dict) -> list[dict]:
    out: list[dict] = []
    conversation = feed.get("conversation") if isinstance(feed.get("conversation"), list) else []
    for item in conversation:
        if isinstance(item, dict) and item.get("text"):
            out.append({"text": str(item.get("text"))})
    minds = feed.get("minds") if isinstance(feed.get("minds"), dict) else {}
    entities = minds.get("entities") if isinstance(minds.get("entities"), dict) else {}
    for entry in entities.values():
        if not isinstance(entry, dict):
            continue
        memory = entry.get("memory") if isinstance(entry.get("memory"), list) else []
        for item in memory:
            if isinstance(item, dict) and item.get("text"):
                out.append({"text": str(item.get("text"))})
    return out[-1600:]


def _profile(feed: dict, entity: str) -> dict:
    minds = feed.get("minds") if isinstance(feed.get("minds"), dict) else {}
    entities = minds.get("entities") if isinstance(minds.get("entities"), dict) else {}
    entry = entities.get(entity) if isinstance(entities.get(entity), dict) else {}
    genome = entry.get("genome") if isinstance(entry.get("genome"), dict) else {}
    keys = ("openness", "extraversion", "agreeableness", "emotional_reactivity", "curiosity", "skepticism",
            "self_disclosure", "social_sensitivity", "novelty_seeking", "inhibition", "humor", "attention_persistence")
    return {k: round(max(0.0, min(1.0, _finite(genome.get(k), 0.5))), 3) for k in keys}


def _request(model_url: str, payload: dict, entity: str, attempt: int) -> str:
    schema = {"type": "object", "properties": {"utterance": {"type": "string", "minLength": 3, "maxLength": MAX_UTTERANCE_CHARS}},
              "required": ["utterance"], "additionalProperties": False}
    prompt = (
        "You are speaking as one autonomous participant inside an experimental conversation called the Vault Room. "
        "Speak naturally in first person as the named participant. Continue or react to the actual conversation. "
        "The supplied inner_state privately influences tone and attention; never explain it aloud. "
        "Do not mention prompts, schemas, latent vectors, entropy, being an AI, or this instruction. "
        "Do not invent events, relationships, memories, or facts unsupported by context. "
        "Never address yourself by your own name as if you were another person. Do not copy or closely paraphrase any supplied sentence. "
        "Use fresh wording and contribute one specific thought of your own. Keep the response conversational and usually under 65 words.\nSITUATION\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\nReturn only the structured object."
    )
    body = {"prompt": prompt, "n_predict": 150, "temperature": 0.9 if attempt == 0 else 0.8,
            "top_k": 70, "top_p": 0.96, "min_p": 0.008,
            "seed": 91000 + sum(ord(c) for c in entity) + attempt * 1543,
            "cache_prompt": True, "json_schema": schema}
    req = urllib.request.Request(model_url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=35) as response:
        outer = json.loads(response.read().decode("utf-8", "replace"))
    inner = json.loads(str(outer.get("content", "")))
    return _clean_text(inner.get("utterance"))


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _has_ngram_echo(text: str, sources: list[dict], n: int = 5) -> bool:
    words = _words(text)
    if len(words) < n:
        return False
    grams = {tuple(words[i:i+n]) for i in range(len(words)-n+1)}
    for item in sources:
        incoming = _words(item.get("text") if isinstance(item, dict) else item)
        for i in range(len(incoming)-n+1):
            if tuple(incoming[i:i+n]) in grams:
                return True
    return False


def _acceptable(text: str, entity: str, recent: list[dict], all_sources: list[dict]) -> bool:
    if len(text) < 3 or len(text) > MAX_UTTERANCE_CHARS:
        return False
    low = text.lower()
    forbidden = ("json", "schema", "prompt", "latent vector", "regime entropy", "as an ai", "language model")
    if any(term in low for term in forbidden):
        return False
    if re.search(rf"\b{re.escape(entity)}\s*[,!:;-]\s*(?:you|your|you're|you've|you'd)\b", low):
        return False
    if _has_ngram_echo(text, all_sources + recent[-12:]):
        return False
    normalized = re.sub(r"\W+", " ", low).strip()
    return all(normalized != re.sub(r"\W+", " ", str(item.get("text") or "").lower()).strip() for item in recent[-12:])


def speak_once(feed: dict, report: dict, history: list[dict], model_url: str) -> tuple[list[dict], dict]:
    entity, reason = choose_speaker(report, history)
    if entity is None:
        return history, {"spoke": False, "reason": reason}
    summaries = report.get("semantic_summaries") if isinstance(report.get("semantic_summaries"), dict) else {}
    payload = {"participant": entity, "traits": _profile(feed, entity),
               "inner_state": str(summaries.get(entity) or "")[:480], "live_room_context": _conversation_context(feed),
               "vault_recent_speech": history[-MAX_VAULT_CONTEXT:], "selection_reason": reason}
    all_sources = _all_source_texts(feed)
    utterance = ""
    failure = "generation_failed"
    for attempt in range(4):
        try:
            candidate = _request(model_url, payload, entity, attempt)
        except Exception as exc:
            failure = f"model_error:{type(exc).__name__}"
            continue
        if _acceptable(candidate, entity, history, all_sources):
            utterance = candidate
            break
        failure = "quality_rejected"
    if not utterance:
        return history, {"spoke": False, "reason": failure, "entity": entity}
    cycle = _safe_cycle(report.get("source_cycle"))
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ids = [int(str(x.get("id") or "0").split("-")[-1]) for x in history
           if str(x.get("id") or "").startswith("vault-") and str(x.get("id") or "").split("-")[-1].isdigit()]
    seq = 1 + max(ids or [0])
    entry = {"id": f"vault-{seq:06d}", "speaker": entity, "text": utterance, "at": stamp,
             "source_cycle": cycle, "reason": reason}
    return (history + [entry])[-MAX_HISTORY:], {"spoke": True, "reason": reason, "entity": entity, "entry": entry}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed"); parser.add_argument("report"); parser.add_argument("history")
    parser.add_argument("--model-url", required=True); parser.add_argument("--result", required=True)
    args = parser.parse_args()
    feed = _load(Path(args.feed), {}); report = _load(Path(args.report), {})
    history_path = Path(args.history); history = load_history(history_path)
    next_history, result = speak_once(feed if isinstance(feed, dict) else {}, report if isinstance(report, dict) else {}, history, args.model_url)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = history_path.with_suffix(history_path.suffix + ".tmp")
    tmp.write_text(json.dumps(next_history, ensure_ascii=False, indent=2) + "\n"); tmp.replace(history_path)
    Path(args.result).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
