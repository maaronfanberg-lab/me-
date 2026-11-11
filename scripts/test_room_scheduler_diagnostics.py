#!/usr/bin/env python3
"""Static contract for scheduler telemetry; no live runner is required."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class SchedulerDiagnosticsTests(unittest.TestCase):
    def test_native_exports_minimal_scheduler_diagnostics(self):
        source = (ROOT / "room_concordia_native.py").read_text()
        ast.parse(source)
        self.assertIn('"scheduler_diagnostics": scheduler_diagnostics', source)
        for key in ("mask_sizes", "timer_present", "queued_events", "exhausted", "acted_steps"):
            self.assertIn(f'"{key}"', source)

    def test_live_persists_scheduler_diagnostics(self):
        source = (ROOT / "room_concordia_live.py").read_text()
        ast.parse(source)
        self.assertIn('"scheduler_diagnostics": output.get("scheduler_diagnostics", {})', source)


if __name__ == "__main__":
    unittest.main()
