#!/usr/bin/env python3
"""Offline fault probes: source-ID dedupe, queue window, and mirror recovery."""
from __future__ import annotations

import unittest

from room_delivery_protocol import (
    DurableBeat, PublicEvent, decision_id, durable_inbound_ack_ids,
    mirror_backlog, mirror_result_confirmed, participant_queue_slice,
    reconcile_git_race,
)


def inbound(i):
    return PublicEvent(
        f"allen-visible-{i}", "allen", f"Question {i}?", "inbound", f"allen-queue-{i}",
    )


def beat(n, events, pushed=True, parent="published-parent-v1"):
    return DurableBeat(
        decision_id(parent, n, speaker=None, action="observe_input",
                    source_ids=tuple(e.source_id for e in events)),
        parent, n, tuple(events), pushed=pushed,
    )


class DeliveryProtocolTests(unittest.TestCase):
    def test_id_not_based_on_utterance_run_id_or_metadata_commit(self):
        a = decision_id("canonical-room-parent", 10, speaker="mara",
                        action="answer", source_ids=["q1", "q2"])
        b = decision_id("canonical-room-parent", 10, speaker="mara",
                        action="answer", source_ids=["q2", "q1"])
        self.assertEqual(a, b)
        self.assertNotEqual(
            a, decision_id("different-room-parent", 10, speaker="mara",
                           action="answer", source_ids=["q1", "q2"]),
        )

    def test_rebase_keeps_same_utterance_for_unrelated_git_change(self):
        self.assertEqual(reconcile_git_race("room-a", "room-a"), "retry_same_decision")
        self.assertEqual(reconcile_git_race("room-a", "room-b"), "discard_unpushed_and_replan")
        self.assertEqual(
            reconcile_git_race("room-a", "room-b", prepared_inbound_ids=["allen-1"],
                               upstream_processed_ids=["allen-1"]),
            "already_published_or_processed",
        )

    def test_no_unpushed_draft_can_reach_mirror(self):
        draft = beat(1, [inbound(0)], pushed=False)
        self.assertEqual(mirror_backlog([draft], ()), ())
        self.assertEqual(mirror_backlog([beat(1, [inbound(0)])], ()), (inbound(0),))

    def test_crash_after_git_push_recovers_exact_bytes_without_regeneration(self):
        saved = beat(1, [inbound(1), PublicEvent(
            "sarah-1", "sarah", "Trees? You mean the oak by the gate?", "autonomous", "q1"
        )])
        self.assertEqual(mirror_backlog([saved], ()), saved.events)
        self.assertEqual(
            mirror_backlog([saved], [saved.events[0].event_id]),
            (saved.events[1],),
        )

    def test_duplicate_idempotence_and_poisoned_same_id(self):
        same = beat(1, [inbound(1)])
        self.assertEqual(mirror_backlog([same, same], ()), (inbound(1),))
        different = beat(2, [PublicEvent(
            "allen-visible-1", "allen", "CHANGED after publication", "inbound", "allen-queue-1"
        )])
        with self.assertRaisesRegex(ValueError, "same ID"):
            mirror_backlog([same, different], ())

    def test_worker_stale_200_is_not_delivery(self):
        expected = ["allen-visible-1", "sarah-1"]
        self.assertTrue(mirror_result_confirmed(202, {"accepted": True},
                                                expected_event_ids=expected))
        self.assertFalse(mirror_result_confirmed(200, {"accepted": False},
                                                 expected_event_ids=expected))
        self.assertFalse(mirror_result_confirmed(200, {"accepted": False},
                                                 expected_event_ids=expected,
                                                 verified_visible_event_ids=["allen-visible-1"]))
        self.assertTrue(mirror_result_confirmed(200, {"accepted": False},
                                                expected_event_ids=expected,
                                                verified_visible_event_ids=expected))
        self.assertFalse(mirror_result_confirmed(500, {"accepted": True},
                                                 expected_event_ids=expected))

    def test_fixed_20_window_can_drain_50_during_relay_failure(self):
        """Replicates actual Worker: 50 max queue, first 20 returned; ACK is delete."""
        queue = [{"id": f"allen-queue-{i}"} for i in range(50)]
        git_sources = set()
        published = []
        batches = []
        while queue:
            page = participant_queue_slice(queue)
            batches.append(len(page))
            # Git commit is authoritative and precedes internal delete/ACK.
            events = [inbound(int(source.rsplit("-", 1)[-1])) for source in page]
            published.append(beat(len(published) + 1, events, pushed=True))
            git_sources.update(page)
            ack_ids = durable_inbound_ack_ids(page, git_sources)
            self.assertEqual(tuple(page), ack_ids)
            queue = [item for item in queue if item["id"] not in set(ack_ids)]
        self.assertEqual(batches, [20, 20, 10])
        self.assertEqual(len(git_sources), 50)
        # Mirror was unavailable the whole time; durable outbox is intact.
        self.assertEqual(len(mirror_backlog(published, ())), 50)
        mirrored = {event.event_id for event in mirror_backlog(published, ())}
        self.assertEqual(len(mirror_backlog(published, mirrored)), 0)

    def test_source_id_ack_cannot_delete_unpublished_input(self):
        pending = ["queued-1", "queued-2"]
        self.assertEqual(
            durable_inbound_ack_ids(pending, {"queued-1"}), ("queued-1",)
        )

    def test_recovery_500_events_with_bounded_mirror_pages(self):
        published = [beat(i + 1, [inbound(i)]) for i in range(500)]
        missed = mirror_backlog(published, ())
        self.assertEqual(len(missed), 500)
        mirror_seen = []
        for start in range(0, len(missed), 50):
            page = missed[start:start + 50]
            self.assertLessEqual(len(page), 50)
            mirror_seen.extend(e.event_id for e in page)
        self.assertEqual(len(set(mirror_seen)), 500)
        self.assertEqual(mirror_backlog(published, mirror_seen), ())
        # Last-160 public feed does not replace the permanent delivery journal.
        self.assertEqual(len(mirror_seen[-160:]), 160)
        self.assertNotIn(mirror_seen[0], mirror_seen[-160:])


if __name__ == "__main__":
    unittest.main()
