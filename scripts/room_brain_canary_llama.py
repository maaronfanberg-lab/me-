#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import room_brain_canary as canary

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_model"
RESULTS = ROOT / "canary-results.json"


def main() -> int:
    candidate = MODEL_DIR / "llama-3.2-1b-instruct-q4_k_m.gguf"
    fallback = MODEL_DIR / "society-brain-q4_0.gguf"
    missing = MODEL_DIR / "this-model-does-not-exist.gguf"

    report = {
        "autonomy_engine": getattr(canary.autonomy, "AUTONOMY_ENGINE", "unknown"),
        "low_steering_transform": "not_tested",
        "candidate": {"status": "not_tested"},
        "deliberate_failure": "not_tested",
        "qwen_brain_fallback": {"status": "not_tested"},
    }

    canary.verify_low_steering_transform()
    report["low_steering_transform"] = "pass"
    report["candidate"] = canary.run_model("llama3.2-1b", candidate)

    proc = log_handle = None
    try:
        proc, log_handle, _ = canary.start_server("deliberately-broken", missing)
        report["deliberate_failure"] = "unexpected_start"
        canary.stop_server(proc, log_handle)
        RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return 1
    except Exception:
        report["deliberate_failure"] = "pass"

    proc = log_handle = None
    try:
        proc, log_handle, startup = canary.start_server("qwen-brain-fallback", fallback)
        report["qwen_brain_fallback"] = {
            "status": "pass",
            "startup_seconds": round(startup, 3),
            "probe": canary.autonomy_chain("sarah", "qwen2.5-0.5b-autonomy-fallback"),
        }
    except Exception as exc:
        report["qwen_brain_fallback"] = {
            "status": "fail",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if proc is not None and log_handle is not None:
            canary.stop_server(proc, log_handle)

    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["candidate"].get("status") != "pass":
        return 1
    if report["qwen_brain_fallback"].get("status") != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
