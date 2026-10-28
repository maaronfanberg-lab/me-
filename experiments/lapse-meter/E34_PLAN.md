# Experiment 34 (exploratory): why the network tears down its own pile-up (written before any run)

Written 2026-10-28, 18:45, after experiments 24–33. Exploratory: the questions and how each is read are fixed now;
nothing is tested. A pre-registered test (experiment 35) follows once these traces suggest an account.

## What is known

In plain 96-layer residual ReLU (digits, seed 0; CORRECTIONS 53 and 57):

- The last stream shrinks 234 → 105 at step 1 and → 20 at step 2.
- Gates open per example fall from 0.50 to 0.26.
- Transport then drains over about 100 steps.
- Capped, step 1 is the same (105) but step 2 is 83, not 20.
- Cutting the readout-to-stream gradient along the shared direction m̂ makes the stream *grow* and the run diverge.

## Questions and their readings

**Q1. What moves the pre-activations during the teardown?**

For every block and step, the change in pre-activations splits exactly:

```
z_new − z_old = ΔW·h_old + Δb  (own: the block's own update)  +  W_new·(h_new − h_old)  (inherited: the stream feeding it changed)
```

Read: the RMS of each part, and the share of each that is common to all examples (the batch mean), at steps 1–5,
averaged over blocks.

**Q2. Which way does the own part push, and on which units?**

Read: the correlation, over units, between each unit's mean own-part change and the shared stream direction m
projected through W (W·m). Also the fraction of the gate closings at steps 1–2 that the own part alone would cause
(sign of z_old + own part, against sign of z_old).

**Q3. What ends the teardown?**

Read: the shared error |d̄| = |mean_i (p_i − y_i)| and the stream's step-to-step shrink, steps 0–50. The candidate
answer is that the teardown stops when the shared error has been corrected. Read: does the shrink fall to under
10% per step within a step of |d̄| falling below half its peak?

**Q4. Why does transport keep draining after the teardown?**

Read: per-block open-gate fraction and per-block stream-gradient size at steps 2, 20, 100, 500 and 2,000. Where
in depth does the backward signal stop?

## Design

- Plain 96-layer residual ReLU, width 64, SGD lr 0.05.
- Both tasks, seeds 0–4.
- Traced every step for 300 steps, then every 10 steps to step 3,000. These are two runs from the same start;
  the code is deterministic, which the script checks.
- Controls: kick cap 10 and the signed twin, same seeds.
- Every run is the runner's own run (`probe_run.py`) with a read-only hook, so nothing about training changes.
