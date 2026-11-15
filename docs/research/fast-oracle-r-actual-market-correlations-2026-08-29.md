# Fast Oracle: R correlations against actual market data

Date: 2026-08-29

## Observed problem
The Oracle's `All R correlations` table currently compares 5-second changes in R against changes in normalized internal factors. Those factor values are useful diagnostics, but they are not direct market returns. The requested experiment is R versus actual market data.

## Research question
How should the live Oracle compare R with actual market instruments while avoiding misleading correlation from trending price levels?

## Evidence
- Granger & Newbold (1974), *Journal of Econometrics*, documented spurious relationships that can arise when persistent/non-stationary time-series levels are compared directly.
- Phillips (1986), *Journal of Econometrics*, developed asymptotic results explaining spurious regressions in integrated economic time series.
- Therefore the live comparison should use synchronized price changes/returns rather than raw price levels.

## Competing explanations / limitations
A Pearson correlation on short-horizon returns is descriptive only. It does not establish causality or prediction. Five-second crypto returns can be serially dependent and noisy; Yahoo futures update at one-minute resolution, so repeated 5-second samples between new bars must not be treated as independent futures observations. Market closures can leave futures prices unchanged for long periods. Multiple instruments are being inspected, so a large absolute correlation can occur by chance.

## 10-level gate
1. Observed problem: current table uses normalized factors, not actual market returns.
2. Foundational evidence: spurious time-series relationships in levels are well established.
3. Current evidence: no newer standard reverses the basic warning; differenced/return-style comparisons remain appropriate for short-horizon descriptive co-movement.
4. Natural-behavior evidence: not applicable.
5. Mechanism: compute percentage price return between synchronized observations, pair it with contemporaneous ΔR, and apply Pearson correlation.
6. Competing explanations: serial dependence, stale one-minute futures bars, common market drivers, and chance are explicitly retained as limitations.
7. Replication/correction limits: correlation is descriptive, not a significance or causal test.
8. Context transfer: applies directly to this numeric time-series experiment.
9. Implementation mapping: replace factor-based R rows with actual-price-return rows for target, BTC, ETH, SOL, DOGE, LTC, LINK, AVAX, BCH, XRP, NQ, GC, and CL. Remove Wiki and order pressure from the market-correlation table.
10. Validation: confirm rows are built from raw market prices, return observations are only added when a valid prior price exists, futures rows only advance when their market timestamp advances, and no non-market source appears in the table.

## Pre-change baseline
`R ↔ signal` rows use `state.cards[k].factor` deltas sampled every five seconds. NQ has a separate one-minute synchronized panel.

## Validation criteria
- Table label explicitly says actual market returns.
- Crypto rows use Coinbase price-to-price percentage returns.
- selected target uses Yahoo 1-minute price returns when a new bar arrives.
- NQ, gold (`GC=F`), and oil (`CL=F`) use Yahoo 1-minute returns only when market timestamps advance.
- R is paired with the R value observed at the same sampling/update point.
- Wiki and order pressure do not appear in the market table.
- Existing R formula and recorder are unchanged by this interface/statistics change.

## Post-change result
Pending deployment verification.
