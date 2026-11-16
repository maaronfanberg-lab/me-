# Isolated real-neural OBLITERATUS pilot, 2026-11-16

This is a continuation of research-only PR #417. **Never promote changes into the live Room from these results.** Source revision is OBLITERATUS v0.1.4, commit `461ff086e675d93969bbd7c99c53505762452309`, checked by SHA256 `e2d0fb696b8cd025124e6d7cc69bbd8b7d969adc0f019697cb2a5dd6696eba99`. Pretrained probe model: HuggingFaceTB/SmolLM2-135M-Instruct at revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, not the Room's 3B quantized GGUF.

## First genuine neural run: complete, hypothesis rejected

- Reproducible run: https://github.com/maaronfanberg-lab/me-/actions/runs/43924496036
- Verified on GitHub hosted CPU: exact OBLITERATUS release installed and imported; pinned pretrained model downloaded; real hidden-state activations extracted at middle layer 15.
- Train: 32 fictional items per class. Independent holdout: 24 items per class.
- Observed independent validation: supplied-vector heldout AUC = 1.0, but **text-only lexical AUC = 1.0**. Random-direction percentile = 82.03125 (required >= 95). Both are fails.
- Consequently **no intervention/steering was executed**; no Room model, state, memory, feed, or deployment changed. GitHub Actions success means the scientific protocol ran and correctly rejected a confounded direction, not that steering improved conversational behavior.
- Additional validation warnings: 24 samples per class (minimum passes, warnings < 32); no masked confound, mean-pool comparison, or additional readout cached.
- Evidence artifact: https://github.com/maaronfanberg-lab/me-/actions/runs/43924496036/artifacts/14256445310

## Revised prospective test, without weakening gates

To reduce the demonstrated lexical confound, the research-only script now creates **counterbalanced pairs**: for each fictional object, two opposite location statements are used, and correct vs incorrect responses are swapped. The positive and negative classes now have matched words across matched pairs; only correctness relative to preceding context changes. 48 train prompts per class and 40 independent held-out prompts per class use disjoint objects. Upstream thresholds remain unchanged; if validation fails again, steering remains blocked.

This explicitly tests context-sensitive matching, not the full construct of conversational responsiveness. Short answer probes, shared templates, non-independent controls, lack of long-running dialogue and no dedicated collateral safety battery still limit interpretation. Even a validated direction and a changed synthetic response are not evidence of improved spontaneous conversation in the Room.

## Independent decision criterion

Only after a PASS/WARN from the unmodified upstream validation with a matching pack hash and model revision may `apply_concept_intervention(..., mode="steer")` run on the independent dense pretrained model. Alpha=0 and post-hook restoration must be byte-identical to pristine outputs under greedy decoding. Failed scientific gates are recorded as negative findings, not silently bypassed.
