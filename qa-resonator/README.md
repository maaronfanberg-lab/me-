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
