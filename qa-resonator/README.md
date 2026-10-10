# RESONATOR QA harness

Runs the RESONATOR audio engine offline in Node (no browser) and measures it.

- `audit.mjs` — Stage 1 audit: determinism, numeric health, loudness/true peak, every control.
- `verify.mjs` — compares against the previous build. First run
  `git show 3a484d7:apps/resonator.html > qa-resonator/resonator.orig.html`.
- `ceil.mjs` — true-peak ceiling across 112 extreme cases.
- `ui_test.py`, `selftest.py`, `bench.py` — Playwright checks on a phone-sized touch viewport.
- `patch.py`, `patch2.py`, `patch3.py` — the verified edits applied (abort on any mismatch).
- `eig_tql.js` — the fast eigen-solver (also embedded in the engine); `f5verify.mjs` — old vs new on every shape/size; `tank_switch.py` — shape-switch browser check.

Check (ratchet): controls that only act in one strike mode are tested in that mode.
