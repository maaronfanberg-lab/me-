"""Offline reference for recoverable Git-authored Room events and mirror delivery.

Pure functions only. No GitHub, Cloudflare or model access. A caller must
independently verify current Git ancestry and Worker history before passing
evidence into this module. No live Room behavior is modified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decision_id(
    parent_room_digest: str,
    next_sequence: int,
    *,
    speaker: str | None,
    action: str,
    source_ids: Iterable[str] = (),
) -> str:
    """Stable under irrelevant Git commits; independent of model wording."""
    if (
        not isinstance(parent_room_digest, str) or not parent_room_digest
        or type(next_sequence) is not int or next_sequence < 1
        or not isinstance(action, str) or not action
        or (speaker is not None and (not isinstance(speaker, str) or not speaker))
        or isinstance(source_ids, (str, bytes))
    ):
        raise ValueError("invalid decision identity")
    supplied = tuple(source_ids)
    if any(not isinstance(x, str) or not x for x in supplied) or len(set(supplied)) != len(supplied):
        raise ValueError("source IDs must be unique nonempty strings")
    values = {
        "parent": parent_room_digest, "sequence": next_sequence,
        "speaker": speaker, "action": action,
        "sources": tuple(sorted(supplied)), "schema": 2,
    }
    return hashlib.sha256(_canonical(values)).hexdigest()[:32]


@dataclass(frozen=True)
class PublicEvent:
    event_id: str
    speaker: str
    text: str
    kind: str  # inbound or autonomous
    source_id: str

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip() for x in (
            self.event_id, self.speaker, self.text, self.source_id
        )):
            raise ValueError("public events need stable ID, speaker, text, source")
        if self.kind not in {"inbound", "autonomous"}:
            raise ValueError("unsupported event kind")


@dataclass(frozen=True)
class DurableBeat:
    decision_id: str
    parent_room_digest: str
    generation: int
    events: tuple[PublicEvent, ...]
    git_commit: str | None = None  # None means not durably published

    def __post_init__(self):
        if (
            not isinstance(self.decision_id, str) or not self.decision_id
            or not isinstance(self.parent_room_digest, str) or not self.parent_room_digest
            or type(self.generation) is not int or self.generation < 1
            or type(self.events) is not tuple
        ):
            raise ValueError("invalid durable beat")
        if self.git_commit is not None and (
            not isinstance(self.git_commit, str) or not self.git_commit
        ):
            raise ValueError("invalid Git commit identity")
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("duplicate event ID in beat")


def _git_verified_events(
    beats: Iterable[DurableBeat],
    verified_main_commits: Iterable[str],
) -> tuple[PublicEvent, ...]:
    """Require independent Git proof, and reject forks and source-ID collisions."""
    trusted = set(verified_main_commits)
    by_generation: dict[int, DurableBeat] = {}
    by_decision: dict[str, int] = {}
    seen_ids: dict[str, PublicEvent] = {}
    inbound_sources: dict[str, str] = {}
    result = []
    for beat in beats:
        if beat.git_commit is None:
            continue  # Local draft: never mirrored or ACKed.
        if beat.git_commit not in trusted:
            raise ValueError("published Git commit not independently verified")
        prior_gen = by_generation.get(beat.generation)
        if prior_gen is not None:
            if prior_gen != beat:
                raise ValueError("generation collision")
            continue  # Idempotent replay of exactly the same published beat.
        by_generation[beat.generation] = beat
        prior_decision_gen = by_decision.get(beat.decision_id)
        if prior_decision_gen is not None and prior_decision_gen != beat.generation:
            raise ValueError("decision ID published at two generations")
        by_decision[beat.decision_id] = beat.generation
    for generation in sorted(by_generation):
        beat = by_generation[generation]
        for event in beat.events:
            prior = seen_ids.get(event.event_id)
            if prior is not None:
                if prior != event:
                    raise ValueError("same event ID with different bytes")
                continue
            if event.kind == "inbound":
                prior_source = inbound_sources.get(event.source_id)
                if prior_source is not None and prior_source != event.event_id:
                    raise ValueError("inbound queue source published under two event IDs")
                inbound_sources[event.source_id] = event.event_id
            seen_ids[event.event_id] = event
            result.append(event)
    return tuple(result)


def mirror_backlog(
    published: Iterable[DurableBeat],
    mirrored_event_ids: Iterable[str],
    *,
    verified_main_commits: Iterable[str],
) -> tuple[PublicEvent, ...]:
    """Recover all missing Git-published events without regenerating any text."""
    seen = set(mirrored_event_ids)
    return tuple(
        e for e in _git_verified_events(published, verified_main_commits)
        if e.event_id not in seen
    )


def recovery_pages(
    published: Iterable[DurableBeat],
    mirrored_event_ids: Iterable[str],
    *,
    verified_main_commits: Iterable[str],
    max_page_size: int = 50,
) -> tuple[tuple[PublicEvent, ...], ...]:
    """Build ordered bounded catch-up pages from durable source events."""
    if type(max_page_size) is not int or not 1 <= max_page_size <= 50:
        raise ValueError("page size must be between one and fifty")
    remaining = mirror_backlog(
        published, mirrored_event_ids, verified_main_commits=verified_main_commits
    )
    return tuple(
        remaining[i:i + max_page_size]
        for i in range(0, len(remaining), max_page_size)
    )


def mirror_result_confirmed(
    status: int,
    body: Mapping | None,
    *,
    expected_event_digests: Mapping[str, str],
    verified_visible_event_digests: Mapping[str, str] | None = None,
) -> bool:
    """Require independent Worker event-bytes verification, including on 202.

    The existing Worker latest-feed endpoint does not yet offer durable per-ID
    hashes. Until that Worker extension is implemented, a caller MUST NOT
    claim exact history delivery by passing a fabricated evidence mapping.
    """
    if not isinstance(body, Mapping) or not expected_event_digests:
        return False
    verified = verified_visible_event_digests or {}
    if not all(verified.get(k) == digest for k, digest in expected_event_digests.items()):
        return False
    return (status == 202 and body.get("accepted") is True) or (
        status == 200 and body.get("accepted") is False
    )


def reconcile_git_race(
    prepared_parent_digest: str,
    upstream_parent_digest: str,
    *,
    prepared_decision_id: str,
    upstream_decision_ids: Iterable[str] = (),
    prepared_inbound_ids: Iterable[str] = (),
    upstream_processed_ids: Iterable[str] = (),
) -> str:
    """Separate an already-published reply from its already-consumed question."""
    if not prepared_parent_digest or not upstream_parent_digest or not prepared_decision_id:
        raise ValueError("missing canonical decision or Room parent")
    if prepared_decision_id in set(upstream_decision_ids):
        return "already_published"
    if set(prepared_inbound_ids) & set(upstream_processed_ids):
        return "discard_unpushed_and_replan"
    if prepared_parent_digest == upstream_parent_digest:
        return "retry_same_decision"
    return "discard_unpushed_and_replan"


def participant_queue_slice(pending: Iterable[Mapping], *, max_items: int = 20) -> tuple[str, ...]:
    if type(max_items) is not int or max_items < 1:
        raise ValueError("invalid page size")
    batch = list(pending)[:max_items]
    ids = tuple(item.get("id") for item in batch)
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or repeated queue source ID")
    return ids


def durable_inbound_ack_ids(
    current_pending_ids: Iterable[str],
    git_published_beats: Iterable[DurableBeat],
    *,
    verified_main_commits: Iterable[str],
) -> tuple[str, ...]:
    """Never ACK from a reply's reference to an input; require pushed inbound."""
    events = _git_verified_events(git_published_beats, verified_main_commits)
    pushed_inbound = {e.source_id for e in events if e.kind == "inbound"}
    return tuple(x for x in current_pending_ids if x in pushed_inbound)
