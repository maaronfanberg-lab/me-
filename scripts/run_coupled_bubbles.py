#!/usr/bin/env python3
"""Run the in-memory coupled bubble world and write a JSON artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Direct script execution sets scripts/ as sys.path[0]. Add the repository root
# so the sibling bubble package resolves without installation or external setup.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bubble.core import BubbleParams
from bubble.coupled import CoupledConfig, simulate_coupled_world


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--nodes", type=int, default=12)
    p.add_argument("--model", choices=["rp", "km"], default="km")
    p.add_argument("--radius", type=float, default=10e-6)
    p.add_argument("--radius-spread", type=float, default=0.02)
    p.add_argument("--spacing", type=float, default=1e-3)
    p.add_argument("--drive-amplitude", type=float, default=1000.0)
    p.add_argument("--drive-frequency", type=float, default=20_000.0)
    p.add_argument("--end-time", type=float, default=5e-5)
    p.add_argument("--macro-dt", type=float, default=2.5e-6)
    p.add_argument("--min-macro-dt", type=float, default=7.8125e-8)
    p.add_argument("--max-corrections", type=int, default=4)
    p.add_argument("--coupling-rel-tol", type=float, default=1e-3)
    p.add_argument("--coupling-abs-tol", type=float, default=0.5)
    p.add_argument("--under-relaxation", type=float, default=0.65)
    p.add_argument("--rtol", type=float, default=1e-8)
    p.add_argument("--output", default="artifacts/coupled-bubble-world.json")
    return p


def main() -> int:
    args = build_parser().parse_args()
    base = BubbleParams(
        R0=args.radius,
        drive_amplitude=args.drive_amplitude,
        drive_frequency=args.drive_frequency,
    )
    config = CoupledConfig(
        node_count=args.nodes,
        model=args.model,
        nearest_spacing_m=args.spacing,
        radius_spread_fraction=args.radius_spread,
        end_time=args.end_time,
        macro_dt=args.macro_dt,
        min_macro_dt=args.min_macro_dt,
        max_corrections=args.max_corrections,
        coupling_rel_tol=args.coupling_rel_tol,
        coupling_abs_tol_pa=args.coupling_abs_tol,
        under_relaxation=args.under_relaxation,
        rtol=args.rtol,
    )
    result = simulate_coupled_world(base, config)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    max_mach = max((step["max_wall_mach"] for step in result["history"]), default=0.0)
    max_coupling = max(
        (max(abs(x) for x in step["coupling_pressure_pa"]) for step in result["history"]),
        default=0.0,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "simulation_time": result["simulation_time"],
                "steps": len(result["history"]),
                "rollbacks": result["rollbacks"],
                "max_wall_mach": max_mach,
                "max_abs_coupling_pressure_pa": max_coupling,
                "output": str(output),
            },
            indent=2,
        )
    )
    return 0 if result["status"] in {"complete", "collapsed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
