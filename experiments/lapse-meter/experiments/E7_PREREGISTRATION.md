# Experiment 7: is the tilt independent of depth at matched training loss? (written before any run)

Written 2026-10-27, before running `experiments/e7.py`. This file, `e7.py` and `e7_analyze.py` are committed to
GitHub before any experiment-7 run. Results go in the README and `results/e7_analysis.md`.

**Why.** Experiment 1 found that residual tanh networks settle at nearly the same total tilt T* from 12 to 96
layers, but it read T* after a fixed 4,000 steps. Experiment 6 then showed that T* keeps rising as training loss
falls. Networks of different depth reach different losses in 4,000 steps, so experiment 1's depth-independence
could be real, or could be two effects cancelling (deeper networks fitting faster or slower while also tilting
differently). Comparing depths at the same training loss separates these.

**Design.** Residual networks, width 64, α = 1/√depth removed (T* as before), SGD lr 0.05, batch 64,
6,000 steps, 3 seeds. Depths 6, 12, 24, 48, 96. Two activations: tanh and ReLU. Two tasks that both reach very
low training loss: handwritten digits (10 classes) and the clean circle. T* and full training loss are logged
every 50 steps. T* is read at the first crossing of training loss below each level L* in {0.3, 0.1, 0.03, 0.01},
interpolated linearly in log-loss, exactly as in experiment 6 (`e6_analyze.at_loss`). Runs that never reach a
level are excluded at that level and counted in the table.

**Prediction (tanh, the confirmatory test).** At every loss level where all four depths 12, 24, 48 and 96 have
at least two runs, no pair of those depths differs in mean T* by more than 2 × sqrt(sd₁² + sd₂²) (the rule used
in experiments 4 and 6). The prediction holds for a task if it holds at every such level; it fails for a task if
any pair at any level exceeds the threshold.

**Secondary (tanh).** Over depths 12–96 at each level, the least-squares slope of T* against log₂(depth) is
reported with its sign. Depth-independence predicts slopes near zero; a consistent sign across levels and tasks
would mean depth does matter at matched loss even if no pair crosses the threshold.

**ReLU: exploratory, no prediction.** Experiment 1 found deep residual ReLU networks drifting. The same table is
reported for ReLU, with no pass or fail.

**Depth 6** is reported but excluded from the test, as in experiment 1, where shallow networks sat below the
deep-network value.
