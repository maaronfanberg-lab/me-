"""Deterministic in-memory transport harness for the Room.

This is deliberately NOT a production GitHub or Cloudflare client. It models
the real existing Worker's 50-item Allen queue / oldest-20 pending window
and the *proposed* authenticated history/resync extensions. No network, files,
credentials, public speech generation, or hidden prompt access.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from dataclasses import dataclass, field

from room_delivery_protocol import (
    DurableBeat, PublicEvent, decision_id, durable_inbound_ack_ids,
    mirror_backlog, mirror_result_confirmed, recovery_pages,
)


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class Crash(Exception):
    """Injected process loss at a precisely named transaction boundary."""


class GitConflict(Exception):
    """Simulated failed push against a changed canonical Room parent."""


@dataclass
class FakeRemote:
    """Independent simulated main-branch commit membership oracle."""
    main_commits: set[str] = field(default_factory=set)
    head: str | None = None

    def confirm(self, commit_sha: str):
        self.main_commits.add(commit_sha)
        self.head = commit_sha


@dataclass
class FakeGit:
    parent: str = "room-initial-parent"
    generation: int = 0
    beats: list[DurableBeat] = field(default_factory=list)
    processed_inputs: set[str] = field(default_factory=set)
    metadata_commits: int = 0
    remote: FakeRemote = field(default_factory=FakeRemote)

    @property
    def verified_commits(self) -> set[str]:
        # Separate from the local event journal: tampering with that list
        # must not silently grant a fake push authoritative status.
        return set(self.remote.main_commits)

    def bump_metadata(self):
        """A README change is not a Room state change."""
        self.metadata_commits += 1

    def bump_conversation(self):
        self.parent = digest(self.parent + "|external-conversation")

    def publish(self, draft: DurableBeat) -> DurableBeat:
        if draft.parent_room_digest != self.parent:
            raise GitConflict("relevant Room parent changed")
        if draft.git_commit is not None:
            raise ValueError("draft was already pushed")
        incoming = {e.source_id for e in draft.events if e.kind == "inbound"}
        if incoming & self.processed_inputs:
            raise GitConflict("inbound queue sources were already consumed upstream")
        committed = replace(
            draft, generation=self.generation + 1,
            git_commit=f"verified-main-commit-{self.generation + 1}",
        )
        self.remote.confirm(committed.git_commit)
        self.beats.append(committed)
        self.generation += 1
        self.parent = digest(self.parent + "|" + committed.decision_id)
        self.processed_inputs.update(
            event.source_id for event in committed.events if event.kind == "inbound"
        )
        return committed


@dataclass
class FakeWorker:
    max_queue: int = 50
    pending_page_size: int = 20
    next_id: int = 0
    queue: list[dict] = field(default_factory=list)
    mirror_down: bool = False
    stale_reject: bool = False
    history: list[PublicEvent] = field(default_factory=list)
    visible_digests: dict[str, str] = field(default_factory=dict)
    latest_generation: int = 0

    def enqueue(self, text: str) -> tuple[int, str | None]:
        if len(self.queue) >= self.max_queue:
            return 429, None
        if not isinstance(text, str) or not text.strip():
            return 400, None
        key = f"allen-queue-{self.next_id}"
        self.next_id += 1
        self.queue.append({"id": key, "text": text})
        return 202, key

    def pending(self) -> tuple[dict, ...]:
        return tuple(self.queue[:self.pending_page_size])

    def ack(self, ids) -> int:
        ids = set(ids)
        before = len(self.queue)
        self.queue = [item for item in self.queue if item["id"] not in ids]
        return before - len(self.queue)

    @staticmethod
    def event_checksum(event: PublicEvent) -> str:
        return digest(event.text + "|" + event.speaker + "|" + event.source_id)

    def ingest(self, events: tuple[PublicEvent, ...], generation: int) -> tuple[int, dict]:
        if self.mirror_down:
            return 500, {"error": "mirror-unreachable"}
        if self.stale_reject or generation < self.latest_generation:
            return 200, {"accepted": False, "reason": "stale-feed"}
        # Preflight the WHOLE batch before mutating the Durable Object.
        # A poisoned last event cannot leave the first ones half committed.
        checksums = []
        for event in events:
            checksum = self.event_checksum(event)
            existing = self.visible_digests.get(event.event_id)
            if existing is not None and existing != checksum:
                raise ValueError("mirror has changed bytes for same event")
            checksums.append((event, checksum))
        for event, checksum in checksums:
            if event.event_id not in self.visible_digests:
                self.visible_digests[event.event_id] = checksum
                self.history.append(event)
        self.latest_generation = generation
        return 202, {"accepted": True}

    def resync(self, events, generation: int, *, authorized: bool, current_git_head: bool):
        """Hypothetical authenticated authoritative replace, NOT real Worker API.

        This accepts fake Boolean proof only in the offline harness. Real
        implementation MUST validate main-head OIDC and an event manifest.
        """
        if not authorized or not current_git_head:
            raise PermissionError("invalid authenticated Git-authoritative resync")
        if self.mirror_down:
            raise ConnectionError("mirror-unreachable")
        candidate = tuple(events)
        checksums = {}
        for event in candidate:
            checksum = self.event_checksum(event)
            if event.event_id in checksums and checksums[event.event_id] != checksum:
                raise ValueError("conflicting authoritative event ID")
            checksums[event.event_id] = checksum
        # Explicitly reconcile phantom/stale mirror history against full Git
        # history, unlike the ordinary append-only ingestion path.
        self.visible_digests = checksums
        self.history = list(candidate)
        self.latest_generation = generation
        self.stale_reject = False
        return 202, {"accepted": True}


@dataclass
class OfflineHarness:
    git: FakeGit = field(default_factory=FakeGit)
    worker: FakeWorker = field(default_factory=FakeWorker)
    abandoned_decisions: list[str] = field(default_factory=list)
    last_prepared_decision: str | None = None
    last_pushed_decision: str | None = None

    @staticmethod
    def input_event(item: dict) -> PublicEvent:
        source_id = item["id"]
        return PublicEvent(
            "public-" + digest(source_id)[:20],
            "allen",
            item["text"],
            "inbound",
            source_id,
        )

    def process_pending(self, *, crash_at: str | None = None,
                        race: str | None = None) -> int:
        """Push first20; never ACK content that differs from a published source.

        A prior Git push is recovered without a second public message. A
        competing writer that already consumed the input wins the race.
        """
        selected = self.worker.pending()
        if not selected:
            return 0
        published_sources = {
            e.source_id: e
            for b in self.git.beats
            if b.git_commit in self.git.verified_commits
            for e in b.events if e.kind == "inbound"
        }
        for item in selected:
            previous = published_sources.get(item["id"])
            if previous is not None and previous.text != item["text"]:
                raise ValueError("queue source ID reused with different content")
        published = durable_inbound_ack_ids(
            (item["id"] for item in selected),
            self.git.beats,
            verified_main_commits=self.git.verified_commits,
        )
        if published:
            self.worker.ack(published)
        new_items = [item for item in selected if item["id"] not in set(published)]
        if not new_items:
            return len(published)
        events = tuple(self.input_event(item) for item in new_items)
        original_parent = self.git.parent
        candidate_id = decision_id(
            original_parent, self.git.generation + 1, speaker=None,
            action="observe_input", source_ids=(event.source_id for event in events),
        )
        self.last_prepared_decision = candidate_id
        draft = DurableBeat(
            candidate_id, original_parent, self.git.generation + 1, events,
        )
        if crash_at == "before_push":
            raise Crash("before_push")
        if race == "metadata":
            self.git.bump_metadata()
        elif race == "conversation":
            self.git.bump_conversation()
        elif race == "competing_same_input":
            # Another worker publishes the exact selected input first.
            self.git.publish(draft)
        elif race is not None:
            raise ValueError("unknown Git race")
        try:
            pushed = self.git.publish(draft)
        except GitConflict:
            self.abandoned_decisions.append(candidate_id)
            already = {e.source_id: e for b in self.git.beats
                       for e in b.events if e.kind == "inbound"}
            committed_elsewhere = []
            for event in events:
                prior = already.get(event.source_id)
                if prior is not None:
                    if prior.text != event.text:
                        raise ValueError("competing publisher changed inbound source bytes")
                    committed_elsewhere.append(event.source_id)
            if committed_elsewhere:
                self.worker.ack(committed_elsewhere)
            events = tuple(e for e in events if e.source_id not in set(committed_elsewhere))
            if not events:
                self.last_pushed_decision = self.git.beats[-1].decision_id
                return len(published) + len(committed_elsewhere)
            current_parent = self.git.parent
            new_id = decision_id(
                current_parent, self.git.generation + 1, speaker=None,
                action="observe_input", source_ids=(e.source_id for e in events),
            )
            draft = DurableBeat(new_id, current_parent, self.git.generation + 1, events)
            pushed = self.git.publish(draft)
        self.last_pushed_decision = pushed.decision_id
        if crash_at == "after_push":
            raise Crash("after_push")
        self.worker.ack(tuple(event.source_id for event in events))
        if crash_at == "after_ack":
            raise Crash("after_ack")
        return len(events) + len(published)


    def deliver_mirror(self, *, crash_at: str | None = None,
                       page_size: int = 50) -> int:
        """Audit mirror bytes, then replay only canonical Git-published events."""
        authoritative = mirror_backlog(
            self.git.beats, (), verified_main_commits=self.git.verified_commits
        )
        expected = {e.event_id: self.worker.event_checksum(e) for e in authoritative}
        for event_id, mirror_digest in self.worker.visible_digests.items():
            if event_id not in expected:
                raise ValueError("mirror contains phantom event not in Git")
            if expected[event_id] != mirror_digest:
                raise ValueError("mirror has same ID with different content")
        pages = recovery_pages(
            self.git.beats, self.worker.visible_digests,
            verified_main_commits=self.git.verified_commits,
            max_page_size=page_size,
        )
        count = 0
        for page in pages:
            code, body = self.worker.ingest(page, self.git.generation)
            page_digests = {e.event_id: self.worker.event_checksum(e) for e in page}
            if not mirror_result_confirmed(
                code, body, expected_event_digests=page_digests,
                verified_visible_event_digests=self.worker.visible_digests,
            ):
                return count
            count += len(page)
            if crash_at == "after_mirror":
                raise Crash("after_mirror")
        return count

    def resume(self) -> tuple[int, int]:
        """Replay pending mirror before starting the next user-input batch."""
        mirrored = self.deliver_mirror()
        processed = self.process_pending()
        return mirrored, processed
