#!/usr/bin/env python3
"""Guardrails: offline tests must have no production write paths or credentials."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from room_experiment_guard import check_offline_environment


class OfflineGuardTests(unittest.TestCase):
    def test_explicit_mode_required(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "explicitly"):
                check_offline_environment(d, environment={})

    def test_reject_secrets_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
                         "ROOM_RELAY_URL", "ROOM_RELAY_AUTHORIZATION"):
                with self.subTest(name=name):
                    with self.assertRaises(RuntimeError) as cm:
                        check_offline_environment(
                            d, environment={"ROOM_EXPERIMENTAL": "1", name: "SECRET_SENTINEL"}
                        )
                    self.assertIn(name, str(cm.exception))
                    self.assertNotIn("SECRET_SENTINEL", str(cm.exception))

    def test_disallow_same_tree_as_live_repo(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            prod = base / "production"
            prod.mkdir()
            (prod / "room").mkdir()
            with self.assertRaisesRegex(RuntimeError, "disjoint"):
                check_offline_environment(
                    prod / "room", environment={"ROOM_EXPERIMENTAL": "1"},
                    live_repository_root=prod
                )
            isolated = base / "isolated"
            isolated.mkdir()
            self.assertEqual(
                check_offline_environment(
                    isolated, environment={"ROOM_EXPERIMENTAL": "1"},
                    live_repository_root=prod
                ),
                isolated.resolve()
            )

    def test_git_worktree_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / ".git").mkdir()
            nested = base / "nested"
            nested.mkdir()
            with self.assertRaisesRegex(RuntimeError, "Git working tree"):
                check_offline_environment(
                    nested, environment={"ROOM_EXPERIMENTAL": "1"}
                )


if __name__ == "__main__":
    unittest.main()
