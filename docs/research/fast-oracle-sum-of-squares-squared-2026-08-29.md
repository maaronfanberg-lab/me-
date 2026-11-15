# Fast Oracle: sum-of-squares-squared R with adaptive roots

Date: 2026-08-29

## Observed problem
The original displayed R was `sqrt(x_1000)`, which capped R near 1,000 and reflected only the final recurrence stage. The requested replacement, `Rraw = (sum x_n^2)^2` over all 1,000 modular stages, produces values on the order of 10^30 and is awkward for display and comparison.

## Research question
Can the Oracle retain the full-path sum-of-squares-squared construction while repeatedly applying square roots only until the resulting number is computationally and visually manageable?

## Evidence and constraints
This is a user-defined mathematical experiment, not a claim of predictive validity. The recurrence remains modular at every stage, so each stage stays tractable. `BigInt` is used for the exact raw integer. The tamed R is produced by repeatedly applying `sqrt` while R is greater than 1,000,000. The raw exact integer is retained by the recorder for auditability.

## Competing explanations / limitations
Repeated square roots are a monotonic compression. They preserve ordering only among observations that receive the same number of roots. If observations ever cross a root-count boundary, the scale changes discontinuously. The recorder therefore stores `rootCount` alongside R so this can be detected. A larger or differently compressed R does not itself create predictive information.

## 10-level gate
1. Observed problem: established from the original ~1,000 ceiling and the huge raw replacement.
2. Foundational evidence: elementary modular arithmetic, sums of squares, and monotonic square-root transforms.
3. Current evidence: JavaScript `BigInt` is required for exact raw values; `Number` is sufficient after compression for plotting/correlation.
4. Natural-behavior evidence: not applicable.
5. Mechanism: compute 1,000 modular stages, accumulate `sumSquares += x*x`, set `Rraw=sumSquares^2`, repeatedly apply sqrt while `R>1,000,000`.
6. Competing explanations: compression may magnify or hide distributional quirks; documented above.
7. Replication/correction limits: deterministic results can be independently recomputed from seed.
8. Context transfer: non-market Wikimedia seed and recurrence remain unchanged.
9. Implementation mapping: browser `alex`, recorder `alex`, display labels, prediction normalization, model-specific history key, recorder model version.
10. Validation: browser and recorder must use identical recurrence/compression, old forecast history must not mix with the new model, and root count/raw integer must be logged.

## Pre-change baseline
`R=sqrt(x_1000)` in the browser, with a theoretical ceiling near 1,000. The intermediate attempted recorder model used the exact uncompressed sum-of-squares-squared value.

## Validation criteria
- Raw statistic is exactly `(sum_{n=1}^{1000} x_n^2)^2`.
- Repeated square roots continue only while the current value exceeds 1,000,000.
- Recorder stores tamed `r`, `rootCount`, exact raw R string, and exact sum-of-squares string.
- Browser uses the same adaptive-root rule and shows the root count.
- Browser prediction history uses `fastOracleResults-adaptive-roots-v1`, preventing contamination from prior R formulas.
- Market, crypto, futures, and order-pressure data remain excluded from R.

## Post-change result
Implemented in the browser and persistent recorder. Browser commit: `b48543d525db2867a4893d9de7ec9d53423f286e`. Recorder commit: `cd3be7c123cb3321a0e56e128edc459f6ea5bcca`. The browser also rejects zero-valued market placeholders when selecting prices.