"""Fail-closed guard for Room offline conversation experiments.

A shadow or A/B run must never be able to push to production, acknowledge
Allen's live queue, or deliver public speech. This is a safety guard, not a
substitute for running jobs with read-only credentials and network isolation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

BLOCKED_ENV_KEYS = frozenset({
    "GITHUB_TOKEN", "GH_TOKEN", "GH_ENTERPRISE_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL",
    "ROOM_RELAY_URL", "ROOM_RELAY_TOKEN", "ROOM_PUBLISH_TOKEN",
})
BLOCKED_ENV_PREFIXES = ("ROOM_RELAY_", "ROOM_LIVE_ACK_")


def check_offline_environment(
    sandbox_root: str | Path,
    *,
    environment: Mapping[str, str],
    live_repository_root: str | Path | None = None,
) -> Path:
    """Return safe resolved writable sandbox root or raise without side effects."""
    if environment.get("ROOM_EXPERIMENTAL") != "1":
        raise RuntimeError("offline Room mode must be explicitly enabled")
    risky = sorted(
        k for k, v in environment.items()
        if v and (k in BLOCKED_ENV_KEYS or k.startswith(BLOCKED_ENV_PREFIXES))
    )
    if risky:
        # Never print the actual value, token or endpoint.
        raise RuntimeError("offline process inherited a live-capable variable: " + ",".join(risky))
    root = Path(sandbox_root).resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("offline sandbox root must be an existing directory")
    if root == Path(root.anchor):
        raise RuntimeError("filesystem root cannot be a sandbox")
    if live_repository_root is not None:
        production = Path(live_repository_root).resolve(strict=True)
        if root == production or production in root.parents or root in production.parents:
            raise RuntimeError("sandbox and production repository must be disjoint")
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise RuntimeError("offline sandbox cannot be inside a Git working tree")
    return root
