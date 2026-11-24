# OMEF Exclusive — sliders that visibly reshape the Original attractor

**Observed problem (Alex, 2026-11-24):** moving sliders did not produce significantly different shapes; the image mostly just evolved.

**Measurement before change.** Headless Chromium at phone size, Original mode, auto drift off. For every one of the 61 genome controls: screenshot, move the slider 30% of its range, wait 4 s, screenshot. Difference = normalised L1 between the two canvas images; noise floor = same wait with no change (0.12). Result: 36 of 61 controls cleared 2× floor; worst were Delay C (0.10, below the floor), Feedback mix, R1 U4², Retention span, Delay B, Feedback damping. Cause: in the historical OMEF-A recurrence many coefficients sit inside small term weights (e.g. market 0.04–0.15), so the trajectory changes but its drawn silhouette barely does.

**Mechanism implemented.** The recurrence is untouched. Each control also turns the 2D observation window through the running 10D state toward the quantities that control acts on: its own equation term at two coordinates, its delay (delay coordinates of the pre-activation drive), its regime weight, or its phase. Angle = 3.3 × (distance from the loaded configuration / slider range). Observables are taken through a 34-step running memory and centred/scaled by their own running statistics. Feedback and dynamics still use the native output, so this is observational only. Reference = the configuration last loaded by Restore / Next attractor.

**Validation.**
- Additivity: all 6 tested starting configurations × 50,000 steps bit-identical to the previous version when no control is moved. Coupled mode bit-identical (unchanged).
- Same 61-control live test after the change: 61 of 61 clear 2× floor; minimum 0.24 (was 0.095), median 0.33 (was 0.26).
- Distinctness between controls (nearest other control's image): median 0.24.
- Cost: ~165k steps/s with all 61 controls moved vs ~420k before (dev machine; not a phone measurement).

**Coupled mode — not changed.** The same approach was tried there and measured worse: 51/61 vs 61/61 against the floor, and lower distinctness between controls (median 0.15 vs 0.18). The existing coupled observer bends every control into a similar rope; that remains open.
