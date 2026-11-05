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
