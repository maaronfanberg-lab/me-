#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sarah-society.yml"
OUT = ROOT / "room/warm-runner-watchdog-diagnostic.json"

text = WORKFLOW.read_text(encoding="utf-8")

node_timeout_decl = re.search(r"ROOM_NODE_TIMEOUT_SECONDS=([0-9]+)", text)
kill_grace_decl = re.search(r"ROOM_NODE_KILL_GRACE_SECONDS=([0-9]+)", text)
failure_limit_decl = re.search(r"ROOM_BEAT_FAILURE_LIMIT=([0-9]+)", text)
relay_connect_decl = re.search(r"ROOM_RELAY_CONNECT_TIMEOUT_SECONDS=([0-9]+)", text)
relay_max_decl = re.search(r"ROOM_RELAY_MAX_TIME_SECONDS=([0-9]+)", text)

# Structural checks against the actual production workflow. These intentionally
# fail on the unbounded baseline, then turn green only when the runner itself has
# bounded node execution, bounded relay requests, and an escape to fresh-runner
# handoff after repeated failed beats.
timeout_marker = 'timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s"'
timeout_markers = text.count(timeout_marker)
relay_guard_marker = '--connect-timeout "${ROOM_RELAY_CONNECT_TIMEOUT_SECONDS}" --max-time "${ROOM_RELAY_MAX_TIME_SECONDS}"'
relay_guard_markers = text.count(relay_guard_marker)

has_sense_timeout = "room_engine_v5.py node --phase sense" in text and timeout_markers >= 2
has_recurrent_timeout = "room_engine_v5.py node --phase recurrent" in text and timeout_markers >= 4
has_expression_timeout = "ROOM_EXPRESSION_RANK" in text and timeout_markers >= 5
has_failure_counter = "consecutive_failures" in text
has_failure_break = bool(re.search(r'consecutive_failures.*ROOM_BEAT_FAILURE_LIMIT', text, re.S)) and "break" in text
has_success_reset = bool(re.search(r'consecutive_failures=0', text))
has_warm_window = "stop_at=$((SECONDS + 19800))" in text
has_self_handoff = "gh workflow run sarah-society.yml" in text
has_relay_guards = relay_guard_markers >= 4

# Behavioral probe A: a child that never returns survives an unbounded wait
# window. Then prove GNU timeout can terminate that synthetic hung child.
probe_sleep_seconds = 30
unbounded_probe_window = 1.0
p = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({probe_sleep_seconds})"])
time.sleep(unbounded_probe_window)
unbounded_hang_survived = p.poll() is None
if p.poll() is None:
    p.terminate()
    try:
        p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(timeout=2)

bounded_probe = {
    "attempted": True,
    "terminated": False,
    "elapsed_seconds": None,
    "returncode": None,
}
started = time.monotonic()
proc = subprocess.run(
    ["timeout", "-k", "1s", "1s", sys.executable, "-c", "import time; time.sleep(30)"],
    capture_output=True,
    text=True,
)
elapsed = time.monotonic() - started
bounded_probe.update(
    terminated=elapsed < 5 and proc.returncode in (124, 137, -signal.SIGTERM, -signal.SIGKILL),
    elapsed_seconds=round(elapsed, 3),
    returncode=proc.returncode,
)

# Behavioral probe B: create a local TCP endpoint that accepts a connection and
# then never sends an HTTP response. curl without --max-time could wait
# indefinitely; the production mechanism must use connect/max-time guards.
listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", 0))
listener.listen(1)
port = listener.getsockname()[1]

def stall_server() -> None:
    try:
        conn, _ = listener.accept()
        try:
            time.sleep(30)
        finally:
            conn.close()
    except OSError:
        pass

threading.Thread(target=stall_server, daemon=True).start()
network_started = time.monotonic()
network_proc = subprocess.run(
    ["curl", "-sS", "--connect-timeout", "1", "--max-time", "1", f"http://127.0.0.1:{port}/stall"],
    capture_output=True,
    text=True,
)
network_elapsed = time.monotonic() - network_started
listener.close()
network_probe = {
    "attempted": True,
    "terminated": network_elapsed < 5 and network_proc.returncode == 28,
    "elapsed_seconds": round(network_elapsed, 3),
    "returncode": network_proc.returncode,
}

checks = {
    "unbounded_hang_reproduced": unbounded_hang_survived,
    "node_timeout_declared": bool(node_timeout_decl),
    "kill_grace_declared": bool(kill_grace_decl),
    "failure_limit_declared": bool(failure_limit_decl),
    "relay_connect_timeout_declared": bool(relay_connect_decl),
    "relay_max_time_declared": bool(relay_max_decl),
    "relay_requests_bounded": has_relay_guards,
    "sense_nodes_bounded": has_sense_timeout,
    "recurrent_nodes_bounded": has_recurrent_timeout,
    "expression_nodes_bounded": has_expression_timeout,
    "failure_counter_present": has_failure_counter,
    "failure_threshold_breaks_to_handoff": has_failure_break,
    "successful_beat_resets_failure_counter": has_success_reset,
    "warm_5_5h_window_preserved": has_warm_window,
    "self_handoff_preserved": has_self_handoff,
    "bounded_timeout_behavior": bounded_probe["terminated"],
    "bounded_network_behavior": network_probe["terminated"],
}

required = [
    checks["node_timeout_declared"],
    checks["kill_grace_declared"],
    checks["failure_limit_declared"],
    checks["relay_connect_timeout_declared"],
    checks["relay_max_time_declared"],
    checks["relay_requests_bounded"],
    checks["sense_nodes_bounded"],
    checks["recurrent_nodes_bounded"],
    checks["expression_nodes_bounded"],
    checks["failure_counter_present"],
    checks["failure_threshold_breaks_to_handoff"],
    checks["successful_beat_resets_failure_counter"],
    checks["warm_5_5h_window_preserved"],
    checks["self_handoff_preserved"],
    checks["bounded_timeout_behavior"],
    checks["bounded_network_behavior"],
]

out = {
    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "pass": all(required),
    "workflow": str(WORKFLOW.relative_to(ROOT)),
    "baseline_mechanism": "one never-returning cognition/model subprocess or relay request can block the warm run_beat indefinitely",
    "synthetic_unbounded_child_survived_probe_window": unbounded_hang_survived,
    "production_timeout_seconds": int(node_timeout_decl.group(1)) if node_timeout_decl else None,
    "production_kill_grace_seconds": int(kill_grace_decl.group(1)) if kill_grace_decl else None,
    "production_failure_limit": int(failure_limit_decl.group(1)) if failure_limit_decl else None,
    "relay_connect_timeout_seconds": int(relay_connect_decl.group(1)) if relay_connect_decl else None,
    "relay_max_time_seconds": int(relay_max_decl.group(1)) if relay_max_decl else None,
    "timeout_marker_occurrences": timeout_markers,
    "relay_guard_occurrences": relay_guard_markers,
    "bounded_process_probe": bounded_probe,
    "bounded_network_probe": network_probe,
    "checks": checks,
}
OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
sys.exit(0 if out["pass"] else 1)
