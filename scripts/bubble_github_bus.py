#!/usr/bin/env python3
"""GitHub-native macrostep bus for the distributed coupled-bubble solver.

One issue body is the authoritative simulation state.  A single coordinator
job is the only writer of that body.  Each bubble node owns one fixed issue
comment and updates only that slot with stamped integration results.  This
keeps the stiff radial solve local while giving the 12 runners a barrier at
macrostep/correction boundaries without an external database.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ISSUE_MARKER = "<!-- bubble-github-bus-v1 -->"
SLOT_MARKER = "<!-- bubble-github-slot-v1 -->"


def _token() -> str:
    value = os.environ.get("GITHUB_TOKEN", "").strip()
    if not value:
        raise RuntimeError("GITHUB_TOKEN is required")
    return value


def _repo() -> str:
    value = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not value or "/" not in value:
        raise RuntimeError("GITHUB_REPOSITORY is required")
    return value


def api(path: str, *, method: str = "GET", payload: dict | None = None) -> dict | list:
    url = f"https://api.github.com/repos/{_repo()}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "coupled-bubble-github-bus/1",
    }
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {error.code} {method} {path}: {body[:1000]}") from error


def encode_doc(marker: str, doc: dict) -> str:
    return f"{marker}\n```json\n{json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)}\n```\n"


def decode_doc(text: str, marker: str) -> dict | None:
    if marker not in str(text or ""):
        return None
    source = str(text)
    start = source.find("```json")
    if start < 0:
        return None
    start = source.find("\n", start)
    end = source.find("```", start + 1)
    if start < 0 or end < 0:
        return None
    try:
        value = json.loads(source[start + 1 : end])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def issue_state(issue: int) -> dict:
    row = api(f"/issues/{issue}")
    state = decode_doc(str(row.get("body") or ""), ISSUE_MARKER)
    if not state:
        raise RuntimeError(f"issue {issue} does not contain a bubble bus state")
    return state


def update_issue(issue: int, state: dict) -> None:
    api(f"/issues/{issue}", method="PATCH", payload={"body": encode_doc(ISSUE_MARKER, state)})


def list_slots(issue: int) -> dict[int, tuple[int, dict]]:
    rows = api(f"/issues/{issue}/comments?per_page=100")
    slots: dict[int, tuple[int, dict]] = {}
    for row in rows:
        doc = decode_doc(str(row.get("body") or ""), SLOT_MARKER)
        if not doc or doc.get("kind") != "bubble-slot":
            continue
        try:
            node = int(doc["node"])
            comment_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        slots[node] = (comment_id, doc)
    return slots


def patch_slot(comment_id: int, doc: dict) -> None:
    api(f"/issues/comments/{comment_id}", method="PATCH", payload={"body": encode_doc(SLOT_MARKER, doc)})


def ring_positions(count: int, spacing: float) -> list[list[float]]:
    if count == 1:
        return [[0.0, 0.0, 0.0]]
    radius = spacing / (2.0 * math.sin(math.pi / count))
    return [
        [radius * math.cos(2.0 * math.pi * i / count), radius * math.sin(2.0 * math.pi * i / count), 0.0]
        for i in range(count)
    ]


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def stamp_of(state: dict) -> dict:
    return {
        "macrostep": int(state["macrostep"]),
        "iteration": int(state["iteration"]),
        "version": int(state["version"]),
    }


def stamp_key(stamp: dict | None) -> tuple[int, int, int] | None:
    if not stamp:
        return None
    try:
        return int(stamp["macrostep"]), int(stamp["iteration"]), int(stamp["version"])
    except (KeyError, TypeError, ValueError):
        return None


def make_tasks(state: dict) -> dict[str, dict]:
    if state.get("status") != "running":
        return {}
    t_start = float(state["sim_time"])
    t_end = min(t_start + float(state["dt"]), float(state["end_time"]))
    stamp = stamp_of(state)
    tasks: dict[str, dict] = {}
    for node in range(int(state["node_count"])):
        tasks[str(node)] = {
            "stamp": stamp,
            "t_start": t_start,
            "t_end": t_end,
            "checkpoint": state["checkpoints"][node],
            "coupling_start": state["coupling_start"][node],
            "coupling_end": state["coupling_guess"][node],
            "model": state["model"],
            "params": state["params_by_node"][node],
            "rtol": state["rtol"],
        }
    return tasks


def create_bus(args: argparse.Namespace) -> int:
    count = max(2, min(12, int(args.nodes)))
    if not (args.radius > 0 and args.spacing > 20.0 * args.radius):
        raise ValueError("spacing must exceed 20 R0 for the v1 far-field coupling model")
    if not (args.dt > 0 and args.end_time > 0 and 0 < args.min_dt <= args.dt):
        raise ValueError("invalid time configuration")

    common = {
        "rho": 997.0,
        "mu": 8.9e-4,
        "sigma": 0.072,
        "c": 1480.0,
        "p0": 101325.0,
        "pv": 2339.0,
        "R0": float(args.radius),
        "kappa": 1.4,
        "drive_amplitude": float(args.drive_amplitude),
        "drive_frequency": float(args.drive_frequency),
    }
    params_by_node = []
    for node in range(count):
        phase = 2.0 * math.pi * node / count
        row = dict(common)
        row["R0"] = common["R0"] * (1.0 + args.radius_spread * math.cos(phase))
        params_by_node.append(row)

    state = {
        "schema": 1,
        "transport": "github-issue-slots",
        "sim_id": args.sim_id,
        "status": "running",
        "node_count": count,
        "model": args.model,
        "params_by_node": params_by_node,
        "positions": ring_positions(count, float(args.spacing)),
        "sim_time": 0.0,
        "end_time": float(args.end_time),
        "macrostep": 0,
        "iteration": 0,
        "dt": float(args.dt),
        "initial_dt": float(args.dt),
        "min_dt": float(args.min_dt),
        "max_iterations": max(1, min(8, int(args.max_corrections))),
        "coupling_rel_tol": float(args.coupling_rel_tol),
        "coupling_abs_tol": float(args.coupling_abs_tol),
        "under_relax": float(args.under_relaxation),
        "rtol": float(args.rtol),
        "checkpoints": [[p["R0"], 0.0] for p in params_by_node],
        "coupling_start": [0.0] * count,
        "coupling_guess": [0.0] * count,
        "version": 1,
        "last_residual_abs": 0.0,
        "last_residual_rel": 0.0,
        "accepted_steps": 0,
        "rollbacks": 0,
        "warnings": [
            "v1 inter-bubble coupling uses instantaneous leading-monopole p=K/r coupling; finite propagation delay is not yet modeled."
        ],
        "history": [],
        "failure": "",
        "terminal_event": None,
    }
    state["tasks"] = make_tasks(state)
    created = api(
        "/issues",
        method="POST",
        payload={
            "title": f"[bubble-bus] {args.sim_id}",
            "body": encode_doc(ISSUE_MARKER, state),
            "labels": [],
        },
    )
    issue = int(created["number"])
    for node in range(count):
        doc = {"kind": "bubble-slot", "sim_id": args.sim_id, "node": node, "stamp": None, "result": None}
        api(f"/issues/{issue}/comments", method="POST", payload={"body": encode_doc(SLOT_MARKER, doc)})
    print(json.dumps({"issue": issue, "sim_id": args.sim_id, "node_count": count}, sort_keys=True))
    return 0


def coupling_from_results(state: dict, results: dict[int, dict]) -> list[float]:
    count = int(state["node_count"])
    outputs = [0.0] * count
    for target in range(count):
        pressure = 0.0
        for source in range(count):
            if source == target:
                continue
            K = float(results[source]["emitted_pressure_coeff"])
            d = distance(state["positions"][target], state["positions"][source])
            if not math.isfinite(K) or not d > 0:
                raise RuntimeError("invalid coupling submission")
            pressure += K / d
        outputs[target] = pressure
    return outputs


def advance_state(state: dict, results: dict[int, dict]) -> dict:
    count = int(state["node_count"])
    for node, result in results.items():
        if not bool(result.get("success")):
            state["status"] = "failed"
            state["failure"] = f"node-{node}-integration-failure"
            state["tasks"] = {}
            return state
        if bool(result.get("collapsed")):
            state["status"] = "complete"
            state["terminal_event"] = {
                "type": "physical-collapse",
                "node": node,
                "macrostep": state["macrostep"],
                "iteration": state["iteration"],
                "sim_time": float(result.get("t_end", state["sim_time"])),
                "R": float(result["R"]),
                "U": float(result["U"]),
                "max_wall_mach": float(result.get("max_wall_mach", 0.0)),
            }
            state["history"].append(dict(state["terminal_event"]))
            state["tasks"] = {}
            return state

    new_coupling = coupling_from_results(state, results)
    max_abs = 0.0
    max_rel = 0.0
    for i in range(count):
        delta = abs(new_coupling[i] - float(state["coupling_guess"][i]))
        max_abs = max(max_abs, delta)
        scale = max(1.0, abs(new_coupling[i]), abs(float(state["coupling_guess"][i])))
        max_rel = max(max_rel, delta / scale)
    state["last_residual_abs"] = max_abs
    state["last_residual_rel"] = max_rel

    converged = max_abs <= float(state["coupling_abs_tol"]) or max_rel <= float(state["coupling_rel_tol"])
    if converged:
        previous_start = list(state["coupling_start"])
        state["checkpoints"] = [[float(results[i]["R"]), float(results[i]["U"])] for i in range(count)]
        accepted_iteration = int(state["iteration"])
        accepted_dt = min(float(state["dt"]), float(state["end_time"]) - float(state["sim_time"]))
        state["sim_time"] = float(state["sim_time"]) + accepted_dt
        state["macrostep"] = int(state["macrostep"]) + 1
        state["iteration"] = 0
        state["accepted_steps"] = int(state["accepted_steps"]) + 1
        state["coupling_start"] = new_coupling
        state["coupling_guess"] = [value + 0.35 * (value - previous_start[i]) for i, value in enumerate(new_coupling)]
        rows = list(results.values())
        summary = {
            "macrostep": int(state["macrostep"]) - 1,
            "sim_time": float(state["sim_time"]),
            "dt": accepted_dt,
            "corrections": accepted_iteration,
            "coupling_residual_abs": max_abs,
            "coupling_residual_rel": max_rel,
            "max_wall_mach": max(float(r.get("max_wall_mach", 0.0)) for r in rows),
            "min_radius": min(float(r.get("min_R", r["R"])) for r in rows),
            "max_radius": max(float(r.get("max_R", r["R"])) for r in rows),
        }
        state["history"].append(summary)
        state["history"] = state["history"][-200:]
        if accepted_iteration == 0 and float(state["dt"]) < float(state["initial_dt"]):
            state["dt"] = min(float(state["initial_dt"]), float(state["dt"]) * 1.5)
        if summary["max_wall_mach"] > 0.1:
            state["warnings"].append(
                f"macrostep-{summary['macrostep']}: wall Mach exceeded 0.1; Keller-Miksis weak-compressibility validity should be scrutinized."
            )
            state["warnings"] = state["warnings"][-40:]
        state["version"] = int(state["version"]) + 1
        if float(state["sim_time"]) >= float(state["end_time"]) * (1.0 - 1e-12):
            state["sim_time"] = float(state["end_time"])
            state["status"] = "complete"
            state["tasks"] = {}
        else:
            state["tasks"] = make_tasks(state)
        return state

    if int(state["iteration"]) + 1 < int(state["max_iterations"]):
        relax = float(state["under_relax"])
        state["coupling_guess"] = [
            float(state["coupling_guess"][i]) + relax * (new_coupling[i] - float(state["coupling_guess"][i]))
            for i in range(count)
        ]
        state["iteration"] = int(state["iteration"]) + 1
        state["version"] = int(state["version"]) + 1
        state["tasks"] = make_tasks(state)
        return state

    next_dt = float(state["dt"]) / 2.0
    if next_dt >= float(state["min_dt"]) * (1.0 - 1e-12):
        state["dt"] = next_dt
        state["iteration"] = 0
        state["rollbacks"] = int(state["rollbacks"]) + 1
        state["coupling_guess"] = list(state["coupling_start"])
        state["version"] = int(state["version"]) + 1
        state["history"].append(
            {
                "macrostep": int(state["macrostep"]),
                "sim_time": float(state["sim_time"]),
                "event": "rollback",
                "next_dt": next_dt,
                "coupling_residual_abs": max_abs,
                "coupling_residual_rel": max_rel,
            }
        )
        state["history"] = state["history"][-200:]
        state["tasks"] = make_tasks(state)
        return state

    state["status"] = "failed"
    state["failure"] = "coupling-failed-at-minimum-macrostep"
    state["tasks"] = {}
    return state


def coordinator(args: argparse.Namespace) -> int:
    started = time.monotonic()
    while True:
        if time.monotonic() - started > args.max_wall_seconds:
            raise RuntimeError("coordinator wall-clock safety limit reached")
        state = issue_state(args.issue)
        status = str(state.get("status"))
        if status in {"complete", "failed"}:
            print(json.dumps({"status": status, "issue": args.issue, "summary": state.get("history", [])[-1:]}, sort_keys=True))
            return 0 if status == "complete" else 2
        expected = stamp_key(stamp_of(state))
        slots = list_slots(args.issue)
        results: dict[int, dict] = {}
        for node in range(int(state["node_count"])):
            row = slots.get(node)
            if not row:
                break
            doc = row[1]
            if stamp_key(doc.get("stamp")) != expected or not isinstance(doc.get("result"), dict):
                break
            results[node] = doc["result"]
        if len(results) != int(state["node_count"]):
            time.sleep(args.poll_seconds)
            continue
        state = advance_state(state, results)
        update_issue(args.issue, state)
        last = state.get("history", [])[-1] if state.get("history") else {}
        print(
            json.dumps(
                {
                    "status": state["status"],
                    "macrostep": state["macrostep"],
                    "iteration": state["iteration"],
                    "version": state["version"],
                    "sim_time": state["sim_time"],
                    "dt": state["dt"],
                    "last": last,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        if state["status"] == "complete":
            return 0
        if state["status"] == "failed":
            return 2


def node_runner(args: argparse.Namespace) -> int:
    from bubble.core import BubbleParams, integrate_segment

    rng = random.Random(104729 * (args.node + 1))
    slots = list_slots(args.issue)
    if args.node not in slots:
        raise RuntimeError(f"node slot {args.node} not found")
    comment_id = slots[args.node][0]
    last_stamp = None
    integrations = 0
    started = time.monotonic()

    while True:
        if time.monotonic() - started > args.max_wall_seconds:
            raise RuntimeError("node wall-clock safety limit reached")
        state = issue_state(args.issue)
        status = str(state.get("status"))
        if status == "complete":
            print(json.dumps({"node": args.node, "status": status, "integrations": integrations}))
            return 0
        if status == "failed":
            print(json.dumps({"node": args.node, "status": status, "failure": state.get("failure")}))
            return 2
        task = (state.get("tasks") or {}).get(str(args.node))
        if not isinstance(task, dict):
            time.sleep(args.poll_seconds + rng.uniform(0.0, args.poll_jitter))
            continue
        current_stamp = stamp_key(task.get("stamp"))
        if current_stamp is None or current_stamp == last_stamp:
            time.sleep(args.poll_seconds + rng.uniform(0.0, args.poll_jitter))
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
        if args.inject_latency_ms > 0:
            time.sleep(rng.random() * args.inject_latency_ms / 1000.0)
        doc = {
            "kind": "bubble-slot",
            "sim_id": state["sim_id"],
            "node": args.node,
            "stamp": task["stamp"],
            "result": out.as_dict(),
        }
        patch_slot(comment_id, doc)
        last_stamp = current_stamp
        print(
            json.dumps(
                {
                    "node": args.node,
                    "stamp": current_stamp,
                    "R": out.R,
                    "U": out.U,
                    "mach": out.max_wall_mach,
                    "collapsed": out.collapsed,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        time.sleep(args.poll_seconds + rng.uniform(0.0, args.poll_jitter))


def status_cmd(args: argparse.Namespace) -> int:
    state = issue_state(args.issue)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state.get("status") in {"running", "complete"} else 1


def close_cmd(args: argparse.Namespace) -> int:
    state = issue_state(args.issue)
    api(f"/issues/{args.issue}", method="PATCH", payload={"state": "closed"})
    print(json.dumps({"issue": args.issue, "closed": True, "status": state.get("status")}))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create")
    c.add_argument("--sim-id", required=True)
    c.add_argument("--nodes", type=int, default=12)
    c.add_argument("--model", choices=["rp", "km"], default="km")
    c.add_argument("--radius", type=float, default=10e-6)
    c.add_argument("--radius-spread", type=float, default=0.02)
    c.add_argument("--spacing", type=float, default=1e-3)
    c.add_argument("--drive-amplitude", type=float, default=1000.0)
    c.add_argument("--drive-frequency", type=float, default=20000.0)
    c.add_argument("--end-time", type=float, default=5e-5)
    c.add_argument("--dt", type=float, default=6.25e-6)
    c.add_argument("--min-dt", type=float, default=3.90625e-7)
    c.add_argument("--max-corrections", type=int, default=3)
    c.add_argument("--coupling-rel-tol", type=float, default=1e-3)
    c.add_argument("--coupling-abs-tol", type=float, default=0.5)
    c.add_argument("--under-relaxation", type=float, default=0.65)
    c.add_argument("--rtol", type=float, default=1e-8)

    coord = sub.add_parser("coordinate")
    coord.add_argument("--issue", type=int, required=True)
    coord.add_argument("--poll-seconds", type=float, default=1.0)
    coord.add_argument("--max-wall-seconds", type=float, default=900.0)

    node = sub.add_parser("node")
    node.add_argument("--issue", type=int, required=True)
    node.add_argument("--node", type=int, required=True)
    node.add_argument("--poll-seconds", type=float, default=1.5)
    node.add_argument("--poll-jitter", type=float, default=0.5)
    node.add_argument("--inject-latency-ms", type=float, default=0.0)
    node.add_argument("--max-wall-seconds", type=float, default=900.0)

    status = sub.add_parser("status")
    status.add_argument("--issue", type=int, required=True)
    close = sub.add_parser("close")
    close.add_argument("--issue", type=int, required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    if args.command == "create":
        return create_bus(args)
    if args.command == "coordinate":
        return coordinator(args)
    if args.command == "node":
        return node_runner(args)
    if args.command == "status":
        return status_cmd(args)
    return close_cmd(args)


if __name__ == "__main__":
    raise SystemExit(main())
