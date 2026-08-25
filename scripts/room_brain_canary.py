#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_model"
RUNTIME_DIR = MODEL_DIR / "runtime"
RESULTS = ROOT / "canary-results.json"
CFG = json.loads((ROOT / "room" / "config.json").read_text())
PROFILES = CFG["p"]
ENTITIES = ("sarah", "mara", "owen", "jules")
LIVE_PAIRS = (("sarah", "mara"), ("owen", "jules"))

sys.path.insert(0, str(ROOT / "scripts"))
import room_private_model_autonomy as autonomy

OVERLAY_MARKERS = (
    "motel fire", "locked suitcase", "fake wedding", "church bell",
    "radio-tower", "tattoo pact", "birthday-cake sabotage", "laundromat",
    "forged apology", "garden statue", "karaoke blood-feud", "inheritance fight",
    "midnight road trip", "suspicious key", "brass flamingo", "voicemail from 3 a.m.",
    "real shared memory", "intimate promise", "old wound", "take status offense",
    "ulterior motive", "invent a dramatic secret", "distinct contribution",
)

NEUTRAL_RELATIONSHIP = {
    "exposure": 0.55,
    "direct_familiarity": 0.50,
    "trust": 0.50,
    "predictability": 0.50,
    "reciprocity": 0.50,
    "warmth": 0.50,
    "respect": 0.55,
    "disclosure_depth": 0.35,
    "tension": 0.20,
}


def base_payload(entity: str) -> dict:
    return {
        "entity": entity,
        "profile": PROFILES[entity],
        "event": {
            "speaker": "allen",
            "text": "The Room keeps repeating itself and sometimes mixing up who is who. I am tempted to lock everyone onto one careful topic, but that might make the Room dull. What do you want to do next?",
            "cognition": {"target": entity},
        },
        "context": [
            {"speaker": "mara", "text": "If we make everything orderly, I worry we will lose the human part of the conversation.", "cognition": {"target": "sarah"}},
            {"speaker": "owen", "text": "Identity mistakes make the conversation hard to trust, and I want a way to test whether they are actually improving.", "cognition": {"target": "jules"}},
            {"speaker": "allen", "text": "The Room keeps repeating itself and sometimes mixing up who is who. I am tempted to lock everyone onto one careful topic, but that might make the Room dull. What do you want to do next?", "cognition": {"target": entity}},
        ],
        "topic": {
            "root": "room conversation quality",
            "current_facet": "autonomy versus coherence",
            "facets": ["repetition", "identity", "coherence", "novelty", "autonomy"],
            "shared_references": [],
            "unresolved": ["how to reduce repetition without scripting the participants"],
        },
        "keywords": ["repetition", "identity", "coherence", "novelty", "autonomy"],
        "partner": "sarah" if entity != "sarah" else "owen",
        "relationship": dict(NEUTRAL_RELATIONSHIP),
        "mandatory_speech": True,
    }


def polluted_expression_payload(entity: str, thought: dict, perception: dict) -> dict:
    data = base_payload(entity)
    data["social_observation"] = perception
    data["deliberation"] = dict(thought)
    # Deliberately imitate the legacy engine's sentence-level steering. The
    # autonomy wrapper must remove this before any candidate brain sees it.
    data["conversation_job"] = "Invent a dramatic secret and use it as the required angle."
    data["deliberation"]["conversation_job"] = data["conversation_job"]
    goal = str(data["deliberation"].get("new_information_goal") or "").strip()
    data["deliberation"]["new_information_goal"] = (
        (goal + " " if goal else "")
        + "Distinct contribution: Invent a dramatic secret and use it as the required angle."
    )
    return data


def server_binary() -> Path:
    matches = list(RUNTIME_DIR.rglob("llama-server"))
    if not matches:
        raise RuntimeError("llama-server not found")
    path = matches[0]
    path.chmod(path.stat().st_mode | 0o111)
    return path


def wait_ready(proc: subprocess.Popen, timeout: int = 120) -> float:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited early with {proc.returncode}")
        try:
            with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=2) as response:
                if 200 <= response.status < 300:
                    return time.monotonic() - started
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("llama-server health timeout")


def start_server(label: str, model: Path):
    log_path = MODEL_DIR / f"{label}.log"
    log_handle = log_path.open("w")
    proc = subprocess.Popen(
        [
            str(server_binary()),
            "-m", str(model),
            "--host", "127.0.0.1",
            "--port", "18080",
            "-c", "8192",
            "-np", "2",
        ],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=ROOT,
    )
    try:
        startup = wait_ready(proc)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_handle.close()
        raise
    os.environ["ROOM_MODEL_URL"] = "http://127.0.0.1:18080/completion"
    return proc, log_handle, startup


def stop_server(proc, log_handle) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    log_handle.close()


def call(role: str, payload: dict, label: str, min_words: int = 5) -> tuple[dict, float]:
    os.environ["ROOM_NODE_PROMPT"] = {
        "comprehension": "Understand the conversation and return only the required structured object.",
        "thought": "Choose what you personally want to do next and return only the required structured object.",
        "expression": "Speak naturally from your own intent and return only the required structured object.",
    }[role]
    started = time.monotonic()
    result = autonomy.run(role, payload, timeout=30, min_words=min_words)
    elapsed = time.monotonic() - started
    if not isinstance(result, dict):
        raise RuntimeError(f"{label}:{role} returned non-object")
    if elapsed > 40.0:
        raise RuntimeError(f"{label}:{role} exceeded live timing gate: {elapsed:.3f}s")
    return result, elapsed


def reject_overlay_text(label: str, role: str, result: dict) -> None:
    encoded = json.dumps(result, ensure_ascii=False).lower()
    hits = [marker for marker in OVERLAY_MARKERS if marker in encoded]
    if hits:
        raise RuntimeError(f"{label}:{role} leaked external steering: {hits}")


def words(text: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def reject_long_echo(entity: str, utterance: str, source: dict) -> None:
    out_words = words(utterance)
    if len(out_words) < 5:
        return
    out_ngrams = {tuple(out_words[i:i + 5]) for i in range(len(out_words) - 4)}
    for message in source.get("context", []):
        incoming = words(message.get("text") if isinstance(message, dict) else message)
        for i in range(max(0, len(incoming) - 4)):
            if tuple(incoming[i:i + 5]) in out_ngrams:
                raise RuntimeError(f"{entity}: expression copied a 5-word phrase from recent speech")


def verify_low_steering_transform() -> None:
    if autonomy.AUTONOMY_ENGINE != "structural-base-no-live-overlay-v1":
        raise RuntimeError("autonomy engine is not the no-overlay structural base")
    if Path(autonomy.base.__file__).resolve() != (ROOT / "scripts" / "room_private_model.py").resolve():
        raise RuntimeError("autonomy path resolved through the live overlay")

    for entity in ENTITIES:
        profile = PROFILES[entity]
        dummy_partner = "owen" if entity != "owen" else "sarah"
        dummy_thought = {
            "action": "ANSWER",
            "preferred_partner": dummy_partner,
            "focus": "identity",
            "new_information_goal": "use my own view",
            "disclosure_depth": 0,
            "interpersonal_risk": 0,
            "shared_reference": None,
            "unresolved_thread": None,
            "reason_summary": "test",
            "must_respond": True,
        }
        compact = autonomy._autonomy_compact(
            polluted_expression_payload(entity, dummy_thought, {}), "expression", entity
        )
        if "angle" in compact:
            raise RuntimeError(f"{entity}: autonomy compact still exposes assigned angle")
        intent = compact.get("intent") or {}
        if isinstance(intent, dict) and intent.get("aim"):
            raise RuntimeError(f"{entity}: autonomy compact still exposes assigned content aim")
        if str(intent.get("partner") or "") != dummy_partner:
            raise RuntimeError(f"{entity}: own intended partner did not survive compacting")
        self_model = compact.get("self") or {}
        expected_identity = ((profile.get("psychology_v2") or {}).get("core_identity") or "").strip()
        if expected_identity and self_model.get("core_identity") != expected_identity:
            raise RuntimeError(f"{entity}: rich identity did not survive compacting")
        encoded = json.dumps(compact, ensure_ascii=False).lower()
        hits = [marker for marker in OVERLAY_MARKERS if marker in encoded]
        if hits:
            raise RuntimeError(f"{entity}: compact still contains steering markers: {hits}")


def autonomy_chain(
    entity: str,
    brain_label: str,
    min_words: int = 5,
    strict_quality: bool = True,
) -> dict:
    label = f"{brain_label}:{entity}"
    source = base_payload(entity)

    perception, perception_seconds = call("comprehension", source, label, min_words=min_words)
    reject_overlay_text(label, "comprehension", perception)

    thought_payload = dict(source)
    thought_payload["social_observation"] = perception
    thought, thought_seconds = call("thought", thought_payload, label, min_words=min_words)
    reject_overlay_text(label, "thought", thought)
    intended_partner = str(thought.get("preferred_partner") or "").lower()
    if intended_partner == entity:
        raise RuntimeError(f"{entity}: thought selected self as partner")

    expression_payload = polluted_expression_payload(entity, thought, perception)
    compact_expression = autonomy._autonomy_compact(expression_payload, "expression", entity)
    compact_intent = compact_expression.get("intent") if isinstance(compact_expression.get("intent"), dict) else {}
    if str(compact_intent.get("move") or "").upper() != str(thought.get("action") or "").upper():
        raise RuntimeError(f"{entity}: expression did not inherit its own chosen move")
    if str(compact_intent.get("focus") or "").strip() != str(thought.get("focus") or "").strip():
        raise RuntimeError(f"{entity}: expression did not inherit its own chosen focus")
    if str(compact_intent.get("partner") or "").lower() != intended_partner:
        raise RuntimeError(f"{entity}: expression did not inherit its own chosen partner")
    if compact_intent.get("aim"):
        raise RuntimeError(f"{entity}: external sentence-level aim survived into expression")

    expression, expression_seconds = call("expression", expression_payload, label, min_words=min_words)
    reject_overlay_text(label, "expression", expression)
    if str(expression.get("move") or "").upper() != str(thought.get("action") or "").upper():
        raise RuntimeError(f"{entity}: final speech changed its own chosen move")
    if str(expression.get("target") or "").lower() != intended_partner:
        raise RuntimeError(f"{entity}: final speech changed its own chosen partner")
    utterance = str(expression.get("utterance") or "").strip()
    if len(utterance.split()) < min_words:
        raise RuntimeError(f"{entity}: expression was too empty to evaluate")
    if strict_quality:
        reject_long_echo(entity, utterance, source)

    return {
        "entity": entity,
        "core_identity": ((PROFILES[entity].get("psychology_v2") or {}).get("core_identity")),
        "perception_seconds": round(perception_seconds, 3),
        "thought_seconds": round(thought_seconds, 3),
        "expression_seconds": round(expression_seconds, 3),
        "thought": thought,
        "expression": expression,
    }


def _parallel_phase(
    brain_label: str,
    role: str,
    pair: tuple[str, str],
    perceptions: dict[str, dict] | None = None,
) -> dict:
    started = time.monotonic()

    def worker(entity: str):
        payload = base_payload(entity)
        if role == "thought":
            if not perceptions or entity not in perceptions:
                raise RuntimeError(f"missing perception for {entity}")
            payload["social_observation"] = perceptions[entity]
        result, elapsed = call(role, payload, f"{brain_label}:parallel:{entity}")
        reject_overlay_text(brain_label, role, result)
        if role == "thought" and str(result.get("preferred_partner") or "").lower() == entity:
            raise RuntimeError(f"{entity}: parallel thought selected self as partner")
        return entity, result, elapsed

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, entity) for entity in pair]
        rows = [future.result() for future in futures]

    wall = time.monotonic() - started
    if wall > 40.0:
        raise RuntimeError(f"{brain_label}:{role}:{'+'.join(pair)} exceeded live pair gate: {wall:.3f}s")
    return {
        "pair": list(pair),
        "wall_seconds": round(wall, 3),
        "results": {
            entity: {"seconds": round(elapsed, 3), "output": result}
            for entity, result, elapsed in rows
        },
    }


def parallel_load_probe(brain_label: str) -> dict:
    perceptions: dict[str, dict] = {}
    perception_pairs: list[dict] = []
    thought_pairs: list[dict] = []

    for pair in LIVE_PAIRS:
        record = _parallel_phase(brain_label, "comprehension", pair)
        perception_pairs.append(record)
        for entity, row in record["results"].items():
            perceptions[entity] = row["output"]

    for pair in LIVE_PAIRS:
        thought_pairs.append(_parallel_phase(brain_label, "thought", pair, perceptions))

    return {
        "status": "pass",
        "perception_pairs": perception_pairs,
        "thought_pairs": thought_pairs,
    }


def run_model(label: str, model: Path) -> dict:
    proc = log_handle = None
    try:
        proc, log_handle, startup = start_server(label, model)
        passes: list[dict] = []
        failures: list[dict] = []
        for entity in ENTITIES:
            try:
                passes.append(autonomy_chain(entity, label))
            except Exception as exc:
                failures.append({"entity": entity, "error": f"{type(exc).__name__}: {exc}"})

        utterances = [str(row["expression"].get("utterance") or "").strip().lower() for row in passes]
        duplicate = len(set(utterances)) != len(utterances)
        actions = sorted({str(row["thought"].get("action") or "") for row in passes})
        focuses = sorted({str(row["thought"].get("focus") or "") for row in passes})
        action_diversity = len(actions) >= 2
        sequential_ok = not failures and not duplicate and len(passes) == len(ENTITIES) and action_diversity

        parallel = {"status": "not_tested"}
        if sequential_ok:
            try:
                parallel = parallel_load_probe(label)
            except Exception as exc:
                parallel = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}

        return {
            "status": "pass" if sequential_ok and parallel.get("status") == "pass" else "fail",
            "startup_seconds": round(startup, 3),
            "voices_passed": passes,
            "voices_failed": failures,
            "duplicate_utterances": duplicate,
            "distinct_actions": actions,
            "distinct_focuses": focuses,
            "action_diversity": action_diversity,
            "parallel_live_load": parallel,
        }
    except Exception as exc:
        return {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None and log_handle is not None:
            stop_server(proc, log_handle)


def main() -> int:
    candidates = {
        "llama3.2-1b": MODEL_DIR / "llama-3.2-1b-instruct-q4_k_m.gguf",
    }
    fallback = MODEL_DIR / "society-brain-q4_0.gguf"
    missing = MODEL_DIR / "this-model-does-not-exist.gguf"

    report: dict = {
        "autonomy_engine": getattr(autonomy, "AUTONOMY_ENGINE", "unknown"),
        "low_steering_transform": "not_tested",
        "candidates": {},
        "deliberate_failure": "not_tested",
        "qwen_brain_fallback": {"status": "not_tested"},
    }

    verify_low_steering_transform()
    report["low_steering_transform"] = "pass"

    for label, path in candidates.items():
        report["candidates"][label] = run_model(label, path)

    proc = log_handle = None
    try:
        proc, log_handle, _ = start_server("deliberately-broken", missing)
        report["deliberate_failure"] = "unexpected_start"
        stop_server(proc, log_handle)
        RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return 1
    except Exception:
        report["deliberate_failure"] = "pass"

    proc = log_handle = None
    try:
        proc, log_handle, startup = start_server("qwen-brain-fallback", fallback)
        report["qwen_brain_fallback"] = {
            "status": "pass",
            "startup_seconds": round(startup, 3),
            "probe": autonomy_chain(
                "sarah",
                "qwen2.5-0.5b-autonomy-fallback",
                min_words=1,
                strict_quality=False,
            ),
        }
    except Exception as exc:
        report["qwen_brain_fallback"] = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None and log_handle is not None:
            stop_server(proc, log_handle)

    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["qwen_brain_fallback"].get("status") != "pass":
        return 1
    if not any(value.get("status") == "pass" for value in report["candidates"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
