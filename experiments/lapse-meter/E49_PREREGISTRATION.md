# Experiment 49: the per-step fix's weak spot (written before any run)

Written 2026-10-29, after experiment 48. Committed with `ci/e49.txt` and `experiments/e49_analyze.py` before any run.

**Background.** On the language model ×10, `out_lr_norm = 64` was healthy in only 3 of 5 runs (experiment 48).
The division is now guarded against a zero stream.

**Design.** Language model ×10, 96 layers, seeds 0–9, with the readout normalization constant c ∈ {64, 16, 4}:
30 runs. A smaller c gives a smaller readout step, so a smaller bound on the kick. The outcome rule is experiment
48's.

**Predictions.**

- **P49a:** c = 16 is healthy in at least 8 of 10 runs.
- **P49b:** c = 4 is healthy in at least 8 of 10 runs.
- **P49c:** c = 64 has fewer healthy runs than c = 16.
