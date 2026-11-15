#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import room_skill_exec as router


class RoomSkillRouterTests(unittest.TestCase):
    def names(self, role: str, text: str, node: int | None = None):
        selected, available = router.select_skills(role, router._norm(text), "test-cycle", node=node)
        self.assertGreaterEqual(available, 7)
        self.assertLessEqual(len(selected), router.ROLE_BUDGETS[role]["max_skills"])
        return [item["name"] for item in selected]

    def test_technical_context_routes_technical_skill(self):
        self.assertIn(
            "technical-systems",
            self.names("thought", "The GitHub workflow and AI model are failing on the audio system."),
        )

    def test_emotional_context_routes_attunement(self):
        self.assertIn(
            "emotional-attunement",
            self.names("comprehension", "She felt hurt and worried about trust in the relationship."),
        )

    def test_single_generic_trust_cue_does_not_double_route(self):
        selected, _ = router.select_skills("thought", "trust", "test-cycle")
        self.assertLessEqual(len(selected), 1)

    def test_unrelated_context_can_route_nothing(self):
        selected, _ = router.select_skills("thought", "lampshade violet corridor", "test-cycle")
        self.assertEqual(selected, [])

    def test_prompt_is_unchanged_when_no_context_match(self):
        env = {
            "ROOM_NODE_PROMPT": "BASE",
            "ROOM_NODE_ID": "1",
            "ROOM_CYCLE_KEY": "test-cycle",
            "ROOM_ATTENTION_AUDIT": "0",
        }
        routed = router.prepare_environment(env, "lampshade violet corridor")
        self.assertEqual(routed["ROOM_NODE_PROMPT"], "BASE")

    def test_role_specific_budget_caps_temporary_context(self):
        for node, role in ((0, "comprehension"), (1, "thought"), (2, "expression")):
            env = {
                "ROOM_NODE_PROMPT": "BASE",
                "ROOM_NODE_ID": str(node),
                "ROOM_CYCLE_KEY": f"test-cycle-{role}",
                "ROOM_ATTENTION_AUDIT": "0",
            }
            routed = router.prepare_environment(
                env,
                "github workflow model software system code audio physics evidence test verify example specific detail",
            )
            extra = len(routed["ROOM_NODE_PROMPT"]) - len("BASE\n")
            self.assertLessEqual(extra, router.ROLE_BUDGETS[role]["max_chars"])

    def test_comprehension_and_expression_load_at_most_one_skill(self):
        context = "hurt worried question asked answer relationship trust misunderstanding"
        for role in ("comprehension", "expression"):
            selected, _ = router.select_skills(role, context, "test-cycle")
            self.assertLessEqual(len(selected), 1)

    def test_reference_tier_never_auto_routes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "explicit-only"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\n"
                "name: explicit-only\n"
                "domain: analysis\n"
                "roles: [\"thought\"]\n"
                "triggers: [\"github\"]\n"
                "---\n"
                "Explicit procedure.\n"
            )
            with mock.patch.object(router, "REFERENCE_SKILL_ROOT", root):
                env = {
                    "ROOM_NODE_PROMPT": "BASE",
                    "ROOM_NODE_ID": "1",
                    "ROOM_CYCLE_KEY": "test-cycle",
                    "ROOM_ATTENTION_AUDIT": "0",
                }
                routed = router.prepare_environment(env, "github workflow")
                self.assertNotIn("REFERENCE:explicit-only", routed["ROOM_NODE_PROMPT"])

    def test_explicit_reference_request_loads_reference_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "explicit-only"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\n"
                "name: explicit-only\n"
                "domain: analysis\n"
                "roles: [\"thought\"]\n"
                "triggers: []\n"
                "---\n"
                "Explicit procedure.\n"
            )
            with mock.patch.object(router, "REFERENCE_SKILL_ROOT", root):
                env = {
                    "ROOM_NODE_PROMPT": "BASE",
                    "ROOM_NODE_ID": "1",
                    "ROOM_CYCLE_KEY": "test-cycle",
                    "ROOM_ATTENTION_AUDIT": "0",
                    "ROOM_REFERENCE_SKILLS": "explicit-only",
                }
                routed = router.prepare_environment(env, "lampshade violet corridor")
                self.assertIn("[REFERENCE:explicit-only]", routed["ROOM_NODE_PROMPT"])

    def test_repeat_penalty_only_affects_weak_repeated_skill(self):
        with tempfile.TemporaryDirectory() as td:
            room = Path(td)
            attention = room / "attention"
            attention.mkdir()
            (attention / "node-01.json").write_text(
                json.dumps({"selected_skills": [{"name": "technical-systems"}]})
            )
            with mock.patch.object(router, "ROOM", room):
                weak, _ = router.select_skills("thought", "github", "cycle-2", node=1)
                strong, _ = router.select_skills(
                    "thought", "github workflow model software system", "cycle-2", node=1
                )
                self.assertNotIn("technical-systems", [item["name"] for item in weak])
                self.assertIn("technical-systems", [item["name"] for item in strong])

    def test_audit_is_prompt_safe(self):
        with tempfile.TemporaryDirectory() as td:
            room = Path(td)
            with mock.patch.object(router, "ROOM", room):
                router.write_audit(
                    node=1,
                    entity="sarah",
                    role="thought",
                    selected=[],
                    project_available=7,
                    reference_available=0,
                    context="PRIVATE CONVERSATION TEXT SHOULD NOT APPEAR",
                    base_chars=3000,
                    added_chars=0,
                    cycle_key="test-cycle",
                )
                raw = (room / "attention" / "node-01.json").read_text()
                self.assertNotIn("PRIVATE CONVERSATION TEXT", raw)
                data = json.loads(raw)
                self.assertEqual(data["version"], "room-attention-v2")
                self.assertIn("context_fingerprint", data)
                self.assertEqual(data["tiers"]["resident"]["project_skill_chars"], 0)


if __name__ == "__main__":
    unittest.main()
