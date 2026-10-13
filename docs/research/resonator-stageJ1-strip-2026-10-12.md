# RESONATOR Stage J1 — finish the strip: the engine loses everything the Tank page cannot reach (2026-10-12)

## 1. Observed problem
- Stage I took every feature except the Tank off the preview page, but left their engine code in place,
  switched off and unreachable, and the page still sent all ~50 removed controls at their defaults
  (`resonator-stageI-tank-only-2026-10-12.md`, "Leftover code"). The page also carried an unused first Tank
  definition and seven other shapes.
- Alex asked to finish the strip before the water tower is added.

## 2–3. Evidence used
No new external evidence is needed: this is a removal. The claim to prove is internal — that nothing the Tank
page can do changes. The method is the one used for Stages 1, P1, F and I: render the old and new engines with
the same input and compare every sample exactly (`Object.is`).

## 4. What changed
- **Engine (worklet), removed:** OMEF (attractor, coupling, regimes, inference, memory), spatialisation, FX
  (chorus, delay, wow, tremolo, orbit drive), the Dattorro plate reverb, the exciters other than the mallet
  (splash, plectrum, oscillator, wind, bow, phone mic in), Mics 2–4 and the stereo second mic, the
  modulators (LFOs, envelopes, followers), feedback, the humbucker/out-of-phase coils, the amp, tone stack and
  cabinet, WAV recording, the orbit stream.
- **Kept constants:** the pickup's fixed coil aperture (0.18) and its resonance (3 kHz, Q 1.6), and the level
  trim the Tank always used (`specTrim` 2.6, previously set by a `spec` message on every new body).
- **The engine accepts only the controls the page has** (`KEYS`: ratio, decay, loss, sub, drive, hard, blend,
  gain, tune, tone, bite, nl, angle, voices, osMax). Any other `p` message is ignored.
- **Page:** the unused first Tank definition and the other seven shapes; the removed knobs; the messages
  `pk`, `mode`, `spec`, `mic2`; the removed controls are no longer sent.
- Size: 3,059 → 1,993 lines, 187,348 → ~113,000 bytes.

## 6–7. Competing explanations, limits
- A removal can only be "the same" for what is tested. The proof covers every Size, every kept control at
  its minimum, a middle value and its maximum, 1, 3 and 8 voices, chords, strike and mic moves, a moved mass,
  Hush mid-ring, retuning mid-ring, a new body mid-ring, the sleep/governor path, the buffered engine's
  `osMax`, at 32 and 48 kHz.
- The CPU governor acts on measured time, which differs run to run, so the proof holds the clock still for
  both engines (a test of the code, not of the machine's timing).

## 9. Implementation mapping
- `qa-resonator/patch_j1.py` (verified edits; aborts on any mismatch, and on any leftover reference to a
  removed field).

## 10. Validation
| check | result |
|---|---|
| `j1_verify.mjs`: old engine with the old page's messages vs new engine with the new page's messages, 54 setups × 2 rates | 108/108 bit-identical, both channels, every sample |
| …and the new engine fed the OLD messages (stray messages for removed controls) | identical as well |
| mutation: level trim 2.6 → 2.59 | fails (max difference 0.0023) |
| `i1_browser.py` (same taps on the page before Stage I and this one, replayed) | bit-identical; every Stage I check passes |
| `stage1_verify`, `stage1_browser`, `p1_verify`, `p1_browser`, `webkit_check --browser=chromium` | pass (scoped to what the preview still has; see ratchets) |

**Ratchets (an error a check missed becomes a check):**
- *The harness must send what the page sends.* `harness.render()` never sent the `spec` message that every page
  sends with a new body, so offline renders ran the Tank without its level trim. The Sustain readout
  ("rings 1.25 × the setting") had been calibrated there. Measured with the trim (i.e. as the phone plays it),
  the 40 dB fall is 1.55 × the setting (1.32–1.73 × across Size, Stiffness, Damping, mallet, key, strength
  and Level). The readout now says 1.55 ×; `i1_engine.mjs` holds it within 15%. The harness, `p1_verify` and
  the in-browser offline render now send `spec` like the pages do, and the J1 engine no longer depends on it.
- Suites that compared the preview with older engines on removed features (`stage1_verify` T1, `p1_verify`
  sweep, `webkit_check` shapes) now compare only what the preview still has; a check that builds another
  shape takes its geometry from the live page.

**Post-change result after deployment:** pending Alex (nothing should sound or look different on the Tank).
