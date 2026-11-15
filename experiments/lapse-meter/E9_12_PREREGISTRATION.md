# Experiments 9–12: is the deep-ReLU break caused by the positive-mean pile-up? (written before any run)

Written 2026-10-27. Committed to GitHub with the code, job lists and `experiments/e9_12_analyze.py` before any
experiment 9–12 run.

## What experiment 8 showed (exploratory)

Residual ReLU networks at 12–48 layers carry the gradient back along the stream about as well as tanh networks do.
At 96 layers this breaks. Transport `ln_transport` at training loss 0.03 is +0.12 ± 0.13 on digits, against
+0.82 for tanh, and +0.07 ± 0.05 on the circle, against +1.61. The first block's gate also closes far more than
its open-gate fraction implies. The break happens in the first ~100 steps.

Checks at initialization (no training) explain where it comes from. ReLU outputs are all positive, so every block
adds a vector in roughly the same direction, and the stream piles up:

- At 96 layers the stream is about 38× larger at the last block than at the first.
- 80% of its energy is one vector shared by every example.
- The starting loss on digits is 57.8, against 2.6 for tanh.
- Within 10 steps the output layer's weights triple.

Activations whose output averages zero (tanh, and a soft threshold with hard 0/1 gates) do not pile up. Those
with a positive mean (ReLU, and tanh + 1) do.

## Disclosure

Before writing this, I ran 100-step smoke tests of the warm-up and zero-output conditions below, on one seed of
digits at 96 layers. In both, transport fell within the first 100 steps: to about +0.5 with warm-up and to about
0.0 with the zero-output start. Experiment 11's predictions were written knowing this. Nothing else from
experiments 9–12 was run beyond initialization checks.

## Common design

Residual networks, width 64, α = 1/√depth, SGD lr 0.05, batch 64, 6,000 steps, seeds 0–2, both tasks (digits and
the clean circle). This is identical to experiment 8 except for the one change named in each condition.

**Primary measure:** `ln_transport` at the first crossing of training loss 0.03, interpolated in log-loss
(`e8_analyze.at_loss_key`).

**Reference groups,** taken from experiment 8 at the same seeds: R = plain ReLU at 96 layers, T = tanh at 96 layers.

**Rule:** a condition is **rescued** on a task if its mean exceeds R's by more than 2·sqrt(sd_R² + sd²) (the rule
of experiments 4, 6 and 7). Runs that never reach loss 0.03 are excluded and counted. If fewer than 2 runs of a
condition reach it, that condition is untestable on that task.

## Experiment 9: signed ReLU (the main test)

`branch_sign=True` multiplies each block's output units by a fixed random ±1 sign, drawn separately for each
block. The gates, their open fraction (0.50 at initialization) and the weights at initialization are exactly
ReLU's, but block outputs no longer share a direction. At initialization the stream grows 1.2–1.3× instead of
38×, and the digits loss starts at 2.7.

- **P9 (primary):** signed ReLU at 96 layers is rescued on both tasks.
- **P9b:** signed ReLU shows no depth break. Its transport at 96 layers is not below its own transport at 24
  layers by more than the threshold, on both tasks.

## Experiment 10: the two activation properties separated

- **shrink:** odd soft threshold, zero mean, hard 0/1 gates. The threshold is 0.4 on digits and 0.12 on the
  circle, chosen at initialization so about half the gates are open.
  **P10:** shrink at 96 layers is rescued on both tasks.
- **tanh+1:** tanh's exact derivative with a positive mean. **Exploratory, no prediction.** Its pile-up at 96
  layers is about 9×, similar to ReLU at 48 layers, which did not break. So whether it breaks is informative
  either way.

## Experiment 11: is it a learning-rate shock?

- **warm-up:** learning rate rises linearly from 0 to 0.05 over the first 500 steps.
- **zero-out:** the output layer starts at zero, so the starting logits are zero and the starting loss is normal,
  but the stream still piles up.

The pile-up hypothesis says the problem is the stream itself, not the first step's size. The smoke tests point
the same way.

- **P11a:** warm-up is not rescued on both tasks.
- **P11b:** zero-out is not rescued on both tasks.

## Experiment 12: does the break grow with depth?

Plain ReLU at 64, 80 and 128 layers, with experiment 8's 12–96 alongside.

- **P12:** transport at 128 layers is lower than at 48 layers by more than the threshold, on both tasks.
- **Exploratory:** initial stream growth against transport, to locate where the break begins.

## Decision on the hypothesis

The positive-mean pile-up hypothesis is **supported** if P9 and P10 both hold on both tasks. It is **refuted** if
P9 fails on both tasks. Anything else counts as mixed and is reported as such.
