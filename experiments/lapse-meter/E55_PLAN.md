# Experiment 55 (exploratory): does the kick matter in a transformer? (written before any run)

Written 2026-10-29. A small transformer with no normalization (`experiments/torch_transformer.py`), 8 and 32 blocks,
on the pinned character corpus. Conditions: plain, kick cap 10, per-step readout normalization, final LayerNorm.
3 seeds each, 24 runs.

This is exploratory because the architecture is new here: attention mixes positions, and learned embeddings have no
ReLU pile-up at the input.

**Question.** Does plain training break where the fixes do not (higher loss, divergence, or lower transport), and
does that get worse with depth?

**Read.** Final training and test loss and final transport, against the fixes.
