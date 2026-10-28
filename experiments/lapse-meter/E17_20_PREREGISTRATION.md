# Experiments 17–20: does the deep-ReLU break reach real architectures? (written before any run)

Written 2026-10-27, after experiments 13–16 and before any experiment 17–20 run. Committed to GitHub with the
code, job list (`experiments/e17_20_jobs.txt`) and `experiments/e17_20_analyze.py` before the first run.

## Where things stand

Experiments 8–16 found:

- Deep residual ReLU breaks because its always-positive block outputs pile up on the stream.
- The damage happens in the first training steps, and it lands on the output layer. That layer is fed the
  piled-up stream and takes full-size steps.
- A warm-up of the output layer alone rescues the network; a warm-up of the blocks alone does not. Even a
  50-step warm-up of everything is enough.
- Results are in `results/e13_16_analysis.md`.

All of that used the simplest residual block, h + α·act(W h). Real networks (ResNets, transformer feed-forward
layers) use a second matrix, h + α·V·act(W h). Its random signs should stop block outputs from sharing a
direction. At initialization the stream grows 1.3× at 96 layers in that design, against 38×. These experiments
ask whether the break survives in that design, under Adam, and at a larger width. A fourth pools everything to
ask whether the break costs learning.

**Disclosure.** Before writing this I ran only initialization checks for these designs (stream growth and
starting loss, as quoted here) and 20-step smoke tests confirming the code runs. No transport values from
training were looked at.

## Common design and rule

Identical to experiments 8–16 except for the named change: width 64, α = 1/√depth, SGD lr 0.05, batch 64,
6,000 steps, seeds 0–2, digits and the clean circle.

- **Primary measure:** `ln_transport` at training loss 0.03.
- **Rescued** = above the stated reference by more than 2·sqrt(sd₁² + sd₂²).
- **No depth break** = the 96-layer mean not below the 24-layer mean by more than that threshold.
- Each table also counts runs that failed to train (final loss above half of ln(classes)).

## Experiment 17: the standard two-matrix block

`lapse/nets2.py`: h_l = h_{l−1} + α·V_l·relu(W_l h_{l−1} + b_l), V_l drawn like W_l. The gradients are checked
against finite differences in `tests/test_nets2.py`. The tilt split is the same; the gate part now includes V.

- **P17a:** two-matrix ReLU at 96 layers is rescued against plain one-matrix ReLU at 96 layers (experiment 8),
  on both tasks.
- **P17b:** two-matrix ReLU shows no depth break from 24 to 96 layers, on both tasks.

## Experiment 18: Adam

Adam (lr 0.001, as in experiment 2) bounds each parameter's step at roughly the learning rate, whatever the
gradient's size. So the output layer cannot take the oversized first steps that experiments 13–16 point to.

- **P18:** with Adam, plain one-matrix ReLU at 96 layers shows no depth break against Adam ReLU at 24 layers,
  on both tasks.
- **Loss level:** Adam at this learning rate may train slowly. The measuring level is the lowest of 0.03, 0.1 and
  0.3 that both Adam ReLU groups reach in at least 2 runs. This rule is fixed now.
- Adam tanh at 96 layers is reported alongside, not tested.

## Experiment 19: width 128

The pile-up does not depend on width: plain ReLU at width 128 grows 37.6× at initialization, signed ReLU 1.2×.

- **P19:** at width 128 and 96 layers, signed ReLU is rescued against plain ReLU at the same width, on both
  tasks.

## Experiment 20 (exploratory, no new runs, no prediction): does losing transport cost learning?

Every 96-layer, width-64, SGD condition from experiments 8–17 is pooled. Reported:

- final training loss and test accuracy per condition
- per task, the Spearman correlation across runs between transport at loss 0.03 and final log training loss,
  and between transport and test accuracy

These are exploratory and make no claim of cause.
