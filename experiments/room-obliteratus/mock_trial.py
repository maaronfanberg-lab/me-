"""Deterministic FAKE model for testing orchestration only. NOT model inference."""
from __future__ import annotations
import argparse
import contextlib
import json
from pathlib import Path
from ab_trial import ROOT, load_cases, run_trial


def run_demo():
    cases = load_cases(Path(__file__).with_name("synthetic_cases.json"))
    state = {"alpha": None}

    def generate(messages):
        assert state["alpha"] is None or -3 <= state["alpha"] <= 3
        # Explicitly simulated responses. Not a trained or neural model.
        first = messages[0]["content"].split(", a participant", 1)[0]
        if state["alpha"] is None or state["alpha"] == 0:
            return f"I heard that, {first[-5:].strip()}. Could we check the details?"
        if state["alpha"] < 0:
            return "[SILENT]"
        return "I disagree. Let's check what actually happened before drawing conclusions."

    @contextlib.contextmanager
    def intervention(alpha):
        if state["alpha"] is not None:
            raise RuntimeError("Intervention hooks were nested")
        state["alpha"] = alpha
        try:
            yield
        finally:
            state["alpha"] = None

    report = run_trial(cases, generate, intervention, [0, -0.5, 0.5, 1])
    report["provenance"] = {"source": "deterministic_simulated_generator",
                            "NOT_NEURAL_INFERENCE": True, "NOT_OBLITERATUS": True}
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(ROOT):
        p.error("Outputs must be outside repository")
    report = run_demo()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Simulated control test:", "PASS" if report["passed_controls"] else "FAIL")
    return 0 if report["passed_controls"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
