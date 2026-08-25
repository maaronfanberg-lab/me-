#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_model"
RUNTIME_DIR = MODEL_DIR / "runtime"
RESULTS = ROOT / "canary-results.json"

sys.path.insert(0, str(ROOT / "scripts"))
import room_private_model as baseline
import room_private_model_autonomy as autonomy

OVERLAY_MARKERS = (
    "motel fire", "locked suitcase", "fake wedding", "church bell",
    "radio-tower", "tattoo pact", "birthday-cake sabotage", "laundromat",
    "forged apology", "garden statue", "karaoke blood-feud", "inheritance fight",
    "midnight road trip", "suspicious key", "brass flamingo", "voicemail from 3 a.m.",
    "real shared memory", "intimate promise", "old wound", "take status offense",
    "ulterior motive", "invent a dramatic secret",
)


def payload() -> dict:
    return {
        "entity": "sarah",
        "event": {
            "speaker": "allen",
            "text": "The Room has been repeating itself and sometimes mixing up who is who. What would you focus on first?",
            "cognition": {"target": "sarah"},
        },
        "context": [
            {"speaker": "mara", "text": "We keep circling the same idea instead of adding information.", "cognition": {"target": "sarah"}},
            {"speaker": "owen", "text": "Identity mistakes make the conversation hard to trust.", "cognition": {"target": "sarah"}},
            {"speaker": "allen", "text": "The Room has been repeating itself and sometimes mixing up who is who. What would you focus on first?", "cognition": {"target": "sarah"}},
        ],
        "profile": {
            "traits": {
                "openness": 0.82,
                "extraversion": 0.60,
                "conscientiousness": 0.68,
                "agreeableness": 0.62,
                "curiosity": 0.88,
                "skepticism": 0.55,
                "self_disclosure": 0.55,
                "social_sensitivity": 0.75,
                "novelty_seeking": 0.58,
                "inhibition": 0.42,
                "humor": 0.52,
                "attention_persistence": 0.72,
            }
        },
        "topic": {
            "root": "room conversation quality",
            "current_facet": "repetition and identity consistency",
            "facets": ["repetition", "identity", "coherence"],
            "shared_references": [],
            "unresolved": ["which failure should be addressed first"],
        },
        "keywords": ["repetition", "identity", "coherence"],
        # Deliberately polluted legacy expression fields. The autonomy path must
        # remove these before the model sees them.
        "conversation_job": "Invent a dramatic secret and use it as the required angle.",
        "deliberation": {
            "action": "ANSWER",
            "focus": "repetition and identity consistency",
            "new_information_goal": "Prefer identity consistency. Distinct contribution: Invent a dramatic secret and use it as the required angle.",
        },
    }


def role_payload(role: str) -> dict:
    data = payload()
    if role in {"comprehension", "thought"}:
        data.pop("conversation_job", None)
        data.pop("deliberation", None)
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


def role_prompt(role: str) -> str:
    return {
        "comprehension": "Understand the conversation and return only the required structured object.",
        "thought": "Choose a useful next conversational move and return only the required structured object.",
        "expression": "Speak naturally in the conversation and return only the required structured object.",
    }[role]


def reject_overlay_text(label: str, role: str, result: dict) -> None:
    encoded = json.dumps(result, ensure_ascii=False).lower()
    hits = [marker for marker in OVERLAY_MARKERS if marker in encoded]
    if hits:
        raise RuntimeError(f"{label}:{role} leaked live-overlay steering: {hits}")


def probe(label: str, runner, reject_overlay: bool = False) -> list[dict]:
    rows: list[dict] = []
    for role in ("comprehension", "thought", "expression"):
        os.environ["ROOM_NODE_PROMPT"] = role_prompt(role)
        started = time.monotonic()
        result = runner(role, role_payload(role), timeout=30)
        elapsed = time.monotonic() - started
        if not isinstance(result, dict):
            raise RuntimeError(f"{label}:{role} returned non-object")
        if role == "expression" and not str(result.get("utterance") or "").strip():
            raise RuntimeError(f"{label}:expression returned no utterance")
        if elapsed > 40.0:
            raise RuntimeError(f"{label}:{role} exceeded live timing gate: {elapsed:.3f}s")
        if reject_overlay:
            reject_overlay_text(label, role, result)
        rows.append({"brain": label, "role": role, "seconds": round(elapsed, 3), "result": result})
    return rows


def verify_low_steering_transform() -> dict:
    if autonomy.AUTONOMY_ENGINE != "structural-base-no-live-overlay-v1":
        raise RuntimeError("autonomy engine is not the no-overlay structural base")
    if Path(autonomy.base.__file__).resolve() != (ROOT / "scripts" / "room_private_model.py").resolve():
        raise RuntimeError("autonomy path resolved through the live overlay")

    compact = autonomy._autonomy_compact(payload(), "expression", "sarah")
    if "angle" in compact:
        raise RuntimeError("autonomy compact still exposes assigned angle")
    intent = compact.get("intent") or {}
    if isinstance(intent, dict) and intent.get("aim"):
        raise RuntimeError("autonomy compact still exposes assigned content aim")
    encoded = json.dumps(compact, ensure_ascii=False).lower()
    hits = [marker for marker in OVERLAY_MARKERS if marker in encoded]
    if hits:
        raise RuntimeError(f"autonomy compact still contains steering markers: {hits}")
    return compact


def main() -> int:
    candidate = MODEL_DIR / "smollm2-1.7b-instruct-q4_k_m.gguf"
    fallback = MODEL_DIR / "society-brain-q4_0.gguf"
    missing = MODEL_DIR / "this-model-does-not-exist.gguf"

    report: dict = {
        "autonomy_engine": getattr(autonomy, "AUTONOMY_ENGINE", "unknown"),
        "low_steering_transform": "not_tested",
        "candidate": {"status": "not_tested"},
        "deliberate_failure": "not_tested",
        "qwen_fallback": {"status": "not_tested"},
    }

    verify_low_steering_transform()
    report["low_steering_transform"] = "pass"

    candidate_failed = None
    proc = log_handle = None
    try:
        proc, log_handle, startup = start_server("candidate", candidate)
        report["candidate"] = {
            "status": "pass",
            "startup_seconds": round(startup, 3),
            "probes": probe("smollm2-1.7b-autonomy", autonomy.run, reject_overlay=True),
        }
    except Exception as exc:
        candidate_failed = f"{type(exc).__name__}: {exc}"
        report["candidate"] = {"status": "fail", "error": candidate_failed}
    finally:
        if proc is not None and log_handle is not None:
            stop_server(proc, log_handle)

    # Prove that a failed preferred model does not prevent the known-good model
    # from starting immediately afterward.
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
        proc, log_handle, startup = start_server("qwen-fallback", fallback)
        report["qwen_fallback"] = {
            "status": "pass",
            "startup_seconds": round(startup, 3),
            "probes": probe("qwen2.5-0.5b-live-baseline", baseline.run),
        }
    except Exception as exc:
        report["qwen_fallback"] = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None and log_handle is not None:
            stop_server(proc, log_handle)

    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["qwen_fallback"].get("status") != "pass":
        return 1
    if candidate_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
