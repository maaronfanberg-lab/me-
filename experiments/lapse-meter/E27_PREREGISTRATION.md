# Experiment 27: how long is the critical window? (written before any run)

Written 2026-10-28, before any experiment-27 run. I had seen experiments 24–26 and the uncapped kick traces of
experiment 25 (four plain runs; the other two were being rerun). Committed with `experiments/e27_jobs.txt` and
`experiments/e27_analyze.py`.

## Why

Uncapped, the readout kick is large only at steps 0 and 1 (circle 125–464, digits 1,346 then 366) and is near zero
from step 2 on (experiment 25). In experiment 24, a cap binding only at steps 0–1 rescued digits.

## Design

96-layer residual ReLU, width 64, SGD lr 0.05, 6,000 steps, seeds 0–2, both tasks. The kick is capped at 10 during
the first k steps only, `kick_cap_until = k` with k ∈ {1, 2, 3, 5, 10}; after that, nothing is changed. A window of
zero is checked to be identical to no cap.

**Outcome.** As in experiment 24: broken if transport at loss 0.03 is below +0.3 (falling back to 0.1, then 0.3),
or if the run fails to train.

## Predictions

- **P27a:** k = 2 is healthy (at least 2 of 3 runs) on both tasks. Protecting the two steps in which the kick is
  large is enough.
- **P27b:** k = 5 and k = 10 are healthy on both tasks.
- **k = 1 and k = 3:** reported, not tested. Capping step 0 may change step 1's natural kick in either direction.

## Decision

"The damage happens in the first two readout updates" is **supported** if P27a holds on both tasks. It is
**refuted** if k = 10 does not rescue.
