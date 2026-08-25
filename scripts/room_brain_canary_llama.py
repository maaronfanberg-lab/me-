#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import room_brain_canary as canary

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_model"
RESULTS = ROOT / "canary-results.json"
ENTITIES = canary.ENTITIES


def verify_autonomy_v2() -> None:
    if canary.autonomy.AUTONOMY_ENGINE != "structural-base-no-live-overlay-v2":
        raise RuntimeError("autonomy engine is not the expected no-overlay v2 path")
    if Path(canary.autonomy.base.__file__).resolve() != (ROOT / "scripts" / "room_private_model.py").resolve():
        raise RuntimeError("autonomy path resolved through the live overlay")

    for entity in ENTITIES:
        partner = "owen" if entity != "owen" else "sarah"
        thought = {
            "action": "ANSWER",
            "preferred_partner": partner,
            "focus": "identity",
            "new_information_goal": "use my own view",
            "disclosure_depth": 0,
            "interpersonal_risk": 0,
            "shared_reference": None,
            "unresolved_thread": None,
            "reason_summary": "test",
            "must_respond": True,
        }
        compact = canary.autonomy._autonomy_compact(
            canary.polluted_expression_payload(entity, thought, {}), "expression", entity
        )
        if "angle" in compact:
            raise RuntimeError(f"{entity}: external angle survived")
        intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
        if intent.get("aim"):
            raise RuntimeError(f"{entity}: external sentence-level aim survived")
        if str(intent.get("partner") or "") != partner:
            raise RuntimeError(f"{entity}: own intended partner was lost")
        self_model = compact.get("self") if isinstance(compact.get("self"), dict) else {}
        expected = ((canary.PROFILES[entity].get("psychology_v2") or {}).get("core_identity") or "").strip()
        if expected and self_model.get("core_identity") != expected:
            raise RuntimeError(f"{entity}: identity did not survive compacting")
        canary.reject_overlay_text(entity, "compact", compact)


def focused_candidate(model: Path) -> dict:
    label = "llama3.2-1b"
    proc = log_handle = None
    try:
        proc, log_handle, startup = canary.start_server(label, model)

        passes: list[dict] = []
        failures: list[dict] = []
        for entity in ENTITIES:
            try:
                passes.append(canary.autonomy_chain(entity, label))
            except Exception as exc:
                failures.append({"entity": entity, "error": f"{type(exc).__name__}: {exc}"})

        utterances = [str(row["expression"].get("utterance") or "").strip().lower() for row in passes]
        duplicate = len(set(utterances)) != len(utterances)
        actions = sorted({str(row["thought"].get("action") or "") for row in passes})
        focuses = sorted({str(row["thought"].get("focus") or "") for row in passes})
        sequential_technical = not failures and not duplicate and len(passes) == len(ENTITIES)
        action_diversity = len(actions) >= 2

        # Measure live-style pair load even if the dialogue-quality gate fails.
        # That keeps performance evidence separate from personality evidence.
        try:
            parallel = canary.parallel_load_probe(label)
        except Exception as exc:
            parallel = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}

        quality = {
            "status": "pass" if sequential_technical and action_diversity else "fail",
            "sequential_technical": sequential_technical,
            "action_diversity": action_diversity,
            "distinct_actions": actions,
            "distinct_focuses": focuses,
            "duplicate_utterances": duplicate,
            "voices_passed": passes,
            "voices_failed": failures,
        }

        return {
            "status": "pass" if quality["status"] == "pass" and parallel.get("status") == "pass" else "fail",
            "startup_seconds": round(startup, 3),
            "quality": quality,
            "parallel_live_load": parallel,
        }
    except Exception as exc:
        return {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None and log_handle is not None:
            canary.stop_server(proc, log_handle)


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

    verify_autonomy_v2()
    report["low_steering_transform"] = "pass"
    report["candidate"] = focused_candidate(candidate)

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
            "probe": canary.autonomy_chain(
                "sarah",
                "qwen2.5-0.5b-autonomy-fallback",
                min_words=1,
                strict_quality=False,
            ),
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
