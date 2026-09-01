#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE_FILES = (
    HERE / "stanford_native_cycle.py",
    HERE / "community_cycle.py",
    HERE / "community_session.py",
    HERE / "first_exchange.py",
)
FORBIDDEN_MODULES = {
    "endogenous_workspace",
    "endogenous_semantic_refractory_v8",
    "endogenous_semantic_refractory_v6",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


class LiveIsolationTests(unittest.TestCase):
    def test_live_stanford_chain_does_not_import_experimental_workspace_or_v8(self):
        for path in LIVE_FILES:
            with self.subTest(path=path.name):
                imports = imported_modules(path)
                violations = {
                    module for module in imports
                    if module in FORBIDDEN_MODULES
                    or module.startswith("endogenous_semantic_refractory_v8.")
                    or module.startswith("endogenous_workspace.")
                }
                self.assertEqual(violations, set())

    def test_live_chain_has_no_workspace_activation_flag(self):
        for path in LIVE_FILES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("COMMUNITY_ENDOGENOUS_WORKSPACE", text)

    def test_prospective_workflow_cannot_dispatch_or_write_live_repository(self):
        workflow = REPO / ".github" / "workflows" / "emily-olivia-endogenous-v8-prospective.yml"
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn("Emily Olivia Community Run", text)
        self.assertNotIn("workflow_dispatch:", text)
        self.assertNotIn("actions: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh workflow run", text)
        self.assertNotIn("rerun", text.lower())


if __name__ == "__main__":
    unittest.main()
