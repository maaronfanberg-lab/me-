# Experiment 35: is the teardown the damage or the escape? (written before any run)

Written 2026-10-28, after experiment 34. Committed with `ci/e35.txt` and `experiments/e35_analyze.py` before any run.

## Manipulation

`block_nomean` (checked in `tests/test_detach.py`): every block's update is projected so that it cannot shift that
block's minibatch-mean pre-activation (ΔW·h̄ = 0, Δb = 0). The readout and its kick are untouched.

## Design

- 96-layer residual ReLU, SGD lr 0.05, 6,000 steps.
- Both tasks, seeds 0–4.
- Conditions:
  - plain (the reference);
  - nomean;
  - nomean + kick cap 10 (control).
- Each run also gets an every-step trace of the first 300 steps (`e34_trace.py`).

## Measures

- **Teardown:** the last stream at step 5 is below 25% of its step-0 value.
- **Outcome:**
  - broken if transport at loss 0.03 is below +0.3 (falling back to 0.1, then 0.3), or if the run fails to train;
  - **diverged** if the run stops on non-finite values.
- A condition takes the state at least 3 of its 5 runs show.

## Predictions

- **P35a:** nomean prevents the teardown on both tasks.
- **P35b (my bet, about 60%: the teardown is the escape):** nomean diverges on digits.
- **P35c:** nomean + cap 10 is healthy on both tasks.

## Decision

- If nomean prevents the teardown and diverges, the teardown is **the escape**.
- If nomean prevents the teardown and is healthy, the teardown is **the damage**.
- If nomean does not prevent the teardown, the test is **void**: the teardown is carried by the inherited part.
