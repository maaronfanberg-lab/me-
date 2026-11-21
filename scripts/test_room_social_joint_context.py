#!/usr/bin/env python3
"""Tests for the non-production evidence-linked social-opportunity compiler."""
import unittest

from room_social_joint_context import joint_context


class SocialJointContextTests(unittest.TestCase):
    def test_named_vocative_is_a_bid_not_ordinary_mention(self):
        events = [
            {"id": "a", "speaker": "mara", "text": "Sarah, why did the plant wilt?"},
            {"id": "b", "speaker": "jules", "text": "Sarah's notebook is on the table."},
        ]
        sarah = joint_context(events, "sarah")
        self.assertEqual([b["source_id"] for b in sarah["open_bids"]], ["a"])
        self.assertEqual(sarah["open_bids"][0]["kind"], "question")
        self.assertEqual(joint_context(events, "owen")["open_bids"], [])

    def test_live_period_vocative_routes_allen_request_to_owen_only(self):
        # An actual live Room input begins "Owen." rather than "Owen,".
        event = {"id": "allen-observed", "speaker": "allen",
                 "text": "Owen. Please read me the 128 written pages"}
        self.assertEqual([x["source_id"] for x in
                          joint_context([event], "owen")["open_bids"]],
                         ["allen-observed"])
        for other in ("sarah", "mara", "jules"):
            self.assertEqual(joint_context([event], other)["open_bids"], [])
        # Ordinary third-person mentions are not directed requests.
        unrelated = {"id": "mention", "speaker": "mara",
                     "text": "Owen's notebook is beside the plant."}
        self.assertEqual(joint_context([unrelated], "owen")["open_bids"], [])

    def test_explicit_addressee_and_no_forced_response(self):
        events = [{"id": "q", "speaker": "owen", "text": "What happened?",
                   "to": "jules"}]
        self.assertEqual(joint_context(events, "jules")["open_bids"][0]["source_id"], "q")
        self.assertEqual(joint_context(events, "sarah")["open_bids"], [])
        self.assertTrue(joint_context(events, "jules")["no_speech_required"])

    def test_allen_public_message_available_without_inventing_answer(self):
        events = [{"id": "allen-1", "speaker": "allen", "text": "Can you see the plant?"}]
        result = joint_context(events, "mara")
        self.assertEqual(result["open_bids"][0]["kind"], "allen_input")
        self.assertFalse("answer" in result)
        self.assertTrue(result["no_speech_required"])

    def test_unwitnessed_private_event_never_enters_context(self):
        events = [
            {"id": "private", "speaker": "jules", "text": "Sarah, private question?",
             "visibility": "private", "witnesses": ["jules", "sarah"]},
        ]
        self.assertEqual([x["source_id"] for x in joint_context(events, "sarah")["open_bids"]],
                         ["private"])
        self.assertEqual(joint_context(events, "mara")["open_bids"], [])

    def test_only_later_visible_linked_reply_resolves_bid(self):
        original = {"id": "q", "speaker": "sarah", "text": "Mara, did you finish?",
                    "visibility": "public"}
        reply = {"id": "r", "speaker": "mara", "text": "Not yet.", "reply_to": "q"}
        self.assertEqual(joint_context([original, reply], "mara")["open_bids"], [])
        self.assertEqual(joint_context([original, reply], "mara")["linked_reply_ids"], ["q"])
        private_reply = dict(reply, visibility="private", witnesses=["mara"])
        self.assertEqual([x["source_id"] for x in
                          joint_context([original, private_reply], "mara")["open_bids"]], ["q"])

    def test_future_or_unlinked_message_is_not_a_reply(self):
        events = [
            {"id": "r", "speaker": "sarah", "text": "I already decided.", "reply_to": "q"},
            {"id": "q", "speaker": "mara", "text": "Sarah, do you agree?"},
            {"id": "other", "speaker": "sarah", "text": "The room is warm."}
        ]
        self.assertEqual(joint_context(events, "sarah")["open_bids"][0]["source_id"], "q")
        self.assertEqual(joint_context(events, "sarah")["linked_reply_ids"], [])

    def test_hidden_duplicate_id_cannot_override_witnessed_metadata(self):
        events = [
            {"id": "same", "speaker": "allen", "text": "Jules, a private question.",
             "to": "jules", "visibility": "private", "witnesses": ["allen", "jules"]},
            {"id": "same", "speaker": "allen", "text": "Sarah, a public question.",
             "to": "sarah", "visibility": "public"},
        ]
        result = joint_context(events, "sarah")
        self.assertEqual([b["source_id"] for b in result["open_bids"]], ["same"])
        self.assertEqual(result["open_bids"][0]["text"], "Sarah, a public question.")


    def test_explicit_unknown_visibility_cannot_retire_public_bid(self):
        # A linked private-looking response with malformed visibility must
        # not count as delivered to the original speaker.
        question = {"id": "q", "speaker": "sarah",
                    "text": "Mara, did you finish?"}
        for bad in ("", "unknown", None):
            reply = {"id": "r", "speaker": "mara", "text": "Yes.",
                     "reply_to": "q", "visibility": bad,
                     "witnesses": ["mara", "sarah"]}
            result = joint_context([question, reply], "mara")
            self.assertEqual([x["source_id"] for x in result["open_bids"]], ["q"])
            self.assertEqual(result["linked_reply_ids"], [])

    def test_legacy_missing_visibility_can_retire_public_bid(self):
        events = [
            {"id": "q", "speaker": "sarah", "text": "Mara, is it ready?"},
            {"id": "r", "speaker": "mara", "text": "Yes.",
             "reply_to": "q"},
        ]
        self.assertEqual(joint_context(events, "mara")["linked_reply_ids"], ["q"])

    def test_limits_empty_and_unknown(self):
        self.assertEqual(joint_context([], "owen")["open_bids"], [])
        self.assertEqual(joint_context([], "owen", limit=0)["open_bids"], [])
        with self.assertRaises(ValueError):
            joint_context([], "stranger")
        with self.assertRaises(ValueError):
            joint_context([], "sarah", limit=100)


if __name__ == "__main__":
    unittest.main()
