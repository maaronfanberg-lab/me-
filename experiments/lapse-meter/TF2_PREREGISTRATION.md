# Transformer, part 2: is the pile-up the switch? (written before any run)

Written 2026-10-29. The no-normalization transformer did not collapse (`results/e55_analysis.md`; train loss 0.36,
transport +0.88 at 32 blocks). Its MLP branches use two matrices, which did not pile up in the MLP study
(experiment 17).

**Manipulation.** Replace each MLP branch with the one-matrix ReLU branch h += a·relu(W h), which piles up.
32 blocks, 3 seeds each. Conditions:

- onemat;
- onemat + kick cap 10;
- onemat + readout batch centering;
- bcenter on the original two-matrix transformer (the control).

**Predictions.**

- **T2a:** onemat collapses: final transport below +0.3 in at least 2 of 3 runs, or failure to train (final
  loss above 3.17).
- **T2b:** onemat + bcenter does not collapse, in at least 2 of 3 runs.
- **T2c:** onemat + cap 10 does not collapse, in at least 2 of 3 runs.
- **Reported:** final stream growth and the shared share of the last stream at the end of training.
