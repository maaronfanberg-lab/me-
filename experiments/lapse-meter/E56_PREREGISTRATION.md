# Experiment 56: two readout-side fixes, DyT and live batch centering (written before any run)

Written 2026-10-29. Committed with `ci/e56.txt` and `experiments/e56_analyze.py` before any run.

**Modes** (`lapse/nets_ln.py`, gradients checked by finite differences):

- `dyt`: readout input tanh(h_L), the DyT of Zhu et al. 2025 with α = 1. Measured step-one kick 0.1–1.3.
- `bcenter`: readout input h_L minus the current batch's mean. This is the live version of experiment 29's stale
  centering. Measured kick: digits 171, circle 20, language model ×10 20, digits 192 layers 4,645.

**Design.** Plain residual ReLU with each mode, in four settings: digits 96, circle 96, digits 192, language model
×10. Seeds 0–4, 40 runs. Outcome rule as in experiment 47.

**Predictions.**

- **P56a (kick account):** bcenter is healthy on digits 96, circle 96 and the language model ×10, and broken on
  digits 192.
- **P56b (my bet, about 55%):** dyt is broken on digits 96. Its kick is tiny, but the piled-up input saturates tanh,
  and the readout's gradient into the stream is multiplied by 1 − tanh², which is near 0. That would starve the blocks.
  The kick account predicts healthy.
- **Reported:** dyt in every setting.
