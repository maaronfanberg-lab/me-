#!/usr/bin/env python3
"""Offline, evidence-bound contract tests for Concordia-inspired Room referee."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import room_concordia_world as world


def turn(cycle, speaker, text, uid=None):
    return {"id": uid or f"published-{cycle}", "beat_id": f"beat-room-{cycle:06}",
            "speaker": speaker, "text": text}


class WorldTests(unittest.TestCase):
    def test_action_is_completable_not_planned_or_imagined(self):
        self.assertEqual(world.witnessed_action("jules", "I open the window."), "open_window")
        self.assertEqual(world.witnessed_action("sarah", "I filled the kettle."), "fill_kettle")
        for text in ("I will open the window.", "I would open the window.",
                     "I open the window if it rains.", "I opened the window yesterday.",
                     "I don't open the window.", "Should I open the window?",
                     "What if I open the window?", "I imagine I open the window."):
            self.assertIsNone(world.witnessed_action("sarah", text), text)
        self.assertIsNone(world.witnessed_action("allen", "I open the window."))
        self.assertIsNone(world.witnessed_action("jules", "We open the window."))

    def test_source_bound_world_state_and_real_constraints(self):
        w = world.initial(9)
        world.update(w, [turn(10,"sarah","I boil the kettle."),
                         turn(11,"mara","I fill the kettle."),
                         turn(12,"owen","I boil the kettle."),
                         turn(13,"jules","I pour a cup of tea.")], 13)
        self.assertEqual(w["objects"]["cups"], 1)
        self.assertEqual(w["objects"]["kettle"], "empty")
        self.assertEqual(w["recent_actions"][0]["changed"], False)
        self.assertEqual(w["recent_actions"][0]["source_id"], "published-10")
        self.assertEqual(w["recent_actions"][-1]["actor"], "jules")

    def test_retrospective_ambient_physics_requires_prior_cause(self):
        w = world.initial(0)
        world.update(w, [turn(1,"sarah","I fill the kettle."),
                         turn(2,"mara","I boil the kettle.")], 2)
        self.assertEqual(w["objects"]["kettle"], "hot")
        turns=[turn(i,"owen",f"The count is {i}.") for i in range(3,8)]
        world.update(w,turns,7)
        self.assertEqual(w["objects"]["kettle"], "warm")

    def test_alien_or_user_words_cannot_move_objects(self):
        w = world.initial(0)
        world.update(w,[turn(1,"allen","I open the window."),
                        turn(2,"outside","I fill the kettle.")],2)
        self.assertEqual(w["objects"]["window"], "closed")
        self.assertEqual(w["objects"]["kettle"], "empty")
        self.assertEqual(w["recent_actions"],[])

    def test_missing_or_duplicate_public_evidence_aborts(self):
        w=world.initial(3)
        for transcript in ([turn(5,"jules","I open the window.")],
                           [turn(4,"jules","I open the window.","same"),
                            turn(5,"jules","I close the window.","same")]):
            with self.assertRaises(ValueError):
                world.update(world.initial(3),transcript,5)
        self.assertEqual(w["objects"]["window"],"closed")

    def test_no_double_apply_with_repeated_sync(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"ROOM_CONCORDIA_WORLD_ENABLE":"1"}):
            root=Path(tmp); (root/"room").mkdir()
            first={"state":{"cycle":100},"conversation":[turn(100,"sarah","I write a page in the notebook.")]}
            a=world.sync(root,first)
            self.assertEqual(a["objects"]["notebook_pages"],1)
            self.assertEqual(world.sync(root,first)["objects"]["notebook_pages"],1)
            more={"state":{"cycle":101},"conversation":first["conversation"]+[turn(101,"mara","I open the window.")]}
            self.assertEqual(world.sync(root,more)["objects"]["window"],"open")
            self.assertEqual(world.sync(root,more)["objects"]["notebook_pages"],1)

    def test_restart_preserves_world_and_no_private_data(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"ROOM_CONCORDIA_WORLD_ENABLE":"1"}):
            root=Path(tmp); (root/"room").mkdir()
            state={"state":{"cycle":19},"conversation":[turn(19,"sarah","I water the plant.")]}
            world.sync(root,state)
            (root/"room"/"state.json").write_text(json.dumps({"cycle":19}))
            cue=world.notice("jules",root)
            self.assertIn("plant soil watered",cue)
            self.assertIn("published-19",cue)
            self.assertNotIn("core_identity",cue)
            self.assertNotIn("Jules:",cue)
            self.assertEqual(world.notice("allen",root),"")

    def test_off_by_default_and_fail_closed_on_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"room").mkdir()
            live={"state":{"cycle":5},"conversation":[turn(5,"sarah","I open the window.")]}
            with patch.dict(os.environ,{"ROOM_CONCORDIA_WORLD_ENABLE":"0"}):
                self.assertIsNone(world.sync(root,live))
                self.assertFalse((root/"room"/world.FILE).exists())
            with patch.dict(os.environ,{"ROOM_CONCORDIA_WORLD_ENABLE":"1"}):
                world.sync(root,live)
                (root/"room"/"state.json").write_text(json.dumps({"cycle":6}))
                self.assertEqual(world.notice("mara",root),"")

    def test_action_claims_outcome_before_world_observes_it(self):
        self.assertTrue(world.premature_result("sarah","I open the window and I see a bird."))
        self.assertFalse(world.premature_result("sarah","I open the window."))
        self.assertFalse(world.premature_result("allen","I open the window and I see a bird."))


    def test_native_chat_prompt_respects_real_visitor_priority(self):
        from room_chat_speech import messages
        payload = {
            "entity": "sarah",
            "profile": {"psychology_v2":{"core_identity":"Independent person.",
                                        "motives":["Explore independent interests."]}},
            "room_presence":{"present":["sarah","mara","owen","jules","allen"]},
            "context":[{"id":"real-13","speaker":"mara",
                        "text":"I have a question about the window."}],
        }
        with patch.dict(os.environ,{"ROOM_CONCORDIA_WORLD_ENABLE":"1"}), \
                patch("room_concordia_world.notice",
                      return_value="A VERIFIED ENVIRONMENT NOTICE.") as observer:
            prompt = messages(payload,"sarah")
            self.assertIn("A VERIFIED ENVIRONMENT NOTICE.",prompt[-1]["content"])
            self.assertEqual(observer.call_count,1)
            payload["context"]=[{"id":"allen-real","speaker":"allen",
                                "text":"Please answer my question."}]
            observer.reset_mock()
            prompt = messages(payload,"sarah")
            self.assertNotIn("A VERIFIED ENVIRONMENT NOTICE.",str(prompt))
            observer.assert_not_called()

    def test_publication_outputs_world_as_distinct_non_speech_channel(self):
        import shutil
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"scripts").mkdir(); (root/"room").mkdir()
            source = Path(__file__).resolve().parent
            for name in ("room_concordia_world.py","build_room_feed.py"):
                shutil.copyfile(source/name,root/"scripts"/name)
            live={"generated_at":"test", "state":{"cycle":42},
                  "minds":{"entities":{}},
                  "conversation":[turn(42,"jules","I open the window.")]}
            (root/"room"/"live.json").write_text(json.dumps(live))
            env={**os.environ,"ROOM_CONCORDIA_WORLD_ENABLE":"1"}
            subprocess.run([sys.executable,str(root/"scripts"/"build_room_feed.py")],
                           check=True,env=env,capture_output=True,text=True)
            feed=json.loads((root/"room"/"feed.json").read_text())
            self.assertEqual(feed["concordia_world"]["objects"]["window"],"open")
            self.assertEqual(feed["concordia_world"]["last_action"]["source_id"],
                             "published-42")
            self.assertEqual(len(feed["conversation"]),1)
            self.assertEqual(feed["conversation"][0]["speaker"],"jules")


    def test_unreadable_world_does_not_kill_independent_room_publication(self):
        import shutil
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"scripts").mkdir(); (root/"room").mkdir()
            source=Path(__file__).resolve().parent
            for name in ("room_concordia_world.py","build_room_feed.py"):
                shutil.copyfile(source/name,root/"scripts"/name)
            (root/"room"/"concordia-world.json").write_text('{"version":999}')
            live={"generated_at":"test", "state":{"cycle":43},
                  "minds":{"entities":{}},
                  "conversation":[turn(43,"sarah","I water the plant.")]}
            (root/"room"/"live.json").write_text(json.dumps(live))
            env={**os.environ,"ROOM_CONCORDIA_WORLD_ENABLE":"1"}
            job=subprocess.run([sys.executable,str(root/"scripts"/"build_room_feed.py")],
                               env=env,capture_output=True,text=True)
            self.assertEqual(job.returncode,0,job.stderr)
            feed=json.loads((root/"room"/"feed.json").read_text())
            self.assertNotIn("concordia_world",feed)
            self.assertEqual(feed["conversation"][0]["speaker"],"sarah")


if __name__ == "__main__":
    unittest.main()
