# Experiment 50: can the per-step fix rescue the language model ×10 with a larger constant? (written before any run)

Written 2026-10-29, after the corpus rerun (CORRECTIONS 72). Committed with `ci/e50.txt` and
`experiments/e50_analyze.py` before any run.

With c ∈ {4, 16, 64}, the language model ×10 learned nothing past letter frequencies: 0 of 35 runs. Its readout steps
may simply be too small. Plain training, the limit of large c, collapses (experiment 28).

**Design.** c ∈ {256, 1,024, 4,096, 16,384}, seeds 0–4, 20 runs, on the pinned corpus. Outcome rule as in
experiment 48.

**Prediction (about 50%).** **P50:** some c gives at least 3 of 5 healthy runs. If none does, there is no window,
and this fix does not work for this setting.
