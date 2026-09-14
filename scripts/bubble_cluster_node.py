#!/usr/bin/env python3
"""Long-lived GitHub Actions node for the coupled bubble simulation."""
from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from bubble.core import BubbleParams, integrate_segment

AUDIENCE = "room-live-mirror"
DEFAULT_COORDINATOR = "https://room-live-mirror.dfp6k69dw5.workers.dev"

_token_cache: tuple[str, float] = ("", 0.0)


def github_oidc_token() -> str:
    global _token_cache
    token, expires = _token_cache
    now = time.time()
    if token and now < expires:
        return token

    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not request_url or not request_token:
        raise RuntimeError("GitHub OIDC environment is unavailable; workflow needs id-token: write")
    sep = "&" if "?" in request_url else "?"
    req = urllib.request.Request(
        f"{request_url}{sep}audience={urllib.parse.quote(AUDIENCE)}",
        headers={"Authorization": f"bearer {request_token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.load(response)
    value = str(payload.get("value") or "")
    if not value:
        raise RuntimeError("GitHub OIDC endpoint returned no token")
    _token_cache = (value, now + 240.0)
    return value


def api_request(path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    base = os.environ.get("BUBBLE_COORDINATOR_URL", DEFAULT_COORDINATOR).rstrip("/")
    data = None
    headers = {
        "Authorization": f"Bearer {github_oidc_token()}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"coordinator HTTP {error.code}: {body[:1000]}") from error


def start_simulation(args: argparse.Namespace) -> int:
    config = {
        "sim_id": args.sim_id,
        "reset": args.reset,
        "node_count": args.nodes,
        "model": args.model,
        "radius_spread_fraction": args.radius_spread,
        "nearest_spacing_m": args.spacing,
        "end_time": args.end_time,
        "macro_dt": args.macro_dt,
        "min_macro_dt": args.min_macro_dt,
        "max_corrections": args.max_corrections,
        "coupling_rel_tol": args.coupling_rel_tol,
        "coupling_abs_tol_pa": args.coupling_abs_tol,
        "under_relaxation": args.under_relaxation,
        "rtol": args.rtol,
        "params": {
            "R0": args.radius,
            "drive_amplitude": args.drive_amplitude,
            "drive_frequency": args.drive_frequency,
        },
    }
    result = api_request("/api/bubble/start", method="POST", payload=config)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("accepted") or result.get("reason") == "already-exists":
        return 0
    return 1


def run_node(args: argparse.Namespace) -> int:
    rng = random.Random(104729 * (args.node + 1))
    last_stamp = None
    integrations = 0
    started = time.monotonic()

    while True:
        if time.monotonic() - started > args.max_wall_seconds:
            raise RuntimeError("node wall-clock safety limit reached before simulation completed")

        query = urllib.parse.urlencode({"sim_id": args.sim_id, "node": args.node})
        task = api_request(f"/api/bubble/task?{query}")
        status = task.get("status")

        if status == "complete":
            print(json.dumps({"node": args.node, "status": "complete", "integrations": integrations}))
            return 0
        if status == "failed":
            print(json.dumps(task, indent=2))
            return 2
        if status in {"missing", "invalid-node"}:
            raise RuntimeError(f"coordinator returned {status}")
        if status == "waiting":
            time.sleep(args.poll_seconds + rng.uniform(0, args.poll_jitter))
            continue
        if status != "work":
            raise RuntimeError(f"unexpected coordinator status: {status!r}")

        stamp = (
            int(task["macrostep"]),
            int(task["iteration"]),
            int(task["version"]),
        )
        if stamp == last_stamp:
            time.sleep(args.poll_seconds)
            continue

        p = BubbleParams(**task["params"])
        out = integrate_segment(
            task["checkpoint"],
            p,
            float(task["t_start"]),
            float(task["t_end"]),
            model=str(task["model"]),
            coupling_start=float(task["coupling_start"]),
            coupling_end=float(task["coupling_end"]),
            rtol=float(task.get("rtol", 1e-8)),
        )
        integrations += 1

        inject_ms = max(0.0, args.inject_latency_ms)
        if inject_ms:
            # Validation hook: wall-clock delay must not alter simulated state.
            time.sleep((inject_ms / 1000.0) * rng.random())

        submission = {
            "sim_id": args.sim_id,
            "node": args.node,
            "stamp": {
                "macrostep": stamp[0],
                "iteration": stamp[1],
                "version": stamp[2],
            },
            "result": out.as_dict(),
        }
        response = api_request("/api/bubble/submit", method="POST", payload=submission)
        last_stamp = stamp
        phase = response.get("phase") or response.get("reason") or "submitted"
        print(
            json.dumps(
                {
                    "node": args.node,
                    "macrostep": stamp[0],
                    "iteration": stamp[1],
                    "version": stamp[2],
                    "phase": phase,
                    "R": out.R,
                    "U": out.U,
                    "mach": out.max_wall_mach,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )

        if response.get("status") == "complete" or phase == "complete":
            return 0
        if response.get("status") == "failed":
            return 2
        if response.get("accepted") is False and response.get("reason") not in {"stale"}:
            raise RuntimeError(f"submission rejected: {response}")


def status_simulation(args: argparse.Namespace) -> int:
    query = urllib.parse.urlencode({"sim_id": args.sim_id})
    result = api_request(f"/api/bubble/status?{query}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"running", "complete"} else 1


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--sim-id", required=True)
    start.add_argument("--nodes", type=int, default=12)
    start.add_argument("--model", choices=["rp", "km"], default="km")
    start.add_argument("--radius", type=float, default=10e-6)
    start.add_argument("--radius-spread", type=float, default=0.02)
    start.add_argument("--spacing", type=float, default=1e-3)
    start.add_argument("--drive-amplitude", type=float, default=5000.0)
    start.add_argument("--drive-frequency", type=float, default=20000.0)
    start.add_argument("--end-time", type=float, default=2.5e-4)
    start.add_argument("--macro-dt", type=float, default=1.25e-6)
    start.add_argument("--min-macro-dt", type=float, default=3.90625e-8)
    start.add_argument("--max-corrections", type=int, default=3)
    start.add_argument("--coupling-rel-tol", type=float, default=1e-3)
    start.add_argument("--coupling-abs-tol", type=float, default=0.5)
    start.add_argument("--under-relaxation", type=float, default=0.65)
    start.add_argument("--rtol", type=float, default=1e-8)
    start.add_argument("--reset", action="store_true")

    node = sub.add_parser("node")
    node.add_argument("--sim-id", required=True)
    node.add_argument("--node", type=int, required=True)
    node.add_argument("--poll-seconds", type=float, default=0.35)
    node.add_argument("--poll-jitter", type=float, default=0.20)
    node.add_argument("--inject-latency-ms", type=float, default=0.0)
    node.add_argument("--max-wall-seconds", type=float, default=18000.0)

    status = sub.add_parser("status")
    status.add_argument("--sim-id", required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    if args.command == "start":
        return start_simulation(args)
    if args.command == "node":
        return run_node(args)
    return status_simulation(args)


if __name__ == "__main__":
    raise SystemExit(main())
