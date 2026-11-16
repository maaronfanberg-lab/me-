"""Negative and causal-selection controls for the non-publishing policy."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from room_social_policy import choose_opportunity


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.task = {"task": {"status": "active", "verb": "write",
                              "object": "board", "decision_id": "d1"}}

    def test_direct_witnessed_allen_request_preempts_without_erasing_task(self):
        before = repr(self.task)
        result = choose_opportunity("sarah", self.task, [
            {"kind": "allen_request", "id": "a1", "addresses": ["sarah"],
             "visibility": "public"}])
        self.assertEqual(result["choice"], "reply")
        self.assertEqual(result["source_event_id"], "a1")
        self.assertEqual(repr(self.task), before)

    def test_private_request_not_delivered_to_stranger(self):
        result = choose_opportunity("sarah", self.task, [
            {"kind": "allen_request", "id": "a2", "addresses": ["sarah"],
             "visibility": "private", "witnesses": ["mara"]}])
        self.assertEqual(result["choice"], "continue_work")

    def test_private_witnessed_request(self):
        result = choose_opportunity("sarah", self.task, [
            {"kind": "allen_request", "id": "a3", "addresses": ["sarah"],
             "visibility": "private", "witnesses": ["sarah"]}])
        self.assertEqual(result["choice"], "reply")

    def test_no_request_keeps_existing_work(self):
        self.assertEqual(choose_opportunity("sarah", self.task, [])["decision_id"], "d1")

    def test_unverified_task_is_not_a_completion(self):
        result = choose_opportunity("sarah", self.task, [])
        self.assertEqual(result["choice"], "continue_work")
        self.assertNotIn("completed", result)
        self.assertNotIn("event_id", result)

    def test_invalid_affordance_does_not_generate_action(self):
        result = choose_opportunity("sarah", {"task": {"status": "active",
            "verb": "fly", "object": "window", "decision_id": "d1"}}, [])
        self.assertEqual(result["choice"], "quiet")

    def test_intentional_silence(self):
        self.assertEqual(choose_opportunity("jules", {}, [])["choice"], "quiet")

    def test_missing_allen_provenance_fails_closed(self):
        with self.assertRaises(ValueError):
            choose_opportunity("sarah", {}, [{"kind": "allen_request",
                "addresses": ["sarah"], "visibility": "public"}])

    def test_unknown_actor_fails(self):
        with self.assertRaises(ValueError):
            choose_opportunity("allen", {}, [])


if __name__ == "__main__":
    unittest.main()
