#!/usr/bin/env python3
import unittest
from room_social_decision import decide, decide_from_history, visible


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
        result = decide("mara", [event], proposals=work)
        self.assertEqual((result.kind, result.verb, result.object), ("work", "inspect", "notebook"))
        self.assertEqual(decide("mara", [event], proposals=work, active_task={"verb": "measure"}).reason,
                         "continuing_unfinished_task")
        self.assertEqual(decide("mara", [event]).source_event_id, "a")

    def test_malformed_proposals_do_not_crash_or_hide_valid_options(self):
        event = {"id": "u1", "speaker": "allen", "visibility": "public",
                 "addresses": ["sarah"], "text": "Can you help?"}
        reply = {"kind": "reply", "source_event_id": "u1", "text": "Yes."}
        self.assertEqual(decide("sarah", [event], proposals=[None, 4, [], reply]).kind, "reply")
        self.assertEqual(decide("sarah", [event], proposals=[None, 4]).reason,
                         "awaiting_grounded_reply")
        work = {"kind": "work", "verb": "inspect", "object": "notebook"}
        self.assertEqual(decide("owen", [], proposals=[None, 4, work]).kind, "work")
        self.assertEqual(decide("owen", [], proposals=[None, 4]).kind, "observe")

    def test_pending_reply_does_not_discard_unfinished_task(self):
        event = {"id": "allen-urgent", "speaker": "allen", "visibility": "public",
                 "addresses": ["sarah"], "text": "Can you answer?"}
        reply = [{"kind": "reply", "source_event_id": "allen-urgent", "text": "Yes."}]
        task = {"verb": "measure", "object": "plant", "id": "task-1"}
        # A conversation can interrupt attention without destroying work.
        original_task = dict(task)
        interrupted = decide("sarah", [event], proposals=reply, active_task=task)
        self.assertEqual(interrupted.kind, "reply")
        self.assertEqual(interrupted.source_event_id, "allen-urgent")
        self.assertEqual(task, original_task)
        self.assertEqual(decide("sarah", [event], active_task=task).kind, "observe")
        self.assertEqual(decide("sarah", [event], acknowledged=["allen-urgent"],
                                proposals=reply, active_task=task).kind, "observe")
        resumed = decide("sarah", [event], proposals=reply)
        self.assertEqual((resumed.kind, resumed.source_event_id),
                         ("reply", "allen-urgent"))
        self.assertEqual(decide("sarah", [event], acknowledged=["allen-urgent"],
                                proposals=reply).kind, "observe")

    def test_busy_agent_cannot_leak_private_message_or_invent_reply(self):
        task = {"verb": "write", "object": "board", "id": "t"}
        hidden = {"id": "private", "speaker": "allen", "visibility": "private",
                  "witnesses": ["allen", "mara"], "addresses": ["owen"]}
        possible = [{"kind": "reply", "source_event_id": "private", "text": "I heard you."}]
        self.assertEqual(decide("owen", [hidden], proposals=possible,
                                active_task=task).kind, "observe")
        addressed = dict(hidden, visibility="public")
        self.assertEqual(decide("owen", [addressed], active_task=task).kind, "observe")
        self.assertEqual(decide("owen", [addressed], proposals=possible,
                                active_task=task).kind, "reply")
        self.assertEqual(task, {"verb": "write", "object": "board", "id": "t"})

    def test_colliding_event_ids_cannot_authorize_a_reply(self):
        address = {"id": "same", "speaker": "allen", "visibility": "public",
                   "addresses": ["sarah"], "text": "Can you answer?"}
        forged = {"id": "same", "speaker": "mara", "visibility": "private",
                  "witnesses": ["mara"], "addresses": ["sarah"]}
        reply = [{"kind": "reply", "source_event_id": "same", "text": "Yes."}]
        for events in ([address, forged], [forged, address], [address, dict(address)]):
            with self.subTest(events=events):
                self.assertNotEqual(decide("sarah", events, proposals=reply).kind, "reply")
        distinct = dict(forged, id="different")
        self.assertEqual(decide("sarah", [address, distinct], proposals=reply).kind, "reply")

    def test_live_legacy_allen_request_reaches_owen_without_losing_task(self):
        # Recorded wording from the public production feed; no model answer is invented.
        event_id = "20261117T115445607-allen-v5-d05d69466d"
        live = {"id": event_id, "speaker": "allen",
                "text": "Owen. Please read me the 128 written pages"}
        proposal = [{"kind": "reply", "source_event_id": event_id,
                     "text": "I can discuss the recorded pages."}]
        task = {"id": "t", "verb": "measure", "object": "plant"}
        self.assertEqual(decide_from_history("owen", [live]).kind, "observe")
        result = decide_from_history("owen", [live], proposals=proposal, active_task=task)
        self.assertEqual((result.kind, result.source_event_id), ("reply", event_id))
        self.assertEqual(task, {"id": "t", "verb": "measure", "object": "plant"})
        self.assertEqual(decide_from_history("owen", [live],
                         acknowledged=[event_id], proposals=proposal).kind, "observe")
        self.assertEqual(decide_from_history("mara", [live],
                         proposals=proposal).kind, "observe")

    def test_history_bridge_private_duplicate_and_quiet_controls(self):
        event = {"id": "private-bid", "speaker": "mara",
                 "text": "Sarah. Did you check the plant?", "visibility": "private",
                 "witnesses": ["mara", "sarah"]}
        reply = [{"kind": "reply", "source_event_id": "private-bid",
                  "text": "I checked the leaves."}]
        self.assertEqual(decide_from_history("sarah", [event], proposals=reply).kind,
                         "reply")
        self.assertEqual(decide_from_history("owen", [event], proposals=reply).kind,
                         "observe")
        unknown = dict(event, visibility="unknown")
        self.assertEqual(decide_from_history("sarah", [unknown],
                         proposals=reply).kind, "observe")
        # A colliding source cannot be accepted even if one copy is witnessed.
        collision = dict(event, speaker="allen", visibility="public")
        self.assertEqual(decide_from_history("sarah", [event, collision],
                         proposals=reply).kind, "observe")
        self.assertEqual(decide_from_history("jules", []).kind, "observe")

    def test_unknown_participant(self):
        with self.assertRaises(ValueError):
            decide("visitor", [])


if __name__ == "__main__":
    unittest.main()
