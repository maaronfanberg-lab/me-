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

## Third design: verified successful real steering (but not quality improvement)

- Exact successful six-case run: https://github.com/maaronfanberg-lab/me-/actions/runs/43925951461
- Exact successful twenty-case replication: https://github.com/maaronfanberg-lab/me-/actions/runs/43926958798
- Correct and incorrect answer candidates are both included verbatim in every probe, so a local audit confirmed identical binary word/character-trigram feature presence in all 88 paired examples. Upstream validation was **WARN, not PASS**: held-out direction AUC 0.755; random-direction percentile 100 with 256 random directions; text-only lexical AUC about 0.133. The gate warned of marginal 0.755 discrimination, and unavailable masked-confound and final/mean readout comparisons. Do not reinterpret WARN as strong or fully controlled scientific evidence.
- The actual `apply_concept_intervention(model, direction, "steer", ...)` hook was installed and executed with alpha = 0, -0.5 and +0.5; both alpha-zero and full hook removal reproduced the pristine outputs exactly. The model was the separate dense 135M Hugging Face checkpoint, not the Room 3B production model. Source is genuine verified OBLITERATUS v0.1.4, not a simulated steering implementation.
- Twenty fictional dialogue cases. The pristine model produced four-gram reuse in 12/20; alpha -0.5 produced 2/20 (10 paired reductions, no new reuse), changing 18/20 responses; alpha +0.5 produced reuse in 15/20 (5 new cases, 2 reduced), changing 19/20 responses. Average spoken words were 20.7 (pristine), 18.05 (negative), 24.7 (positive). Shorter outputs can mechanically reduce four-gram reuse.
- Wrong-speaker prefix counts were 7/20, 6/20, 9/20 respectively. Naive copied-experiment-prompt markers were 3/20, 4/20, 0/20. No tested condition produced an acceptable natural conversation. Outputs frequently echo fictional transcripts or explicit generator questions, and the 135M baseline itself is poor. None chose silence.
- The same dataset design/gate produced the same heldout AUC in both runs. However shared templates and a single architecture mean this does **not** demonstrate cross-model generalization or improve spontaneous multi-agent dialogue. No blind human ratings, full independent control set, long-term memory, KL/safety collateral, or KV-cache tests were completed.
- A reproducible zero-dependency unit test asserts the binary lexical-feature equality, independent train/holdout object lists, and non-refusal target. The twenty-case GitHub Actions run passed these regression tests.

**Decision:** Genuine neural manipulation and reversible hook behavior are verified. **Production release is blocked** because conversational quality is poor and key validation/collateral channels remain untested. No changes were merged into, deployed to, or written to the live Room.
