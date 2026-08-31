#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("COMMUNITY_BITNET_ROOT", HERE / "vendor" / "BitNet"))
MODEL = Path(os.environ.get("COMMUNITY_BITNET_MODEL", HERE / "models" / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"))
SERVER = ROOT / "build" / "bin" / "llama-server"
PID_FILE = HERE / ".bitnet-server.pid"
LOG_FILE = HERE / "replay" / "bitnet-server.log"
STATE_FILE = HERE / "replay" / "bitnet-server-state.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
BASE = f"http://{HOST}:{PORT}"
START_TIMEOUT = int(os.environ.get("COMMUNITY_BITNET_START_TIMEOUT", "900"))
REQUEST_TIMEOUT = int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def saved_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return None
    if not pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def write_state(**values: object) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"host": HOST, "port": PORT, "model": str(MODEL), **values}
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def port_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


def health(timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def request_completion(prompt: str, n_predict: int, temperature: float, timeout: int = REQUEST_TIMEOUT) -> str:
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": max(1, min(int(n_predict), 256)),
        "temperature": float(temperature),
        "stream": False,
        "cache_prompt": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = data.get("content")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"BitNet server returned no usable content: {data!r}")
    return text.strip()


def wait_until_ready(timeout: int = START_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        pid = saved_pid()
        if pid is None:
            tail = ""
            if LOG_FILE.exists():
                tail = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"BitNet server exited before becoming ready. Log tail:\n{tail}")
        try:
            if health(timeout=3) or port_open():
                write_state(running=True, pid=pid, ready=True)
                return
        except Exception as exc:
            last_error = exc
        time.sleep(2)
    write_state(running=True, pid=saved_pid(), ready=False, error=str(last_error) if last_error else "startup timeout")
    raise TimeoutError(f"BitNet server did not become ready in {timeout}s")


def start() -> None:
    existing = saved_pid()
    if existing is not None and (health() or port_open()):
        print(f"BitNet server already running as PID {existing}")
        write_state(running=True, pid=existing, ready=True, reused=True)
        return
    if existing is not None:
        stop()
    if port_open():
        raise RuntimeError(f"Port {PORT} is already in use by an unmanaged process")
    if not SERVER.exists() or not os.access(SERVER, os.X_OK):
        raise FileNotFoundError(f"Executable BitNet llama-server not found: {SERVER}")
    if not MODEL.exists() or MODEL.stat().st_size == 0:
        raise FileNotFoundError(f"BitNet model not found or empty: {MODEL}")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")
    log = LOG_FILE.open("ab", buffering=0)
    threads = max(4, min(6, os.cpu_count() or 4))
    cmd = [
        str(SERVER), "-m", str(MODEL), "-c", "2048", "-t", str(threads),
        "-ngl", "0", "--host", HOST, "--port", str(PORT), "-cb",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    write_state(running=True, pid=proc.pid, ready=False, reused=False, threads=threads, command=cmd)
    print(f"Started persistent BitNet server as PID {proc.pid}")
    wait_until_ready()
    print("BitNet server is ready; Stanford requests will reuse the loaded model over localhost HTTP.")


def stop() -> None:
    pid = saved_pid()
    if pid is None:
        PID_FILE.unlink(missing_ok=True)
        write_state(running=False, pid=None, ready=False)
        print("BitNet server is not running")
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and pid_alive(pid):
        time.sleep(0.25)
    if pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    PID_FILE.unlink(missing_ok=True)
    write_state(running=False, pid=None, ready=False)
    print("Stopped BitNet server")


def status() -> int:
    pid = saved_pid()
    ready = bool(pid is not None and (health() or port_open()))
    payload = {"running": pid is not None, "ready": ready, "pid": pid, "endpoint": BASE}
    print(json.dumps(payload, sort_keys=True))
    write_state(**payload)
    return 0 if ready else 1


def probe() -> None:
    started = time.monotonic()
    text = request_completion("Reply with only the word OK.", 2, 0.0)
    elapsed = time.monotonic() - started
    print("BITNET_SERVER_PROBE:", text[:200])
    print(f"BITNET_SERVER_PROBE_SECONDS: {elapsed:.3f}")
    write_state(running=True, pid=saved_pid(), ready=True, probe_seconds=round(elapsed, 3), probe_text=text[:200])


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Community's persistent localhost BitNet server.")
    parser.add_argument("command", choices=("start", "stop", "status", "probe"))
    args = parser.parse_args()
    if args.command == "start":
        start()
        return 0
    if args.command == "stop":
        stop()
        return 0
    if args.command == "status":
        return status()
    probe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
