# G7A: original PathCond + Adam vs Adam and G5

**Date:** 2026-10-28. **Source:** [GAUGE_G7A_PREREGISTRATION.md](../../GAUGE_G7A_PREREGISTRATION.md), [executable](../../experiments/g7_official_pathcond.py), [clean-machine tests](../../tests/test_g7_official_pathcond.py). **Original authors' source:** [Artim436/pathcond @ 535b202e](https://github.com/Artim436/pathcond/tree/535b202e3476c64d5e7e9ec5e817344fb5cfd787), used via its actual `rescaling_path_cond` entry point (no reimplementation), CC BY 4.0. Original paper: Lebeurrier, Vayer, Gribonval (ICML 2026), https://proceedings.mlr.press/v306/lebeurrier26a.html .

## Chain of custody and numerical smoke failure

- Protocol committed before any G7A training. First CI run [40791460819](https://github.com/maaronfanberg-lab/me-/actions/runs/40791460819) installed upstream successfully and verified G5 cross-framework equivalence but failed its strict smoke test: PathCond shifted initial logits by **4.32671726e-7**, exceeding preregistered `<1e-7`.
- Before any tuning or holdout had been run, a protocol addendum documented the smoke failure and an *exploratory practical numerical tolerance* `<1e-3` for allowing subsequent training to run. **The original H1 scientific threshold `<1e-7` was NOT relaxed.** All H2/H3 methods, seeds, rates, datasets, and success criteria stayed unchanged.
- Clean GitHub Actions run **[40791722049](https://github.com/maaronfanberg-lab/me-/actions/runs/40791722049) completed SUCCESS** and generated the full `lapse-g7a-full-results` JSON artifact. GitHub runner: Python 3.11, torch 2.5.1+cpu, torchvision 0.20.1+cpu, NumPy 2.3.5, sklearn 1.8.0.
- 48 tuning configurations (4 task/depth cells × 3 methods × 2 rates × 2 tuning seeds), 12 selected configurations, **36 untouched-seed heldout evaluations**, all complete without numerical training failure. Three heldout seeds 50/51/52, tuning seeds 40/41. 100 mini-batch updates per run.

## Locked scientific decisions

- **H1 FAIL:** official PathCond initial function preserved within the strict 1e-7 threshold on **10/12**, not 12/12, normal-coordinate holdout models. Two failing initial errors were **1.80036e-7** (digits, depth3, seed52) and **1.03035e-7** (circle, depth3, seed52). Other 10 errors were below threshold. On equivalent reparameterized copies some further PathCond initialization errors were >1e-7, recorded. All errors remained below the exploratory practical 1e-3 threshold. No model was dropped.
- **H2 PASS under locked rule:** PathCond+Adam improved mean heldout test cross entropy over Adam in **3/4** cells, matching the preregistered required 3/4.
- **H3 PASS under locked rule:** PathCond+Adam had smaller **mean terminal gauge logit gap** than ordinary Adam in **4/4** cells, exceeding required 3/4. This means improved **robustness**, not exact coordinate invariance. G5 stayed markedly more gauge-stable but generally learned more slowly.
- **No software/benchmark training failures** across tuning/holdout. A CI *software* check passing does not mean all *scientific* hypotheses passed.

## Heldout means (three independent seeds per cell; lower CE is better)

| Task | Hidden depth | Adam CE | Official PathCond+Adam CE | G5 CE | Adam gauge logit gap | PathCond gauge logit gap |
|---|---:|---:|---:|---:|---:|---:|
| digits | 3 | 0.168212 | **0.159970** | 1.049869 | 16.1083 | **1.5852** |
| digits | 6 | 0.281713 | **0.263150** | 1.306713 | 32.3362 | **10.4546** |
| circle | 3 | 0.110139 | **0.105447** | 0.290187 | 9.8124 | **1.2313** |
| circle | 6 | **0.042208** | 0.060547 | 0.208888 | 8.9593 | **5.9974** |

Raw G5 terminal gauge logit gaps are near float64 roundoff and round to zero at six decimal places. That doesn't mean its performance is equivalent to Adam. The PathCond transformed models were **each conditioned independently from their own equivalent starting coordinates**, so this tests whether one-time preprocessing can reduce initial gauge sensitivity, not whether post-conditioned Adam becomes mathematically gauge-equivariant.

### Heldout test accuracies

| Task / depth | Adam | PathCond+Adam | G5 |
|---|---:|---:|---:|
| digits / 3 | 94.72% | 95.19% | 69.17% |
| digits / 6 | 92.78% | 93.15% | 65.56% |
| circle / 3 | **96.48%** | 96.20% | 84.07% |
| circle / 6 | **97.96%** | 97.31% | 90.74% |

### Compute overhead

Normal-coordinate *tuning run* timings (100 updates on GitHub runner, median of the 2 selected-rate tuning runs): Adam 0.10–0.155 seconds per run; PathCond+Adam 0.186–0.335 seconds; G5 0.119–0.196 seconds. PathCond+Adam therefore costs roughly **1.9–2.2×** Adam's short-run wall time on these very small CPU networks, including the one-time conditioning. Report holdout stress timing separately because it trains **two networks** and applies PathCond **twice**, which is not the same as normal-coordinate training overhead. These very short wall-clock measurements have noise and do not extrapolate to larger networks/epochs.

### Learning rate selection

Both Adam and PathCond+Adam selected `lr=0.003` in all four cells; G5 selected `lr=0.05` in all four cells, using only validation means over seeds 40 and 41. No test-set retuning occurred.

## Interpretation and limits

The important outcome is a **trade-off**: official PathCond at initialization reduced functional coordinate sensitivity relative to unconditioned Adam in four small-model comparisons and slightly improved test CE in three, while G5 had much stronger gauge equivariance but substantially worse CE. PathCond **does not guarantee gauge-invariant Adam training** here. The two H1 threshold violations highlight float32 internal casting in upstream `optimize_rescaling_polynomial` and its effects on float64 models. This is a numerical observation, not a proof of the complete cause. Keep H1 recorded as failure.

Sample size is only 3 heldout seeds per cell; no inferential significance claimed. Results concern **plain ReLU MLPs** at widths 32, depths 3/6, 100 steps, two relatively easy datasets, fixed learning-rate grids. No results are claimed for our one-matrix residual networks because the original upstream MLP rescaling code assumes a sequential graph. The original ICML paper's reported benefits were not necessarily established under Adam; this is a distinct evaluation.

## Reproduction

```bash
cd experiments/lapse-meter
# Follow .github/workflows/lapse-g7-official-pathcond.yml to install CPU torch,
# torchvision, scikit-learn and exact original PathCond commit.
python tests/test_g7_official_pathcond.py
python experiments/g7_official_pathcond.py results/g7a/full.json
```

The official GitHub Actions artifact is `lapse-g7a-full-results` from run **40791722049**. It contains all 48 tuning records, 12 chosen configurations and all 36 complete individual heldout records including checkpoints and numerical gauge drifts. No records were removed.
