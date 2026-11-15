# Experiment 33: cut the bias channel (written before any run)

Written 2026-10-28, before any experiment-33 run and before any result of experiments 27, 29 or 30. The account it
tests (B) is in `THEORY_KICK.md`, amendment 2. Committed with `experiments/e33_jobs.txt`,
`experiments/e33_predictions.json`, `experiments/e33_analyze.py` and the `detach` option (`lapse/nets.py`, checked by `tests/test_detach.py`).

## Manipulation

Plain 96-layer residual ReLU, width 64, SGD lr 0.05, batch 64, 6,000 steps, seeds 0–2, both tasks. These are
experiment 8's runs, with one change.

In every training step, the readout's gradient into the stream, dL/dh_{L−1} = d·W_out, has its component along a
unit vector u removed before it flows into the blocks:

- **detach = "mean":** u is the batch's mean readout input, normalized. This is the shared direction m̂, so the cut
  removes the bias channel.
- **detach = "random":** u is a fixed random unit vector (the control).

Nothing else changes:

- the forward pass, the loss and the readout's own update, so the step-one kick is the full 1,640–2,396 on digits
  and 108–369 on the circle;
- every logged diagnostic, which uses the true, uncut gradient, so transport measures the network's real backward
  signal.

## Outcome

As in experiments 23, 24, 29 and 30: **broken** if transport at loss 0.03 is below +0.3 (falling back to 0.1, then
0.3), or if the run fails to train (final loss above 0.5·ln K). A condition is broken or healthy if at least 2 of 3
runs are.

## Predictions (account B)

- **P33a:** detach = "mean" is healthy on both tasks.
- **P33b:** detach = "random" is broken on both tasks (like experiment 8's plain runs, all broken).

## Decision

- B is **supported** if P33a and P33b hold on both tasks.
- B is **refuted** if detach = "mean" is broken on both tasks. The kick would then do its damage through the
  example-specific errors it leaves (account K).
- Anything else is **mixed**.

Per-run kick rule (cutoffs 328 and 124): every run here has a kick above its cutoff except circle seed 0 (108), in
both conditions. So the rule says broken for 10 of 12 runs, and if P33a holds it will be wrong for most of the
detach = "mean" runs. Its hit rate is
reported, not tested.
