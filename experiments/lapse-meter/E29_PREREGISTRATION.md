# Experiment 29: is the damaging part of the kick the shared "bias" input? (written before any run)

Written 2026-10-28, before any experiment-29 run. While writing it I had seen the first six of experiment 25's
traces: in a collapsing run the readout weights end with 70% of their energy along the shared direction, against
0.1–0.4% in rescued runs. Committed with `experiments/e29_jobs.txt`, `experiments/e29_predictions.json` and
`experiments/e29_analyze.py`.

## Why

In piled-up ReLU networks almost every example's last stream is the same large vector m. To the readout, m looks
like a giant constant input, a bias, which is Clevert et al.'s "bias shift" in a residual setting. At initialization,
73–82% of the readout kick's energy is common-mode, the same logit shift for every example (tanh: 0.5%). The
hypothesis is that this common-mode part, not the kick's total size, is what does the damage.

## Manipulation (`lapse/nets_ln.py`)

- **center:** logits = W_out (h_L − m₀) + b_out, with m₀ the mean of the last stream over the training set at
  initialization, held fixed. This removes the shared input at the start and leaves the pile-up and the
  example-specific signal intact. Gradients are checked by finite differences.
- **center_random (control):** subtract instead a random fixed vector with m₀'s norm. This does not remove the
  shared direction.

Step-one kicks, measured before writing this:

| condition | digits | circle |
|---|---|---|
| center | 108–170 | 20–142 |
| center_random | 2,417–3,804 | 219–544 |

## Design and outcome

96-layer residual ReLU, width 64, SGD lr 0.05, 6,000 steps, seeds 0–2, both tasks. Centering does not change the
backward signal's scale, so the outcome rule of experiments 23–24 applies: **broken** if transport at loss 0.03 is
below +0.3 (falling back to 0.1, then 0.3), or if the run fails to train.

## Predictions

- **P29a:** center is healthy (at least 2 of 3 runs) on both tasks.
- **P29b:** center_random is broken (at least 2 of 3 runs) on both tasks.
- **Per-run kick rule** (cutoffs 328 and 124): share right reported, not tested.

## Decision

"The common-mode (bias) part of the kick does the damage" is **supported** if P29a and P29b hold on both tasks. It
is **refuted** if centering does not rescue on either task.
