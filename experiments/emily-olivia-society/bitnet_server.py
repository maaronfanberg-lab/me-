#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("COMMUNITY_BITNET_ROOT", HERE / "vendor" / "BitNet"))
MODEL = Path(os.environ.get("COMMUNITY_BITNET_MODEL", HERE / "models" / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"))
SERVER = ROOT / "build" / "bin" / "llama-server"
CLI = ROOT / "build" / "bin" / "llama-cli"
REAL_CLI = ROOT / "build" / "bin" / "llama-cli.real"
PID_FILE = HERE / ".bitnet-server.pid"
LOG_FILE = HERE / "replay" / "bitnet-server.log"
HOST = "127.0.0.1"
PORT = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
BASE = f"http://{HOST}:{PORT}"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def saved_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return None
    return pid if pid_alive(pid) else None


def request_completion(prompt: str, n_predict: int, temperature: float, timeout: int = 900) -> str:
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "stream": False,
        "cache_prompt": True,
    }).encode()
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


def wait_until_ready(timeout: int = 900) -> None:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        pid = saved_pid()
        if pid is None:
            raise RuntimeError("BitNet server exited before becoming ready")
        try:
            with socket.create_connection((HOST, PORT), timeout=2):
                pass
            text = request_completion("Say OK.", 2, 0.0, timeout=120)
            print("BITNET_SERVER_PROBE:", text[:200])
            return
        except Exception as exc:
            last_error = exc
            time.sleep(5)
    raise TimeoutError(f"BitNet server did not become ready in {timeout}s: {last_error}")


def install_cli_proxy() -> None:
    if not CLI.exists() and not REAL_CLI.exists():
        raise FileNotFoundError(f"BitNet llama-cli not found: {CLI}")
    proxy = Path(__file__).resolve()
    if CLI.is_symlink() and CLI.resolve() == proxy:
        return
    if CLI.exists() or CLI.is_symlink():
        if REAL_CLI.exists() or REAL_CLI.is_symlink():
            REAL_CLI.unlink()
        CLI.rename(REAL_CLI)
    CLI.symlink_to(proxy)


def start() -> None:
    existing = saved_pid()
    if existing is not None:
        print(f"BitNet server already running as PID {existing}")
        install_cli_proxy()
        return
    if not SERVER.exists():
        raise FileNotFoundError(f"BitNet llama-server not found: {SERVER}")
    if not MODEL.exists():
        raise FileNotFoundError(f"BitNet model not found: {MODEL}")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_FILE.open("ab", buffering=0)
    threads = max(4, min(6, os.cpu_count() or 4))
    proc = subprocess.Popen(
        [
            str(SERVER), "-m", str(MODEL), "-c", "2048", "-t", str(threads),
            "-n", "128", "-ngl", "0", "--temp", "0.7",
            "--host", HOST, "--port", str(PORT), "-cb",
        ],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"Started persistent BitNet server as PID {proc.pid}")
    wait_until_ready()
    install_cli_proxy()
    print("Installed llama-cli compatibility proxy; subsequent Stanford calls reuse the loaded model.")


def stop() -> None:
    pid = saved_pid()
    if pid is None:
        PID_FILE.unlink(missing_ok=True)
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
    print("Stopped BitNet server")


def proxy_cli(argv: list[str]) -> int:
    prompt = ""
    n_predict = 64
    temperature = 0.7
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-p", "--prompt") and i + 1 < len(argv):
            prompt = argv[i + 1]
            i += 2
            continue
        if arg in ("-n", "--n-predict") and i + 1 < len(argv):
            n_predict = min(int(argv[i + 1]), 256)
            i += 2
            continue
        if arg in ("--temp", "-temp", "--temperature") and i + 1 < len(argv):
            temperature = float(argv[i + 1])
            i += 2
            continue
        i += 1
    if not prompt:
        print("GENERATION ERROR: llama-cli proxy received no prompt", file=sys.stderr)
        return 2
    try:
        print(request_completion(prompt, n_predict, temperature))
        return 0
    except Exception as exc:
        print(f"GENERATION ERROR: persistent BitNet request failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    # When invoked through the llama-cli symlink, behave like the small subset of
    # llama-cli used by the pinned Stanford runtime.
    if Path(sys.argv[0]).name == "llama-cli":
        return proxy_cli(sys.argv[1:])
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("start", "stop", "status", "probe"))
    args = parser.parse_args()
    if args.command == "start":
        start()
    elif args.command == "stop":
        stop()
    elif args.command == "status":
        pid = saved_pid()
        print(json.dumps({"running": pid is not None, "pid": pid, "endpoint": BASE}))
        return 0 if pid is not None else 1
    else:
        print(request_completion("Say OK.", 2, 0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
