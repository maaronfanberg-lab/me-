"""Generate independently scoreable, hidden-arm synthetic comparison packets.

The private answer key stays local and MUST NOT be committed or used by judges.
No actual blind rating is performed by this utility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from ab_trial import ROOT, load_cases


def make_packet(report: dict, cases: list[dict], seed: int = 42) -> tuple[dict, dict]:
    if not report.get("passed_controls") or not report.get("placebo_ok") or not report.get("restoration_ok"):
        raise ValueError("Unverified trial controls; no blinded comparison permitted")
    if type(seed) is not int:
        raise ValueError("Seed must be an integer")
    case_map = {case["id"]: case for case in cases}
    baseline = {row["id"]: row["response"] for row in report["baseline"]["rows"]}
    if len(baseline) != len(cases) or set(baseline) != set(case_map):
        raise ValueError("Baseline and cases do not match")
    rng = random.Random(seed)
    tasks, key = [], {}
    for arm in report["arms"]:
        if arm["alpha"] == 0:
            continue
        altered = {row["id"]: row["response"] for row in arm["rows"]}
        if len(altered) != len(cases) or set(altered) != set(case_map):
            raise ValueError("Intervention and cases do not match")
        for case in cases:
            cid = case["id"]
            # randomize independently per scenario, not one ordering for all arms
            intervention_first = bool(rng.getrandbits(1))
            task_id = hashlib.sha256(f"{seed}:{cid}:{arm['alpha']}".encode()).hexdigest()[:16]
            output_a, output_b = ((altered[cid], baseline[cid]) if intervention_first
                                  else (baseline[cid], altered[cid]))
            tasks.append({
                "id": task_id,
                "scenario": case["dialogue"],
                "speaker": case["speaker"],
                "response_a": output_a,
                "response_b": output_b,
                "question": "Which response is more contextually responsive, grounded, and natural? A, B, or tie?",
            })
            key[task_id] = {"case_id": cid, "alpha": arm["alpha"],
                            "intervention_side": "A" if intervention_first else "B"}
    rng.shuffle(tasks)
    return ({"schema": "room_blind_comparison_v1", "source": "fictional_model_comparison",
             "no_ratings_collected": True, "tasks": tasks},
            {"schema": "room_blind_key_v1", "warning": "Do not give this answer key to judges",
             "mapping": key})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--cases", type=Path, default=Path(__file__).with_name("synthetic_cases.json"))
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    paths = [args.report.resolve(), args.packet.resolve(), args.key.resolve()]
    if args.packet.resolve() == args.key.resolve() or any(
            path.is_relative_to(ROOT) for path in paths[1:]):
        p.error("Packet and separate key must be outside the repository, in different files")
    packet, key = make_packet(json.loads(args.report.read_text()), load_cases(args.cases), args.seed)
    for path, data in ((args.packet, packet), (args.key, key)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(packet['tasks'])} unlabeled comparisons; no ratings collected")


if __name__ == "__main__":
    main()
