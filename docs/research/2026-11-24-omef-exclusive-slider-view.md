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

## Stage 2 — silk starting attractors (2026-11-24)

**Observed:** Alex shared silk/veil reference images and asked that the sliders be able to reach that look. Measured: from the existing "orbital lattice" start, slider moves already give folded silk sheets; from the other five starts they mostly give scribbles.

**Search.** 6,111 random coefficient sets near the six existing starts (native recurrence, no view). Silk criterion: sharp turns (>0.6 rad between consecutive steps) in <0.8% of steps, mean turning >0.012 rad (not a plain loop), sheet occupancy 22–62%, irregular silhouette. 220 passed. Robustness: 21 controls moved ±12% each with the view on; kept sets where ≥95% of moves stay silky (100 left), then picked by farthest-apart image.

**Stationarity check (caught 4 failures):** compared the drawing at 30k vs 60k steps. Four candidates (silk leaf, silk horn, silk loop, nested silk shell) keep drifting by themselves (window difference 0.56–0.64), so a slider move could not be told apart from drift. They were dropped.

**Added to Next attractor:** silk fin, silk drape, twisted silk ribbon, silk bell. The six original starts are bit-identical.

**Gate.** Every control moved 15% from each new start: 244/244 clear max(0.2, 2× that start's own drift), minimum 0.25. Live page: no errors; Next attractor reaches the new starts; silk drape + Shadow cross +15% gives a folded silk shell.
