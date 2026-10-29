# G8A results: final float32 cast is the cause of PathCond's initial logit drift in tested double networks

**Date:** 2026-10-28. **Protocol:** [GAUGE_G8A_PREREGISTRATION.md](../../GAUGE_G8A_PREREGISTRATION.md), committed before testing target seeds 60–69. **Executable:** [g8_pathcond_precision.py](../../experiments/g8_pathcond_precision.py); **tests:** [test_g8_pathcond_precision.py](../../tests/test_g8_pathcond_precision.py). Official upstream PathCond pinned exactly at [535b202e3476c64d5e7e9ec5e817344fb5cfd787](https://github.com/Artim436/pathcond/tree/535b202e3476c64d5e7e9ec5e817344fb5cfd787), original CC BY 4.0 code. No upstream code changed.

**Reproducibility:** GitHub Actions [40795731073](https://github.com/maaronfanberg-lab/me-/actions/runs/40795731073), completed **SUCCESS**, including exact-original upstream install, unused-seed smoke, all 80 model comparisons and artifact upload **`lapse-g8a-precision-complete`**, artifact id **12862914975**. Full artifact was downloaded and independently inspected: exactly 80 usable records, no failed networks, prereg decisions in JSON.

## All three preregistered hypotheses passed

- **H1 PASS (80/80, required >=72/80)**: the diagnostic variant retaining 64-bit BZ factors produced maximum full heldout-input logit changes **<1e-10** on every model/gauge, with the worst observed difference **7.1054e-15**.
- **H2 PASS (80/80, required all 80 and >=64 quantized)**: taking the same double factors and *rounding them to 32 bits* produced parameters **exactly matching** the unmodified official PathCond transformations, on all 80 cases. Max A-vs-C parameter error was **0.0** (not merely <1e-10). All 80 sets of factors had nonzero quantization errors.
- **H3 PASS (80/80 eligible, required >=75% with >=10 cases)**: every official run showed initial drift >1e-10, and the 64-bit diagnostic reduced that max logit error by >10x in all **80/80** cases.
- **H4 descriptive:** the released upstream variant exceeded G7's strict 1e-7 initial-logit preservation rule in **34/80** conditions, the 64-bit diagnostic in **0/80**. This does not change the G7 record of 2/12 failing runs.

## Aggregate prediction errors

| Quantity | Released official (BZ cast to float32) | Double-precision diagnostic (no cast) |
|---|---:|---:|
| Median max heldout-logit error | 7.36676e-8 | 7.49401e-16 |
| Largest max heldout-logit error | 1.10306e-6 | 7.10543e-15 |
| Cases with max error >=1e-7 | 34/80 | 0/80 |
| Cases with max error <1e-10 | 0/80 | 80/80 |

These are not training/generative performance metrics; they are **pure initial-function invariance errors** after reparameterization on never-trained networks.

## Detailed matrix: number exceeding 1e-7

Each group has 10 fresh seeds, 60–69, and used the same original or independently neuronwise-rescaled starting network. Total 80 cases.

| Dataset | Depth | Gauge | Published upstream | 64-bit diagnostic | Max published error |
|---|---:|---|---:|---:|---:|
| digits | 3 | identity | 8/10 | 0/10 | 1.08965e-6 |
| digits | 3 | neuronwise | 10/10 | 0/10 | 1.10306e-6 |
| digits | 6 | identity | 3/10 | 0/10 | 1.89981e-7 |
| digits | 6 | neuronwise | 6/10 | 0/10 | 7.80636e-7 |
| circle | 3 | identity | 2/10 | 0/10 | 1.22011e-7 |
| circle | 3 | neuronwise | 5/10 | 0/10 | 1.54250e-7 |
| circle | 6 | identity | 0/10 | 0/10 | 3.65189e-8 |
| circle | 6 | neuronwise | 0/10 | 0/10 | 6.70474e-8 |

## Source-level cause, strongly isolated

The authors' `pathcond/rescaling_polyn.py` function `optimize_rescaling_polynomial` computes `BZ` from `compute_diag_G`, `compute_B_mlp`, and `update_z_polynomial` in **float64**, but then explicitly converts `BZ` and `Z` to **float32** before returning. In the `rescaling_path_cond` entrypoint, `reweight_model_inplace` exponentiates those quantized factors, affecting float64 network parameters.

G8 A used the original method unchanged. G8 B called the **same original upstream primitives**, with the same objective, iterations, graph and factors, but bypassed that final 64-to-32 conversion. G8 C rounded B's factors to float32 *before* passing them to the exact original reweighting primitive. The **bit-exact A/C parameter match in all 80 cases**, and B's near-machine-precision prediction equivalence, identifies that cast as the cause **within these tested models**. Rounding the individual connection log-factors can break the cancellation required for pathwise gauge rescaling.

This is a concrete, reproducible **implementation precision fix**, not a new PathCond algorithm and not evidence that PathCond-trained Adam outperforms other methods. Upstream software may intentionally favor 32-bit models; our evidence is specifically about applying it to double-precision networks.

## What G8 does not establish

- No optimizer training took place in G8A, so improved loss/accuracy or numerical stability during training remains untested.
- Exact mathematical function preservation still requires the graph symmetry to be applicable; the original G7 sequential MLP requirement remains.
- Other PyTorch devices/releases, float32 baseline models, and convolutional architectures are untested.
- The G7A H1 scientific hypothesis remains **FAILED (10/12)**. G8 identifies a cause but does not retroactively rewrite those G7 observations.
- All 80 records (including both starting gauges, train/test input probes, factor quantization magnitudes and runtime) are retained in the GitHub Actions artifact.

## Next locked step

An independent long-horizon learning replication should use **new holdout seeds and identical fixed Adam LR** to compare official PathCond, the float64 diagnostic, and unmodified Adam on both test CE and terminal gauge sensitivity, with an equal wall-clock budget report. Such a study must be separately preregistered before new seeds are examined.
