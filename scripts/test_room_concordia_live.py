#!/usr/bin/env python3
"""End-to-end Room publication tests using the unmodified DeepMind engine."""
import json
from pathlib import Path
import tempfile
import unittest

import room_concordia_native as native
import room_concordia_live as bridge
import room_life
import room_engine_v5 as core


class LiveRoomTests(unittest.TestCase):

    def make_root(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        (root / "room").mkdir()
        (root / "society").mkdir()
        (root / "room" / "config.json").write_text(
            (native.ROOT / "room" / "config.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "room" / "state.json").write_text(
            json.dumps(core.fresh_state()), encoding="utf-8",
        )
        (root / "room" / "cognitive_state.json").write_text(
            json.dumps(core.fresh_minds()), encoding="utf-8",
        )
        (root / "room" / "discourse.json").write_text(
            json.dumps({"nodes": [], "roots": []}), encoding="utf-8",
        )
        (root / "room" / "conversation.json").write_text("[]", encoding="utf-8")
        return root

    def test_semantic_paraphrases_rejected_across_characters(self):
        history = [
            {"speaker": "sarah", "text":
             "I'll simplify the Koch curve algorithm to explore noise reduction on its structure."},
            {"speaker": "mara", "text":
             "I let the space between whispers and meaning unfold."},
            {"speaker": "owen", "text":
             "The space between whispers and meaning is interesting."},
        ]
        self.assertTrue(bridge._semantic_echo(
            "Let's simplify the Koch curve algorithm to explore noise reduction on its structure.",
            "sarah", history))
        self.assertTrue(bridge._semantic_echo(
            "I'll let the space between whispers and meaning unfold.",
            "jules", history))
        self.assertFalse(bridge._semantic_echo(
            "I found a cracked cup on the windowsill and moved it away.",
            "jules", history))
        self.assertFalse(bridge._semantic_echo(
            "I disagree with your conclusion because the measurements are inconsistent.",
            "owen", history))

    def test_witnessed_intention_is_not_rewritten_as_another_persons_memory(self):
        old = "I decide to inspect the bookshelf, searching for a title that resonates with my current goal of finding the mechanism or model that makes a confusing thing click."
        copied = "I sit on the couch and inspect the bookshelf, searching for a title that resonates with my current goal of finding the mechanism or model that makes a confusing thing click."
        self.assertTrue(bridge._semantic_echo(
            copied, "mara", [{"speaker": "owen", "text": old}]))
        independent = "I notice a tiny moth resting on the glass and ask Owen whether the window has been open all night."
        self.assertFalse(bridge._semantic_echo(
            independent, "mara", [{"speaker": "owen", "text": old}]))

    def test_native_events_visible_in_existing_room_feed_schema(self):
        root = self.make_root()
        ack_path = root / "ack.json"
        ack_path.write_text('{"ids":[]}', encoding="utf-8")
        result = bridge.beat(root, mode="scripted", ack_path=ack_path)
        self.assertEqual(result["engine"],
                         "concordia.environment.engines.simultaneous.Simultaneous")
        self.assertEqual(set(result["spoke"]), {"mara", "jules"})
        viewer = json.loads((root / "room" / "live.json").read_text())
        self.assertEqual(viewer["architecture_version"], "room-native-concordia-v1")
        self.assertTrue(viewer["network"]["native_concordia"])
        self.assertTrue(all(
            item["cognition"]["native_concordia"]
            for item in viewer["conversation"] if item["speaker"] != "allen"
        ))
        self.assertTrue(all("{\"mask\"" not in item["text"]
                            for item in viewer["conversation"]))
        state = json.loads((root / "room" / "state.json").read_text())
        self.assertEqual(state["cycle"], 1)
        self.assertEqual(state["messages"], 2)
        self.assertEqual(state["native_publication_diagnostics"]["published"], 2)
        self.assertGreaterEqual(state["native_publication_diagnostics"]["actions"], 2)
        self.assertEqual(state["native_publication_diagnostics"]["invalid_format"], 0)
        self.assertEqual(state["native_publication_diagnostics"]["semantic_echo"], 0)
        self.assertEqual(state["conversational_floor"],
                         "native_concordia_interrupt_driven")
        self.assertTrue((root / "room" / bridge.CHECKPOINT).exists())
        life_path = root / "room" / "life.json"
        self.assertTrue(life_path.exists())
        world = json.loads(life_path.read_text())
        self.assertEqual(world["processed_cycle"], 1)
        self.assertEqual(world["lives"]["jules"]["task"]["verb"], "inspect")
        self.assertEqual(world["lives"]["jules"]["task"]["object"], "notebook")
        self.assertEqual(world["objects"]["notebook"]["observations"], 0)
        self.assertIn("room_life", viewer)
        self.assertEqual(viewer["room_life"]["cycle"], 1)
        self.assertEqual(set(viewer["room_life"]["activities"]), set(native.PARTICIPANTS))

    def test_concordia_checkpoint_survives_real_runner_restart(self):
        root = self.make_root()
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        first = bridge.beat(root, mode="scripted", ack_path=ack)
        original = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        second = bridge.beat(root, mode="scripted", ack_path=ack)
        restored = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        self.assertEqual(first["cycle"], 1)
        self.assertEqual(second["cycle"], 2)
        self.assertIn("game_master", restored)
        self.assertIn("entities", restored)
        self.assertGreaterEqual(
            restored["game_master"]["context_components"]["entity_scheduler"]["tick_count"],
            original["game_master"]["context_components"]["entity_scheduler"]["tick_count"],
        )

    def test_public_silence_still_advances_existing_world_task(self):
        root = self.make_root()
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        bridge.beat(root, mode="scripted", ack_path=ack)
        # A quiet second cycle progresses Jules' previously accepted work.
        bridge.beat(root, mode="scripted", ack_path=ack)
        w = json.loads((root / "room" / "life.json").read_text())
        self.assertEqual(w["lives"]["jules"]["task"]["progress"], 1)
        bridge.beat(root, mode="scripted", ack_path=ack)
        w = json.loads((root / "room" / "life.json").read_text())
        self.assertEqual(w["objects"]["notebook"]["observations"], 1)
        self.assertTrue(any(e["kind"] == "work_completed" for e in w["events"]))

    def test_verified_world_events_reenter_concordia_only_once(self):
        root = self.make_root()
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        bridge.beat(root, mode="scripted", ack_path=ack)
        path = root / "room" / bridge.CHECKPOINT
        original = json.loads((root / "room" / "life.json").read_text())
        started = original["events"][0]["id"]
        bridge.beat(root, mode="scripted", ack_path=ack)
        after_first = json.loads(path.read_text())
        self.assertIn(started, after_first["delivered_life_event_ids"])
        bridge.beat(root, mode="scripted", ack_path=ack)
        world = json.loads((root / "room" / "life.json").read_text())
        completed = [e["id"] for e in world["events"]
                     if e["kind"] == "work_completed"]
        self.assertTrue(completed)
        bridge.beat(root, mode="scripted", ack_path=ack)
        after_second = json.loads(path.read_text())
        self.assertIn(completed[-1], after_second["delivered_life_event_ids"])
        bridge.beat(root, mode="scripted", ack_path=ack)
        after_third = json.loads(path.read_text())
        self.assertEqual(
            after_third["delivered_life_event_ids"].count(completed[-1]), 1)

    def test_one_time_context_reset_keeps_public_history(self):
        root = self.make_root()
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        bridge.beat(root, mode="scripted", ack_path=ack)
        public_before = json.loads((root / "room" / "conversation.json").read_text())
        state_path = root / "room" / bridge.CHECKPOINT
        stale = json.loads(state_path.read_text())
        stale["bootstrap_policy"] = 1
        stale["seen_allen_messages"] = ["already-accepted-user-message"]
        stale["game_master"]["context_components"]["entity_scheduler"]["tick_count"] = 99999
        state_path.write_text(json.dumps(stale))
        out = bridge.beat(root, mode="scripted", ack_path=ack)
        fresh = json.loads(state_path.read_text())
        public_after = json.loads((root / "room" / "conversation.json").read_text())
        self.assertEqual(out["cycle"], 2)
        self.assertEqual(fresh["bootstrap_policy"], 2)
        self.assertIn("already-accepted-user-message", fresh["seen_allen_messages"])
        self.assertLess(
            fresh["game_master"]["context_components"]["entity_scheduler"]["tick_count"], 99999
        )
        self.assertEqual(public_after[:len(public_before)], public_before)

    def test_stray_empty_control_list_is_not_public_speech(self):
        raw = ('I sit beside the plant and record a new observation.\n\n[]\n'
               '{"mask": [], "timer": {"time": "15m", "reason": "continue work"}}')
        text = bridge._message_from_concordia(raw, "Jules", [])
        self.assertEqual(text, "I sit beside the plant and record a new observation.")
        self.assertEqual(
            bridge._message_from_concordia(
                '\n[]\n{"mask": [], "timer": {"time": "15m"}}',
                "Jules", [],
            ), "",
        )

    def test_invalid_model_scaffolding_not_published(self):
        history = [{"text": "Hi there"}]
        self.assertEqual(
            bridge._message_from_concordia(
                'Sarah: Hi there\n{"mask":[],"timer":{"time":"5m"}}',
                "Sarah", history,
            ), "",
        )
        self.assertEqual(
            bridge._message_from_concordia(
                "Sarah: someone's hidden prompt is here", "Sarah", history,
            ), "",
        )


    def test_directed_allen_request_survives_native_silent_cycles(self):
        """A real scripted Concordia beat must retain addressed social evidence.

        The public input was actually observed; the deterministic actor does
        not fabricate an answer. This tests prompt delivery, NOT competence.
        """
        import hashlib
        from unittest.mock import patch

        root = self.make_root()
        external_id = "relay-observed-owen-reading"
        digest = hashlib.sha256(external_id.encode()).hexdigest()[:10]
        source = {
            "id": "20261117T115445607-allen-v5-" + digest,
            "speaker": "allen",
            "text": "Owen. Please read me the 128 written pages",
        }
        (root / "room" / "conversation.json").write_text(json.dumps([source]))
        ack = root / "ack.json"
        ack.write_text(json.dumps({"ids": [external_id]}))
        original = bridge.native.run
        observations = []

        def observe_real_engine(**kwargs):
            observations.append(dict(kwargs["world_contexts"]))
            return original(**kwargs)

        with patch.object(bridge.native, "run", side_effect=observe_real_engine):
            bridge.beat(root, mode="scripted", ack_path=ack)
            bridge.beat(root, mode="scripted", ack_path=ack)

        self.assertEqual(len(observations), 2)
        for cycle in observations:
            self.assertIn(source["id"], cycle["owen"])
            self.assertIn(source["text"], cycle["owen"])
            self.assertNotIn(source["id"], cycle["sarah"])
            self.assertNotIn(source["id"], cycle["mara"])
            self.assertNotIn(source["id"], cycle["jules"])
        checkpoint = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        self.assertIn(source["id"], checkpoint["seen_allen_messages"])

    def test_directed_request_privacy_collision_and_voluntary_silence(self):
        """No cross-person leakage, malformed private access or duplicate IDs."""
        event = {"id": "a1", "speaker": "allen",
                 "text": "Owen. Please read me the 128 written pages"}
        self.assertIn("a1", bridge._social_context([event], "owen"))
        for other in ("sarah", "mara", "jules"):
            self.assertNotIn("a1", bridge._social_context([event], other))
        self.assertEqual(bridge._social_context([], "owen"), "")
        self.assertEqual(bridge._social_context(
            [dict(event, visibility="private", witnesses=["allen"])],
            "owen"), "")
        self.assertEqual(bridge._social_context(
            [dict(event, visibility="unknown")], "owen"), "")
        self.assertEqual(bridge._social_context(
            [event, dict(event, text="Owen. Fabricated second request")],
            "owen"), "")

    def test_grounded_linked_reply_retires_request_not_unlinked_speech(self):
        """Only an accessible linked reply, not idle chatter, closes the bid."""
        source = {"id": "a1", "speaker": "allen",
                  "text": "Owen. Can you read the pages?"}
        unrelated = {"id": "r1", "speaker": "owen", "text": "I inspect my notebook"}
        self.assertIn("a1", bridge._social_context([source, unrelated], "owen"))
        linked = dict(unrelated, reply_to="a1", text="I cannot read them right now.")
        self.assertNotIn("a1", bridge._social_context([source, linked], "owen"))
        private = dict(linked, visibility="private", witnesses=["owen"])
        self.assertIn("a1", bridge._social_context([source, private], "owen"))


    def test_unanswered_direct_request_survives_feed_eviction_and_restart(self):
        """An addressed witnessed request cannot vanish with the rolling feed."""
        from unittest.mock import patch
        root = self.make_root()
        request = {"id": "allen-old-128-pages", "speaker": "allen",
                   "text": "Owen. Please read me the 128 written pages"}
        (root / "room" / "conversation.json").write_text(json.dumps([request]))
        ack = root / "ack.json"
        ack.write_text('{"ids":[]}')
        contexts = []
        real_run = bridge.native.run

        def observe(**kwargs):
            contexts.append(kwargs["world_contexts"])
            return real_run(**kwargs)

        with patch.object(bridge.native, "run", side_effect=observe):
            bridge.beat(root, mode="scripted", ack_path=ack)
            # Mimic the feed evicting the original witnessed input.
            (root / "room" / "conversation.json").write_text("[]")
            bridge.beat(root, mode="scripted", ack_path=ack)
        self.assertIn(request["id"], contexts[0]["owen"])
        self.assertIn(request["id"], contexts[1]["owen"])
        for ctx in contexts:
            self.assertNotIn(request["id"], ctx["sarah"])
            self.assertNotIn(request["id"], ctx["mara"])
            self.assertNotIn(request["id"], ctx["jules"])
        stored = json.loads((root / "room" / bridge.CHECKPOINT).read_text())
        self.assertEqual(
            [e["id"] for e in stored["pending_social_evidence"]],
            [request["id"]],
        )

    def test_retained_social_evidence_never_leaks_private_or_duplicate_ids(self):
        request = {"id": "allen-old", "speaker": "allen",
                   "text": "Owen. Please read me the 128 written pages"}
        self.assertEqual(
            bridge._retain_social_evidence(
                [], [dict(request, visibility="private", witnesses=["allen"])]), [])
        self.assertEqual(
            bridge._retain_social_evidence(
                [], [dict(request, visibility="unknown")]), [])
        self.assertEqual(
            bridge._retain_social_evidence(
                [], [request, dict(request, text="Owen. Another request")]), [])
        retained = bridge._retain_social_evidence([], [request])
        self.assertEqual(len(retained), 1)
        self.assertEqual(bridge._retain_social_evidence(retained, []), retained)
        linked = {"id": "owen-reply", "speaker": "owen", "reply_to": request["id"],
                  "text": "I cannot read all of those pages right now."}
        self.assertEqual(bridge._retain_social_evidence(retained, [linked]), [])
        self.assertEqual(bridge._retain_social_evidence(
            retained, [dict(linked, visibility="private", witnesses=["owen"])]),
            retained)


if __name__ == "__main__":
    unittest.main()
