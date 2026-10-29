# Experiment 54: do the findings survive an independent PyTorch implementation? (written before any run)

Written 2026-10-29. `experiments/torch_replicate.py` shares nothing with `lapse/` but the data. It is float32 and
uses autograd. 96-layer one-matrix residual ReLU, SGD lr 0.05, both tasks, seeds 0–4, run on GitHub Actions
(PyTorch CPU).

Conditions:

- plain;
- kick cap 10 every step;
- per-step readout normalization (64 / mean |h_L|²).

The outcome rule is the usual one: broken if transport at loss 0.03 (falling back to 0.1, then 0.3) is below +0.3,
or if the run fails to train.

**Predictions.**

- **P54a:** plain is broken on both tasks.
- **P54b:** cap 10 is healthy on both tasks.
- **P54c:** the per-step readout normalization is healthy on both tasks.
