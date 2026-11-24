# OMEF Exclusive — Full Spectrum Evolution (24 November 2026)

## Why previous evolutions looked similar
The former evolution engine changed only about 6–11 coefficients and one link per cycle, despite exposing 122 A/B coefficients and 24 numeric link sliders. Its observation lens could saturate near 98.5% transfer into one dominant state projection, so different mathematical inputs often mapped to visually similar wing or vertical-spire silhouettes. Its short-run histogram-novelty test could mislabel small changes inside the same silhouette as a newly discovered structure.

## Implemented correction
- **61/61 Original OMEF coefficients** are mutated simultaneously in automatic drift. Numeric slider thumbs track the actual smoothed equation state, rather than jumping to a target; evolution cadence follows the user's existing speed choice without changing that speed slider.
- **122/122 Coupled A/B equation coefficients** are mutated in every search proposal and successful exploration transition.
- **24/24 numeric directed-link controls** (eight strengths, eight real delays, eight phase offsets) move in each proposal, along with four numeric global controls and the shared projection selector.
- The topology's sending and receiving nodes, gates and sending engine also evolve across cycles, using causal directed signals between the two actual 10D equations.
- Mutation-depth and drift-smoothness controls may evolve. **Points, ink, size, evolution speed and trail persistence never change autonomously.**
- Slider thumbs are updated continuously to follow the equations and link crossfade; no fake UI input events are generated.
- The delayed state-space observation now blends **three continuously weighted native/cross-delayed OMEF coordinate bases**, retains at least 15% of the native observer, and smoothly interpolates wrapped phase. No hand-selected flower/wing/spiral shape paths are inserted.
- Structural novelty now considers the long-run, coarse 8×6 outline/mass distribution and aspect ratio, not only fine particle occupancy, curvature and pixel difference. An archive avoids repeatedly declaring an already-seen silhouette a new family. Failed search proposals are rejected; valid but repetitive ones remain search steps.
- Extended search exploration can make larger equation-space jumps after repeated failures to discover a distinct family, while maintaining bounded coherent trajectories.
- Discovered families are held briefly for inspection before exploration resumes; the user can still pause evolution at any time.

## Independent verification
[GitHub Actions run 45433517773](https://github.com/maaronfanberg-lab/me-/actions/runs/45433517773) passed **99/99 checks** with a real browser engine and mobile-sized iPhone 13 screen emulation in Chromium and WebKit.

- 61/61 Original equation sliders visibly moved in each browser over auto-drift, with no excluded sliders moving.
- 122/122 Coupled formula sliders and 24/24 numeric coupling sliders visibly moved during the same three accepted auto-evolution cycles.
- All exposed range sliders accepted actual min/max pointer/user-event testing, mode switching and pause/resume, with no uncaught JavaScript errors.
- 1,000,000 default Coupled steps, 400,000 extreme-coupling steps, and 40,000 decoupled steps completed without non-finite output. Original independent oscillator parity was zero.
- 9/9 offscreen full-spectrum evolution tests accepted coherent candidates and each moved all 122 coefficients, 24 link values and all five global settings while protecting excluded controls.
- Each of the 122 separately tested A/B formula slider endpoints changed the normalized 32×32 trajectory distribution: **minimum 69.15%, median 83.13%, maximum 93.20%**. These are histogram-distribution differences, not perceptual percentages of screen pixels changed or a promise of equally beautiful sculptures.

## Release
The isolated experimental source is `experiment/omef-full-spectrum-search-2026-11-24:apps/omef-exclusive.html`. A separate public Pages file, `apps/omef-exclusive-full-spectrum-20261124.html`, was created from the exact audited source with only the HTML title and heading altered. The original public `apps/omef-exclusive.html` and earlier Lab versions were not overwritten.

Public URL: https://maaronfanberg-lab.github.io/me-/apps/omef-exclusive-full-spectrum-20261124.html

## What remains empirical
A physical iPhone browser was not remotely accessed; automated iPhone-sized WebKit/Chromium behavior has been tested. Screen-level beauty remains subjective, and a true near-100% transformation for every control is not demonstrated. The visual search now discriminates broad morphological families more rigorously, but the user's real experience with its shapes remains the ultimate evaluation.
