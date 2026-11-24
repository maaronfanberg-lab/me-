# OMEF Coupled Link Lab — controlled experiment, 24 Nov 2026

## Objective
Strengthen *real* OMEF A/B directed mathematical feedback and visual sensitivity without substituting canned geometric shapes. This branch is experimental. The existing `apps/omef-exclusive.html` was not overwritten as part of this experiment; a separately published Lab file contains the source.

## Mechanisms
- Normalize per-node source signals before transmission. The eight source nodes have very different natural signal scales (e.g. Triad standard deviation around .003; Golden around .77 in earlier uncoupled measurements).
- Make link strength respond across its full signed -2..+2 range while bounding the receiving node with nonlinear activation.
- Apply equation-level receiving-node sensitivity for Triad (5x), Market (2.5x), and Regime (1.6x).
- Extend true delayed coupled-state history to 256 slots and expose delays 1..144, replacing the previous delay maximum 34.
- Retain two separate ten-coordinate equations; outputs still form one combined native state-derived trajectory, with no post-hoc shape-switch code.
- Keep Original OMEF parity under zero external injection.

## Reproducible stress audit
[GitHub Actions run 45405487935](https://github.com/maaronfanberg-lab/me-/actions/runs/45405487935) succeeded and archives the numerical JSON and Chromium/WebKit mobile-browser artifacts. Test source is `audit/omef-link-stress.cjs`.

- Default: **1,000,000 finite steps**, 0 non-finite outputs, minor/major covariance ratio **0.7723**, maximum radius **3.3034**.
- Full coupling and cross-influence: **400,000 finite steps**, 0 non-finite outputs, covariance ratio **0.6380**, maximum radius **3.7946**.
- Decoupled global gain zero: **40,000 finite steps**, mean transmitted drive exactly **0**.
- Unlinked Original solver parity: **0** error.
- Identical-config comparison score: exactly **0%** difference.

## Per-link endpoint comparisons
Computed from **the same 14,000-point simulation horizon** in each comparison, using 32x32 normalized trajectory histograms. Numbers are statistical image-distribution differences, **not percentages of actual screen pixels changed or aesthetic quality guarantees**.

| Link | Far-right strength vs default | Delay 144 vs default |
|---|---:|---:|
| B Pair → A Shadow | 31.65% | 25.74% |
| A Shadow → B Golden | 38.52% | 36.01% |
| B Golden → A Regime | 29.31% | 39.48% |
| A Regime → B Market | 37.22% | 43.60% |
| B Market → A Triad | 41.46% | 15.42% |
| A Triad → B Projection | 30.84% | 27.20% |
| B Projection → A Fibonacci | 38.55% | 25.35% |
| A Fibonacci → B Pair | 33.49% | 23.80% |

## Browser verification
**89/89 automated checks passed** across mobile-sized Chromium, WebKit, and a separately checked public GitHub Pages preview in [run 45406132088](https://github.com/maaronfanberg-lab/me-/actions/runs/45406132088), including 154 Coupled sliders, 63 Original and common sliders, all eight expanded delay controls, a direct browser check that delay=144 changes the actual math, mode controls, themes and full-screen controls. No uncaught runtime errors reported. Automated browser emulation is not equivalent to testing the user's physical iPhone.

## Visual-quality caveats
Compared 134,550-point rasterizations for old/new defaults and maximum settings at matched point counts. The new output preserves the layered canopy rather than abruptly becoming a single flower, but the change is not yet a new family of highly intricate sculptures. The user-set target of **near-100% visual transformation at slider extremes is not yet achieved**. The weakest tested delay endpoint still changed only ~15%.

## Preview
[Open public Coupled Link Lab](https://maaronfanberg-lab.github.io/me-/apps/omef-exclusive-link-lab-20261124.html). HTTP 200, true 144-step delays, node calibration and visible rendered attractor were verified by the public Chromium audit. The exact published app matches the tested experimental source except for its HTML page heading and title.

`apps/omef-exclusive-link-lab-20261124.html` on the public GitHub Pages repository. This is separate from `apps/omef-exclusive-coupled-lab-20261124.html` and the original Exclusive app.
