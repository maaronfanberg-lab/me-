# Experiment 21: which part of Adam raises the transport? (written before any run)

Written 2026-10-28, before any experiment-21 run. Committed to GitHub with the code, the job list
(`experiments/e21_jobs.txt`) and `experiments/e21_analyze.py` first.

**Why.** In experiment 18, Adam left networks with clearly higher transport than SGD:

- digits, 96 layers: +1.42 for ReLU and +1.47 for tanh under Adam, against +0.82 for tanh under SGD
- the circle: +2.21 for ReLU under Adam, against +1.61 for tanh under SGD

Adam differs from SGD in two ways. It normalizes each parameter's step by that parameter's recent gradient size,
and it uses momentum. This experiment separates the two.

**Design.**

- Residual tanh networks at 24 layers. This avoids the ReLU pile-up studied in experiments 8–20, so only the
  optimizer differs.
- Width 64, batch 64, 6,000 steps, seeds 0–2, digits and the clean circle, as in experiment 8. Experiment 8's
  tanh 24-layer runs are the SGD reference (lr 0.05).
- Conditions:
  - **Adam**, lr 0.001: normalization and momentum.
  - **RMSprop**, lr 0.001: implemented as Adam with β₁ = 0, so normalization without momentum.
  - **Momentum SGD**, μ = 0.9, lr 0.005: momentum without normalization. The lr is a tenth of SGD's, so its
    steady-state step matches SGD at 0.05.
  - **SGD at lr 0.02 and 0.1:** exploratory, no prediction. These show whether step size alone moves transport.

**Measure and rule.** As in experiments 9–20:

- `ln_transport` at the first crossing of training loss 0.03.
- **Above** = mean higher than SGD's by more than 2·sqrt(sd₁² + sd₂²).
- Runs that fail to train are counted. Fewer than 2 runs reaching the loss level makes a condition untestable.

**Hypothesis H21:** per-parameter normalization, not momentum, is what raises transport.

- **P21a:** Adam is above SGD on both tasks (replicates experiment 18 in a different network).
- **P21b:** RMSprop is above SGD on both tasks.
- **P21c:** momentum SGD is not above SGD on either task.

**Decision.** H21 is **supported** if P21b and P21c both hold. It is **refuted** if P21b fails on both tasks.
Anything else is mixed.
