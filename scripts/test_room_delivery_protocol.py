#!/usr/bin/env python3
"""Failing examples from a real adversarial review, now executable offline."""
from __future__ import annotations

import unittest

from room_delivery_protocol import (
    DurableBeat, PublicEvent, decision_id, durable_inbound_ack_ids,
    mirror_backlog, mirror_result_confirmed, participant_queue_slice,
    reconcile_git_race, recovery_pages,
)


def inbound(i):
    return PublicEvent(
        f"allen-visible-{i}", "allen", f"Question {i}?", "inbound", f"allen-queue-{i}",
    )


def beat(n, events, pushed=True, parent="published-parent-v1"):
    return DurableBeat(
        decision_id(parent, n, speaker=None, action="observe_input",
                    source_ids=tuple(e.source_id for e in events)),
        parent, n, tuple(events),
        git_commit=f"published-commit-{n}" if pushed else None,
    )


def verified(beats):
    return {b.git_commit for b in beats if b.git_commit}


def pending(beats, already=()):
    return mirror_backlog(beats, already, verified_main_commits=verified(beats))


class DeliveryProtocolTests(unittest.TestCase):
    def test_canonical_decision_ids_reject_poisoned_sources(self):
        a = decision_id("canonical-parent", 10, speaker="mara",
                        action="answer", source_ids=("q1", "q2"))
        b = decision_id("canonical-parent", 10, speaker="mara",
                        action="answer", source_ids=("q2", "q1"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, decision_id("different-parent", 10, speaker="mara",
                                          action="answer", source_ids=("q1", "q2")))
        self.assertNotEqual(
            decision_id("parent", 1, speaker=None, action="wait"),
            decision_id("parent", 1, speaker="mara", action="wait"),
        )
        for ids in ("q12", ("q1", "q1")):
            with self.assertRaises(ValueError):
                decision_id("parent", 1, speaker="mara", action="answer", source_ids=ids)
        with self.assertRaises(ValueError):
            decision_id("parent", True, speaker="mara", action="answer")

    def test_rebase_does_not_confuse_processed_input_with_published_reply(self):
        self.assertEqual(
            reconcile_git_race("room-a", "room-a", prepared_decision_id="D"),
            "retry_same_decision",
        )
        self.assertEqual(
            reconcile_git_race("room-a", "room-b", prepared_decision_id="D"),
            "discard_unpushed_and_replan",
        )
        self.assertEqual(
            reconcile_git_race("room-a", "room-b", prepared_decision_id="D",
                               upstream_decision_ids=("D",)),
            "already_published",
        )
        self.assertEqual(
            reconcile_git_race("room-a", "room-a", prepared_decision_id="D",
                               prepared_inbound_ids=("allen-1",),
                               upstream_processed_ids=("allen-1",)),
            "discard_unpushed_and_replan",
        )

    def test_unpushed_or_unverified_draft_cannot_reach_mirror(self):
        draft = beat(1, (inbound(0),), pushed=False)
        self.assertEqual(pending((draft,)), ())
        published = beat(1, (inbound(0),))
        self.assertEqual(pending((published,)), (inbound(0),))
        with self.assertRaisesRegex(ValueError, "not independently verified"):
            mirror_backlog((published,), (), verified_main_commits=())

    def test_crash_after_push_replays_same_bytes_not_regenerated(self):
        stored = beat(1, (
            inbound(1),
            PublicEvent("sarah-1", "sarah", "Trees? You mean that oak?", "autonomous", "q1"),
        ))
        self.assertEqual(pending((stored,)), stored.events)
        self.assertEqual(pending((stored,), ("allen-visible-1",)), (stored.events[1],))

    def test_duplicate_and_forked_generations_rejected(self):
        same = beat(1, (inbound(1),))
        self.assertEqual(pending((same, same)), (inbound(1),))
        with self.assertRaisesRegex(ValueError, "generation collision"):
            pending((same, beat(1, (inbound(2),))))
        reused_id = DurableBeat(
            same.decision_id, same.parent_room_digest, 2, (inbound(2),),
            git_commit="published-commit-2",
        )
        with self.assertRaisesRegex(ValueError, "decision ID published"):
            pending((same, reused_id))

    def test_same_event_id_new_bytes_and_same_source_new_id_are_rejected(self):
        one = beat(1, (inbound(1),))
        changed = beat(2, (
            PublicEvent("allen-visible-1", "allen", "changed", "inbound", "allen-queue-1"),
        ))
        with self.assertRaisesRegex(ValueError, "same event ID"):
            pending((one, changed))
        second_id = beat(2, (
            PublicEvent("different-public-id", "allen", "Question 1?", "inbound", "allen-queue-1"),
        ))
        with self.assertRaisesRegex(ValueError, "source published"):
            pending((one, second_id))

    def test_worker_stale_http_200_requires_independent_matching_bytes(self):
        expected = {"allen-visible-1": "sha-aaa", "sarah-1": "sha-bbb"}
        self.assertTrue(mirror_result_confirmed(
            202, {"accepted": True}, expected_event_digests=expected,
            verified_visible_event_digests=dict(expected)))
        self.assertFalse(mirror_result_confirmed(
            202, {"accepted": True}, expected_event_digests=expected))
        self.assertFalse(mirror_result_confirmed(
            200, {"accepted": False}, expected_event_digests=expected,
            verified_visible_event_digests={"allen-visible-1": "sha-wrong", "sarah-1": "sha-bbb"}))
        self.assertTrue(mirror_result_confirmed(
            200, {"accepted": False}, expected_event_digests=expected,
            verified_visible_event_digests=dict(expected)))
        self.assertFalse(mirror_result_confirmed(
            202, None, expected_event_digests=expected,
            verified_visible_event_digests=dict(expected)))
        self.assertFalse(mirror_result_confirmed(
            500, {"accepted": True}, expected_event_digests=expected,
            verified_visible_event_digests=dict(expected)))

    def test_queue_ack_cannot_be_derived_from_an_autonomous_reply_reference(self):
        reply = beat(1, (
            PublicEvent("sarah-1", "sarah", "Yes, I saw it.", "autonomous", "allen-queue-1"),
        ))
        self.assertEqual(durable_inbound_ack_ids(
            ("allen-queue-1",), (reply,), verified_main_commits=verified((reply,))), ())

    def test_actual_worker_20_of_50_queue_drains_when_relay_offline(self):
        queue = [{"id": f"allen-queue-{i}"} for i in range(50)]
        stored, window_sizes = [], []
        while queue:
            first20 = participant_queue_slice(queue)
            window_sizes.append(len(first20))
            events = [inbound(int(id.rsplit("-", 1)[-1])) for id in first20]
            stored.append(beat(len(stored) + 1, events))
            git_ack = durable_inbound_ack_ids(
                first20, stored, verified_main_commits=verified(stored))
            self.assertEqual(first20, git_ack)
            queue = [m for m in queue if m["id"] not in set(git_ack)]
        self.assertEqual(window_sizes, [20, 20, 10])
        self.assertEqual(len(pending(stored)), 50)
        self.assertEqual(pending(stored, (e.event_id for e in pending(stored))), ())

    def test_500_event_catch_up_real_paging_procedure(self):
        stored = [beat(i + 1, (inbound(i),)) for i in range(500)]
        pages = recovery_pages(stored, (), verified_main_commits=verified(stored))
        self.assertEqual(len(pages), 10)
        self.assertTrue(all(0 < len(page) <= 50 for page in pages))
        flattened = [event.event_id for page in pages for event in page]
        self.assertEqual(flattened, [inbound(i).event_id for i in range(500)])
        self.assertNotIn(flattened[0], flattened[-160:])
        with self.assertRaises(ValueError):
            recovery_pages(stored, (), verified_main_commits=verified(stored),
                           max_page_size=51)

    def test_malformed_queue_identifiers_fail_closed(self):
        for queue in (({"id": None},), ({"id": "dup"}, {"id": "dup"})):
            with self.assertRaises(ValueError):
                participant_queue_slice(queue)


if __name__ == "__main__":
    unittest.main()
