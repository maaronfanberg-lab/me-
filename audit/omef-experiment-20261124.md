# OMEF Exclusive — protected coupled-system experiment
Date: 2026-11-24

## Goal and guardrails
Recover naturally emergent, asymmetrical, interwoven mathematical filament sculpture from **two interacting ten-coordinate OMEF systems**, not decorative wave/flower presets. Keep the existing public `apps/omef-exclusive.html` unchanged until an experiment passes both numerical and browser tests. A backup was created at `backup/omef-pre-cross-memory-2026-11-24`.

## Code implemented
- Formula A retains the current coupled-filament coefficient set.
- Formula B starts from a distinct, quantized OMEF genome: `c=-2.12,d=.70,e=-3,h=-2.47,i=.24,pairFreqB=3,phaseSpeed=.005,edgeSpan=.345,projReg=.65,projCross=.09`.
- The shared projection starts at Formula B influence `0.70`, so both genuinely independent systems contribute to the single image.
- Directed links carry bounded signed influence through a phase gate that depends on the sender's actual OMEF signal and the cross-coupling setting: no shape templates or independent particles.
- A longer 5,100-step candidate screening check was added for autonomous evolution, rejecting some candidates that only briefly appear coherent.

## Numerical evidence
- **1,000,000 finite steps** in the asymmetric default coupled configuration. Mean transmitted drive ≈ 0.71992. Covariance minor/major eigenvalue ratio over the first 100k sampled steps ≈ 0.784 (a substantial 2D spread).
- **350,000 finite steps** at global coupling 4 and cross-system influence 3. Mean transmitted drive ≈ 0.9899. Covariance ratio ≈ 0.688.
- **100,000 finite steps** with cross-coupling 0, producing exactly zero transmitted drive.
- Unlinked Original/uncoupled Twin parity difference: exactly 0 in the test.
- Deterministic search covered 150 asymmetric A/B configurations. Several 90k-point renders showed layered, intertwined forms instead of the previous narrow stripe.
- A control-baseline sanity check uses **equal-length samples** and returns 0% difference for identical settings.

## Mobile-sized browser audit
GitHub Actions workflow run [45392695932](https://github.com/maaronfanberg-lab/me-/actions/runs/45392695932) passed **82/82** checks. Tested Chromium and WebKit with mobile viewports, Original 63 range inputs, Coupled 154 range inputs, restoring distinct A/B coefficients, real pointer interactions, themes, full-screen controls, and JS runtime errors. This does not test the user's physical iPhone.

## What is *not* proven
- This is an experimental preview, **not the replacement for live OMEF Exclusive**.
- It has **not** proven equivalence to the user's best historical image by a controlled, equal-point-count visual comparison.
- Individual coupling endpoint responsiveness is **not yet at the near-100% standard**. In a deterministic equal-length 3,500-step histogram check, the weakest far-right link change was ~1.65%; strongest tested right-end change was ~70%. There were 28 coupling-related controls in the endpoint sweep. This is a known gap, not a passed requirement.
- Browser automation is not a substitute for testing the app on the user's actual iPhone.

## Published preview
The separate Pages file `apps/omef-exclusive-coupled-lab-20261124.html` was created from this experiment. It leaves the existing `apps/omef-exclusive.html` untouched.

## Next technical experiment
Improve individual-link sensitivity **inside the delayed node-to-node equations**, with explicit controls over transferred memory and phase response, while rejecting high-entropy clouds and preserving the strong nonlinear interactions already observed. Re-run equal-length endpoint tests, 1M-step render, and Chromium/WebKit interface audit before considering replacement of the live app.
