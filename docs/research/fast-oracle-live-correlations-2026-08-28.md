# Fast Oracle live correlations — 2026-08-28

## Goal
Add rolling correlation analysis across every active Fast Oracle input and make prediction accuracy explicit as a percentage.

## Method
- Sample the current normalized factor for every LIVE stream every 5 seconds.
- Correlate **changes in normalized factors**, not raw prices or raw levels. This reduces spurious correlation caused merely by different scale/level trends.
- Retain up to 180 synchronized samples, approximately 15 minutes at a 5-second cadence.
- For every pair of streams, compute Pearson correlation on timestamps where both changes are finite.
- Require at least 6 paired changes before displaying a numeric correlation. If either side has zero variance, correlation remains undefined.
- Show all available pairwise correlations, sorted by absolute magnitude, including weak and inverse values.
- Separately rank each non-target stream against the selected target.

## Prediction accuracy
Prediction accuracy is the percentage of settled forecasts whose predicted direction matches the realized direction. The UI shows both the percentage and the number of settled forecasts. Pearson correlation between predicted and realized percentage returns remains a separate metric.

## Limitations
Short rolling windows can produce unstable correlations, especially when a source changes infrequently. Correlation is descriptive, not causal. Multiple crypto instruments can share common market drivers, so high pairwise correlation is unsurprising and does not establish independent predictive information.
