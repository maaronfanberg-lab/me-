#!/usr/bin/env python3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from endogenous_workspace_artifact_tape import build_exact_tape


def text_hash(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:20]


class ArtifactTapeEvidenceTests(unittest.TestCase):
    def test_retrieval_time_evidence_needs_no_final_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay = root / "replay"
            replay.mkdir(parents=True)
            rows = []
            for step in range(1, 13):
                memories = [f"memory {step} a", f"memory {step} b", "persistent memory"]
                evidence = []
                for rank, text in enumerate(memories, start=1):
                    evidence.append(
                        {
                            "retrieval_rank": rank,
                            "content_hash": text_hash(text),
                            "stanford_node_id": f"n-{step}-{rank}",
                            "stanford_node_type": "event",
                            "stanford_importance_raw": 50 + rank,
                            "stanford_created": max(1, step - rank),
                            "stanford_last_retrieved": step,
                            "observed_time_step": step,
                        }
                    )
                rows.append(
                    json.dumps(
                        {
                            "type": "turn",
                            "session_id": "prospective-session",
                            "turn": {
                                "agent": "Emily" if step % 2 else "Olivia",
                                "time_step": step,
                                "retrieved_memories": memories,
                                "retrieved_memory_evidence": evidence,
                            },
                        }
                    )
                )
            (replay / "community_session.jsonl").write_text("\n".join(rows) + "\n")

            tape = build_exact_tape(root, min_ticks=12, artifact_run_id=999, artifact_sha256="abc")
            self.assertEqual(tape["metadata"]["tick_count"], 12)
            self.assertEqual(tape["metadata"]["chosen_metadata_mode"], "retrieval_time_evidence")
            self.assertEqual(tape["metadata"]["checkpoint_join_turns_seen"], 0)
            self.assertEqual(tape["metadata"]["retrieval_time_evidence_turns_seen"], 12)
            self.assertTrue(tape["metadata"]["exact_node_metadata"])
            self.assertEqual(tape["ticks"][0]["candidates"][0]["metadata_source"], "retrieval_time_evidence")

    def test_hash_mismatch_is_not_accepted_as_recorded_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay = root / "replay"
            replay.mkdir(parents=True)
            turn = {
                "type": "turn",
                "session_id": "bad",
                "turn": {
                    "agent": "Emily",
                    "time_step": 1,
                    "retrieved_memories": ["real memory"],
                    "retrieved_memory_evidence": [
                        {
                            "retrieval_rank": 1,
                            "content_hash": "wrong",
                            "stanford_node_id": "n1",
                            "stanford_node_type": "event",
                            "stanford_importance_raw": 50,
                            "stanford_created": 1,
                            "stanford_last_retrieved": 1,
                            "observed_time_step": 1,
                        }
                    ],
                },
            }
            (replay / "community_session.jsonl").write_text(json.dumps(turn) + "\n")
            with self.assertRaises(ValueError):
                build_exact_tape(root, min_ticks=1)


if __name__ == "__main__":
    unittest.main()
