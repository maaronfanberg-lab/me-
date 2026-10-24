#!/usr/bin/env python3
"""Deterministic fault matrix for the purely in-memory Room transport adapter."""
from __future__ import annotations

import random
import unittest

from room_offline_transport import Crash, FakeWorker, OfflineHarness


def send_n(harness, n):
    for i in range(n):
        status, source_id = harness.worker.enqueue(f"Message {i} about the oak.")
        if status != 202:
            raise AssertionError(f"unexpected queue response {status}")
        if source_id is None:
            raise AssertionError("accepted message missing source ID")


class OfflineTransportTests(unittest.TestCase):
    def test_worker_reproduces_real_50_limit_and_oldest_20(self):
        h = OfflineHarness()
        send_n(h, 50)
        self.assertEqual(len(h.worker.pending()), 20)
        self.assertEqual(h.worker.enqueue("one too many")[0], 429)
        self.assertEqual(h.process_pending(), 20)
        self.assertEqual(len(h.worker.pending()), 20)
        self.assertEqual(h.process_pending(), 20)
        self.assertEqual(h.process_pending(), 10)
        self.assertEqual(len(h.worker.queue), 0)
        self.assertEqual(len(h.git.processed_inputs), 50)

    def test_mirror_outage_does_not_block_first_20_queue_drainage(self):
        h = OfflineHarness()
        h.worker.mirror_down = True
        send_n(h, 50)
        self.assertEqual([h.process_pending() for _ in range(3)], [20, 20, 10])
        self.assertEqual(len(h.worker.queue), 0)
        self.assertEqual(h.deliver_mirror(), 0)
        self.assertEqual(len(h.git.processed_inputs), 50)
        h.worker.mirror_down = False
        self.assertEqual(h.deliver_mirror(), 50)
        self.assertEqual(len(h.worker.history), 50)
        self.assertEqual(h.deliver_mirror(), 0)

    def test_crash_at_each_input_publish_ack_boundary(self):
        for boundary in ("before_push", "after_push", "after_ack"):
            with self.subTest(boundary=boundary):
                h = OfflineHarness()
                status, id0 = h.worker.enqueue("Trees? The same oak tree?")
                self.assertEqual(status, 202)
                with self.assertRaises(Crash):
                    h.process_pending(crash_at=boundary)
                # On restart pending published events are replayed before
                # deciding anything else. Repeating the content is legitimate.
                h.resume()
                h.deliver_mirror()
                self.assertEqual(len(h.worker.queue), 0)
                self.assertEqual(len(h.git.beats), 1)
                self.assertEqual(len(h.worker.history), 1)
                self.assertEqual({e.source_id for e in h.worker.history}, {id0})
                self.assertEqual(h.deliver_mirror(), 0)

    def test_crash_after_mirror_retries_idempotently(self):
        h = OfflineHarness()
        send_n(h, 1)
        h.process_pending()
        with self.assertRaises(Crash):
            h.deliver_mirror(crash_at="after_mirror")
        h.resume()
        self.assertEqual(len(h.worker.history), 1)

    def test_metadata_race_preserves_content_decision(self):
        h = OfflineHarness()
        send_n(h, 1)
        h.process_pending(race="metadata")
        self.assertEqual(h.last_prepared_decision, h.last_pushed_decision)
        self.assertEqual(h.git.metadata_commits, 1)
        self.assertEqual(len(h.git.beats), 1)

    def test_relevant_conversation_race_discards_unpublished_decision(self):
        h = OfflineHarness()
        send_n(h, 1)
        h.process_pending(race="conversation")
        self.assertNotEqual(h.last_prepared_decision, h.last_pushed_decision)
        self.assertEqual(h.abandoned_decisions, [h.last_prepared_decision])
        self.assertEqual(len(h.git.beats), 1)
        h.deliver_mirror()
        self.assertEqual(len(h.worker.history), 1)

    def test_stale_200_is_not_accepted_as_delivery(self):
        h = OfflineHarness()
        send_n(h, 1)
        h.process_pending()
        h.worker.stale_reject = True
        self.assertEqual(h.deliver_mirror(), 0)
        self.assertEqual(len(h.worker.history), 0)
        with self.assertRaises(PermissionError):
            h.worker.resync((), h.git.generation,
                            authorized=False, current_git_head=True)
        with self.assertRaises(PermissionError):
            h.worker.resync((), h.git.generation,
                            authorized=True, current_git_head=False)
        remaining = tuple(e for b in h.git.beats for e in b.events)
        status, payload = h.worker.resync(
            remaining, h.git.generation,
            authorized=True, current_git_head=True,
        )
        self.assertEqual(status, 202)
        self.assertTrue(payload["accepted"])
        self.assertEqual(h.deliver_mirror(), 0)
        self.assertEqual(len(h.worker.history), 1)

    def test_500_event_backfill_beyond_latest_160_window(self):
        h = OfflineHarness()
        h.worker.mirror_down = True
        # Enqueue-and-drain enables 500 accepted inputs despite MAX_QUEUE=50.
        for batch in range(10):
            send_n(h, 50)
            for _ in range(3):
                h.process_pending()
        self.assertEqual(len(h.git.processed_inputs), 500)
        self.assertEqual(len(h.worker.history), 0)
        self.assertEqual(len(h.worker.queue), 0)
        h.worker.mirror_down = False
        self.assertEqual(h.deliver_mirror(), 500)
        self.assertEqual(len(h.worker.history), 500)
        self.assertNotIn(h.worker.history[0], h.worker.history[-160:])
        self.assertEqual(h.deliver_mirror(), 0)

    def test_fuzz_crashes_outage_races_and_repeated_speech(self):
        for seed in range(20):
            r = random.Random(seed)
            h = OfflineHarness()
            h.worker.mirror_down = True
            accepted = []
            for i in range(30):
                text = "Trees?" if i % 3 == 0 else "Where did the moths go?"
                status, source_id = h.worker.enqueue(text)
                self.assertEqual(status, 202)
                accepted.append(source_id)
                if r.random() < 0.40:
                    boundary = r.choice(("before_push", "after_push", "after_ack", None))
                    try:
                        h.process_pending(crash_at=boundary)
                    except Crash:
                        pass
            while h.worker.queue:
                h.process_pending()
            h.worker.mirror_down = False
            h.deliver_mirror()
            self.assertEqual(set(accepted), h.git.processed_inputs)
            self.assertEqual(len(h.worker.history), len(accepted))
            self.assertEqual(
                {e.source_id for e in h.worker.history}, set(accepted)
            )
            self.assertEqual(len(h.worker.queue), 0)
            self.assertEqual(h.deliver_mirror(), 0)


if __name__ == "__main__":
    unittest.main()
