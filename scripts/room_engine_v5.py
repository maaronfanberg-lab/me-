#!/usr/bin/env python3
from __future__ import annotations

"""Select the lean autonomy-v2 model path only for the Llama Room brain.

The complete pre-Llama production wrapper is preserved in
room_engine_v5_legacy.py. Qwen fallback uses that code unchanged. When the
workflow has positively identified Llama 3.2 as the active brain, only the
language-model call boundary is replaced with the canary-tested autonomy-v2
adapter; the Room engine, Allen routing, state transitions, and commit behavior
remain the preserved production implementation.
"""

import os

import room_engine_v5_legacy as _legacy


def _llama_model_run(role: str, payload: dict, timeout: int = 30):
    # Preserve the production gate: unprompted cognitive nodes remain purely
    # deterministic and never call the private model.
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    import room_private_model_autonomy as _autonomy
    return _autonomy.run(role, payload, timeout=timeout)


if os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":
    # The core imported model_run by value when the legacy wrapper loaded, so
    # patch both bindings. Qwen never enters this branch.
    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run


# Re-export the preserved production API so existing callers keep seeing the
# same engine surface.
for _name in dir(_legacy):
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = getattr(_legacy, _name)


def main():
    # room_private_commit.py assigns room_engine_v5.commit dynamically. Forward
    # that override into the preserved wrapper, whose own main() then forwards
    # it to room_engine_v5_core.
    if "commit" in globals():
        _legacy.commit = globals()["commit"]
    return _legacy.main()


if __name__ == "__main__":
    main()
