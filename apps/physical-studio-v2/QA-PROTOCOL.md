# Physical Studio — Verification Protocol

This protocol exists to prevent “code changed” from being reported as “works.” A build is not considered verified until the required QA evidence exists for the exact current commit and the applicable simulator/device gates have passed.

## Non-negotiable rule

**No test evidence for the current commit = no user-facing claim that the build works, is fixed, is ready, or should be tested.**

Before presenting a build link as a candidate, the development sequence is mandatory:

1. Commit the current source.
2. Run simulator self-test.
3. Run dev-browser checks for the changed interaction.
4. Run full simulator.
5. Run automated Playwright/WebKit/Chromium QA against the current commit.
6. Run physics fuzzer for physics-related changes.
7. Run audio analysis for audio-related changes.
8. Inspect screenshots/error logs/release report.
9. Fix every blocking error code.
10. Rerun the focused failing test.
11. Rerun the full applicable gate.
12. Only then present the build, explicitly separating simulator verification from real-iPhone verification.

If any required result is missing, failed, stale relative to the current commit SHA, or produced by a harness whose self-test has not passed, the release status is RED.

## Status words

- **Prototype** — code exists, behavior is not yet verified.
- **Implemented** — feature is wired into the running app; verification may still be pending.
- **Verified in simulator** — required automated/browser/simulator evidence passes for the exact current commit.
- **Verified on iPhone** — the user has confirmed the named behavior on the target iPhone.
- Never use **fixed** or **works** for target-device behavior until the target-device gate has passed.

## Change discipline

1. Preserve a known-good commit before any risky change.
2. Change one subsystem at a time whenever possible: camera, scene interaction, physics, audio, or UI.
3. Do not mix a camera change with a UI/layout change in the same commit unless inseparable.
4. After every change, run the directly relevant diagnostic before the full gate.
5. A failed check blocks the build. Fix it before asking the user to test.
6. A code edit is never evidence of a fix.
7. Every fix attempt must be followed by a rerun of the test that exposed the failure.
8. After the focused test passes, rerun the full applicable gate to detect regressions.
9. If the same bug survives two attempted fixes, stop guessing. Research a proven implementation/reference before another attempt.
10. If the test harness produces suspicious or contradictory results, test the harness before changing the app.

## Error-code rule

All automated diagnostics should emit a `QA-*` code from `qa/error-codes.json` whenever possible. Every blocking failure record must include:

- error code
- observed value/behavior
- expected value/range
- subsystem
- evidence (log, screenshot, trace, waveform, seed, or state dump)
- suggested next diagnostic step
- reproduction seed/sequence when available

An unresolved blocking error code automatically keeps the release gate RED.

## Simulator gate

Open `simulator.html` and run the full suite. The suite must test the real app, not a copied mockup.

### Boot and rendering
- App iframe loads without an uncaught error.
- WebGL canvas exists and has non-zero dimensions.
- A captured frame contains real visual variation (not a blank/solid canvas).
- Scene continues to render after interaction.

### Camera interaction
- Horizontal one-finger-style drag measurably changes the rendered frame.
- Vertical one-finger-style drag measurably changes the rendered frame.
- Repeated horizontal drags continue to change the scene rather than toggling between two orientations.
- Repeated vertical drags continue to change the scene.
- Zoom interaction changes the rendered frame without throwing.
- Camera movement must not cause NaN/blank rendering.

### UI interaction
- Palette buttons can be activated.
- Active tool state changes visibly.
- Inspector can be shown for a selectable object when the app exposes selection.
- UI remains inside the viewport at phone dimensions.
- No control may cover its own label/value.

### Physics
- A dynamic body changes position after excitation.
- Anchored bodies remain fixed.
- Spring endpoints continue to follow their bodies.
- Simulation does not produce NaN/Infinity after a stress interval.
- Reset returns to a finite stable state.
- Seeded fuzz test passes or yields a reproducible blocking seed.

### Audio
- The actual `physics-worklet.js` is loaded into an AudioWorklet.
- A small test graph is sent to the worklet.
- Before excitation, measured output is near silence.
- After a `hit`, measurable non-zero RMS output appears.
- Output decays rather than remaining DC/full-scale.
- Left and right channels remain finite and below clipping threshold.

## Visual review gate

Automated pass is necessary but not sufficient. Before sending a build link:

1. Look at the simulator’s live app view at an iPhone-sized viewport.
2. Look at captured before/after/stress frames.
3. Confirm that the intended object and controls are visually present and not overlapping.
4. Confirm the design still follows the current reference direction: 3D workspace first, compact floating contextual inspectors, minimal permanent chrome.
5. If the simulator view looks ugly, crowded, clipped, or obviously wrong, do not send it merely because tests are green.

## Audio review gate

Before sharing a build that changes audio:

1. Run the worklet audio test.
2. Inspect RMS, peak, DC, decay and waveform evidence.
3. Reject silence, DC offset, runaway full-scale output, NaN, clipping, or unstable sustained output.
4. If timbre is materially changed, report it as simulator-verified only; subjective sound quality still requires listening on a real device.

## Target iPhone gate

The simulator cannot perfectly reproduce iOS Safari, speaker response, touch hardware, or ChatGPT’s in-app browser. The final gate for touch feel and perceived sound is the actual iPhone.

When asking for device verification, name the exact behavior to test. Example: “Automated WebKit and simulator gates passed vertical orbit; please verify vertical orbit on iPhone.” Do not ask the user to retest unrelated features.

## Release checklist

A link may be presented as a verified candidate only when:

- [ ] Current source committed
- [ ] QA evidence references current commit SHA
- [ ] Simulator self-test PASS
- [ ] Dev-browser changed-behavior check PASS
- [ ] Automated WebKit/Chromium gate PASS
- [ ] Simulator boot/render PASS
- [ ] Horizontal orbit PASS
- [ ] Vertical orbit PASS
- [ ] UI interaction PASS
- [ ] Physics stability/fuzz PASS when applicable
- [ ] Audio worklet output PASS when applicable
- [ ] Visual review PASS
- [ ] No uncaught errors in logs
- [ ] No unresolved blocking `QA-*` codes
- [ ] Exact unverified target-device behaviors explicitly stated
