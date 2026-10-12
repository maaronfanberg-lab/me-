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

## Stage G, video with sound (preview)
- `patch_g1.py` (Record video / Save video on the Strike tab: canvas.captureStream + a stream tap on
  the master gain, MediaRecorder, the share sheet or a download) and `patch_g2.py` (the stage
  gradient painted into the canvas while recording).
- `g1_browser.py [--browser=webkit]` — records 4 s while playing, then checks the file: the browser
  decodes its own recording (picture size, sound level); ffprobe/ffmpeg confirm one video and one
  audio stream, the length, the sound in it, and a frame that shows the body (full resolution:
  a downscale averaged the small balls away, a test artefact). Also: Save hands over a named file,
  the time limit stops by itself, it still plays afterwards, and without MediaRecorder the page
  explains.
- `webkit_check.py` now also records the page's main-thread gaps beside the audio-clock freeze, so
  an audio stall can be told from a page stall.
- Ratchet: a pixel check on the canvas reads it at the canvas's own scale (`cv.width / W`), not at
  `devicePixelRatio`: the page draws at min(2, devicePixelRatio), so on an emulated iPhone (3×) the
  recording-dot check looked a third too far right and failed while the dot was there (WebKit macOS
  CI, 2026-10-12; that run also showed Safari's engine recording MP4 with sound).

## Stage H, factory presets and the Learn tab (preview)
- `patch_h1.py` — page only (the engine is byte-identical): ten factory presets listed first in
  Presets, the Learn tab (nine A/B lessons and a building how-to), and presets that come back as saved
  (the tuning reference, spectrum, bow, Mic axis X, chips, a readable load message).
- `h1_claims.mjs [page]` — every number the Learn tab teaches, measured with exactly what the page
  sends (the lessons, presets and `presetFrom()` are read from the page, so the text checked is the
  text shipped), at 32, 22.05 and 48 kHz (`H1_RATES=32000` for one). Also each factory preset: clean,
  true peak, loudness near the default instrument's, no near-silent key, and what its description
  says (the bow and wind sound with no key, the gong's pitch sinks, the pad's tone opens, the bell
  moves between the ears).
- `h1_browser.py [--browser=webkit]` — tabs fit at 390 and 375 px; every lesson's A and B set exactly
  their values, build the body with the shape's own strike and mic, and play E4 at 0.8 once; the
  explanation opens after both; Play again; Build your own; "Put my instrument back" returns shape,
  knobs, bow, Mic axis X, spectrum, scale, pickups and tuning; each factory preset loads, says what it
  is (still readable 2 s later) and plays; Delete refuses factory presets; a saved preset reloads with
  the same partial tuned; a preset from before this stage still loads.
- Ratchet: a preset rebuilt with its *saved* strike and mic can tune a different partial than the one
  it was saved with (the engine ranks modes with the build-time strike and mic, Stage 1). Measured:
  a 15-mass string with the strike and mic near an end reloaded with its reference mode at 622 Hz
  instead of 314 Hz, an octave up the mode ladder, so the keys sounded an octave down. Presets now save
  the build-time strike and mic and rebuild with them; the check keeps the round trip honest.
- Ratchet: a description is a claim. The first "Feedback organ" was measured before shipping: its
  self-oscillation landed hundreds of cents from the key and sat at full scale whatever the Level
  (the output's tanh saturates), so it was replaced.
- Ratchet: an expectation about the page comes from the page's own rule. The heavy-body note is shown
  when springs × oversampling > 190; Steel tank is 168 × 1, and the note seen right after loading it
  was computed with the previous body's oversampling.
- Ratchet (Stage 4 test, fixed here): two analysers read one after the other can straddle a render
  quantum, so a mono signal once measured 0.049 different left to right. The difference is now formed
  inside the audio graph and read once.
