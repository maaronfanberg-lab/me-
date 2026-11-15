# Fast Oracle: R-only correlation view

Date: 2026-08-29

## Observed problem
The Oracle currently shows a large all-pairs correlation table across market, crypto, order-pressure, and Wikimedia factors. The user's actual experimental question is narrower: how does R move relative to each external signal?

## Research question
Can the correlation UI be reduced to only correlations between changes in R and changes in each live factor, without changing the underlying R formula or live data feeds?

## Evidence and constraints
Pearson correlation is already used in the app. The existing sampling cadence is 5 seconds with a rolling maximum of 180 samples. The change should preserve those mechanics and simply add `dR` to the synchronized sample row, then compute Pearson `r` between `dR` and each factor change.

## Competing explanations / limitations
Correlation remains descriptive, not causal. R is derived from Wikimedia activity, so the R↔WIKI row is structurally related and should not be interpreted as an independent external test. Other rows can still be affected by autocorrelation, heterogeneous factor definitions, and multiple comparisons.

## 10-level gate
1. Observed problem: established from the current UI and explicit user request.
2. Foundational evidence: standard Pearson correlation already implemented.
3. Current evidence: no external empirical claim is introduced; this is an interface/measurement refocus.
4. Natural-behavior evidence: not applicable.
5. Mechanism: record 5-second `dR`, pair it with each existing factor delta, and compute Pearson r.
6. Competing explanations: documented above.
7. Replication/correction limits: unchanged from current correlation implementation.
8. Context transfer: same live samples and same rolling window.
9. Implementation mapping: replace the two pairwise-correlation panels with one R-only panel; add `lastSampleR`; compute and sort R correlations by absolute r.
10. Validation: no non-R pair rows remain; R rows populate after at least 6 paired changes; N counts reflect valid paired samples.

## Pre-change baseline
Two correlation panels: target correlations and all 66 pair correlations among 12 factors.

## Validation criteria
- Only R↔signal rows appear in the general correlation section.
- Rows include TARGET, BTC, ETH, SOL, DOGE, LTC, LINK, AVAX, BCH, XRP, ORDER PRESSURE, and WIKI EDITS when data are available.
- Correlations use synchronized 5-second changes and require at least 6 paired samples.
- Rows are sorted by absolute correlation strength.
- Dedicated R↔NQ futures panel remains unchanged.

## Post-change result
Pending deployment verification.
