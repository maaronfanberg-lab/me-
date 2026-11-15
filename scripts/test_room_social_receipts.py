#!/usr/bin/env python3
import unittest
from room_social_receipts import verify_work_receipt, witnessed_receipt


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.event = {"id": "world-12", "cycle": 12, "actor": "mara",
                      "kind": "work_completed", "source_decision_id": "d-10",
                      "verb": "inspect", "object": "plant", "visibility": "public"}

    def receipt(self, events=None):
        return verify_work_receipt("mara", "d-10", "inspect", "plant", 10,
                                   [self.event] if events is None else events)

    def test_only_matching_trusted_world_event_produces_receipt(self):
        result = self.receipt()
        self.assertEqual(result["event_id"], "world-12")
        self.assertTrue(witnessed_receipt(result, self.event, "jules"))

    def test_unverified_promise_does_not_produce_receipt(self):
        self.assertIsNone(self.receipt([{"id": "claim", "cycle": 12,
                                        "speaker": "mara",
                                        "text": "I finished inspecting the plant."}]))
        self.assertIsNone(self.receipt([]))

    def test_mismatched_cause_actor_object_and_time_fail(self):
        for patch in ({"source_decision_id": "d-9"}, {"actor": "jules"},
                      {"object": "notebook"}, {"cycle": 10},
                      {"kind": "work_started"}, {"id": ""}):
            event = dict(self.event, **patch)
            with self.subTest(patch=patch):
                self.assertIsNone(self.receipt([event]))

    def test_duplicate_receipts_fail_closed(self):
        self.assertIsNone(self.receipt([self.event, dict(self.event)]))

    def test_private_receipt_stays_private(self):
        event = dict(self.event, visibility="private", witnesses=["mara", "owen"])
        receipt = self.receipt([event])
        self.assertTrue(witnessed_receipt(receipt, event, "owen"))
        self.assertFalse(witnessed_receipt(receipt, event, "sarah"))
        self.assertFalse(witnessed_receipt(receipt, dict(event, id="other"), "owen"))

    def test_invalid_requests_fail(self):
        with self.assertRaises(ValueError):
            verify_work_receipt("mara", "d-10", "write", "plant", 10, [])
        with self.assertRaises(ValueError):
            verify_work_receipt("unknown", "d-10", "inspect", "plant", 10, [])
        with self.assertRaises(ValueError):
            verify_work_receipt("mara", "d-10", "inspect", "plant", True, [])


if __name__ == "__main__":
    unittest.main()
