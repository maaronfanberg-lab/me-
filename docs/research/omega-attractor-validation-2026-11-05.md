# Research and verification record: Project Ω attractor (2026-11-05)

## Observed problem and research question
The user requested that a sprawling statistical mathematical manuscript be transformed into a **mathematically accurate interactive attractor** with numerous controls that actually affect computations. The central distinction is between a numerical orbit rendering and a proof that an invariant attractor exists.

## Ten-level research gate
1. **Observed baseline:** A standalone 9D graph-coupled Lorenz simulator was developed and tested locally; 31 sliders were counted.
2. **Foundations:** Lorenz (1963), deterministic nonperiodic flow; classical finite-dimensional ODE local existence and uniqueness; weighted graph Laplacians and positive semidefinite spectral theory.
3. **Current evidence:** No claim is made that the precise coupling is an established model or that numerical results certify an invariant set; its graph spectral identities are ordinary finite-dimensional mathematics.
4. **Natural observations:** This is a synthetic mathematical system, not a model of human dialogue or human behavior, so not applicable.
5. **Mechanism:** The graph heat operator modifies local `rho_i`; graph coupling changes the vector field; RK4 advances the nine state variables. View controls only change rendering.
6. **Competing explanations:** A visually butterfly-shaped cloud can arise from numerical artifacts or transient dynamics. Slider response alone does not establish chaos.
7. **Limits and failure modes:** Large time steps or extreme parameters can escape numerically. Lyapunov estimates are finite-time numerical estimates. Reproducibility depends on solver settings.
8. **Transfer:** Graph-coupling and Gaussian information metrics from the Ω research framework are used as independent diagnostics; no unsupported claim is made that a manuscript theorem proves the existence of this exact attractor.
9. **Implementation:** Self-contained HTML Canvas app under `experiments/omega-attractor/index.html`, with 31 range sliders, 9D RK4, covariance/spectral diagnostics and settings controls. Existing Room code is untouched.
10. **Post-change validation:** Local Chromium/Playwright smoke tests verified graph heat trace, Gaussian Wasserstein and KL identities, Betti counts, 31 slider registration, page errors, dynamic slider effects, and mobile viewport fit. GitHub Pages must be separately checked after publication.

## Sources
- Edward N. Lorenz (1963), Deterministic Nonperiodic Flow, Journal of the Atmospheric Sciences, DOI 10.1175/1520-0469(1963)020<0130:DNF>2.0.CO;2
- Fan R. K. Chung (1997), Spectral Graph Theory, CBMS.
- Hairer, Nørsett & Wanner, Solving Ordinary Differential Equations I, Springer.
- Cédric Villani, Optimal Transport: Old and New, Springer (2009).

The simulation is **not independently peer reviewed**. The term "attractor" is a visualization title, not a mathematical certification of attractor existence.
