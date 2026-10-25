#!/usr/bin/env python3
"""Action-project regressions: real Allen reply, public evidence, independent initiative."""
from __future__ import annotations

import os
import unittest

import room_conversation_project as project
import room_private_model_autonomy_legacy as autonomy
import room_engine_v5_core as core

PROFILE = {
    "name": "Jules",
    "psychology_v2": {
        "core_identity": "An evolutionary biologist interested in unfamiliar organisms.",
        "motives": ["Investigate curious evolutionary mechanisms."],
        "values": ["interesting truth", "freedom"],
        "attention_magnets": ["odd details", "surprising organisms"],
        "education": {"graduate_domains": ["evolutionary ecology", "animal behavior"]},
    },
}
MOTIVATION = {
    "who_i_am": "An evolutionary biologist.",
    "what_i_want": "To discover unfamiliar patterns.",
    "what_i_currently_believe": "Category classification trees forever.",
    "what_just_changed": "Category classification tree again.",
}


def event(who, text, ident="m1", target=""):
    return {"speaker": who, "text": text, "id": ident,
            "cognition": {"target": target} if target else {}}


class Projects(unittest.TestCase):
    def setUp(self):
        self.before = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"

    def tearDown(self):
        if self.before is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = self.before

    def input(self, last):
        return {"entity": "jules", "profile": PROFILE,
                "event": last, "context": [event("sarah", "Category classification trees", "s0"), last],
                "private_self_state": MOTIVATION, "topic": {"root": "category classification trees"},
                "partner": "mara"}

    def test_unrequested_statement_allows_personal_initiative(self):
        old = event("mara", "Experimental classification trees are good.", "m1")
        p = project.expression_project(entity="jules", latest=old,
            context=[old], profile=PROFILE, private_self_state=MOTIVATION)
        self.assertEqual(p["interaction_project"]["kind"], "self_initiated_contribution")
        self.assertEqual(p["interaction_project"]["observed_source_id"], "m1")
        self.assertIsNone(p["event"])
        self.assertEqual(p["context"], [])
        self.assertIn("animal behavior", p["interaction_project"]["resources"]["knowledge_domains"])
        self.assertNotIn("what_i_currently_believe", p["private_self_state"])
        compact = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertEqual(compact["interaction_project"]["kind"], "self_initiated_contribution")
        self.assertEqual(compact["social_opportunity"]["action_due"], "self_initiated_contribution")
        self.assertEqual(compact["social_opportunity"]["source_id"], "m1")
        self.assertIsNone(compact["event"])
        self.assertEqual(compact["context"], [])
        self.assertIsNone(compact["discussion"]["subject"])
        self.assertNotIn("Category classification tree", str(compact))
        self.assertIn("animal behavior", str(compact["interaction_project"]))

    def test_accepted_allen_turn_keeps_full_verbatim_evidence(self):
        old = event("allen", "Jules, why do octopuses camouflage?", "allen-queue-88")
        self.assertTrue(project.response_project(old, "jules"))
        compact = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertEqual(compact["interaction_project"]["kind"], "respond_or_repair")
        self.assertEqual(compact["event"]["text"], old["text"])
        self.assertEqual(compact["social_opportunity"]["source_id"], old["id"])
        self.assertEqual(compact["social_opportunity"]["action_due"], "directed_response_or_repair")
        self.assertTrue(any(x["speaker"] == "allen" for x in compact["context"]))

    def test_unaddressed_question_is_open_response_opportunity(self):
        old = event("mara", "Why do people keep their favorite objects?", "m2")
        self.assertTrue(project.response_project(old, "jules"))
        packed = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertEqual(packed["interaction_project"]["kind"], "respond_or_repair")
        self.assertEqual(packed["event"]["text"], old["text"])
        self.assertEqual(packed["interaction_project"]["observed_source_id"], "m2")

    def test_personal_attention_without_canned_subject_rotation(self):
        old = event("mara", "Nothing else needed.", "m3")
        a = project.expression_project(entity="jules", latest=old, context=[old],
             profile=PROFILE, private_self_state=MOTIVATION)
        b = project.expression_project(entity="jules", latest=old, context=[old],
             profile=PROFILE, private_self_state=MOTIVATION)
        self.assertEqual(a, b)
        self.assertNotIn("forced_topic", str(a))
        self.assertNotIn("prohibit_words", str(a))
        self.assertNotIn("last_topic", str(a))
        self.assertEqual(a["interaction_project"]["resources"]["personal_motives"],
                         ["Investigate curious evolutionary mechanisms."])

    def test_legacy_mode_does_not_use_new_projection(self):
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "0"
        old = event("mara", "Classification trees are good.", "m4")
        compact = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertNotIn("interaction_project", compact)
        self.assertEqual(compact["event"]["text"], old["text"])

    def test_real_cognition_stage_observes_allen_source(self):
        original = core.conv, core.minds, core.state, core.model_run
        latest = event("allen", "Sarah, I have a question.", "allen-event-909")
        mind = core.fresh_minds()
        try:
            core.conv = lambda: [event("mara", "Previous idea", "mara-1"), latest]
            core.minds = lambda: mind
            core.state = lambda: core.fresh_state()
            core.model_run = lambda *args, **kwargs: None
            sensed = core.sense(0, "test-allen")
            self.assertEqual(sensed["private"]["event"]["id"], "allen-event-909")
            self.assertEqual(sensed["private"]["context"][-1]["speaker"], "allen")
            self.assertEqual(sensed["private"]["partner"], "allen")
            self.assertEqual(sensed["private"]["keywords"], [])
            self.assertEqual(sensed["private"]["topic"], {})
        finally:
            core.conv, core.minds, core.state, core.model_run = original


if __name__ == "__main__":
    unittest.main()
