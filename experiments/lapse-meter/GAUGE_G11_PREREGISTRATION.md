# G11 preregistration: does official PathCond amortize on larger, longer-running float32 models?

**Frozen 2026-10-28, before G11 target training.** Parent G10 showed original PathCond+Adam improves starting-gauge robustness but requires 2.8–3.8x Adam's CPU time to a 90% validation-accuracy target on tiny width32, 300-update networks when preprocessing is counted. Here we increase width, depth, sample size, steps, batch size and the accuracy target. No hidden architecture-specific hyperparameter tuning.

## Methods and provenance
Official published `rescaling_path_cond` from [Artim436/pathcond at commit 535b202e3476c64d5e7e9ec5e817344fb5cfd787](https://github.com/Artim436/pathcond/tree/535b202e3476c64d5e7e9ec5e817344fb5cfd787) once at initialization plus PyTorch Adam, versus otherwise identical plain Adam. **Native float32 model parameters** and only plain sequential ReLU MLPs. Original author code is installed unmodified; **no** G8 float64 diagnostic, substitute or custom PathCond. Frozen Adam learning rate 0.003, betas 0.9/0.999, eps1e-8, no weight decay. Exactly the same random initialization in function space and mini-batch sequence for each pair.

## Locked data and architecture
Four task/architecture cells:
- Digits (sklearn's original 1,797 images, 64 features, 10 classes), width64 hidden depth6; width128 hidden depth12.
- Large synthetic circle, **8,192** independently generated 2D points sampled uniform([-1,1]^2), class 1 iff radius <0.55, width64 depth6; width128 depth12. Fresh dataset for each seed (generator seed 600000+seed). The circle data's class proportions may be imbalanced; split by stratification.
- Stratified 60% training, 20% validation, 20% test; fit StandardScaler to training partition only. No test access for hyperparameters or selecting stopping steps.
- **Five untouched seeds 120,121,122,123,124**. Seed119 is used for an engineering smoke test before accessing target seeds. For each cell/seed/method train both (a) normal initialization and (b) functionally equivalent neuronwise-gauge starting point spanning positive scales [1/8,8] with independent per-layer permutations. On PathCond arm apply original conditioning **separately** to each of these equivalents before Adam. **40 paired experiments, 80 trajectories** (4 cells ×5 seeds ×2 methods ×2 gauges). Every trajectory runs 600 steps, batch128 with replacement, `default_rng(10000+seed)`. Fixed PyTorch CPU single-thread, NumPy and sklearn versions pinned by workflow.
- Report initial functional gauge error, preprocessing function-preservation max-logit drift, and all numerical errors. Official float32 PathCond with error >=1e-3 or nonfinite factors is reported as **failure**, not silently replaced or dropped.
- Validation accuracy sampled every **10 steps**. Target is **95% for digits**, **96% for synthetic circle**. Record first step crossing and cumulative actual per-network CPU wall-clock time **including** PathCond initialization, minibatch forward/backward/update, but **excluding** shared model creation, dataset prep and validation-evaluation overhead. Never-crossed targets explicitly **right-censored** at step600 and paired total compute time, not discarded.
- Test cross-entropy and test accuracy at fixed steps **100, 300, 600**; final max absolute test-logit mismatch across gauge starts at step600. Do not choose or adjust learning rate or thresholds based on test outcomes.
- Retain per-seed full checkpoint trace, target crossings, per-method initialization costs, end times, and failures, to enable independent reproduction.

## Locked outcomes (all include failures)
- **H1 (compute amortization):** PathCond+Adam's median *including initialization* time to reach target is lower than Adam in **at least 3 of 4** cells on the *normal starting gauge*. A cell counts as a win only if both methods reach target in >=4 of 5 seeds, all five runs finish successfully, and PathCond's median time among reached runs is strictly lower. Otherwise no win. Any never-crossed run is counted in crossing rate even when median of the crossed is shown; no cherry-picking.
- **H2 (robustness):** PathCond+Adam's **mean** step600 max test-logit mismatch between gauge-equivalent starts is lower than Adam's in **at least 3 of 4** cells, and both methods have 5/5 successful pairs. Nonfinite/failure prevents cell win.
- **H3 (predictive noninferiority):** PathCond+Adam's mean normal-gauge step600 test accuracy is at most 1 **percentage point** below Adam in >=3/4 cells, again requiring 5/5 successful pairs per method.
- **H4 (initial-function preservation):** all 40 native-float32 PathCond preconditioning transforms (20 cell×seed ×2 gauges) change logits by <1e-3 on the first 128 training samples and all values remain finite; any failure falsifies H4.
- **Secondary, descriptive:** fraction crossing target by step600; median **steps** to target (not substitute for time); median computation time conditioned on success; total run wall time; relative overhead at width64 vs width128; identity vs neuronwise time-to-target. Report fixed-step test CE and accuracy for every cell, and compare 600-step CE with G10 only qualitatively due to changes in size/targets/data. No significance claim from n=5.
- A GitHub CI job succeeding means the *benchmark* completed, not that H1–H4 predictions succeeded.

## Scope, risks, and constraints
This is a CPU-only controlled screen, not matched-GPU/FLOPs or large-scale ML benchmark. The digits dataset is unchanged small; the circle data is synthetic and simple despite 8,192 examples. Larger widths and depths may cause some models to fail before 600 updates; log all outcomes. Python CPU wall-clock timings are noisy and may vary across runners. This experiment tests whether one-off PathCond cost **can** amortize in this regime, not that it universally does or does not.

If a code defect is found after any target run, publish the original results, explain correction, and use **new** genuinely untouched seeds for confirmation. Earlier G6–G10 original findings remain immutable; no merge to main before review.

Source: Lebeurrier, Vayer, Gribonval, *Path-conditioned training*, ICML 2026 https://proceedings.mlr.press/v306/lebeurrier26a.html .
