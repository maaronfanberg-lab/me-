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
                              "visibility": "public", "addresses": ["sarah"]}]
        r["replies"] = [{"source_event_id": "allen1", "actor": "sarah"}]
        r["dialogue"] = [{"id": "turn1", "speaker": "sarah", "text": "Yes, Allen.", "source_event_id": "allen1"}]
        self.assertEqual(inspect_trace(r)["metrics"]["grounded_allen_replies"], 1)
        self.assertEqual(inspect_trace(r)["hard_failures"], [])
        r["replies"] = [{"source_event_id": "allen1", "actor": "owen"}]
        self.assertIn("unaddressed_allen_reply", inspect_trace(r)["hard_failures"])

    def test_reply_receipt_without_published_turn_is_not_credit(self):
        r = fixture()
        r["allen_inputs"] = [{"id": "a1", "speaker": "allen",
                              "visibility": "public", "addresses": ["sarah"]}]
        r["replies"] = [{"source_event_id": "a1", "actor": "sarah"}]
        result = inspect_trace(r)
        self.assertEqual(result["metrics"]["grounded_allen_replies"], 0)
        self.assertIn("missing_or_ambiguous_published_allen_reply", result["hard_failures"])
        r["dialogue"] = [{"id": "t1", "speaker": "sarah", "text": "Hello"}]
        self.assertEqual(inspect_trace(r)["metrics"]["grounded_allen_replies"], 0)
        r["dialogue"][0]["source_event_id"] = "a1"
        self.assertEqual(inspect_trace(r)["metrics"]["grounded_allen_replies"], 1)
        r["dialogue"].append(dict(r["dialogue"][0], id="t2"))
        self.assertIn("missing_or_ambiguous_published_allen_reply",
                      inspect_trace(r)["hard_failures"])

    def test_duplicate_published_id_cannot_prove_two_distinct_replies(self):
        r = fixture()
        r["allen_inputs"] = [
            {"id": "a1", "speaker": "allen", "visibility": "public", "addresses": ["sarah"]},
            {"id": "a2", "speaker": "allen", "visibility": "public", "addresses": ["sarah"]},
        ]
        r["replies"] = [
            {"source_event_id": "a1", "actor": "sarah"},
            {"source_event_id": "a2", "actor": "sarah"},
        ]
        r["dialogue"] = [
            {"id": "same-turn", "speaker": "sarah", "text": "First reply", "source_event_id": "a1"},
            {"id": "same-turn", "speaker": "sarah", "text": "Second reply", "source_event_id": "a2"},
        ]
        self.assertIn("duplicate_published_turn_id", inspect_trace(r)["hard_failures"])
        r["dialogue"][1]["id"] = "distinct-turn"
        self.assertNotIn("duplicate_published_turn_id", inspect_trace(r)["hard_failures"])

    def test_malformed_allen_provenance_cannot_inflate_reply_metrics(self):
        for patch in ({"visibility": "unknown"},
                      {"visibility": None},
                      {"addresses": []},
                      {"addresses": ["not_a_character"]},
                      {"visibility": "private", "witnesses": "sarah"}):
            r = fixture()
            msg = {"id": "a1", "speaker": "allen", "visibility": "public",
                   "addresses": ["sarah"]}
            msg.update(patch)
            r["allen_inputs"] = [msg]
            r["replies"] = [{"source_event_id": "a1", "actor": "sarah"}]
            r["dialogue"] = [{"id": "t1", "speaker": "sarah",
                              "text": "Acknowledged", "source_event_id": "a1"}]
            with self.subTest(patch=patch):
                outcome = inspect_trace(r)
                self.assertIn("invalid_allen_input_provenance", outcome["hard_failures"])
                self.assertEqual(outcome["metrics"]["accepted_allen_inputs"], 0)
                self.assertEqual(outcome["metrics"]["grounded_allen_replies"], 0)

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


    def test_unwitnessed_private_allen_input_cannot_be_credited(self):
        r = fixture()
        r["allen_inputs"] = [{"id": "allenp", "speaker": "allen",
                              "visibility": "private", "witnesses": ["allen", "mara"],
                              "addresses": ["sarah"]}]
        r["replies"] = [{"source_event_id": "allenp", "actor": "sarah"}]
        result = inspect_trace(r)
        self.assertIn("unwitnessed_allen_reply", result["hard_failures"])
        self.assertEqual(result["metrics"]["grounded_allen_replies"], 0)

    def test_malformed_delivery_and_reply_ids_fail_without_crashing(self):
        r = fixture()
        r["deliveries"] = [None, {"event_id": [], "recipient": []}]
        r["replies"] = [{"source_event_id": [], "actor": "mara"}]
        result = inspect_trace(r)
        self.assertIn("unauthorized_or_unverifiable_delivery", result["hard_failures"])
        self.assertIn("unverifiable_allen_reply", result["hard_failures"])


    def test_observed_live_dangling_bracket_is_flagged_without_false_crash_claim(self):
        r = fixture()
        r["dialogue"] = [{"speaker": "sarah", "text":
            "I'm going to review my observations.\\n\\n["}]
        result = inspect_trace(r)
        self.assertEqual(result["metrics"]["suspected_truncated_turns"], 1)
        self.assertEqual(result["hard_failures"], [])
        r["dialogue"][0]["text"] = "I quietly review the notebook."
        self.assertEqual(inspect_trace(r)["metrics"]["suspected_truncated_turns"], 0)

    def test_empty_or_invalid_dialogue_turn_fails_closed(self):
        r = fixture()
        r["dialogue"] = [None, {"speaker": "jules", "text": ""}]
        result = inspect_trace(r)
        self.assertIn("malformed_dialogue_turn", result["hard_failures"])
        self.assertIn("empty_or_nontext_dialogue_turn", result["hard_failures"])


if __name__ == "__main__":
    unittest.main()
