# RESONATOR QA harness

Runs the RESONATOR audio engine offline in Node (no browser) and measures it.

- `audit.mjs` — Stage 1 audit: determinism, numeric health, loudness/true peak, every control.
- `verify.mjs` — compares against the previous build. First run
  `git show 3a484d7:apps/resonator.html > qa-resonator/resonator.orig.html`.
- `ceil.mjs` — true-peak ceiling across 112 extreme cases.
- `ui_test.py`, `selftest.py`, `bench.py` — Playwright checks on a phone-sized touch viewport.
- `patch.py`, `patch2.py`, `patch3.py` — the verified edits applied (abort on any mismatch).
- `learn_claims.mjs` — verifies every sound claim taught in the learning path; reports the octave-trap known issue.
- `eig_tql.js` — the fast eigen-solver (also embedded in the engine); `f5verify.mjs` — old vs new on every shape/size; `tank_switch.py` — shape-switch browser check.

Check (ratchet): controls that only act in one strike mode are tested in that mode.

## Stage 1 (preview page `apps/resonator-next.html`)
- `patch_s1.py` — builds the preview from the live page (tuning off the audio thread, octave-trap fix, Copy report).
- `stage1_verify.mjs` — offline proofs: live vs preview bit-identical; background tuning vs ordinary tuning bit-identical; octave trap gone.
- `stage1_browser.py` — browser proofs: audio-clock stalls (live vs preview), every shape sounds, trap via real taps, shadow failure and no-Worker fallbacks, Copy report.
- Any harness script can target the preview with `RESONATOR_SRC=apps/resonator-next.html`.
- All of the above run on GitHub Actions: `.github/workflows/resonator-qa.yml` ("RESONATOR QA").

## Stages 2–4 (preview)
Each stage is a verified patch applied on top of the previous one (`patch_s2.py` → `patch_s3.py` →
`patch_s4.py`); each aborts on any mismatch.
- Stage 2, free building: `stage2_browser.py` — add/delete masses, undo across shape changes, presets, mic placement across cuts.
- Stage 3, new exciters: `stage3_measure.mjs --check` (levels vs mallet, pitch, onset, NaN, determinism); `stage3_browser.py` (plectrum, oscillator hold/release, wind, Mic in with Chromium's fake microphone).
- Stage 4, more mics: `stage4_verify.mjs` (pan isolation, every voice, refusal, worst-case ceiling, determinism, level); `stage4_browser.py` (Mics 2–4 by taps, renumbering, undo, pin, presets, remove).
- Stage 5, envelopes and followers: `stage5_verify.mjs` (LFOs bit-identical to live, envelope times, retrigger/gate, follower vs its equations, calibration across shapes, worst case); `stage5_browser.py` (types by taps, meters, fake phone mic, presets).

Checks added by the ratchet (an error a check missed becomes a permanent check):
- Edits that change nothing physical must send the engine exactly the untouched body (`stage4_browser.py`; mutation-tested).
- Page and engine must agree on every mic after pin and undo (`stage4_browser.py`).
- Depth 0 must return a modulator's destination to its own setting (`stage5_verify.mjs`).

## Safari's engine (WebKit)
- `webkit_check.py` — both pages in Playwright WebKit with iPhone 13 emulation: start-up with no
  script error, background tuner, live audio (when the machine has an audio device; otherwise
  reported as NOTE), every shape, the Tank freeze, the engine rendered offline inside WebKit and
  compared with Node fed the same messages (`webkit_ref.mjs`), JavaScriptCore speed, every tap
  flow (turn pad, add, delete, undo, exciter chips, envelope type, Mic 2), screenshots of every tab.
  `--browser=chromium` runs the same checks locally.
- `.github/workflows/resonator-webkit.yml` ("RESONATOR WebKit") runs it on Linux and macOS and
  pushes the results to branches `qa-results/webkit-linux` and `qa-results/webkit-macos`:
  `git fetch origin qa-results/webkit-linux && git show FETCH_HEAD:summary.txt`.
- Ratchet: an offline render does not deliver the engine's messages while it runs (measured in
  Chromium). The check waits for the engine's `ready` before rendering; a fixed 250 ms wait was
  shorter than Tank's tuning and rendered silence (a test artefact, not an engine fault).

## Phone performance P1 (preview)
- `patch_p1.py` — the verified edits (skip voices at rest, sleep, CPU measurement, governor, no
  per-sample arrays in the effects).
- `p1_verify.mjs [baseline.html]` — sleep and governor off are bit-identical to the preview before P1
  (189 setups); the sleep bound (< −100 dBFS) with real sleeps; the governor (sheds smoothly, respects
  its limit, recovers, consulted only when switched on); the CPU estimate vs a precise clock; a
  timing table (skip with `P1_SKIP_COST=1`).
- `p1_cost_one.mjs` — one timing in a fresh process. Ratchet: several engine copies in one process
  share compiled code and distort small timings (a sleep that looked 4× costlier was this).
- `p1_browser.py [--browser=webkit]` — perf turned on, CPU shown, live reading rises with work,
  governor and its message, voices sleep and wake, Copy report line.

## Stage F, plate reverb (preview)
- `patch_f1.py` (the reverb: Dattorro 1997, Table 1 coefficients, Table 2 taps; delay lengths
  cross-checked against the freeverb3 notes) and `patch_f2.py` (calibration from measurement: reverb
  time, level, Hush).
- `f1_verify.mjs [baseline.html]` — Reverb 0 bit-identical (174 setups); measured T60 (Schroeder,
  ISO 3382 T30) within 5% of the setting over 0.6–12 s; tone vs the damping filter's prediction;
  stereo decorrelation; pre-delay; 12 s stability; level vs dry; true peak; determinism; Hush; a new
  body keeps the tail. `f1_browser.py [--browser=webkit]` — the FX tab, taps, audible tail, shape
  change, Hush, presets old and new, double-tap reset.
- Ratchet: a bit-identity sweep iterates the *baseline's* controls; a control added later is
  supposed to change the sound (`p1_verify.mjs` swept the new page's knobs and flagged Reverb).
