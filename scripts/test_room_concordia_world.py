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

    def test_behavior_audit_reports_actions_without_confusing_abstract_talk(self):
        from room_behavior_audit import measure
        sample = {"conversation": [
            turn(1, "sarah", "We are mirroring the labyrinth."),
            turn(2, "mara", "I open the window."),
            turn(3, "owen", "The window is open now."),
            turn(4, "jules", "I wonder about recursive patterns."),
        ]}
        report = measure(sample)
        self.assertEqual(report["turns"], 4)
        self.assertEqual(report["first_person_actions"], 1)
        self.assertEqual(report["action_followups_within_three_turns"], 1)
        self.assertEqual(report["distinct_action_speakers"], 1)
        self.assertEqual(report["abstract_vocabulary_turn_share"], 0.5)

    def test_natural_enacted_tense_not_unfulfilled_promises(self):
        actual = (
            ("sarah", "I'm opening the window.", "open_window"),
            ("mara", "I am turning off the lamp.", "lamp_off"),
            ("owen", "I've filled the kettle.", "fill_kettle"),
            ("jules", "I am watering the plant.", "water_plant"),
        )
        for speaker, text, expected in actual:
            self.assertEqual(world.witnessed_action(speaker, text), expected, text)
        for text in (
            "I'll open the window.", "I will open the window.",
            "I am about to open the window.", "I'm going to open the window.",
            "I might open the window.", "I haven't opened the window.",
            "I would like to open the window.",
        ):
            self.assertIsNone(world.witnessed_action("sarah", text), text)

    def test_repeated_unsupported_interpretation_is_a_stall(self):
        repetitive = [
            "I think Allen's desire for change suggests a deeper internal motive.",
            "Could Allen's desire for change imply a different psychological state?",
            "Let's explore whether his desire for change has a hidden meaning.",
            "Perhaps the desire for change is actually about personal constraints.",
            "That raises the question of whether his desire for change is symbolic.",
            "I think his desire for change might have a deeper interpretation.",
            "Doesn't that imply his desire for change reflects something internal?",
            "This seems to suggest the desire for change is psychological."
        ]
        turns = [turn(i + 1, ["sarah", "mara", "owen", "jules"][i % 4], t)
                 for i, t in enumerate(repetitive)]
        self.assertFalse(world.stalled_observation(turns))
        self.assertTrue(world.stalled_dialogue(turns))
        turns[-1] = turn(8, "allen", "Please answer my question.")
        self.assertFalse(world.stalled_dialogue(turns))

    def test_native_speaker_receives_personal_agency_not_only_analysis(self):
        from room_chat_speech import messages
        payload = {
            "entity": "mara",
            "profile": {"psychology_v2": {
                "core_identity": "Independent and humorous.",
                "motives": [
                    "Observe social dynamics.",
                    "Consider human consequences.",
                    "Use humor and friendly banter.",
                    "Leave stale topics and start something new.",
                    "This fifth motive is intentionally not selected."
                ],
                "agency_style": "Can challenge, joke, change the subject."
            }},
            "context": [{"id": "real-10", "speaker": "jules",
                         "text": "Is that all we have to say?"}]
        }
        prompt = messages(payload, "mara")[0]["content"]
        self.assertIn("Use humor and friendly banter.", prompt)
        self.assertIn("Leave stale topics and start something new.", prompt)
        self.assertIn("Can challenge, joke, change the subject.", prompt)
        self.assertNotIn("intentionally not selected", prompt)

    def test_stalled_dialogue_prompt_unhooks_but_respects_visitor(self):
        from room_chat_speech import messages
        turns = [turn(i + 1, ["sarah", "mara", "owen", "jules"][i % 4],
                      "I think his desire for change might have a deeper meaning "
                      "that could imply an internal psychological desire.")
                 for i in range(8)]
        payload = {
            "entity": "sarah",
            "profile": {"psychology_v2": {
                "core_identity": "Independent person.",
                "motives": ["Explore independent interests."]}},
            "room_presence": {"present": [
                "sarah", "mara", "owen", "jules", "allen"]},
            "context": turns,
        }
        with patch.dict(os.environ, {"ROOM_CONCORDIA_WORLD_ENABLE": "1"}), \
                patch("room_concordia_world.notice", return_value=""):
            out = messages(payload, "sarah")
            self.assertIn("Independently choose", out[-1]["content"])
            self.assertIn("speculate about anyone's unstated motives",
                          out[0]["content"])
            payload["context"] = turns[:-1] + [
                turn(8, "allen", "Please answer my question.")]
            out = messages(payload, "sarah")
            self.assertNotIn("Independently choose", out[-1]["content"])
            self.assertIn("Please answer my question.", out[-1]["content"])

    def test_repeated_observation_detected_without_replacing_allen(self):
        talk = [
            "What if we observe the room again?",
            "I'd like to see how the lamp affects this space.",
            "Let's consider our collective energy in the room.",
            "The light in the room seems subtle, perhaps symbolic.",
            "I wonder what the chair means for our observation.",
            "Could we examine the narrative of the room?",
            "Perhaps the plant's position reflects our collective perception.",
            "Let's observe the atmosphere in the space."
        ]
        history = [turn(i + 1, ["sarah", "mara", "owen", "jules"][i % 4], t)
                   for i, t in enumerate(talk)]
        self.assertTrue(world.stalled_observation(history))
        self.assertFalse(world.stalled_observation(
            history[:-1] + [turn(8, "allen", "What is going on?")]))
        self.assertFalse(world.stalled_observation(
            history[:-1] + [turn(8, "jules", "I'm opening the window.")]))

    def test_world_notice_does_not_reprime_static_room_indefinitely(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {"ROOM_CONCORDIA_WORLD_ENABLE": "1"}):
            root = Path(tmp)
            (root / "room").mkdir()
            w = world.initial(0)
            world.update(w, [turn(1, "sarah", "I open the window.")], 1)
            (root / "room" / world.FILE).write_text(json.dumps(w))
            (root / "room" / "state.json").write_text(json.dumps({"cycle": 1}))
            self.assertIn("Verified outcome", world.notice("jules", root))
            world.update(w, [turn(i, "mara", "That seems worth considering.")
                             for i in range(2, 6)], 5)
            (root / "room" / world.FILE).write_text(json.dumps(w))
            (root / "room" / "state.json").write_text(json.dumps({"cycle": 5}))
            self.assertEqual(world.notice("jules", root), "")

    def test_live_allen_and_sarah_share_a_cycle_without_stalling_world(self):
        # Exact production regression: a visitor speaks on cycle N, the
        # answering character speaks on the same N, and N+1 must still replay.
        w = world.initial(57803)
        live = [turn(57804, "allen", "I open the window.", "allen-57804"),
                turn(57804, "sarah", "I open the window.", "sarah-57804"),
                turn(57805, "owen", "The window is open.", "owen-57805")]
        world.update(w, live, 57805)
        self.assertEqual(w["processed_cycle"], 57805)
        self.assertEqual(w["objects"]["window"], "open")
        self.assertEqual(len(w["recent_actions"]), 1)
        self.assertEqual(w["recent_actions"][0]["source_id"], "sarah-57804")
        # Re-reading an already processed cycle must never reapply it.
        world.update(w, live, 57805)
        self.assertEqual(len(w["recent_actions"]), 1)

    def test_multiple_unique_actions_in_same_cycle_keep_public_order(self):
        w = world.initial(10)
        world.update(w, [turn(11, "sarah", "I open the window.", "first"),
                         turn(11, "mara", "I close the window.", "second")], 11)
        self.assertEqual(w["objects"]["window"], "closed")
        self.assertEqual([a["source_id"] for a in w["recent_actions"]],
                         ["first", "second"])

    def test_internal_gap_is_rejected_without_mutating_world(self):
        w = world.initial(3)
        with self.assertRaisesRegex(ValueError, "intermediate"):
            world.update(w, [turn(4, "sarah", "I open the window."),
                             turn(6, "mara", "I close the window.")], 6)
        self.assertEqual(w["processed_cycle"], 3)
        self.assertEqual(w["objects"]["window"], "closed")

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
