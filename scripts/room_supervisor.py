#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STALE_AFTER_SECONDS = 3 * 60
MAX_RESTARTS_PER_CYCLE = 2
CIRCUIT_COOLDOWN_SECONDS = 15 * 60


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_control(control: dict | None) -> dict:
    source = control if isinstance(control, dict) else {}
    return {
        "version": 1,
        "last_observed_cycle": int(source.get("last_observed_cycle") or 0),
        "restart_cycle": int(source.get("restart_cycle") or 0),
        "restart_attempts": int(source.get("restart_attempts") or 0),
        "circuit_open": bool(source.get("circuit_open", False)),
        "circuit_opened_at": str(source.get("circuit_opened_at") or ""),
        "last_action": str(source.get("last_action") or ""),
        "last_checked_at": str(source.get("last_checked_at") or ""),
    }


def decide(state: dict, control: dict | None = None, *, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    cycle = int((state or {}).get("cycle") or 0)
    last_run = _parse_time((state or {}).get("last_run"))
    age = None if last_run is None else max(0.0, (current - last_run).total_seconds())
    stale = last_run is None or age >= STALE_AFTER_SECONDS
    has_baseline = isinstance(control, dict) and "last_observed_cycle" in control
    ctl = _base_control(control)

    # A missing control file must not cost us an extra supervisor interval when
    # the published Room is already stale. Establish the baseline and launch a
    # bounded replacement in the same check.
    if not has_baseline:
        ctl.update({
            "last_observed_cycle": cycle,
            "restart_cycle": cycle if stale else 0,
            "restart_attempts": 1 if stale else 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "restart" if stale else "initialize",
            "last_checked_at": _stamp(current),
        })
        if stale:
            return {"action": "restart", "reason": "stale_first_observation", "age_seconds": age, "control": ctl}
        return {"action": "initialize", "reason": "baseline_created", "age_seconds": age, "control": ctl}

    previous_cycle = ctl["last_observed_cycle"]
    progressed = cycle > previous_cycle

    if progressed:
        ctl.update({
            "last_observed_cycle": cycle,
            "restart_cycle": 0,
            "restart_attempts": 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "healthy",
            "last_checked_at": _stamp(current),
        })
        return {"action": "healthy", "reason": "cycle_progress", "control": ctl}

    if not stale:
        ctl.update({
            "last_observed_cycle": max(previous_cycle, cycle),
            "restart_cycle": 0,
            "restart_attempts": 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "healthy",
            "last_checked_at": _stamp(current),
        })
        return {"action": "healthy", "reason": "recent_beat", "age_seconds": age, "control": ctl}

    same_stalled_cycle = ctl["restart_cycle"] == cycle
    attempts = ctl["restart_attempts"] if same_stalled_cycle else 0

    if ctl["circuit_open"] and same_stalled_cycle:
        opened = _parse_time(ctl.get("circuit_opened_at"))
        cooled = opened is not None and (current - opened).total_seconds() >= CIRCUIT_COOLDOWN_SECONDS
        if cooled:
            ctl.update({
                "last_observed_cycle": max(previous_cycle, cycle),
                "restart_cycle": cycle,
                "restart_attempts": 1,
                "circuit_open": False,
                "circuit_opened_at": "",
                "last_action": "probe_restart",
                "last_checked_at": _stamp(current),
            })
            return {"action": "probe_restart", "reason": "circuit_cooldown_probe", "age_seconds": age, "control": ctl}
        ctl["last_checked_at"] = _stamp(current)
        ctl["last_action"] = "circuit_open"
        return {"action": "circuit_open", "reason": "cooldown", "age_seconds": age, "control": ctl}

    if attempts >= MAX_RESTARTS_PER_CYCLE:
        ctl.update({
            "last_observed_cycle": max(previous_cycle, cycle),
            "restart_cycle": cycle,
            "restart_attempts": MAX_RESTARTS_PER_CYCLE,
            "circuit_open": True,
            "circuit_opened_at": _stamp(current),
            "last_action": "circuit_open",
            "last_checked_at": _stamp(current),
        })
        return {"action": "circuit_open", "reason": "same_cycle_failed_replacements", "age_seconds": age, "control": ctl}

    ctl.update({
        "last_observed_cycle": max(previous_cycle, cycle),
        "restart_cycle": cycle,
        "restart_attempts": attempts + 1,
        "circuit_open": False,
        "circuit_opened_at": "",
        "last_action": "restart",
        "last_checked_at": _stamp(current),
    })
    return {"action": "restart", "reason": "stale_room", "age_seconds": age, "control": ctl}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] != "check":
        print("usage: room_supervisor.py check [state.json] [control.json] [decision.json]", file=sys.stderr)
        return 2
    state_path = Path(argv[2]) if len(argv) > 2 else Path("room/state.json")
    control_path = Path(argv[3]) if len(argv) > 3 else Path(".github/room-supervisor-state.json")
    decision_path = Path(argv[4]) if len(argv) > 4 else Path(".github/room-supervisor-decision.json")
    result = decide(_load(state_path), _load(control_path))
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["action"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
