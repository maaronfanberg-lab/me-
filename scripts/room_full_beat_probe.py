#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_probe_model"
RUNTIME_DIR = MODEL_DIR / "runtime"
MODEL = MODEL_DIR / "society-brain-q4_0.gguf"
STATUS = ROOT / "room" / "private-full-beat-diagnostic.json"
CTX_TOTAL = 16384
PARALLEL_SLOTS = 2


def safe(text: str) -> str:
    out = str(text or "")
    for key in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION"):
        secret = os.environ.get(key, "")
        if secret:
            out = out.replace(secret, "[redacted]")
    return out[-1200:]


def write(data: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def clean_base_env() -> dict:
    env = dict(os.environ)
    for key in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION", "ROOM_NODE_PROMPT"):
        env.pop(key, None)
    env["ROOM_MODEL_URL"] = "http://127.0.0.1:18080/completion"
    env["ROOM_CYCLE_KEY"] = "full-private-probe"
    return env


def node_prompt(node: int, phase: str) -> str:
    local = node % 3
    if phase == "sense" and local == 0:
        return os.environ.get("ROOM_PROMPT_PERCEPTION", "")
    if phase == "recurrent" and local == 1:
        return os.environ.get("ROOM_PROMPT_DELIBERATION", "")
    if phase == "recurrent" and local == 2:
        return os.environ.get("ROOM_PROMPT_EXPRESSION", "")
    return ""


def launch_nodes(nodes: list[int], phase: str, bus: str | None, results: dict) -> bool:
    procs = []
    for node in nodes:
        env = clean_base_env()
        env["ROOM_NODE_ID"] = str(node)
        env["ROOM_NODE_PROMPT"] = node_prompt(node, phase)
        cmd = ["python3", "scripts/room_engine_v5.py", "node", "--phase", phase]
        if bus:
            cmd += ["--bus", bus]
        procs.append((node, subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
    ok = True
    for node, proc in procs:
        out, err = proc.communicate(timeout=90)
        results[str(node)] = {"returncode": proc.returncode, "stdout": safe(out), "stderr": safe(err)}
        if proc.returncode != 0:
            ok = False
    return ok


def run_nodes(nodes: list[int], phase: str, bus: str | None = None) -> tuple[bool, dict]:
    results: dict = {}
    plain = [node for node in nodes if not node_prompt(node, phase)]
    prompted = [node for node in nodes if node_prompt(node, phase)]
    ok = True
    if plain:
        ok = launch_nodes(plain, phase, bus, results) and ok
    for start in range(0, len(prompted), PARALLEL_SLOTS):
        batch = prompted[start:start + PARALLEL_SLOTS]
        ok = launch_nodes(batch, phase, bus, results) and ok
        if not ok:
            break
    return ok, results


def run_expression_nodes(nodes: list[int], bus: str) -> tuple[bool, dict]:
    results: dict = {}
    for rank, node in enumerate(nodes):
        env = clean_base_env()
        env["ROOM_NODE_ID"] = str(node)
        env["ROOM_NODE_PROMPT"] = node_prompt(node, "recurrent")
        env["ROOM_EXPRESSION_RANK"] = str(rank)
        cmd = ["python3", "scripts/room_engine_v5.py", "node", "--phase", "recurrent", "--bus", bus]
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
        results[str(node)] = {"returncode": proc.returncode, "stdout": safe(proc.stdout), "stderr": safe(proc.stderr)}
        if proc.returncode != 0:
            return False, results
    return True, results


def run_cmd(cmd: list[str]) -> tuple[bool, dict]:
    env = clean_base_env()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
    return proc.returncode == 0, {"returncode": proc.returncode, "stdout": safe(proc.stdout), "stderr": safe(proc.stderr)}


def public_candidates() -> list[dict]:
    path = ROOT / "room" / "conversation.json"
    try:
        conversation = json.loads(path.read_text())
    except Exception:
        return []
    out = []
    for message in conversation[-4:]:
        cognition = message.get("cognition") if isinstance(message.get("cognition"), dict) else {}
        out.append({
            "speaker": message.get("speaker"),
            "text": str(message.get("text", ""))[:700],
            "move": cognition.get("move_type"),
            "target": cognition.get("target"),
            "semantic_terms": list(cognition.get("topic_terms") or [])[:4],
        })
    return out


def main() -> int:
    result = {
        "server_ready": False,
        "phase": "starting",
        "ctx_total": CTX_TOTAL,
        "parallel_slots": PARALLEL_SLOTS,
        "model_node_batching": True,
        "expression_sequential": True,
        "public_fallback": False,
        "safe_public_candidate_capture": True,
    }
    write(result)
    bins = list(RUNTIME_DIR.rglob("llama-server"))
    if not MODEL.exists() or not bins:
        result.update({"phase": "setup", "error": "probe model/runtime missing"})
        write(result)
        return 0
    server = bins[0]
    server.chmod(0o755)
    server_env = clean_base_env()
    server_env.pop("ROOM_MODEL_URL", None)
    proc = subprocess.Popen(
        [str(server), "-m", str(MODEL), "--host", "127.0.0.1", "--port", "18080", "-c", str(CTX_TOTAL), "-np", str(PARALLEL_SLOTS)],
        cwd=ROOT,
        env=server_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(120):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=1):
                    result["server_ready"] = True
                    break
            except Exception:
                time.sleep(1)
        if not result["server_ready"]:
            result.update({"phase": "server", "error": f"server_exit={proc.poll()}"})
            write(result)
            return 0

        shutil.rmtree(ROOT / "room_parts", ignore_errors=True)
        shutil.rmtree(ROOT / "room_work", ignore_errors=True)
        (ROOT / "room_parts").mkdir()
        (ROOT / "room_work").mkdir()

        result["phase"] = "sense"
        ok, detail = run_nodes(list(range(12)), "sense")
        result["sense"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        ok, detail = run_cmd(["python3", "scripts/room_engine_v5.py", "bus"])
        result["bus"] = detail
        write(result)
        if not ok:
            result.update({"phase": "bus", "status": "failed"})
            write(result)
            return 0

        result["phase"] = "deliberation"
        ok, detail = run_nodes([0, 1, 3, 4, 6, 7, 9, 10], "recurrent", "room_work/bus-sense.json")
        result["deliberation"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        ok, detail = run_cmd(["python3", "scripts/room_engine_v5.py", "bus2", "--bus", "room_work/bus-sense.json"])
        result["bus2"] = detail
        write(result)
        if not ok:
            result.update({"phase": "bus2", "status": "failed"})
            write(result)
            return 0

        result["phase"] = "expression"
        ok, detail = run_expression_nodes([2, 5, 8, 11], "room_work/bus-recurrent.json")
        result["expression"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        result["phase"] = "commit"
        ok, detail = run_cmd(["python3", "scripts/room_private_commit.py", "commit"])
        result["commit"] = detail
        if ok:
            result["public_candidates"] = public_candidates()
        result["status"] = "accepted" if ok else "failed"
        write(result)
        return 0
    except Exception as exc:
        result.update({"status": "failed", "error": safe(f"{type(exc).__name__}: {exc}")})
        write(result)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
