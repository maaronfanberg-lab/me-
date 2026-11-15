# Fast Oracle: 50/50 physical-world + human-activity R

Date: 2026-08-29

## Observed problem
The current R seed is derived only from Wikimedia recent-change activity. That keeps market data out of R, but makes the entire experiment depend on one human-activity source. The intended experiment is broader: combine non-market physical-world activity with non-market human activity, while keeping the two categories equally weighted.

## Research question
Can R be seeded from two independent non-market buckets, physical-world activity and human activity, with each bucket receiving exactly 50% of the combined score regardless of how many feeds are inside it?

## First-party source evidence
- USGS GeoJSON earthquake summary feeds are updated every minute and expose recent earthquake features and magnitudes.
- NOAA SWPC publishes machine-readable planetary K-index JSON products for geomagnetic activity.
- Wikimedia EventStreams provides the global recent-change SSE stream used by the current Oracle.
- The official Hacker News Firebase API exposes public data in near real time and documents no rate limit for the v0 API.
- GitHub public events were considered but rejected for this use because GitHub documents that the endpoint is not designed for real-time use and may lag from tens of seconds to hours.

## Proposed bucket construction
Physical-world score:
1. USGS all-earthquakes past-hour feed. Earthquake feature: recent event count with a modest magnitude contribution.
2. NOAA planetary K index. Geomagnetic feature: latest observed Kp centered around ordinary quiet-to-moderate conditions.

Human-activity score:
1. Wikimedia recent-change rate from the existing global SSE stream.
2. Hacker News creation activity, measured from change in the monotonic max item id over elapsed time.

Every source is transformed to a bounded score in [-1,+1]. The bucket score is the arithmetic mean of available source scores. The final input score is `(physical + human) / 2`, so the categories remain exactly 50/50 when both are available.

The combined score is mapped deterministically into the existing integer seed domain and then passed through the existing 1,000-stage modular recurrence, sum-of-squares-squared statistic, and four fixed square roots. No market, crypto, futures, or order-book data enters R.

## Normalization choices and uncertainty
The first implementation intentionally uses simple explicit transforms rather than online z-scores or learned historical calibration. This avoids hidden state and lets the browser and persistent recorder calculate the same score from the same observations. The constants are engineering normalizations, not scientific claims about natural baselines. They should be revisited only after observing source distributions in logs.

- Earthquake score uses past-hour count plus maximum magnitude, bounded to [-1,+1].
- Kp score centers ordinary conditions and rises with geomagnetic disturbance.
- Wikimedia score retains the existing bounded edit-rate transform.
- Hacker News score uses item-id creation rate per minute after a prior sample exists; until then the human bucket can operate on Wikimedia alone.

## Competing explanations / limitations
- Equal weighting prevents feed-count dominance but does not make the sources equally informative.
- Earthquake counts and geomagnetic Kp change more slowly than 5-second market observations, so short-window R changes may still be dominated by the human bucket between physical updates.
- Hacker News max-item growth includes comments and other item types, not just stories, so it is a broad activity proxy rather than a pure posting-rate measure.
- Wikimedia remains part of R; therefore `R ↔ WIKI` is descriptive and not an independent external test.
- A correlation between R and a market can still arise by chance, common time structure, autocorrelation, or repeated testing. The source redesign does not by itself establish predictive validity.

## 10-level gate
1. Observed problem: established from the current single-source Wikimedia seed.
2. Foundational evidence: arithmetic averaging and bounded normalization are sufficient for deterministic equal weighting.
3. Current evidence: first-party USGS, NOAA SWPC, Wikimedia, Hacker News and GitHub API documentation checked on 2026-08-29.
4. Natural-behavior evidence: public live activity feeds are used rather than synthetic human-activity labels.
5. Mechanism: normalize independent feeds, average within category, then average categories 50/50 before seed construction.
6. Competing explanations: differing time scales, source dependence, autocorrelation, and chance correlation documented above.
7. Replication/correction limits: predictive interpretation is explicitly excluded; feed reliability and score distribution require empirical validation.
8. Context transfer: all chosen inputs are public non-market data appropriate for an external-input Oracle experiment.
9. Implementation mapping: update browser data collection/seed construction, recorder collection/seed construction, UI labels/cards, model version and validator.
10. Post-change validation: verify market exclusion, 50/50 bucket math, bounded source scores, browser/recorder formula parity, source failure fallback, fresh model-history key, and JavaScript parse validity.

## Pre-change baseline
R seed uses six Wikimedia-derived features only. R transform is raw `(sum x_n^2)^2` followed by exactly four square roots. Correlation panel shows only R correlations.

## Validation criteria
- Physical and human bucket scores are visible or inspectable.
- With both buckets available, combined score equals exactly `(physical + human)/2`.
- Market/crypto/futures/order-pressure values never enter either bucket.
- USGS and NOAA failures do not crash the app; available bucket sources can still be averaged.
- Hacker News requires a prior max-item sample before contributing a rate.
- Browser and recorder use the same source transforms, bucket weighting, recurrence, and four-root transform.
- Prediction history gets a new model-specific storage key.
- Validator reflects the current MK/version and R-only correlation design.

## Post-change result
Pending deployment verification.
