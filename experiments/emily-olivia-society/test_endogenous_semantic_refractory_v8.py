#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from endogenous_semantic_refractory_v8 import (
    PREREG_COMMITTED_AT,
    build_native_only_tape,
    load_locked_prereg,
    run_prospective,
)

HERE = Path(__file__).resolve().parent
PREREG = HERE / "endogenous_semantic_refractory_v8_preregistration.json"
POST_SESSION = "1788292800-prospective"
PRE_SESSION = "1788289000-legacy"


def _hash(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:20]


def _artifact(root: Path, *, sessions=None, break_hash_at=None, omit_evidence_at=None) -> None:
    replay = root / "replay"
    replay.mkdir(parents=True, exist_ok=True)
    rows = []
    sessions = sessions or [POST_SESSION] * 12
    for index in range(12):
        step = 100 + index
        # Deliberately recycle one semantic pair across multiple candidate IDs so
        # the evaluator has a non-zero semantic baseline to measure.
        texts = [
            f"observes a message from Olivia: shared garden plan detail {index % 3}",
            f"observes a message from Olivia: shared garden plan option {index % 4}",
            f"reflects on careful choice number {index}",
            f"remembers ordinary afternoon note {index}",
        ]
        evidence = []
        for rank, text in enumerate(texts, start=1):
            content_hash = _hash(text)
            if break_hash_at == index and rank == 1:
                content_hash = "0" * 20
            evidence.append(
                {
                    "retrieval_rank": rank,
                    "content_hash": content_hash,
                    "stanford_node_id": f"node-{index}-{rank}",
                    "stanford_node_type": "event",
                    "stanford_importance_raw": 50 + rank,
                    "stanford_created": step - rank,
                    "stanford_last_retrieved": step - 1,
                    "observed_time_step": step,
                }
            )
        turn = {
            "agent": "Emily" if index % 2 == 0 else "Olivia",
            "time_step": step,
            "retrieved_memories": texts,
            "retrieved_memory_evidence": evidence,
            "action": {"type": "wait"},
        }
        if omit_evidence_at == index:
            turn.pop("retrieved_memory_evidence")
        rows.append({"type": "turn", "session_id": sessions[index], "turn": turn})
    (replay / "community_session.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


class ProspectiveV8Tests(unittest.TestCase):
    def test_preregistration_is_still_locked(self):
        prereg = load_locked_prereg(PREREG)
        self.assertEqual(prereg["candidate"], {"refractory_decay": 0.5, "refractory_penalty": 1.0, "k": 4})
        self.assertFalse(prereg["decision"]["prospective_pass_can_permit_live_behavioral_influence"])

    def test_native_single_session_artifact_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root)
            tape, metadata = build_native_only_tape(
                root,
                run_id=999,
                artifact_sha256="a" * 64,
                artifact_created_at="2026-09-01T20:00:00Z",
                min_ticks=12,
            )
            self.assertEqual(len(tape["ticks"]), 12)
            self.assertEqual(metadata["chosen_metadata_mode"], "retrieval_time_evidence")
            self.assertEqual(metadata["session_id"], POST_SESSION)
            self.assertEqual(metadata["session_started_at"], "2026-09-01T20:00:00Z")

    def test_artifact_at_or_before_prereg_boundary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root)
            with self.assertRaisesRegex(ValueError, "postdate"):
                build_native_only_tape(
                    root,
                    run_id=999,
                    artifact_sha256="a" * 64,
                    artifact_created_at=PREREG_COMMITTED_AT,
                    min_ticks=12,
                )

    def test_postdated_zip_cannot_smuggle_a_pre_preregistration_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root, sessions=[PRE_SESSION] * 12)
            with self.assertRaisesRegex(ValueError, "session began before"):
                build_native_only_tape(
                    root,
                    run_id=999,
                    artifact_sha256="a" * 64,
                    artifact_created_at="2026-09-01T20:00:00Z",
                    min_ticks=12,
                )

    def test_mixed_session_epoch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = ["1788292800-sessiona"] * 6 + ["1788292801-sessionb"] * 6
            _artifact(root, sessions=sessions)
            with self.assertRaisesRegex(ValueError, "one named session"):
                build_native_only_tape(
                    root,
                    run_id=999,
                    artifact_sha256="a" * 64,
                    artifact_created_at="2026-09-01T20:00:00Z",
                    min_ticks=12,
                )

    def test_hash_mismatch_fails_closed_instead_of_using_checkpoint_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root, break_hash_at=4)
            with self.assertRaises(ValueError):
                build_native_only_tape(
                    root,
                    run_id=999,
                    artifact_sha256="a" * 64,
                    artifact_created_at="2026-09-01T20:00:00Z",
                    min_ticks=12,
                )

    def test_missing_native_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root, omit_evidence_at=4)
            with self.assertRaises(ValueError):
                build_native_only_tape(
                    root,
                    run_id=999,
                    artifact_sha256="a" * 64,
                    artifact_created_at="2026-09-01T20:00:00Z",
                    min_ticks=12,
                )

    def test_evaluation_can_never_grant_live_behavioral_influence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _artifact(root)
            result = run_prospective(
                PREREG,
                root,
                run_id=999,
                artifact_id=1000,
                artifact_sha256="a" * 64,
                artifact_created_at="2026-09-01T20:00:00Z",
                artifact_head_sha="b" * 40,
            )
            self.assertFalse(result["produced_dialogue"])
            self.assertFalse(result["wrote_live_memory"])
            self.assertFalse(result["activated_live_workspace"])
            self.assertFalse(result["activated_shadow_mode_during_test"])
            self.assertFalse(result["started_community_run"])
            self.assertFalse(result["altered_the_room"])
            self.assertFalse(result["results"]["live_behavioral_influence_permitted"])


if __name__ == "__main__":
    unittest.main()
