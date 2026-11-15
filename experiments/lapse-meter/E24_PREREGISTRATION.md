# Experiment 24: is the readout kick a cause? Cap it directly (written before any run)

Written 2026-10-28. Committed with `experiments/e24_jobs.txt`, the per-run predictions
`experiments/e24_predictions.json` and `experiments/e24_analyze.py` before any run.

## Why

Experiments 22–23 showed that the readout kick at initialization predicts the collapse. But every manipulation so
far changed the kick indirectly. A lower readout learning rate or smaller inputs change other things too.

## The manipulation

`kick_cap = C`: at every step, if the readout's proposed SGD update would change the minibatch's logits by more
than C (RMS), the readout's update alone is scaled down to exactly C. The blocks' updates are untouched, so the
blocks still receive their full initial gradients.

Checks before any run:

- A cap above every kick reproduces the uncapped run bit for bit.
- A cap of 10 on 96-layer ReLU binds only in roughly the first 40 steps.

## Design

- Plain residual ReLU, 96 layers, width 64, SGD lr 0.05, 6,000 steps, seeds 0–2, digits and the clean circle.
- Caps C ∈ {3, 10, 30, 100, 300, 1000}. The uncapped reference is experiment 8.

**z-loss conditions.** Added because it is the standard logit control in large language models (Wortsman et al.
2023): an auxiliary loss z·mean(log²Z), with z = 1e-4 (the usual value) and 1e-2. It acts on the gradient only;
the logged loss stays cross-entropy. Kick theory predicts z-loss does not help, because its gradient also reaches
the readout multiplied by the huge stream. At z = 1e-2 it *raises* the step-one kick on digits to 3,500–5,100.

**Outcome per run.** As in experiment 23: broken if transport at loss 0.03 is below +0.3 (falling back to 0.1, then
0.3, if 0.03 is never reached), or if the run fails to train.

## Predictions

- **P24a:** C ≤ 30 is healthy (at least 2 of 3 runs) on both tasks.
- **P24b:** C = 1000 is broken (at least 2 of 3 runs) on digits. On the circle a cap of 1000 is above every kick,
  so it never binds and should reproduce experiment 8 exactly; reported, not tested.
- **P24c:** across the 18 cap runs of each task, the Spearman correlation between log(effective step-one kick) and
  transport is −0.6 or stronger.
- **P24d:** z-loss at 1e-4 is not rescued: broken in at least 2 of 3 runs on both tasks.
- **P24e:** z-loss at 1e-2 is not rescued, the same way.
- **Per-run rule** (`e24_predictions.json`): broken if the effective step-one kick is above the cutoff fixed in
  experiment 22 (digits 328, circle 124). The share it gets right is reported, not tested. It is already known to
  be wrong for circle seed 0, which collapsed in experiment 8 at a kick of 108.

## Decision

The readout kick is a **cause** of the collapse if P24a, P24b and P24c hold. If P24a fails on both tasks, the
kick is a correlate, not a cause. Anything else is mixed.
