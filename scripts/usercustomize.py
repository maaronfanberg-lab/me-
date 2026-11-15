"""Production startup guards for the persistent Room world.

These guards exist before the Room engine imports so continuity, expression quality,
and semantic hygiene cannot be bypassed by a later wrapper layer.

An explicitly destructive maintenance run can opt out of continuity protection with
``ROOM_ALLOW_DESTRUCTIVE_BOOT_RESET=1``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

_ORIGINAL_READ_TEXT = Path.read_text
_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = (_ROOT / "room" / "config.json").resolve()
_STATE = _ROOT / "room" / "state.json"


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(_ORIGINAL_READ_TEXT(path))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _install_room_boot_guard() -> None:
    if os.environ.get("ROOM_ALLOW_DESTRUCTIVE_BOOT_RESET", "").strip() == "1":
        return
    if not _CONFIG.exists() or not _STATE.exists():
        return

    persisted = _json_file(_STATE)
    configured = _json_file(_CONFIG)
    persisted_boot = str(persisted.get("boot_id") or "").strip()
    configured_boot = str(configured.get("boot_id") or "").strip()
    if not persisted_boot or not configured_boot or persisted_boot == configured_boot:
        return

    protected = dict(configured)
    protected["boot_id"] = persisted_boot
    protected["requested_boot_id"] = configured_boot
    encoded = json.dumps(protected, ensure_ascii=False)

    def _continuity_read_text(path: Path, *args, **kwargs):
        try:
            if path.resolve() == _CONFIG:
                return encoded
        except Exception:
            pass
        return _ORIGINAL_READ_TEXT(path, *args, **kwargs)

    Path.read_text = _continuity_read_text
    print(
        "ROOM_BOOT_CONTINUITY_GUARD "
        f"preserved={persisted_boot} ignored_destructive_config_boot={configured_boot}",
        flush=True,
    )


def _profile_strings(value):
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _profile_strings(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _profile_strings(item)


def _words(value) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _profile_echo(utterance: str, payload: dict, n: int = 5) -> bool:
    """Profiles may shape a voice, but profile prose must not become dialogue."""
    output = _words(utterance)
    if len(output) < n:
        return False
    output_grams = {tuple(output[i:i + n]) for i in range(len(output) - n + 1)}
    profile = (payload or {}).get("profile")
    psychology = profile.get("psychology_v2") if isinstance(profile, dict) and isinstance(profile.get("psychology_v2"), dict) else {}
    for source in _profile_strings(psychology):
        source_words = _words(source)
        for i in range(max(0, len(source_words) - n + 1)):
            if tuple(source_words[i:i + n]) in output_grams:
                return True
    return False


def _install_topic_noise_guard() -> None:
    """Keep discourse/process abstractions from becoming persistent subjects."""
    try:
        import room_topic_bounded as bounded
    except Exception:
        return
    bounded._TOPIC_NOISE.update({
        "step", "steps", "important", "importance", "direction", "directions",
        "issue", "issues", "point", "points", "subject", "subjects",
        "conversation", "conversations", "discussion", "discussions",
        "change", "changes", "changed", "changing", "avoid", "avoids", "avoided", "avoiding",
        "progress", "meaningful", "current", "recent", "recently",
        "stance", "stances", "view", "views", "perceive", "perceived", "perception",
    })


def _install_expression_retry_guard() -> None:
    """Align generation with publication hygiene without weakening the final gate.

    The autonomy model already retries internally, but all of those attempts share the
    same cycle seed family. If the candidate is missing, deterministic-hygiene invalid,
    or copies hidden personality prose, make one more autonomy pass under a fresh seed.
    Six possible model requests are each capped at seven seconds so the outer 45-second
    node watchdog remains authoritative instead of accidentally killing a healthy retry.
    """
    try:
        import room_private_model_autonomy as autonomy
        import room_research_architecture as research
    except Exception:
        return

    if hasattr(autonomy, "_startup_original_run"):
        return
    autonomy._startup_original_run = autonomy.run
    original_run = autonomy.run

    def _guarded_run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
        if role != "expression":
            return original_run(role, payload, timeout=timeout, min_words=min_words)

        entity = str((payload or {}).get("entity") or "").strip().lower()
        original_key = os.environ.get("ROOM_CYCLE_KEY")
        base_key = original_key or "room-cycle"
        try:
            for quality_pass in range(2):
                os.environ["ROOM_CYCLE_KEY"] = (
                    base_key if quality_pass == 0 else f"{base_key}:publish-retry-{quality_pass}"
                )
                result = original_run(
                    role,
                    payload,
                    timeout=min(int(timeout), 7),
                    min_words=max(4, int(min_words)),
                )
                if not isinstance(result, dict):
                    continue
                utterance = str(result.get("utterance") or "").strip()
                issue = research.autonomous_text_issue({"speaker": entity, "text": utterance})
                if issue:
                    print(f"Expression pre-publication retry for {entity}: {issue}", flush=True)
                    continue
                if _profile_echo(utterance, payload):
                    print(f"Expression pre-publication retry for {entity}: profile_echo", flush=True)
                    continue
                return result
            print(f"Expression exhausted pre-publication retries for {entity}", flush=True)
            return None
        finally:
            if original_key is None:
                os.environ.pop("ROOM_CYCLE_KEY", None)
            else:
                os.environ["ROOM_CYCLE_KEY"] = original_key

    autonomy.run = _guarded_run


_install_room_boot_guard()
_install_topic_noise_guard()
_install_expression_retry_guard()
