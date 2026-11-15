# Project Ω: Statistical Attractor Laboratory

Standalone browser visualization of **three graph-coupled Lorenz systems**, forming a **nine-dimensional nonlinear ordinary differential equation**.

## Run

Open [the live app](https://maaronfanberg-lab.github.io/me-/experiments/omega-attractor/) once GitHub Pages deploys the latest main branch. Or open `index.html` locally in a modern browser. There is no backend, build system, or third-party dependency.

## Equations

For nodes `i = 1, 2, 3`, let `L = diag(W1) - W` be the weighted graph Laplacian. The equations are

    x'_i = sigma (y_i - x_i) - kappa_x (Lx)_i
    y'_i = x_i (rho_i - z_i) - y_i - kappa_y (Ly)_i
    z'_i = x_i y_i - beta z_i - kappa_z (Lz)_i

where `rho_i` may incorporate the diagonal of the graph heat operator `exp(-tau*g*L)`.

Graph spectral diagnostics include heat trace, spectral entropy, graph Betti counts, Gaussian KL divergence, and squared 2-Wasserstein distance between centered Gaussian covariances. The Ω score is **not** a probability or a p-value.

The ODE is integrated numerically by fixed-step RK4. A plotted orbit and a finite-time Lyapunov estimate do **not** constitute a mathematical proof of a chaotic attractor. Extreme settings can cause numerical instability; reduce the time step and reset.

## Interaction

31 working range sliders alter the dynamical equations, graph geometry, numerical solver, statistical diagnostics or camera/ink rendering. Additional controls select the initial regime, observable projection and color mapping. The app includes pause, step, reset, JSON preset export/import and PNG export.

The app is self-contained and works offline. On phones, scroll past the visualization to reach the controls.

## Verification

With Python, Playwright and a Chromium browser installed, run

    python tests/test_math.py

The smoke test compares graph heat trace, KL divergence, Wasserstein distance and graph Betti counts against exact finite-dimensional values, counts 31 sliders, and exercises interactive controls.


## Visual-first controls (2026-11-05 update)

On phones, the live plot takes approximately 65% of the initial viewport and remains visible as you scroll through the 31 sliders. Use **Fullscreen** to expand the plot. If the browser supports the Fullscreen API it is used; iPhone browsers that do not allow arbitrary-element fullscreen instead use a full-viewport immersive fallback. Tap **Sliders** in immersive mode for a compact scrollable drawer. The projection shifts to keep the attractor visible above the drawer.

**Live morph while dragging** is on by default. Changing a field/graph/spectral parameter changes the actual 9D ODE and immediately clears the stale trajectory, integrates a new RK4 trajectory segment, and resumes animation even if paused. Slider input is coalesced into animation frames. Uncheck Live morph to preserve a paused orbit while adjusting parameters. Camera/ink sliders redraw immediately. Diagnostic weight and topology-cutoff sliders switch the color view to the Ω diagnostic so their effect can be seen; the statistics-window slider changes numerical readouts, not the vector field.

Two test scripts are available:
```sh
python tests/test_math.py
python tests/test_ui.py
```
The latter checks fullscreen, control drawer, live morph, all 31 slider controls, and absence of browser JavaScript errors at phone/tablet/desktop widths.



## Visual-only mode (2026-11-05)

The entire opening screen is now the live Canvas artwork. No headline, statistics panel, descriptive text, equations, or introductory material renders in the app. Two small icon buttons provide browser fullscreen and a slider drawer. This reduces opportunities for in-app browsers to substitute article/reader content for the simulation, although the browser's own Reader setting remains user-controlled.

All 31 sliders remain in the overlay drawer and respond while dragging. The 9D ODE continues to run and changes to its parameters reset the old trajectory segment. The statistics-memory slider now shifts the baseline for Ω coloring, providing a visible diagnostic effect without adding text. Exact numerical diagnostics are computed but hidden from the default stage.

Direct fresh-path entry: https://maaronfanberg-lab.github.io/me-/experiments/omega-attractor/visual.html

The alternative `visual.html` deliberately uses a distinct URL to help bypass reader preferences cached against the previous path. Both `visual.html` and `index.html` contain the same self-contained app.

