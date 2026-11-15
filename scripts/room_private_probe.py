#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_probe_model"
RUNTIME_DIR = MODEL_DIR / "runtime"
STATUS_PATH = ROOT / "room" / "private-model-diagnostic.json"
MODEL_SHA = "7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed"
RUNTIME_SHA = "360a5bfab5b8fe562c52e060a998a052f5fc7d98a0448b035c2eedbb6acfbd94"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2) + "\n")


def safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION"):
        secret = os.environ.get(key, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return f"{type(exc).__name__}: {text}"[:240]


def main() -> int:
    status = {
        "perception_secret_present": bool(os.environ.get("ROOM_PROMPT_PERCEPTION", "").strip()),
        "deliberation_secret_present": bool(os.environ.get("ROOM_PROMPT_DELIBERATION", "").strip()),
        "expression_secret_present": bool(os.environ.get("ROOM_PROMPT_EXPRESSION", "").strip()),
        "download_ok": False,
        "hashes_ok": False,
        "server_ready": False,
        "perception_status": "not_tested",
        "deliberation_status": "not_tested",
        "expression_status": "not_tested",
        "neutral_contract": True,
    }
    write(status)
    if not all(status[key] for key in ("perception_secret_present", "deliberation_secret_present", "expression_secret_present")):
        return 0

    MODEL_DIR.mkdir(exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    model = MODEL_DIR / "society-brain-q4_0.gguf"
    archive = MODEL_DIR / "llama-runtime-linux-x64.tar.gz"
    try:
        subprocess.run(["gh", "release", "download", "society-brain-v1", "--repo", os.environ["GITHUB_REPOSITORY"], "--pattern", model.name, "--dir", str(MODEL_DIR)], check=True)
        subprocess.run(["gh", "release", "download", "society-brain-v1", "--repo", os.environ["GITHUB_REPOSITORY"], "--pattern", archive.name, "--dir", str(MODEL_DIR)], check=True)
        status["download_ok"] = True
        status["hashes_ok"] = sha256(model) == MODEL_SHA and sha256(archive) == RUNTIME_SHA
        write(status)
        if not status["hashes_ok"]:
            return 0

        with tarfile.open(archive, "r:gz") as archive_file:
            archive_file.extractall(RUNTIME_DIR)
        bins = list(RUNTIME_DIR.rglob("llama-server"))
        if not bins:
            status["server_error"] = "llama-server not found"
            write(status)
            return 0
        server = bins[0]
        server.chmod(0o755)
        clean = dict(os.environ)
        for key in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION", "ROOM_NODE_PROMPT"):
            clean.pop(key, None)
        proc = subprocess.Popen(
            [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", "18080", "-c", "16384", "-np", "2"],
            env=clean,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(120):
                if proc.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=1):
                        status["server_ready"] = True
                        break
                except Exception:
                    time.sleep(1)
            write(status)
            if not status["server_ready"]:
                status["server_error"] = f"server_exit={proc.poll()}"
                write(status)
                return 0

            import sys
            sys.path.insert(0, str(ROOT / "scripts"))
            from room_private_model import run

            base = {
                "entity": "sarah",
                "profile": {},
                "event": {"speaker": "mara", "text": "One counterexample changed my view.", "cognition": {"target": "sarah"}},
                "context": [],
                "topic": {"id": "probe", "root": "belief", "current_facet": "evidence", "facets": ["evidence", "counterexample"]},
                "partner": "mara",
                "relationship": {"trust": 0.1, "direct_familiarity": 0.2},
                "mandatory_speech": True,
            }
            perception_input = base
            thought_input = {
                **base,
                "social_observation": {
                    "participation": "DIRECT_ADDRESSEE",
                    "partner": "mara",
                    "move": "answer",
                    "grounding": "understood",
                    "focus": "evidence",
                    "new_details": ["counterexample"],
                    "bids": [],
                    "relationship_events": [],
                    "shared_references": [],
                    "confidence": 0.8,
                },
            }
            expression_input = {
                **thought_input,
                "deliberation": {
                    "action": "DEEPEN",
                    "preferred_partner": "mara",
                    "focus": "evidence",
                    "new_information_goal": "compare evidence with a counterexample",
                    "disclosure_depth": 0,
                    "interpersonal_risk": 0,
                    "shared_reference": None,
                    "unresolved_thread": None,
                    "reason_summary": "a counterexample can change confidence",
                    "must_respond": True,
                },
            }
            tests = [
                ("comprehension", "ROOM_PROMPT_PERCEPTION", perception_input, "perception_status"),
                ("thought", "ROOM_PROMPT_DELIBERATION", thought_input, "deliberation_status"),
                ("expression", "ROOM_PROMPT_EXPRESSION", expression_input, "expression_status"),
            ]
            for role, secret_name, payload, key in tests:
                os.environ["ROOM_NODE_PROMPT"] = os.environ[secret_name]
                os.environ["ROOM_MODEL_URL"] = "http://127.0.0.1:18080/completion"
                try:
                    result = run(role, payload, timeout=45)
                    status[key] = "accepted" if isinstance(result, dict) else "no_result"
                except Exception as exc:
                    status[key] = safe_error(exc)
                finally:
                    os.environ.pop("ROOM_NODE_PROMPT", None)
                write(status)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    except Exception as exc:
        status["probe_error"] = safe_error(exc)
        write(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
