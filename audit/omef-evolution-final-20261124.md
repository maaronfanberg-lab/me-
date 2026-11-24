# OMEF Exclusive — Evolution Lab release evidence (24 Nov 2026)

## Published separately
`apps/omef-exclusive-evolution-lab-20261124.html` is the new preview. The existing `apps/omef-exclusive.html` and earlier Coupled/Link Lab files are not overwritten by this release. Its mathematical and UI source matches the validated experimental branch, apart from its visible page title and heading.

## Actual implementation
- Original OMEF's automatic drift cycles through **all 61 equation parameters**, rather than only a 16-element whitelist.
- Coupled OMEF has **61 independently editable A + 61 B parameters**, with a cursor sweeping all 122 during autonomous evolution.
- Evolution changes the actual global coupling, B offset, B mixing, interference, shared projection, eight directed source/receiver-node routes, strengths, phase gates, phase offsets, and real 1–144-step delays.
- Two quality/evolution controls (mutation depth and morph smoothness) can evolve; user-excluded points, ink, size, evolution speed and trail persistence remain stable.
- Automatic evolution avoids setting global coupling to zero, so both 10-dimensional OMEF machines remain interconnected unless the user manually decouples them.
- A continuous, parameter-sensitive **delayed state-space observation** combines actual outputs and actual delayed A/B states; there are no canned wave, flower, or silhouette paths. A wrapped sin/cos filter prevents sudden jumps in its observation angle.
- The tested observation coefficients prioritize varying folds and filament families rather than a more numerically different setting that produced nearly identical wing shapes.

## Tests
[Mobile and numeric verification run 45414038337](https://github.com/maaronfanberg-lab/me-/actions/runs/45414038337): **91/91 automated checks passed**, including real WebKit browser evolution with 3 accepted autonomous cycles, visibly changing 17 formula coefficients, changed global/topology variables, preserved excluded controls, and zero uncaught JavaScript errors. All 63 Original/common sliders and 154 Coupled range controls were exercised in mobile Chromium and WebKit. Test environment is browser emulation, not the user's physical iPhone.

The reproducible numerical stress script completed **1,000,000 default + 400,000 extreme-coupling + 40,000 decoupled solver steps** with no nonfinite output. Independent Original solver parity was zero. Matched-config image comparison was exactly zero difference.

### Equal-length normalized trajectory-histogram endpoint differences
These numbers are **statistical distribution changes**, not percentages of visible pixels changed or proofs of aesthetics.

| Directed link | Strength to +2 | Delay to 144 |
|---|---:|---:|
| B Pair → A Shadow | 66.2% | 53.5% |
| A Shadow → B Golden | 64.7% | 58.6% |
| B Golden → A Regime | 63.1% | 73.4% |
| A Regime → B Market | 63.1% | 73.9% |
| B Market → A Triad | 61.0% | 66.7% |
| A Triad → B Projection | 59.8% | 61.5% |
| B Projection → A Fibonacci | 60.9% | 63.2% |
| A Fibonacci → B Pair | 56.5% | 60.5% |

Global extremes changed the measured distribution roughly 55.6–65.2%.

## Limitations
This is a substantial mathematical, visual and functional improvement, but **a near-100% structural transformation for every individual slider is not yet demonstrated**. The historical best OMEF screenshot has not been independently matched by an objective image-similarity score. Test results prove stability and that controls respond, not that every generated sculpture is visually pleasing. Actual iPhone testing remains a user-side check.

The original live app was deliberately preserved as a fallback.
