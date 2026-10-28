# Experiments 13–16: pile-up and first-step shock (written before any run)

Written 2026-10-27, after experiments 9–12 and before any experiment 13–16 run. Committed to GitHub with the code,
job list and `experiments/e13_16_analyze.py` before the first run.

## Where things stand

Experiments 9–12 (see `results/e9_12_analysis.md`) found:

- Removing the positive-mean pile-up rescues 96-layer ReLU. Signed ReLU and the zero-mean soft threshold both
  carry the gradient back as well as tanh does.
- A 500-step learning-rate warm-up also rescues it on digits, against my prediction P11a. I had read a 100-step
  smoke test as showing the collapse, but transport recovered after that point.
- Starting the output layer at zero does not rescue it.

So the pile-up alone is not fatal. The working hypothesis is now: **the collapse is a first-steps shock.** The
piled-up stream makes the first full-size SGD steps very large, and the network does not recover from those steps.
These four experiments test that, with the dose and the location of the shock varied.

## Common design

Identical to experiments 8–12: 96 layers unless noted, width 64, α = 1/√depth, SGD lr 0.05, batch 64,
6,000 steps, seeds 0–2, digits and the clean circle.

**Primary measure:** `ln_transport` at the first crossing of training loss 0.03.

**Rule:** **rescued** = mean above plain ReLU at the same depth by more than 2·sqrt(sd₁² + sd₂²). The reference
groups are from experiment 8 (96 layers) and experiment 12 (128 layers). Runs not reaching the loss level are
excluded and counted; fewer than 2 runs makes a condition untestable on that task.

**Added after experiment 12.** Excluding runs that never reach the loss level can hide the worst outcome. In
experiment 12, one circle run at 128 layers never trained at all: its loss stayed at chance, 0.693, for all
6,000 steps. Every table therefore also reports, for each condition, how many runs **failed to train**, meaning
final training loss above half of ln(number of classes). This count is reported, not tested.

## Experiment 13: how much warm-up is needed?

Linear warm-up over w = 50, 150 or 1,500 steps, alongside 0 (experiment 8) and 500 (experiment 11).

- **P13a:** w = 1,500 is rescued on both tasks.
- **P13b:** w = 50 is not rescued on both tasks. This is a guess: 50 steps may be too short to avoid the shock.
- **Reported, no pass/fail:** the mean transport across w = 0, 50, 150, 500 and 1,500.

## Experiment 14: where does the shock land?

A 500-step warm-up applied to only one part of the network, by scaling that part's gradients, which is exactly a
part-wise learning-rate warm-up for SGD. Either the output layer warms up and the blocks do not, or the reverse.

At initialization the piled-up stream makes the gradient arriving at the early blocks about 10× too large
(transport +2.3 on digits). So the prediction is that the blocks' first steps are the damaging ones.

- **P14a:** warm-up on the blocks only is rescued on both tasks.
- **P14b:** warm-up on the output layer only is not rescued on both tasks.

## Experiment 15: how much pile-up is too much?

Signed ReLU in which each sign is +1 with probability q = 0.625, 0.75 or 0.875, alongside q = 0.5 (experiment 9)
and q = 1 (plain ReLU, which this setting reproduces bit for bit). At initialization the stream grows about 2.6×,
6.4× and 15× at these q, against 1.2× at q = 0.5 and 38× at q = 1. In experiment 12 plain ReLU broke at around
17× (64 layers, seed-dependent).

- **P15a:** q = 0.75 is rescued on both tasks.
- **P15b:** q = 0.625 is rescued on both tasks.
- **q = 0.875:** exploratory, no prediction. It sits near where experiment 12's break began.

## Experiment 16: does warm-up still work at 128 layers?

Plain ReLU at 128 layers (growth 73× at initialization) with a 500-step warm-up, compared with plain ReLU at 128
layers from experiment 12.

- **P16:** rescued on both tasks.

## Decision

The first-step-shock hypothesis is **supported** if P13a, P14a and P16 all hold. It is **refuted** if P13a fails
on both tasks (even a long warm-up does not help). Anything else is mixed.
