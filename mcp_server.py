#!/usr/bin/env python3
"""MCP interface for the repo's existing cluster simulator.

Claude Code can launch this file through the project-level .mcp.json file.
The server intentionally wraps scripts/cluster_worker.py and
scripts/aggregate_cluster.py instead of reimplementing the simulator.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

REPO_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parent)).resolve()
WORKER_SCRIPT = REPO_ROOT / "scripts" / "cluster_worker.py"
AGGREGATE_SCRIPT = REPO_ROOT / "scripts" / "aggregate_cluster.py"
RUN_DIR = Path(os.environ.get("SIMULATOR_RUN_DIR", str(REPO_ROOT / ".simulator_runs"))).resolve()
VALID_WORKLOADS = {"montecarlo", "primes", "hashstorm"}

mcp = MCPServer(
    "Alex Repo Simulator",
    instructions=(
        "Use these tools to run and inspect the repository's cluster simulator. "
        "Prefer modest scales first, inspect results, then increase scale when useful."
    ),
)


def _check_repo() -> None:
    missing = [str(p) for p in (WORKER_SCRIPT, AGGREGATE_SCRIPT) if not p.exists()]
    if missing:
        raise RuntimeError(f"Simulator files are missing: {missing}")


def _validate(workload: str, scale: int, workers: int) -> tuple[str, int, int]:
    workload = workload.lower().strip()
    if workload not in VALID_WORKLOADS:
        raise ValueError(f"workload must be one of {sorted(VALID_WORKLOADS)}")
    if not 1 <= int(scale) <= 20:
        raise ValueError("scale must be between 1 and 20")
    if not 1 <= int(workers) <= 16:
        raise ValueError("workers must be between 1 and 16")
    return workload, int(scale), int(workers)


def _run_one_worker(cwd: Path, workload: str, scale: int, workers: int, worker_id: int) -> None:
    env = os.environ.copy()
    env.update(
        WORKLOAD=workload,
        SCALE=str(scale),
        WORKER_COUNT=str(workers),
        WORKER_ID=str(worker_id),
    )
    proc = subprocess.run(
        [sys.executable, str(WORKER_SCRIPT)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"worker {worker_id} failed: {proc.stderr.strip() or proc.stdout.strip()}")


def _persist(summary: dict[str, Any]) -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    summary = dict(summary)
    summary["run_id"] = run_id
    summary["repo_root"] = str(REPO_ROOT)
    (RUN_DIR / f"{run_id}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (RUN_DIR / "latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _execute(workload: str, scale: int, workers: int) -> dict[str, Any]:
    _check_repo()
    workload, scale, workers = _validate(workload, scale, workers)
    with tempfile.TemporaryDirectory(prefix="repo-sim-") as tmp:
        cwd = Path(tmp)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_run_one_worker, cwd, workload, scale, workers, worker_id)
                for worker_id in range(workers)
            ]
            for future in futures:
                future.result()

        proc = subprocess.run(
            [sys.executable, str(AGGREGATE_SCRIPT)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"aggregation failed: {proc.stderr.strip() or proc.stdout.strip()}")
        summary = json.loads((cwd / "cluster" / "latest.json").read_text(encoding="utf-8"))
    return _persist(summary)


@mcp.tool()
def simulator_info() -> dict[str, Any]:
    """Describe the simulator, allowed workloads, limits, and available persisted runs."""
    _check_repo()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    runs = sorted(p.stem for p in RUN_DIR.glob("*.json") if p.name != "latest.json")
    return {
        "name": "Alex Repo Simulator",
        "workloads": sorted(VALID_WORKLOADS),
        "scale_range": [1, 20],
        "worker_range": [1, 16],
        "worker_script": str(WORKER_SCRIPT.relative_to(REPO_ROOT)),
        "aggregator_script": str(AGGREGATE_SCRIPT.relative_to(REPO_ROOT)),
        "saved_run_count": len(runs),
        "latest_run_id": runs[-1] if runs else None,
    }


@mcp.tool()
def run_simulation(workload: str = "montecarlo", scale: int = 2, workers: int = 4) -> dict[str, Any]:
    """Run one simulator workload and return its complete aggregated result.

    workload: montecarlo, primes, or hashstorm.
    scale: integer 1-20; start small unless a heavier run is genuinely useful.
    workers: integer 1-16.
    """
    return _execute(workload, scale, workers)


@mcp.tool()
def run_batch(workload: str, scales: list[int], workers: int = 4) -> list[dict[str, Any]]:
    """Run the same workload at several scales for comparison. Maximum 8 scale values."""
    if not scales:
        raise ValueError("scales cannot be empty")
    if len(scales) > 8:
        raise ValueError("a batch may contain at most 8 scales")
    return [_execute(workload, int(scale), workers) for scale in scales]


@mcp.tool()
def latest_result() -> dict[str, Any]:
    """Return the latest MCP-driven simulation result, or the repo's cluster/latest.json fallback."""
    local = RUN_DIR / "latest.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    repo_latest = REPO_ROOT / "cluster" / "latest.json"
    if repo_latest.exists():
        result = json.loads(repo_latest.read_text(encoding="utf-8"))
        result["source"] = "cluster/latest.json"
        return result
    return {"status": "no simulation result exists yet"}


@mcp.tool()
def list_runs(limit: int = 10) -> list[dict[str, Any]]:
    """List recent persisted MCP simulation runs with compact summary data."""
    limit = max(1, min(int(limit), 50))
    if not RUN_DIR.exists():
        return []
    paths = sorted(
        (p for p in RUN_DIR.glob("*.json") if p.name != "latest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    output = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        output.append(
            {
                "run_id": data.get("run_id", path.stem),
                "workload": data.get("workload"),
                "workers": data.get("workers"),
                "scale": data.get("scale"),
                "total_units": data.get("total_units"),
                "aggregate_rate": data.get("aggregate_rate"),
                "result": data.get("result"),
            }
        )
    return output


@mcp.tool()
def get_run(run_id: str) -> dict[str, Any]:
    """Load one previously persisted simulation result by run_id."""
    safe = Path(run_id).name
    if safe != run_id or not run_id:
        raise ValueError("invalid run_id")
    path = RUN_DIR / f"{run_id}.json"
    if not path.exists():
        raise ValueError(f"unknown run_id: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    mcp.run()
