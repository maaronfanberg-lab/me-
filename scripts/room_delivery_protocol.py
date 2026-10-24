"""Pure durable-publication rules for an offline Room / Worker harness.

No GitHub calls, network calls, production writes, or model invocation happen
in this module. The authoritative event journal is deliberately separate from
a mirror's last 160 messages. It is never legal to deliver an unpushed draft.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decision_id(
    parent_room_digest: str, next_sequence: int, *,
    speaker: str | None, action: str, source_ids: Iterable[str] = (),
) -> str:
    """Stable across process run IDs, wording and irrelevant Git commits.

    Caller must supply the digest of the *previous published Room state*;
    including this decision's outputs in the parent would break crash replay.
    """
    ids = tuple(sorted(set(source_ids)))
    if not parent_room_digest or next_sequence < 1 or not action:
        raise ValueError("invalid parent/sequence/action")
    if any(not x for x in ids):
        raise ValueError("empty source ID")
    values = {
        "parent": parent_room_digest,
        "sequence": next_sequence,
        "speaker": speaker or "",
        "action": action,
        "sources": ids,
        "schema": 1,
    }
    return hashlib.sha256(_canonical(values)).hexdigest()[:32]


@dataclass(frozen=True)
class PublicEvent:
    event_id: str
    speaker: str
    text: str
    kind: str  # inbound / autonomous
    source_id: str

    def __post_init__(self):
        if not all((self.event_id, self.speaker, self.text.strip(), self.source_id)):
            raise ValueError("public events need stable IDs, author, text and source")
        if self.kind not in {"inbound", "autonomous"}:
            raise ValueError("unsupported event kind")


@dataclass(frozen=True)
class DurableBeat:
    decision_id: str
    parent_room_digest: str
    generation: int
    events: tuple[PublicEvent, ...]
    pushed: bool = False

    def __post_init__(self):
        if not self.decision_id or not self.parent_room_digest or self.generation < 1:
            raise ValueError("invalid published beat identity")
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("duplicate event ID within a beat")


def mirror_backlog(published: Iterable[DurableBeat], mirrored_event_ids: Iterable[str]) -> tuple[PublicEvent, ...]:
    """Recover **only** pushed source events; never generate alternate text.

    A retry of the same public ID with changed bytes is an integrity error,
    not a reason to pick whichever attempt arrived last.
    """
    seen: dict[str, PublicEvent] = {}
    pending = []
    mirrored = set(mirrored_event_ids)
    previous_gen = -1
    for beat in sorted(published, key=lambda x: x.generation):
        if not beat.pushed:
            continue
        if beat.generation < previous_gen:
            raise ValueError("generation regressed")
        previous_gen = beat.generation
        for event in beat.events:
            prior = seen.get(event.event_id)
            if prior is not None:
                if prior != event:
                    raise ValueError("same ID with different public content")
                continue
            seen[event.event_id] = event
            if event.event_id not in mirrored:
                pending.append(event)
    return tuple(pending)


def mirror_result_confirmed(
    status: int,
    body: Mapping,
    *,
    expected_event_ids: Iterable[str],
    verified_visible_event_ids: Iterable[str] = (),
) -> bool:
    """Never treat a Worker HTTP 200 stale response as successful delivery.

    'verified_visible_event_ids' must be from a separately verified Worker
    source-ID history, not from untrusted request body or a truncated feed.
    """
    required = set(expected_event_ids)
    if not required:
        return False
    if status == 202 and body.get("accepted") is True:
        return True
    if status == 200 and body.get("accepted") is False:
        return required.issubset(set(verified_visible_event_ids))
    return False


def reconcile_git_race(
    prepared_parent_digest: str,
    upstream_parent_digest: str,
    *,
    prepared_inbound_ids: Iterable[str] = (),
    upstream_processed_ids: Iterable[str] = (),
) -> str:
    """Choose a safe recovery action; this function never rebases model text.

    On an irrelevant repository change, the canonical Room parent is
    unchanged and previously staged utterance bytes remain valid.
    """
    required = set(prepared_inbound_ids)
    processed = set(upstream_processed_ids)
    if required and required.issubset(processed):
        return "already_published_or_processed"
    if not prepared_parent_digest or not upstream_parent_digest:
        raise ValueError("missing canonical Room parent")
    if prepared_parent_digest == upstream_parent_digest:
        return "retry_same_decision"
    return "discard_unpushed_and_replan"


def participant_queue_slice(pending: Iterable[Mapping], *, max_items: int = 20) -> tuple[str, ...]:
    """Mirror the current Worker's oldest-20 behavior for offline tests."""
    if max_items < 1:
        raise ValueError("invalid page size")
    return tuple(str(m["id"]) for m in list(pending)[:max_items])


def durable_inbound_ack_ids(
    current_pending_ids: Iterable[str],
    git_published_source_ids: Iterable[str],
) -> tuple[str, ...]:
    """Queue-deletion candidates are precisely those *already* in Git main.

    Viewer delivery is recorded/retried independently, to avoid first-20
    head-of-line blocking while the mirror is unavailable.
    """
    durable = set(git_published_source_ids)
    return tuple(x for x in current_pending_ids if x in durable)
