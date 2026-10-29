#!/usr/bin/env python3
"""Pinned model cache cannot block live Room or bypass 1B fallback."""
from __future__ import annotations

import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/".github/workflows/sarah-society.yml"
PREWARM=ROOT/".github/workflows/room-native3b-cache-prewarm.yml"
KEY="room-native-llama32-3b-q4km-6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff"
SHA="6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff"
MODEL=".room_model/llama-3.2-3b-instruct-q4_k_m.gguf"


class PrewarmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live=LIVE.read_text()
        cls.prewarm=PREWARM.read_text()

    def test_matching_verifiable_cache_key_and_gguf_path(self):
        for text in (self.live,self.prewarm):
            self.assertIn(KEY,text)
            self.assertIn(MODEL,text)
            self.assertIn(SHA,text)

    def test_live_worker_never_downloads_large_3b(self):
        self.assertNotIn("bartowski/Llama-3.2-3B-Instruct-GGUF/resolve",self.live)
        self.assertNotIn("hf_hub_download(",self.live)
        self.assertNotIn("HF_XET_HIGH_PERFORMANCE",self.live)
        self.assertIn('if echo "$model_3b_hash  $model_3b_path" | sha256sum -c -;',self.live)
        self.assertIn("start_model 'llama3.2-3b'",self.live)
        self.assertIn("start_model 'llama3.2-1b'",self.live)
        self.assertLess(self.live.index("start_model 'llama3.2-3b'"),
                        self.live.index("start_model 'llama3.2-1b'"))
        self.assertIn("starting 1B without blocking conversation",self.live)
        self.assertIn("ROOM_NATIVE_3B_DISABLE",self.live)

    def test_cache_preparer_does_not_write_live_room_or_start_room(self):
        self.assertIn("hf_hub_download(",self.prewarm)
        self.assertIn("HF_XET_HIGH_PERFORMANCE",self.prewarm)
        self.assertIn("sha256sum -c -",self.prewarm)
        self.assertIn('cp -L "$source" "$target"',self.prewarm)
        self.assertIn("contents: read",self.prewarm)
        self.assertNotIn("contents: write",self.prewarm)
        for action in ("society/pulse-kick.txt","room/feed.json","room/state.json",
                       "gh workflow run", "git push origin HEAD:main"):
            self.assertNotIn(action,self.prewarm)

    def test_3b_download_cannot_enter_cache_before_checksum(self):
        self.assertLess(self.prewarm.index('echo "$expected_sha  $source" | sha256sum -c -'),
                        self.prewarm.index('cp -L "$source" "$target"'))
        self.assertLess(self.prewarm.index('cp -L "$source" "$target"'),
                        self.prewarm.index('echo "$expected_sha  $target" | sha256sum -c -'))

    def test_live_workflow_shell_is_still_parseable(self):
        marker="      - name: Keep all 12 cognitive nodes hot and publish every beat"
        shell=self.live.split(marker,1)[1].split("        run: |",1)[1]
        shell="\n".join(x[10:] if x.startswith("          ") else x
                        for x in shell.splitlines())
        checked=subprocess.run(["bash","-n"],input=shell,text=True,
                               capture_output=True,check=False)
        self.assertEqual(checked.returncode,0,checked.stderr)

    def test_prewarm_workflow_shell_is_parseable(self):
        # Both script stages have no external mutations in parser-only checks.
        import re
        parts=re.findall(r'        run: \|\n((?: {10,}[^\n]*\n|\n)+)',self.prewarm)
        self.assertGreaterEqual(len(parts),2)
        for part in parts:
            shell="\n".join(x[10:] if x.startswith("          ") else x
                            for x in part.splitlines())
            checked=subprocess.run(["bash","-n"],input=shell,text=True,
                                   capture_output=True,check=False)
            self.assertEqual(checked.returncode,0,checked.stderr)


if __name__=="__main__":
    unittest.main()
