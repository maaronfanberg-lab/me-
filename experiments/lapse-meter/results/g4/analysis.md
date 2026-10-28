# Gauge G4: entire learning trajectories under positive ReLU gauges

**Protocol:** [GAUGE_G4_PREREGISTRATION.md](../../GAUGE_G4_PREREGISTRATION.md), including the timing-audit addendum. **Executable:** [g4_trajectory.py](../../experiments/g4_trajectory.py). **Regression tests:** [test_g4_trajectory.py](../../tests/test_g4_trajectory.py).

## Result
**H1 held in 8/8 frozen-code confirmation comparisons (seeds 8/9)**: plain depth8 and residual depth24, two positive-gauge choices (uniform x4 or neuronwise 1/8..8), 150 identical minibatch SGD-style steps (batch64), optimizer `theta <- theta*exp(-2*theta*grad)`. Seven checkpoints per run. Maximum logit discrepancy: **1.24e-13** across the held-out 8, maximum corresponding parameter gauge error **2.11e-14**, maximum first-batch elementwise `theta*grad` discrepancy **4.44e-16**.

**H2, SGD negative control, held in 8/8:** one standard SGD step from the same gauge-equivalent initialization altered logits. Minimum observed maximum-logit discrepancy across the eight controls **0.0352**. For some residual scalings this error was in the thousands; the negative control was intentionally limited to one update.

The initial development seeds 6/7 (eight additional comparisons) also passed, maximum logit discrepancy **2.84e-13**. They are **not** counted as independent code-frozen confirmation; the preregistration documents that the source was committed after those development runs. The held-out seeds were designated after code commit and before execution.

## Optimization is not equally good in all networks
150 steps of the coordinate-equivariant log updater, no training-accuracy selection:

| Architecture | Seed | Start train loss | End train loss | End test accuracy |
|---|---:|---:|---:|---:|
| residual 24 | 6 (dev) | 5.561 | 0.232 | 92.4% |
| residual 24 | 7 (dev) | 5.055 | 0.294 | 85.9% |
| plain 8 | 6 (dev) | 2.307 | 2.253 | 11.6% |
| plain 8 | 7 (dev) | 2.301 | 1.898 | 25.9% |
| residual 24 | 8 (held out) | 5.439 | 0.293 | 90.9% |
| residual 24 | 9 (held out) | 4.734 | 0.286 | 89.9% |
| plain 8 | 8 (held out) | 2.306 | 1.794 | 30.0% |
| plain 8 | 9 (held out) | 2.301 | 2.036 | 25.4% |

The optimizer **freezes all zero-valued weights and biases**; it is not an effective general-purpose optimizer even though its trajectories are gauge-equivariant. The next G5 study targets that defect. A positive scaling symmetry and equivalent updates are established background from Path-SGD / G-SGD; G4 is an experimental demonstration, not an original general theorem.

## Validation
- **40 local synthetic tests passed**, covering finite differences in log parameter coordinates, ReLU signed-residual branches, nonmutating gauge transforms, invalid eta, zero/sign preservation, and first-step equivalence.
- Held-out G4 JSON rerun was **byte-identical**, SHA-256 `b787178e8f700f727451301e3447273db0ee86304a02248c1ad1295273361cbc` (OPENBLAS_NUM_THREADS=1).
- Full JSON available in accompanying local research results archive. The GitHub CI workflow added with this research is intended to regenerate and upload independent artifacts, but a green GitHub-hosted check is not claimed unless the workflow completes successfully.
- The local run used a minimal copy of the repository MLP implementation, compared against the GitHub source; reproducing directly from checkout is the purpose of the CI job.

## Prior work
Neyshabur et al. (2015), [Path-SGD](https://papers.neurips.cc/paper_files/paper/2015/file/eaa32c96f620053cf442ad32258076b9-Paper.pdf); Meng et al., [G-SGD](https://arxiv.org/abs/1802.03713); Lebeurrier et al. (ICML 2026), [Path-conditioned training](https://proceedings.mlr.press/v306/lebeurrier26a.html).
