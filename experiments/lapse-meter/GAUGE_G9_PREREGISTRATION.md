# G9 preregistration: does a float64 PathCond precision correction change longer-horizon Adam learning?

**Frozen 2026-10-28 before any G9 target-seed training or test-set evaluation.** Parent project: G8 precision ablation PR #343, which showed that the official upstream PathCond float32 factor cast causes initial logits to change by >1e-7 on 34/80 float64 models, whereas using exact upstream primitives with float64 BZ changes logits only near 1e-15. G7's prior 3-seed performance results must be replicated, not assumed. G9 is a separate branch.

## Fixed design
- Official original PathCond pinned SHA **535b202e3476c64d5e7e9ec5e817344fb5cfd787**, via `pathcond.pathcond.rescaling_path_cond`. No source changes. Precision-only **diagnostic** uses same original primitives in `g8_pathcond_precision.independent_double_bz`, followed by original `reweight_model_inplace` with float64 BZ, and **is NOT labelled the released implementation**.
- Three arms: **Adam alone**, **official PathCond + Adam**, **float64 diagnostic PathCond + Adam**.
- Two offline tasks: sklearn digits, generated concentric circles. Plain sequential width32 ReLU MLPs, hidden depths 3 and 6, float64 CPU. Exactly the G7 model, data splitting and preprocessing. No residual-MLP claims.
- **10 fresh untouched seeds 80 through 89**, not used by G7 or G8, independently stratified 60/20/20 train/validation/test; train-only StandardScaler. These seeds are not used for learning-rate tuning or code debugging. All three methods share each seed's raw initial parameters and a fixed batch64-with-replacement schedule `rng=default_rng(10000+seed)`.
- **Adam lr = 0.003** for every arm and task, frozen from the G7 held-out comparison (chosen via G7's validation-only tuning seeds40/41); PyTorch betas (.9,.999), eps1e-8, no weight decay, exactly **300 updates**. Report 0,1,100 and 300. The step100 checkpoint replicates G7's previous budget without refitting rates. No early stopping, no test-based optimization.
- Each arm is trained twice: identity starting coordinates and an independent per-layer neuronwise gauge with factors in [1/8,8], using identical minibatches, conditioning separately after the gauge for the two PathCond arms. **40 seed-task-depth cells ×3 arms** = 120 paired runs, 240 training trajectories total. Save raw per-run losses, accuracy, gauge gaps, initial preconditioning drift and failed updates. No dropped runs.

## Precommitted decisions
- **H1: precision correction replicates**, passing if **all 80** (task × depth × seed × gauge) float64 diagnostic *initial* function-preservation max absolute logit drift <1e-10. Its failing count is reported without exclusion. Official 1e-7 failures are descriptive.
- **H2: G7 performance replicates**, passing if the diagnostic float64 PathCond+Adam has lower **mean test cross entropy** than Adam at step100 in **at least 3/4** task×depth cells. More seeds increase reliability. Also report step300 comparisons separately.
- **H3: 300-step gauge stability benefit**, passing if diagnostic PathCond+Adam's mean **terminal max absolute logit gap** is smaller than official PathCond+Adam's in **at least 3/4** task×depth cells. All numerical failures count as infinity and disqualify a comparison; if both methods fail, no win.
- **H4: corrected factors do not harm final predictive performance**, passing if diagnostic PathCond+Adam's mean **test CE** is at most **0.01 worse** than official PathCond+Adam at step300 in **all 4** task×depth cells. If either arm has a numerical failure, the cell fails H4. This modest noninferiority margin is a screening threshold, not a clinical equivalence test or statistically powered claim.
- Report mean and standard deviation across all 10 seeds, failure counts, per-method timing (training both gauges), per-cell accuracy, and per-seed loss/gaps. No reallocation of seed/failure rules after results.

## Instrumentation and provenance
- Reuse G7's PyTorch model builder and positive neuronwise gauge, G6 data loader, and G8 upstream-double-BZ diagnostic.
- Independent preflight uses **seed 79**, not target seeds. Check exact gauge equality at initialization, float64 precision preservation, and identical first-batch indices; if source/implementation fails preflight do not run holdouts.
- Explicitly verify the pathcond imported original function points to installed upstream package. Pinned Python CPU environment and single-thread BLAS.
- If a code bug is found **after the target seeds have been run**, document original and corrected results and designate a different new seed set for a genuinely confirmatory rerun, rather than pretending seeds80–89 were never used.
- Neither predictive superiority nor gauge invariance is a known theorem of PathCond+Adam; negative results are valid findings. A successful GitHub Actions job does not mean scientific hypotheses passed.

## Limitations
Only two small offline datasets, plain ReLU, two depths, 10 seeds, 300 updates, fixed Adam LR. Does not test modern architectures, float32 model training, learning-rate sweeps, or matched-FLOP budgets. The diagnostic variant is a precision alteration, not the authors' published release. See [Path-conditioned training, ICML 2026](https://proceedings.mlr.press/v306/lebeurrier26a.html), [original software](https://github.com/Artim436/pathcond), and [PyTorch floating-point caveats](https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html).
