#!/usr/bin/env python3
import unittest
import json
import sys
import types
from unittest.mock import patch
import room_life
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

    def test_colliding_event_id_cannot_certify_completion(self):
        # Even a different decision/actor using the same world ID invalidates
        # the evidence; one matching row must not mask a contradictory row.
        conflicting = dict(self.event, actor="owen", source_decision_id="other")
        self.assertIsNone(self.receipt([self.event, conflicting]))
        self.assertIsNone(self.receipt([conflicting, self.event]))
        self.assertIsNotNone(self.receipt([self.event, dict(conflicting, id="other")]))

    def test_missing_or_unknown_visibility_cannot_certify_completion(self):
        for visibility in (None, "", "unknown", "PRIVATE"):
            event = dict(self.event)
            if visibility is None:
                event.pop("visibility")
            else:
                event["visibility"] = visibility
            with self.subTest(visibility=visibility):
                self.assertIsNone(self.receipt([event]))

    def test_private_receipt_requires_witness_list(self):
        for witnesses in (None, "mara", {"mara": True}, 12):
            event = dict(self.event, visibility="private", witnesses=witnesses)
            with self.subTest(witnesses=witnesses):
                self.assertIsNone(self.receipt([event]))

    def test_private_receipt_stays_private(self):
        event = dict(self.event, visibility="private", witnesses=["mara", "owen"])
        receipt = self.receipt([event])
        self.assertTrue(witnessed_receipt(receipt, event, "owen"))
        self.assertFalse(witnessed_receipt(receipt, event, "sarah"))
        self.assertFalse(witnessed_receipt(receipt, dict(event, id="other"), "owen"))

    @staticmethod
    def _deterministic_parser():
        # Exercise room_life's actual referee transitions without installing
        # or invoking the production Concordia engine.
        root = types.ModuleType("concordia")
        root.__path__ = []
        components = types.ModuleType("concordia.components")
        components.__path__ = []
        gm = types.ModuleType("concordia.components.game_master")
        gm.__path__ = []
        gm.interrupt_response_parsing = types.SimpleNamespace(
            extract_json_block=lambda raw: ("", json.loads(raw)))
        return patch.dict(sys.modules, {
            "concordia": root, "concordia.components": components,
            "concordia.components.game_master": gm,
        })

    def test_referee_issued_work_start_proves_later_completion(self):
        config = {"p": {}}
        world = room_life.initial(config, 10)
        instruction = json.dumps({"mask": [], "timer": {},
                                  "work": {"verb": "inspect", "object": "plant"}})
        steps = [{"actions": {"Owen": instruction}}]
        with self._deterministic_parser():
            room_life.advance(world, config, 10, steps)
            started = [e for e in world["events"] if e["kind"] == "work_started"]
            self.assertEqual(len(started), 1)
            source_id = started[0]["id"]
            self.assertIsNone(verify_work_receipt(
                "owen", source_id, "inspect", "plant", 10, world["events"]))
            self.assertEqual(world["lives"]["owen"]["task"]["source_decision_id"],
                             source_id)
            room_life.advance(world, config, 11, [])
            self.assertIsNone(verify_work_receipt(
                "owen", source_id, "inspect", "plant", 10, world["events"]))
            room_life.advance(world, config, 12, [])
            finished = [e for e in world["events"] if e["kind"] == "work_completed"]
            self.assertEqual(len(finished), 1)
            self.assertEqual(finished[0]["source_decision_id"], source_id)
            self.assertEqual((finished[0]["verb"], finished[0]["object"]),
                             ("inspect", "plant"))
            receipt = verify_work_receipt(
                "owen", source_id, "inspect", "plant", 10, world["events"])
            self.assertEqual(receipt["event_id"], finished[0]["id"])
            self.assertTrue(witnessed_receipt(receipt, finished[0], "mara"))
            # The consequence is independently retrievable by a different
            # character as witnessed evidence, not a fabricated utterance.
            mara_memories = room_life.retrieve(world, "mara", "plant", limit=4)
            self.assertIn(finished[0]["id"], [m["id"] for m in mara_memories])
            self.assertIn(finished[0]["id"], room_life.context(world, "mara"))
            room_life.advance(world, config, 12, steps)  # Replayed commit.
            self.assertEqual(len([e for e in world["events"]
                                  if e["kind"] == "work_completed"]), 1)

    def test_legacy_task_completion_without_start_receipt_stays_unverified(self):
        config = {"p": {}}
        world = room_life.initial(config, 10)
        world["lives"]["owen"]["task"] = {
            "verb": "inspect", "object": "plant", "duration": 2,
            "progress": 1, "started_cycle": 9,
        }
        with self._deterministic_parser():
            room_life.advance(world, config, 10, [])
        self.assertEqual(len(world["events"]), 1)
        self.assertEqual(world["events"][0]["kind"], "work_completed")
        self.assertNotIn("source_decision_id", world["events"][0])
        self.assertIsNone(verify_work_receipt(
            "owen", "legacy-unknown", "inspect", "plant", 9, world["events"]))

    def test_invalid_requests_fail(self):
        with self.assertRaises(ValueError):
            verify_work_receipt("mara", "d-10", "write", "plant", 10, [])
        with self.assertRaises(ValueError):
            verify_work_receipt("unknown", "d-10", "inspect", "plant", 10, [])
        with self.assertRaises(ValueError):
            verify_work_receipt("mara", "d-10", "inspect", "plant", True, [])


if __name__ == "__main__":
    unittest.main()
