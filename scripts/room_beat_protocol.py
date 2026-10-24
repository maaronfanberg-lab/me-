"""Offline-first beat health protocol for the Room.

This module is intentionally *not* wired into the live runner. It defines the
failure/silence distinction the existing watchdog will need before voluntary
silence or action-aware speaker choice can safely be enabled.

No rule here evaluates words, forbids repetition, changes subjects, chooses
someone to speak, or makes a silent participant produce an utterance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

HEALTHY = frozenset({"spoken", "chosen_silence"})
UNHEALTHY = frozenset({
    "stage_failed", "generation_failed", "validation_failed",
    "model_unavailable", "infrastructure_failure", "invalid_no_eligible_person",
})
ALL_OUTCOMES = HEALTHY | UNHEALTHY
REQUIRED_STAGES = ("perception", "observation", "floor_selection")
DEFAULT_HEARTBEAT_SECONDS = 300
DEFAULT_WATCHDOG_SECONDS = 900


@dataclass(frozen=True)
class BeatOutcome:
    kind: str
    decision_id: str
    selected_speaker: str | None = None
    published_message_ids: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self):
        if self.kind not in ALL_OUTCOMES or not isinstance(self.decision_id, str) or not self.decision_id:
            raise ValueError("unknown beat result or missing decision ID")
        if type(self.published_message_ids) is not tuple or any(
            not isinstance(x, str) or not x for x in self.published_message_ids
        ) or len(set(self.published_message_ids)) != len(self.published_message_ids):
            raise ValueError("published message IDs must be unique nonempty strings")
        if self.selected_speaker is not None and (
            not isinstance(self.selected_speaker, str) or not self.selected_speaker.strip()
        ):
            raise ValueError("invalid selected speaker")
        if self.kind == "chosen_silence" and (self.selected_speaker is not None or self.published_message_ids):
            raise ValueError("chosen silence cannot publish speech")
        if self.kind == "spoken" and (self.selected_speaker is None or not self.published_message_ids):
            raise ValueError("spoken requires selected speaker and message")
        if self.kind in UNHEALTHY and self.published_message_ids:
            raise ValueError("failed generation cannot publish autonomous speech")

    @property
    def healthy(self) -> bool:
        return self.kind in HEALTHY


def classify_beat(
    decision_id: str,
    *,
    completed_stages: Mapping[str, bool],
    eligible_speakers: tuple[str, ...],
    selected_speaker: str | None,
    silence_chosen: bool,
    expression_attempted: bool,
    expression_valid: bool | None = None,
    published_message_ids: tuple[str, ...] = (),
    failure: str | None = None,
) -> BeatOutcome:
    """Silence requires positive evidence of choice; a missing model is a fault.

    Eligible means awake/available, not willing to speak. Allen inbound input
    can be committed independently of an autonomous chosen-silence outcome.
    """
    if not isinstance(completed_stages, Mapping) or type(eligible_speakers) is not tuple:
        raise ValueError("stages/eligible speakers must be structured")
    if any(not isinstance(x, str) or not x for x in eligible_speakers):
        raise ValueError("invalid eligible speaker")
    if type(silence_chosen) is not bool or type(expression_attempted) is not bool:
        raise ValueError("explicit boolean decisions required")
    if expression_valid is not None and type(expression_valid) is not bool:
        raise ValueError("expression_valid must be boolean")
    if type(published_message_ids) is not tuple:
        raise ValueError("published IDs must be tuple, not string or list")
    if failure is not None and published_message_ids:
        return BeatOutcome("infrastructure_failure", decision_id, detail="conflicting_failure_and_publication")
    missing = tuple(stage for stage in REQUIRED_STAGES if completed_stages.get(stage) is not True)
    if missing:
        return BeatOutcome("stage_failed", decision_id, detail="incomplete:" + ",".join(missing))
    if failure is not None:
        if failure not in UNHEALTHY:
            raise ValueError("unknown failure code: " + str(failure))
        return BeatOutcome(failure, decision_id, detail=failure)
    if not eligible_speakers:
        return BeatOutcome("invalid_no_eligible_person", decision_id)
    if selected_speaker is None:
        if not silence_chosen or expression_attempted or expression_valid is not None or published_message_ids:
            return BeatOutcome("infrastructure_failure", decision_id, detail="selection_absent_or_conflicted")
        return BeatOutcome("chosen_silence", decision_id)
    if selected_speaker not in eligible_speakers or silence_chosen:
        return BeatOutcome("infrastructure_failure", decision_id, detail="selection_conflict")
    if not expression_attempted:
        return BeatOutcome("generation_failed", decision_id, detail="selected_but_not_attempted")
    if not expression_valid:
        return BeatOutcome("validation_failed", decision_id, detail="selected_output_invalid")
    if not published_message_ids:
        return BeatOutcome("infrastructure_failure", decision_id, detail="validated_but_not_published")
    return BeatOutcome("spoken", decision_id, selected_speaker, published_message_ids)


def advance_health(
    previous: Mapping | None,
    outcome: BeatOutcome,
    now_seconds: int,
    *,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
    fail_window: int = 20,
    fail_alert_count: int = 5,
    fail_alert_ratio: float = 0.5,
    silence_review_streak: int = 50,
    min_transition_gap_seconds: int = 60,
) -> tuple[dict, bool]:
    """Reduce one beat tentatively; durable confirmation is a separate step.

    Any public expression or Allen input must be committed independently of
    heartbeat batching. After a Git failure, pass the returned tentative state
    back on retry WITHOUT calling mark_durable.
    """
    if type(now_seconds) is not int or now_seconds < 0:
        raise ValueError("clock must be nonnegative integer")
    if type(heartbeat_seconds) is not int or not 1 <= heartbeat_seconds < DEFAULT_WATCHDOG_SECONDS:
        raise ValueError("heartbeat cannot be as slow as watchdog")
    if type(fail_window) is not int or type(fail_alert_count) is not int or not 1 <= fail_alert_count <= fail_window:
        raise ValueError("invalid failure alert window")
    if not isinstance(fail_alert_ratio, (int, float)) or not 0 < fail_alert_ratio <= 1:
        raise ValueError("invalid failure ratio")
    if type(min_transition_gap_seconds) is not int or min_transition_gap_seconds < 0:
        raise ValueError("invalid transition gap")
    if type(silence_review_streak) is not int or silence_review_streak < 1:
        raise ValueError("invalid silence review threshold")
    previous = dict(previous or {})
    last_now = previous.get("last_evaluated_at")
    if last_now is not None and now_seconds < int(last_now):
        raise ValueError("clock moved backwards")
    old_window = list(previous.get("recent_outcomes", ()))
    if any(kind not in ALL_OUTCOMES for kind in old_window):
        raise ValueError("corrupt health history")
    window = (old_window + [outcome.kind])[-fail_window:]
    failures = sum(x in UNHEALTHY for x in window)
    degraded = failures >= fail_alert_count and failures / len(window) >= fail_alert_ratio
    last_write = previous.get("last_durable_write_at")
    elapsed = now_seconds - int(last_write) if last_write is not None else None
    due = elapsed is None or elapsed >= heartbeat_seconds
    flip_degraded = degraded != bool(previous.get("last_durable_degraded", False))
    kind_changed = previous.get("last_durable_outcome") != outcome.kind
    significant_transition = kind_changed and (elapsed is None or elapsed >= min_transition_gap_seconds)
    # Failed attempts remain pending for a future attempt, regardless of gap.
    persist = bool(
        previous.get("pending_durable", False) or due or flip_degraded
        or significant_transition or outcome.kind == "spoken"
    )
    silence_streak = (
        int(previous.get("silence_streak", 0)) + 1
        if outcome.kind == "chosen_silence" else 0
    )
    state = dict(previous)
    state.update({
        "version": 2,
        "last_evaluated_at": now_seconds,
        "last_healthy_beat_at": (
            now_seconds if outcome.healthy else previous.get("last_healthy_beat_at")
        ),
        "last_public_message_at": (
            now_seconds if outcome.kind == "spoken" else previous.get("last_public_message_at")
        ),
        "last_outcome": outcome.kind,
        "last_outcome_healthy": outcome.healthy,
        "recent_outcomes": window,
        "failure_count_window": failures,
        "consecutive_failures": (
            0 if outcome.healthy else int(previous.get("consecutive_failures", 0)) + 1
        ),
        "degraded": degraded,
        "silence_streak": silence_streak,
        "silence_review": silence_streak >= silence_review_streak,
        "pending_durable": persist,
    })
    return state, persist


def mark_durable(state: Mapping, committed_at_seconds: int) -> dict:
    """Call only AFTER an authoritative full Git push is confirmed."""
    if type(committed_at_seconds) is not int or committed_at_seconds < 0:
        raise ValueError("invalid durable confirmation time")
    if state.get("pending_durable") is not True:
        raise ValueError("no pending durable publication")
    if committed_at_seconds < int(state.get("last_evaluated_at", committed_at_seconds)):
        raise ValueError("commit confirmation precedes decision")
    out = dict(state)
    out["pending_durable"] = False
    out["last_durable_write_at"] = committed_at_seconds
    out["last_durable_outcome"] = state["last_outcome"]
    out["last_durable_degraded"] = bool(state["degraded"])
    if state["last_outcome_healthy"]:
        out["last_durable_healthy_at"] = committed_at_seconds
    else:
        out["last_durable_failure_at"] = committed_at_seconds
    return out


def watchdog_status(
    state: Mapping,
    now_seconds: int,
    *,
    stale_after: int = DEFAULT_WATCHDOG_SECONDS,
    consecutive_failure_alert: int = 3,
) -> str:
    """An unsuccessful expression cannot refresh healthy liveness."""
    if type(now_seconds) is not int or now_seconds < 0:
        raise ValueError("invalid watchdog time")
    if (
        bool(state.get("degraded", False))
        or state.get("last_outcome_healthy") is False
        or int(state.get("consecutive_failures", 0)) >= consecutive_failure_alert
    ):
        return "unhealthy"
    last = state.get("last_durable_healthy_at")
    if last is None or now_seconds < int(last):
        return "unknown"
    return "stale" if now_seconds - int(last) >= stale_after else "healthy"
