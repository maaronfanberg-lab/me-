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
MIN_MODEL_BYTES = 100_000_000


def pid_alive(pid: int) -> bool:
    # os.kill(pid, 0) reports Linux zombies as existing. That caused a crashed
    # llama-server child to masquerade as "still starting" for the full health
    # timeout. Reject zombies when procfs is available, then use the portable
    # existence check as the fallback.
    stat_path = Path(f"/proc/{pid}/stat")
    if stat_path.exists():
        try:
            fields = stat_path.read_text(encoding="utf-8", errors="replace").split()
            if len(fields) >= 3 and fields[2] == "Z":
                return False
        except OSError:
            pass
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
    if pid <= 0 or not pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def write_state(**values: object) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"host": HOST, "port": PORT, "model": str(MODEL), **values}
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def log_tail(limit: int = 6000) -> str:
    if not LOG_FILE.exists():
        return ""
    return LOG_FILE.read_text(encoding="utf-8", errors="replace")[-limit:]


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


def request_completion(
    prompt: str,
    n_predict: int,
    temperature: float,
    timeout: int = REQUEST_TIMEOUT,
    stop: list[str] | None = None,
    cache_prompt: bool = True,
) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Completion prompt must be non-empty.")
    if not health(timeout=3):
        raise RuntimeError(f"BitNet server is not healthy before completion request. Log tail:\n{log_tail()}")
    request_data = {
        "prompt": prompt,
        "n_predict": max(1, min(int(n_predict), 256)),
        "temperature": max(0.0, min(float(temperature), 2.0)),
        "stream": False,
        "cache_prompt": bool(cache_prompt),
    }
    if stop:
        request_data["stop"] = list(stop)
    payload = json.dumps(request_data).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"BitNet HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BitNet request failed: {exc.reason}; log tail:\n{log_tail()}") from exc
    text = data.get("content")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"BitNet server returned no usable content: {data!r}")
    return text.strip()


def wait_until_ready(proc: subprocess.Popen[bytes], timeout: int = START_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        returncode = proc.poll()
        if returncode is not None:
            PID_FILE.unlink(missing_ok=True)
            write_state(
                running=False,
                pid=None,
                ready=False,
                error="server exited during startup",
                returncode=returncode,
            )
            raise RuntimeError(
                f"BitNet server exited with code {returncode} before becoming ready. "
                f"Log tail:\n{log_tail()}"
            )
        if health(timeout=3):
            write_state(running=True, pid=proc.pid, ready=True)
            return
        time.sleep(2)

    returncode = proc.poll()
    if returncode is not None:
        PID_FILE.unlink(missing_ok=True)
        write_state(
            running=False,
            pid=None,
            ready=False,
            error="server exited during startup",
            returncode=returncode,
        )
        raise RuntimeError(
            f"BitNet server exited with code {returncode} before becoming ready. "
            f"Log tail:\n{log_tail()}"
        )

    write_state(running=True, pid=proc.pid, ready=False, error="startup health timeout")
    raise TimeoutError(f"BitNet /health did not become ready in {timeout}s. Log tail:\n{log_tail()}")


def start() -> None:
    existing = saved_pid()
    if existing is not None and health():
        print(f"BitNet server already running as PID {existing}")
        write_state(running=True, pid=existing, ready=True, reused=True)
        return
    if existing is not None:
        stop()
    if port_open():
        raise RuntimeError(f"Port {PORT} is already in use by an unmanaged or unhealthy process")
    if not SERVER.exists() or not os.access(SERVER, os.X_OK):
        raise FileNotFoundError(f"Executable BitNet llama-server not found: {SERVER}")
    if not MODEL.exists() or MODEL.stat().st_size < MIN_MODEL_BYTES:
        raise FileNotFoundError(f"BitNet model is missing or implausibly small: {MODEL}")

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
    log.close()
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    write_state(running=True, pid=proc.pid, ready=False, reused=False, threads=threads, command=cmd)
    print(f"Started persistent BitNet server as PID {proc.pid}")
    wait_until_ready(proc)
    print("BitNet server is healthy; Stanford requests will reuse the loaded model over localhost HTTP.")


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
    ready = bool(pid is not None and health())
    payload = {"running": pid is not None, "ready": ready, "pid": pid, "endpoint": BASE, "port_open": port_open()}
    print(json.dumps(payload, sort_keys=True))
    write_state(**payload)
    return 0 if ready else 1


def probe() -> None:
    started = time.monotonic()
    prompt = (
        "System: You are testing conversational BitNet inference. Reply naturally and briefly.<|eot_id|>"
        "User: Say hello in one short sentence.<|eot_id|>"
        "Assistant: "
    )
    text = request_completion(
        prompt,
        24,
        0.0,
        stop=["<|eot_id|>"],
        cache_prompt=False,
    )
    lowered = text.lower()
    forbidden = ("end of dialogue so far", "utterance", "[input]", "fill in >")
    if any(marker in lowered for marker in forbidden):
        raise RuntimeError(f"BitNet chat-format probe produced template junk: {text[:300]!r}")
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
