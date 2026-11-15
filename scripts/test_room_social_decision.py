#!/usr/bin/env python3
import unittest
from room_social_decision import decide, visible


class SocialDecisionTests(unittest.TestCase):
    def test_respond_to_witnessed_address_only_with_real_proposal(self):
        event = {"id": "u1", "speaker": "allen", "visibility": "public",
                 "addresses": ["sarah"], "text": "Can you help?"}
        self.assertEqual(decide("sarah", [event]).kind, "observe")
        options = [{"kind": "reply", "source_event_id": "u1", "text": "What happened?"}]
        self.assertEqual(decide("sarah", [event], proposals=options).kind, "reply")
        self.assertEqual(decide("sarah", [event], acknowledged=["u1"], proposals=options).kind, "observe")

    def test_private_address_never_leaks(self):
        event = {"id": "p1", "speaker": "allen", "visibility": "private",
                 "witnesses": ["allen", "mara"], "addresses": ["sarah"]}
        proposal = [{"kind": "reply", "source_event_id": "p1", "text": "Hello"}]
        self.assertFalse(visible(event, "sarah"))
        self.assertEqual(decide("sarah", [event], proposals=proposal).kind, "observe")
        self.assertFalse(visible({"id": "bad", "speaker": "mara"}, "sarah"))

    def test_no_forced_speech_and_valid_independent_work(self):
        self.assertEqual(decide("owen", []).kind, "observe")
        invalid = [{"kind": "work", "verb": "write", "object": "plant"}]
        self.assertEqual(decide("owen", [], proposals=invalid).kind, "observe")
        valid = [{"kind": "work", "verb": "measure", "object": "plant"}]
        d = decide("owen", [], proposals=valid)
        self.assertEqual((d.kind, d.verb, d.object), ("work", "measure", "plant"))
        self.assertEqual(decide("owen", [], proposals=valid, active_task={"verb": "test"}).kind, "observe")

    def test_unanswered_address_takes_priority_without_inventing_reply(self):
        event = {"id": "a", "speaker": "jules", "visibility": "public", "addresses": ["mara"]}
        work = [{"kind": "work", "verb": "inspect", "object": "notebook"}]
        self.assertEqual(decide("mara", [event], proposals=work).reason, "awaiting_grounded_reply")

    def test_unknown_participant(self):
        with self.assertRaises(ValueError):
            decide("visitor", [])


if __name__ == "__main__":
    unittest.main()
