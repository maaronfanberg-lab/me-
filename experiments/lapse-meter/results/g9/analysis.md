# G9: 10-seed, 300-step longer-horizon PathCond precision replication

**Date:** 2026-10-28. **Precommitted protocol:** [GAUGE_G9_PREREGISTRATION.md](../../GAUGE_G9_PREREGISTRATION.md); **source:** [g9_longrun.py](../../experiments/g9_longrun.py). Original PathCond from [Artim436/pathcond @ 535b202e3476c64d5e7e9ec5e817344fb5cfd787](https://github.com/Artim436/pathcond/tree/535b202e3476c64d5e7e9ec5e817344fb5cfd787) used **unchanged** in the official arm. The separate 64-bit variant is explicitly a **diagnostic** reassembly from original upstream primitives, not an official release.

## Chain of custody

GitHub Actions [run 40796189187](https://github.com/maaronfanberg-lab/me-/actions/runs/40796189187) completed **SUCCESS**: pinned CPU dependencies and upstream software, seed79 smoke, 120 new-seed paired runs and raw JSON archive `lapse-g9-complete` (artifact id **12864235939**). Artifact downloaded, inspected and SHA256 of `ci_results.json`: **`ea741675e01011d6617f6d6f0841be9bfc3bf66d4eb7872f57220417eef59b86`**.

120 paired runs ×2 gauge copies = **240 trajectories**, each trained 300 Adam updates on 64-example batches. Four task/depth cells ×10 fresh seeds 80–89 ×3 methods; fixed Adam lr0.003 chosen in prior G7 tuning, no retuning. All **120/120** paired runs finished, **zero failed training runs**, no dropped seeds. Both task splits train-only standardized; test data used only for outcome measurement, not selection.

## Original preregistered outcomes, including a failure

- **H1 PASS 80/80**: double-BZ diagnostic kept initial predictions within <1e-10 for all 40 models ×2 gauges, max observed **4.44089e-15**. Original official PathCond exceeded G7 strict 1e-7 in **10/40 identity** starting networks and **22/40 neuronwise** starts. This is an initial-function precision result, not learning stability.
- **H2 PASS 3/4**: at 100 steps, the diagnostic PathCond+Adam had lower mean heldout test cross entropy than Adam in 3 of the 4 task/depth cells, using **10 entirely new seeds per cell**. This independently replicates the previous G7 directional result at its original 100-step horizon.
- **H3 FAIL 1/4**: at 300 steps, corrected PathCond had a smaller mean terminal gauge-logit gap than the **published PathCond** in only one of four cells, versus preregistered pass at least 3. Precision repair is *not* a reliable fix for the gauge-sensitive **Adam training trajectory**.
- **H4 PASS 4/4**: corrected PathCond mean test CE at 300 steps was not more than **0.01 worse** than the official implementation in any cell. It also did **not** yield a reliable practical predictive improvement: final errors were very similar, with differences in the third decimal or smaller.

A successful *software test* means the benchmark ran correctly; it does not change H3's *scientific failure*.

## Mean cross-entropy test loss, 10 new seeds per cell

Lower is better. A fixed Adam learning rate 0.003 for every method; no tuning on these outcomes.

| Task / hidden depth | 100-step Adam | 100-step official PathCond + Adam | 100-step corrected + Adam | 300-step Adam | 300-step official PathCond + Adam | 300-step corrected + Adam |
|---|---:|---:|---:|---:|---:|---:|
| Digits / 3 | 0.208524 | 0.198426 | **0.198426** | 0.181619 | 0.172322 | **0.172321** |
| Digits / 6 | 0.360425 | **0.348957** | 0.349080 | **0.349012** | 0.355283 | 0.354562 |
| Circle / 3 | 0.138334 | 0.128990 | **0.128990** | **0.032475** | 0.037186 | 0.037186 |
| Circle / 6 | **0.101137** | 0.103449 | 0.103449 | **0.041178** | 0.045827 | 0.045827 |

**Important new observation:** while the corrected PathCond arm outperformed Adam at **100 steps on three of four cells**, by **300 steps Adam was better in three of four cells**. The earlier advantage appears partly to be **early convergence**, not a durable improvement in final test loss under these settings. This temporal reversal is descriptive, not a separate preregistered confirmatory hypothesis; it motivates future matched-compute / time-to-target comparisons.

## Test accuracy at 300 steps (mean of 10 seeds)

| Task/depth | Adam | Official PathCond+Adam | Corrected PathCond+Adam |
|---|---:|---:|---:|
| Digits / 3 | 96.17% | 96.19% | 96.19% |
| Digits / 6 | **95.39%** | 95.19% | 95.17% |
| Circle / 3 | **98.86%** | 98.53% | 98.53% |
| Circle / 6 | **98.31%** | 98.14% | 98.14% |

## Robustness (mean absolute maximum test-logit drift under starting-gauge changes at step 300)

| Task/depth | Adam | Official PathCond+Adam | Corrected PathCond+Adam |
|---|---:|---:|---:|
| Digits / 3 | 45.0775 | 5.00221 | **4.98507** |
| Digits / 6 | 77.9266 | **27.9794** | 27.9985 |
| Circle / 3 | 6.58369 | **1.82551** | 1.82551 |
| Circle / 6 | 11.4485 | **5.06404** | 5.06405 |

Both PathCond arms reduce starting-parameterization sensitivity versus unconditioned Adam in all four tested cells. But they are **not exactly equivariant** after Adam updates and the numeric precision correction does not materially improve that long-term property. This explains H3's failure.

## Runtime screening

Mean elapsed time for each **paired (identity+rescaled), 300-step** benchmark, including one or two initialization conditions: Adam 0.294–0.500 s; original PathCond 0.393–0.711 s; double diagnostic 0.399–0.705 s. PathCond arms cost roughly 1.3–1.4× Adam for these tiny CPU models. These are paired-run timings, not matched-FLOP or matched-hardware scaled benchmark results.

## Limits and research implications

1. A *numerical implementation defect* (G8) and *gauge-sensitive training with Adam* (G9) are distinct. Fixing the final BZ cast makes initial rescaling function-preserving to near float64 machine precision, but does not make Adam invariant or consistently improve the loss.
2. The G7 three-seed, 100-step directional improvement replicated with ten new seeds, lending support to a modest early-optimization benefit in three selected easy-network conditions.
3. Longer training erased or reversed that advantage in three out of four conditions. No broad superiority is established.
4. The experiments are limited to small, plain ReLU MLPs, two tasks, Adam lr0.003, float64 CPU, seeds80–89; do not extrapolate to modern convolutional architectures, transformers, residual models or full-scale GPU training.
5. The official authors may have intentionally prioritized single-precision model workflows. Our G8/G9 precision evidence applies specifically to **double-precision models**; do not characterize their entire paper or algorithm as incorrect.

## Exact independent reproduction

The independent workflow is `.github/workflows/lapse-g9-longrun.yml`. It installs exact official PathCond from the pinned SHA, runs the unused-seed smoke and executes all 120 paired evaluations. All 120 full records, including step0/1/100/300 checkpoints and per-seed run times, are retained in the GitHub Actions artifact from [run 40796189187](https://github.com/maaronfanberg-lab/me-/actions/runs/40796189187). No original G7/G8 data or failure records were rewritten.
