# Experiment 28: does the kick account carry over to language modelling? (written before any run)

Written 2026-10-28, before any experiment-28 run. Committed with `experiments/e28_jobs.txt`, the per-run
predictions `experiments/e28_predictions.json` and `experiments/e28_analyze.py`.

## Why

All results so far come from two small classification tasks. Here the task is different: predict the next
character from the previous 16, one-hot (82 characters, the corpus of experiment 3). There are 8,000 fixed
training windows and 1,000 held-out test windows (`e4.make("lm")`).

## Measured at initialization

For 96-layer residual ReLU, width 64:

- At natural input scale the stream piles up **37×** (the full pile-up), but one-hot inputs are small, so the kick
  is only **15–19**.
- Multiplying the inputs by 10 raises the kick to **2,756–3,196**.
- A kick cap of 10, or a final LayerNorm (kick 0.8–0.9), brings it back down.

So the pile-up account predicts natural-scale ReLU breaks, while the kick account predicts it does not, and
predicts that ×10 inputs break it.

## Design

96 layers, width 64, SGD lr 0.05, batch 64, 6,000 steps, seeds 0–2. Each ReLU condition is compared with its signed
twin (same weights and gates, no pile-up):

| condition | twin |
|---|---|
| ReLU, inputs ×1 | signed ×1 |
| ReLU, inputs ×10 | signed ×10 |
| ReLU, inputs ×10, kick cap 10 | signed ×10 |
| ReLU, inputs ×10, final LayerNorm | signed ×10, final LayerNorm |

**Level.** The lowest of training loss 1.0, 1.5, 2.0, 2.5 and 3.0 nats that both groups reach in at least 2 runs.

**Failed to train.** Final training loss above 3.17 nats, the letter-frequency entropy, i.e. no better than
guessing from character frequencies.

**Healthy.** ReLU mean transport not below the twin's by more than 2·sqrt(sd₁² + sd₂²), and no more failed runs.

**Per-run rule.** Broken if the effective step-one kick exceeds 124. That is the more cautious of the two cutoffs
from experiment 22, fixed now because this task has no cutoff of its own. The share it gets right is reported, not
tested.

## Predictions

- **P28a:** ReLU ×1 is healthy. This is the key test: the full 37× pile-up with a small kick.
- **P28b:** ReLU ×10 is broken.
- **P28c:** ReLU ×10 with kick cap 10 is healthy.
- **P28d:** ReLU ×10 with a final LayerNorm is healthy.
- **Reported, not tested:** final training and test loss for every condition.

## Decision

The kick account **carries over** if P28a–P28d all hold. It **fails to carry over** if P28a or P28b fails.
