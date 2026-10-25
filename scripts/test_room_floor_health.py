#!/usr/bin/env python3
"""Diagnostic contract: no transcripts, secrets or invalid state get serialized."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from room_floor_health import KNOWN_STAGES, fallback_record


class FallbackHealthTests(unittest.TestCase):
    def test_two_precise_failure_stages_preserved(self):
        j = fallback_record("40205255651", "floor_selection,candidate_preflight",
                            now="2026-10-25T15:00:00Z")
        self.assertEqual(j["failure_stages"], ["floor_selection", "candidate_preflight"])
        self.assertEqual(j["run_id"], "40205255651")
        self.assertEqual(j["outcome"], "runner_fell_back_to_legacy")
        self.assertEqual(set(j), {"schema", "outcome", "failure_stages", "run_id", "recorded_at"})

    def test_raw_private_content_never_serialized(self):
        leaked = "PRIVATE_PROMPT_API_KEY=SECRET"
        j = fallback_record("id-" + leaked, "before_floor," + leaked,
                            now="2026-10-25T15:00:00Z")
        text = json.dumps(j)
        self.assertNotIn("SECRET", text)
        self.assertEqual(j["run_id"], "unknown")
        self.assertEqual(j["failure_stages"], ["before_floor", "unknown"])

    def test_writer_is_separate_and_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "room" / "floor-health.json"
            subprocess.run(
                [sys.executable, str(Path(__file__).with_name("room_floor_health.py")),
                 "--stages", "before_floor,expression_generation",
                 "--run-id", "424242", "--out", str(p)],
                check=True, timeout=10
            )
            j = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(j["failure_stages"], ["before_floor", "expression_generation"])
            self.assertFalse(p.with_name(p.name + ".writing").exists())

    def test_unknown_stage_remains_unknown_not_model_speech(self):
        self.assertEqual(fallback_record("1", "unexpected-stage")["failure_stages"], ["unknown"])
        self.assertEqual(len(KNOWN_STAGES), 6)


if __name__ == "__main__":
    unittest.main()
