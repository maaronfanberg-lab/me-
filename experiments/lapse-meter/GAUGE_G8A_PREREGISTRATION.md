# G8A preregistration: numerical error in official PathCond reparameterization

Date: 2026-10-28 (before any G8A target-seed runs). Parent: G7A, PR #339. This separate branch does not modify G7A findings. Motivation: G7A's strict initial-function-preservation hypothesis failed in 2/12 runs at 1e-7. The ORIGINAL PathCond repository at commit `535b202e3476c64d5e7e9ec5e817344fb5cfd787`, file `pathcond/rescaling_polyn.py`, computes `BZ` in `torch.double` and explicitly converts `BZ = BZ.to(dtype=torch.float32)` before exponentiating the factor and reweighting a float64 network. Determine causality, not just correlation.

## Locked new conditions (no training involved)

Models: exactly the plain sequential float64 PyTorch ReLU MLPs used in G7A, width32, hidden depth 3 or 6; digits and circles (stratified splits and train-only standardization, same as G7A). Fresh seeds **60 through 69 inclusive**; for each task/depth/seed, test both original and G7's function-equivalent `neuronwise` scale gauge (factor range 1/8 to 8), total **80 starting networks**. Compare predictions on the first up to 128 training examples, and full heldout input partition. There is no training, tuning or test-label selection.

A: **Published official PathCond**: use upstream `rescaling_path_cond(copy)` exactly as released, with `nb_iter_optim_rescaling=10`, default tolerance and default `enorm=False`. Original PyTorch dtype float64 with single-thread CPU, pinned dependencies same as G7.

B: **Precision-only diagnostic**: reuse the author's `compute_diag_G`, `compute_B_mlp`, `update_z_polynomial`, and `reweight_model_inplace` from the same pinned source. Keep the computed BZ in **float64** rather than the final published `to(torch.float32)`. No change to objective, graph, iteration count, branch logic, epsilon, or rescaling exponent. This variant is **NOT labelled original/official PathCond**.

C: **Rounded control**: use exactly the double BZ from B but call the author's `reweight_model_inplace` with `BZ.to(torch.float32)`, to reproduce A. Verify all factors in A and C agree bitwise (or max absolute parameter mismatch <1e-10 due to controlled deterministic primitive calls). If A and C disagree more than 1e-10, mark the case invalid instrumentation, report it and do not count as evidence for the cast.

For each of 80 cases report: original-to-transformed max absolute logit difference on 128 train and heldout X for A, B, C; original A/B/C transformation parameter differences; BZ32 vs BZ64 quantization max; finite status; time taken. No excluded networks. Failures, NaN/Inf and invalid instrumentation are explicit records, not dropped.

## Precommitted hypotheses and decisions

- **H1 (float64 numerical rescue)**: among the 80 starting networks, at least 72/80 have B maximum error on the full heldout X **<1e-10**, with zero missing/failed cases. Report threshold count. If fewer than 72, H1 fails.
- **H2 (causal fingerprint)**: all 80 cases produce A and C post-transformation parameters within max absolute **<1e-10**, on every layer; and BZ factor rounding is detected in at least 80% (not identical bitwise). If not, we have not isolated the original rounding step. No silent reinterpretation.
- **H3 (paired benefit)**: across all cases with A output error >1e-10, B decreases max heldout-logit error by at least **10x** in >=75% of those cases. If there are fewer than 10 eligible cases, H3 is INCONCLUSIVE, not pass. Ratio denominator uses the actual B error, with floor 1e-15 only for report; pass comparison uses B_error <= A_error/10.
- **H4 (original issue frequency)**: report (descriptive, no pass) count A drift >1e-7 and B drift >1e-7, and the gauge-conditioned output gap original-vs-rescaled for A/B (not guaranteed equal; algorithm may choose different representatives).
- For H1/2/3, all 80 outcomes are listed, and aggregate results computed without model selection. A software CI pass is distinct from scientific hypothesis pass.

## Guardrails and limits

This probes a single implementation rounding issue and its possible repair in double-precision **plain** ReLU MLPs. It does not establish true gauge-equivariant Adam, accuracy improvements, or general PathCond efficacy. No gradient steps or optimizer learning dynamics in G8A. If instrumentation fails, stop and report; do not alter threshold or seeds. If a software defect requires correction, disclose it and use new seeds for a genuinely confirmatory run. Existing G7A H1 failures remain unchanged. No edits to upstream library; variant is built from publicly exposed, unmodified original primitives.

Prior art: Lebeurrier, Vayer, Gribonval, *Path-conditioned training*, ICML 2026 https://proceedings.mlr.press/v306/lebeurrier26a.html. PyTorch floating-point numerical accuracy https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html.
