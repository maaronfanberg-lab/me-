# Physical Studio — QA Toolchain

This file defines the permanent diagnostic toolchain for Physical Studio. The purpose is to prevent source changes from being mistaken for verified behavior.

## Required release rule

A build is not presented as ready until all applicable required tools below pass, any emitted error codes are resolved, and the relevant tools are rerun clean after the fix.

Order of operations:
1. Simulator self-test.
2. Dev browser interaction checks.
3. Full simulator suite.
4. Automated browser/visual regression suite.
5. Physics invariant/stress suite.
6. Audio analysis suite for audio changes.
7. Persistence/state round-trip suite for model changes.
8. Performance/resource suite for scene/renderer changes.
9. Human visual review in the iPhone-sized harness.
10. Target iPhone verification for touch feel, Safari-specific behavior, and subjective audio.

A code edit alone never changes status to "works" or "fixed."

## Tool 1 — Simulator self-test
File: `simulator-selftest.html`

Purpose: prove the QA system itself can detect deliberately broken conditions.

Must detect:
- blank render
- frozen render
- invalid/NaN signal values
- silence when sound is expected
- UI overflow
- expected-good fixtures

If this fails, every downstream QA result is untrusted.

## Tool 2 — Dev browser
File: `dev-browser.html`

Purpose: manual but repeatable iPhone-sized browser laboratory.

Functions:
- horizontal drag
- vertical drag
- repeated orbit
- tap
- pinch/dolly
- frame capture
- frame-difference measurement
- viewport overflow inspection
- runtime error display

Use this immediately after interaction/UI changes.

## Tool 3 — Full simulator
File: `simulator.html`

Purpose: automated end-to-end behavior checks against the real app.

Required classes:
- boot/render
- horizontal orbit
- vertical orbit
- repeated orbit
- palette/UI interaction
- viewport containment
- physics excitation/stability
- AudioWorklet signal production

## Tool 4 — Automated browser runner
Recommended implementation: Playwright using Chromium plus WebKit projects and mobile/touch emulation.

Purpose:
- run the same core actions without manual clicking
- capture screenshots and traces on failure
- compare behavior across browser engines
- exercise reload/navigation/state restoration
- become the CI gate in GitHub Actions

Required artifacts on failure:
- screenshot
- browser trace
- console/runtime log
- machine-readable result JSON

Important: WebKit automation is a useful approximation but is not equivalent to real iOS Safari hardware; actual iPhone verification remains a separate final gate.

## Tool 5 — Visual regression detector
Purpose: catch "technically functional but visually ruined" changes.

Method:
- capture deterministic screenshots at standard camera states
- compare against approved reference frames
- calculate pixel/perceptual delta
- highlight changed regions

Reference states should include:
- initial scene
- body selected
- spring selected
- microphone selected
- inspector open
- portrait phone viewport

A large unexplained visual delta blocks release.

## Tool 6 — Physics invariant monitor
Purpose: detect unstable or impossible simulation states.

Check continuously during test runs:
- all positions/velocities finite
- no NaN/Infinity
- anchored bodies stay fixed within tolerance
- spring endpoint indices remain valid
- spring lengths remain finite and nonnegative
- kinetic energy remains bounded after a stress excitation
- reset returns to stable finite state

Stress cases:
- maximum stiffness
- minimum/maximum mass
- many repeated hits
- dragging a body far from equilibrium
- rapid create/delete spring operations

## Tool 7 — Physics fuzzer
Purpose: find combinations humans would not think to test.

Generate deterministic seeded sequences of:
- add body
- add anchor
- connect spring
- delete object
- change mass
- change damping
- change stiffness
- hit body
- move body
- reset

Every failure records seed + operation sequence so it can be replayed exactly.

## Tool 8 — Audio laboratory
Purpose: verify what the audio engine actually produces, not just whether AudioWorklet loaded.

Measurements:
- pre-hit RMS/noise floor
- post-hit RMS
- peak amplitude
- DC offset
- decay envelope
- left/right channel finiteness
- clipping count
- FFT/spectral centroid or dominant peaks

Failure cases:
- silence after excitation
- permanent full-scale output
- NaN/Infinity
- excessive DC
- non-decaying runaway signal
- channel unexpectedly dead

For deterministic DSP unit tests, use offline rendering where supported; real AudioWorklet execution must also be tested in a secure browser context.

## Tool 9 — Performance/resource monitor
Purpose: prevent a visually nice build from becoming unusable on phone.

Track:
- frame time / approximate FPS
- long-frame count
- Three.js `renderer.info.memory.geometries`
- Three.js `renderer.info.memory.textures`
- render calls/triangles
- object count
- sustained stress behavior

Regression thresholds should be relative to the last known-good reference build.

## Tool 10 — Persistence round-trip tester
Purpose: verify saved models actually reproduce themselves.

Procedure:
1. create a nontrivial model
2. export/save
3. clear scene
4. import/load
5. compare canonical model data

Check:
- body count/properties/positions
- anchor flags
- spring endpoints/properties
- mic/exciter state
- no orphan links

## Tool 11 — Dependency/boot diagnostic
Purpose: catch external CDN/module/security-context failures.

Check:
- Three.js module loads
- OrbitControls loads
- AudioWorklet available under current origin
- required files return successfully
- no unhandled promise rejection
- no module import failure

## Tool 12 — Release gate report
Purpose: one machine-readable answer to "is this build ready to show?"

Output fields:
- build/commit SHA
- timestamp
- self-test status
- interaction status
- visual status
- physics status
- audio status
- persistence status
- performance status
- unresolved error codes
- simulator verification status
- target-device verification status

Release gate is RED if any required check is failed, skipped without justification, stale relative to the current commit, or if unresolved error codes exist.

## Error code families

- `QA-BOOT-xxx` — loading/import/security-context problems
- `QA-REN-xxx` — rendering/canvas/frame failures
- `QA-CAM-xxx` — orbit/pan/zoom failures
- `QA-UI-xxx` — layout/control/selection failures
- `QA-PHY-xxx` — physics graph/stability failures
- `QA-AUD-xxx` — AudioWorklet/signal failures
- `QA-PERF-xxx` — performance/resource regressions
- `QA-STATE-xxx` — save/load/model integrity failures
- `QA-HARNESS-xxx` — simulator/test-harness failures
- `QA-REG-xxx` — visual/behavior regression failures

Every error must contain:
- code
- short human description
- observed value
- expected value/range
- likely subsystem
- suggested next diagnostic step
- reproducible test/seed if available

## Fix protocol

When a required check fails:
1. Record exact code and evidence.
2. Reproduce failure at least once.
3. Isolate one subsystem where possible.
4. Make the smallest plausible fix.
5. Run the directly related diagnostic first.
6. Run the full required gate again.
7. If the same error survives two fixes, stop guessing and research a proven implementation/reference before another architectural change.
8. Do not send a user-facing test link merely because code was modified.

## Current verification vocabulary

- **Prototype** — exists, unverified.
- **Implemented** — feature is present; applicable automated checks may still be pending.
- **Simulator verified** — required simulator/toolchain checks passed for the current commit.
- **Target-device verified** — user confirmed the named behavior on the actual iPhone.
- **Fixed/works** — only use for a behavior whose applicable verification gate has actually passed.
