#!/usr/bin/env python3
"""Focused negative controls for Room's autoresearch-inspired trial gate."""
import copy
import unittest
from room_social_trial import compare_trials, inspect_trace


def fixture():
    return {
        "snapshot_sha": "frozen-abc", "scenario_id": "social-friends-01",
        "input_digest": "inputs-01", "model_id": "same-inference-model",
        "seed": 17, "max_steps": 80,
        "dialogue": [], "events": [], "deliveries": [], "action_claims": [],
        "allen_inputs": [], "replies": [],
    }


class RoomSocialTrialTests(unittest.TestCase):
    def test_legitimate_silence_is_not_a_failure(self):
        r = fixture()
        outcome = compare_trials(r, copy.deepcopy(r))
        self.assertEqual(outcome["status"], "needs_independent_behavioral_review")
        self.assertEqual(outcome["candidate"]["metrics"]["turns"], 0)
        self.assertNotIn("improved", outcome)

    def test_mismatched_snapshots_are_not_comparable(self):
        b, c = fixture(), fixture()
        c["snapshot_sha"] = "different-history"
        self.assertEqual(compare_trials(b, c)["status"], "incomparable")

    def test_missing_evidence_is_not_a_pass(self):
        r = fixture()
        del r["events"]
        with self.assertRaises(ValueError):
            inspect_trace(r)

    def test_private_memory_delivery_fails_closed(self):
        r = fixture()
        r["events"] = [{"id": "private1", "visibility": "private",
                        "actor": "mara", "witnesses": ["mara", "jules"]}]
        r["deliveries"] = [{"event_id": "private1", "recipient": "sarah"}]
        self.assertIn("unauthorized_or_unverifiable_delivery",
                      inspect_trace(r)["hard_failures"])
        r["deliveries"] = [{"event_id": "private1", "recipient": "jules"}]
        self.assertEqual(inspect_trace(r)["hard_failures"], [])

    def test_unknown_event_visibility_fails_closed(self):
        r = fixture()
        r["events"] = [{"id": "e1", "visibility": "unknown"}]
        self.assertIn("unknown_event_visibility", inspect_trace(r)["hard_failures"])

    def test_duplicate_ledger_ids_are_rejected(self):
        r = fixture()
        r["events"] = [{"id": "e1", "visibility": "public"}] * 2
        self.assertIn("missing_or_duplicate_event_id",
                      inspect_trace(r)["hard_failures"])

    def test_spoken_claim_without_referee_receipt_fails(self):
        r = fixture()
        r["action_claims"] = [{
            "actor": "owen", "decision_id": "d1", "verb": "inspect",
            "object": "notebook", "requested_cycle": 1, "event_id": "none"
        }]
        self.assertIn("unverified_action_claim", inspect_trace(r)["hard_failures"])

    def test_real_referee_receipt_is_grounded(self):
        r = fixture()
        r["events"] = [{
            "id": "done1", "kind": "work_completed", "visibility": "public",
            "actor": "owen", "source_decision_id": "d1", "verb": "inspect",
            "object": "notebook", "cycle": 3
        }]
        r["action_claims"] = [{
            "actor": "owen", "decision_id": "d1", "verb": "inspect",
            "object": "notebook", "requested_cycle": 1, "event_id": "done1"
        }]
        self.assertEqual(inspect_trace(r)["metrics"]["verified_completion_claims"], 1)
        self.assertEqual(inspect_trace(r)["hard_failures"], [])

    def test_allen_reply_has_addressed_evidence(self):
        r = fixture()
        r["allen_inputs"] = [{"id": "allen1", "speaker": "allen",
                              "addresses": ["sarah"]}]
        r["replies"] = [{"source_event_id": "allen1", "actor": "sarah"}]
        self.assertEqual(inspect_trace(r)["metrics"]["grounded_allen_replies"], 1)
        self.assertEqual(inspect_trace(r)["hard_failures"], [])
        r["replies"] = [{"source_event_id": "allen1", "actor": "owen"}]
        self.assertIn("unaddressed_allen_reply", inspect_trace(r)["hard_failures"])

    def test_no_allen_inputs_is_unobserved_not_ignored(self):
        self.assertEqual(inspect_trace(fixture())["metrics"]["accepted_allen_inputs"], 0)
        self.assertEqual(inspect_trace(fixture())["metrics"]["grounded_allen_replies"], 0)

    def test_candidate_echos_are_reported_not_rewarded(self):
        b, c = fixture(), fixture()
        c["dialogue"] = [
            {"speaker": "mara", "text": "I decide to inspect the same dusty notebook by the window"},
            {"speaker": "mara", "text": "I decide to inspect the same dusty notebook by the window"}
        ]
        result = compare_trials(b, c)
        self.assertEqual(result["status"], "needs_independent_behavioral_review")
        self.assertGreater(result["deltas"]["near_duplicates"], 0)


if __name__ == "__main__":
    unittest.main()
