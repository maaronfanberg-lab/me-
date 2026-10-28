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

    def test_open_floor_selection_preserves_single_optional_public_anchor(self):
        source = event("mara", "I found a strange track beside the river.", "river-1")
        older = event("sarah", "Category classification trees again.", "old-1")
        floor = {"reason": "open_floor_uptake", "source_id": "river-1",
                 "speaker": "jules"}
        result = project.expression_project(
            entity="jules", latest=source, context=[older, source],
            profile=PROFILE, private_self_state=MOTIVATION, floor=floor)
        self.assertEqual(result["interaction_project"]["kind"],
                         "self_initiated_contribution")
        self.assertTrue(result["interaction_project"]["optional_uptake"])
        self.assertEqual(result["event"]["id"], "river-1")
        self.assertEqual(result["context"], [source])
        self.assertNotIn("old-1", str(result))
        self.assertNotIn("what_i_currently_believe",
                         result["private_self_state"])

        keys = ("ROOM_FLOOR_REASON", "ROOM_FLOOR_SOURCE_ID", "ROOM_FLOOR_SPEAKER")
        prior = {key: os.environ.get(key) for key in keys}
        try:
            os.environ.update({"ROOM_FLOOR_REASON": "open_floor_uptake",
                               "ROOM_FLOOR_SOURCE_ID": "river-1",
                               "ROOM_FLOOR_SPEAKER": "jules"})
            packed_input = self.input(source)
            packed_input["context"] = [older, source]
            compact = autonomy._autonomy_compact(packed_input, "expression", "jules")
            self.assertEqual(compact["event"]["text"], source["text"])
            self.assertEqual([item["text"] for item in compact["context"]], [source["text"]])
            self.assertEqual(compact["social_opportunity"]["source_id"], "river-1")
            self.assertEqual(compact["social_opportunity"]["action_due"],
                             "optional_uptake_or_self_initiated")
            self.assertIsNone(compact["discussion"]["subject"])
        finally:
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_open_floor_anchor_requires_matching_selected_source_and_speaker(self):
        source = event("mara", "The creek flooded.", "creek-2")
        common = dict(entity="jules", latest=source, context=[source],
                      profile=PROFILE, private_self_state=MOTIVATION)
        for floor in (
            None,
            {"reason": "technical_fallback_opportunity", "source_id": "creek-2",
             "speaker": "jules"},
            {"reason": "open_floor_uptake", "source_id": "other-episode",
             "speaker": "jules"},
            {"reason": "open_floor_uptake", "source_id": "creek-2",
             "speaker": "owen"},
        ):
            with self.subTest(floor=floor):
                output = project.expression_project(**common, floor=floor)
                self.assertIsNone(output["event"])
                self.assertEqual(output["context"], [])
                self.assertFalse(output["interaction_project"].get("optional_uptake", False))

    def test_deliberated_open_floor_relevance_retains_optional_public_anchor(self):
        source = event("owen", "I measured the changing patterns of bird calls.", "birds-1")
        floor = {"reason": "open_floor_relevance", "source_id": "birds-1",
                 "speaker": "mara"}
        result = project.expression_project(
            entity="mara", latest=source, context=[source],
            profile=PROFILE, private_self_state=MOTIVATION, floor=floor)
        self.assertEqual(result["event"]["id"], "birds-1")
        self.assertTrue(result["interaction_project"]["optional_uptake"])
        self.assertEqual(result["interaction_project"]["kind"],
                         "self_initiated_contribution")
        # An independently deliberated initiative may hear the last speaker
        # without mandatory agreement, topic quotas or canned replies.

    def test_optional_anchor_never_treats_directed_or_self_speech_as_own(self):
        examples = (
            event("mara", "Sarah, please answer me.", "m1"),
            event("jules", "I was just speaking.", "m2"),
            event("system", "Unpublished internal note.", "m3"),
        )
        for source in examples:
            with self.subTest(source=source["id"]):
                result = project.expression_project(
                    entity="jules", latest=source, context=[source],
                    profile=PROFILE, private_self_state=MOTIVATION,
                    floor={"reason": "open_floor_uptake", "source_id": source["id"],
                           "speaker": "jules"})
                self.assertIsNone(result["event"])
                self.assertEqual(result["context"], [])

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
        with_history = self.input(old)
        with_history["group_context"] = {
            "relationships": {"mara": {"trust": 0.65}},
            "encounters": [{"speaker": "mara",
                            "text": "Category classification trees are everything."}],
            "activities": [{"proposal": "Experimental classification tree project"}],
            "possible_collaborators": ["sarah", "mara"],
        }
        reduced = autonomy._autonomy_compact(with_history, "expression", "jules")
        self.assertEqual(reduced["group_context"]["relationships"]["mara"]["trust"], 0.65)
        self.assertEqual(reduced["group_context"]["possible_collaborators"], ["sarah", "mara"])
        self.assertNotIn("encounters", reduced["group_context"])
        self.assertNotIn("activities", reduced["group_context"])

    def test_accepted_allen_turn_keeps_full_verbatim_evidence(self):
        old = event("allen", "Jules, why do octopuses camouflage?", "allen-queue-88")
        self.assertTrue(project.response_project(old, "jules"))
        compact = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertEqual(compact["interaction_project"]["kind"], "respond_or_repair")
        self.assertEqual(compact["event"]["text"], old["text"])
        self.assertEqual(compact["social_opportunity"]["source_id"], old["id"])
        self.assertEqual(compact["social_opportunity"]["action_due"], "directed_response_or_repair")
        self.assertTrue(any(x["speaker"] == "allen" for x in compact["context"]))
        with_history = self.input(old)
        with_history["group_context"] = {
            "relationships": {"mara": {"trust": 0.65}},
            "encounters": [{"speaker": "allen", "text": "Why octopuses?"}],
        }
        responsive = autonomy._autonomy_compact(with_history, "expression", "jules")
        self.assertEqual(responsive["group_context"]["encounters"][0]["speaker"], "allen")

    def test_unaddressed_question_is_open_response_opportunity(self):
        old = event("mara", "Why do people keep their favorite objects?", "m2")
        self.assertTrue(project.response_project(old, "jules"))
        packed = autonomy._autonomy_compact(self.input(old), "expression", "jules")
        self.assertEqual(packed["interaction_project"]["kind"], "respond_or_repair")
        self.assertEqual(packed["event"]["text"], old["text"])
        self.assertEqual(packed["interaction_project"]["observed_source_id"], "m2")

    def test_jules_collaboration_invitation_does_not_imply_criticism(self):
        invitation = event("jules",
            "Hey Mara, I was thinking that maybe we could collaborate on a project "
            "and explore some new territory together.", "jules-invite-1")
        self.assertTrue(project.response_project(invitation, "mara"))
        self.assertTrue(project.invitation_project(invitation))
        pack = project.expression_project(entity="mara", latest=invitation,
            context=[invitation], profile=PROFILE, private_self_state=MOTIVATION)
        self.assertEqual(pack["interaction_project"]["kind"], "respond_to_proposal")
        self.assertEqual(pack["interaction_project"]["proposal_status"], "unanswered")
        self.assertEqual(pack["interaction_project"]["reply_opportunities"],
                         ["accept", "decline", "clarify", "counteroffer"])
        self.assertEqual(pack["event"]["text"], invitation["text"])
        reply_input = self.input(invitation)
        reply_input["entity"] = "mara"
        compact = autonomy._autonomy_compact(reply_input, "expression", "mara")
        self.assertEqual(compact["social_opportunity"]["action_due"],
                         "respond_to_proposal")
        self.assertEqual(compact["interaction_project"]["observed_source_id"],
                         "jules-invite-1")
        self.assertIn("collaborate", compact["event"]["text"])

    def test_named_recipient_owns_the_open_response_project(self):
        source = event("jules", "Hey Sarah, can you explain the exercise?", "q1", target="mara")
        self.assertTrue(project.response_project(source, "sarah"))
        self.assertFalse(project.response_project(source, "mara"))
        self.assertFalse(project.response_project(source, "owen"))
        response = project.expression_project(entity="sarah", latest=source,
            context=[source], profile=PROFILE, private_self_state=MOTIVATION)
        self.assertEqual(response["interaction_project"]["kind"], "respond_or_repair")
        self.assertEqual(response["event"]["id"], "q1")
        bystander = project.expression_project(entity="mara", latest=source,
            context=[source], profile=PROFILE, private_self_state=MOTIVATION)
        self.assertEqual(bystander["interaction_project"]["kind"], "self_initiated_contribution")

    def test_accepted_allen_named_turn_is_not_a_group_obligation(self):
        source = event("allen", "Sarah, what happened?", "a1")
        self.assertTrue(project.response_project(source, "sarah"))
        for bystander in ("mara", "jules", "owen"):
            self.assertFalse(project.response_project(source, bystander))
        self.assertTrue(project.response_project(
            event("allen", "What happened?", "a2"), "jules"))

    def test_hundred_named_address_scenarios(self):
        names = ("sarah", "mara", "owen", "jules")
        templates = (
            "Hey {name}, what happened?",
            "{name}, do you have an idea?",
            "Hi {name}: can you help?",
            "@{name} could you answer?",
            "{name} can you explain?")
        for i in range(100):
            author = (*names, "allen")[i % 5]
            recipient = names[(i // 5) % 4]
            if author == recipient:
                recipient = names[(names.index(recipient) + 1) % 4]
            last = event(author, templates[(i // 20) % 5].format(
                name=recipient.capitalize()), "case-%03d" % i)
            with self.subTest(case=i):
                self.assertTrue(project.response_project(last, recipient))
                for other in names:
                    if other != recipient:
                        self.assertFalse(project.response_project(last, other))

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
