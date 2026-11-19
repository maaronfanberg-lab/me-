# TIDE — mathematical amendments and implementation scope

**Version:** 2026-11-19 · **Companion app:** `apps/tide.html` · **Status:** real-time numerical prototype, not the final research-scale implementation.

The governing specification supplied on 2026-11-18 remains the source model. This document makes substantive mathematical corrections explicit and distinguishes implementation from analytic identity. Superseded equations must not be used as if the modifications were absent.

## 1. Corrected accumulator and equilibrium (Part 1)

The original accumulator

\[
\dot\chi=K(s)-s-\chi g,\quad s=1-\phi-r_\chi(\eta)\chi,\quad g=K(s)/\nu-\delta
\]

has a genuine runaway branch. Since \(K(s)\to K_{\min}\) for large negative \(s\), the term \(-s\) grows with \(\chi\); raising \(r_\chi\) through strain may therefore *accelerate* rather than brake the runaway. The real-time app retains this drift and adds a well-defined saturating feedback:

\[
\boxed{\dot\chi=K(s)-s-\chi g-\lambda_\chi(\eta)\chi^3},\quad
\lambda_\chi(\eta)=1.2+0.8\,\zeta_\eta\eta.
\tag{C1}
\]

This cubic is a model change, not an algebraic rearrangement of the original equation. For a frozen background \(\eta\), its interior equilibrium satisfies

\[
K(s^*)=\nu(\beta_\psi+\delta),\quad
\lambda_\chi(\eta)\,(\chi^*)^3+\beta_\psi\chi^*=K(s^*)-s^*,\quad
\phi^*=1-s^*-r_\chi(\eta)\chi^*.
\tag{C2}
\]

Thus the original closed formula for \(\chi^*\) in (1.7) no longer applies. The original Jacobian (1.8) also requires the extra term \(-3\lambda_\chi(\eta)(\chi^*)^2\) in the bottom-right entry. The original Hopf boundary must be recomputed for (C1) rather than imported unchanged.

The labels \(\phi,\psi\in(0,1)\) were **not** guaranteed by the ODEs. The real-time prototype uses positivity/boundary projection (\(\phi\in[10^{-4},0.98],\;\psi\in[10^{-4},0.97]\)) to avoid singular integration; this is a numerical boundary mechanism, not an invariant-set theorem. A research solver should prove invariant bounds or replace the response by a smooth regularized response with clear interpretation.

## 2. Corrected threshold fatigue (Part 6)

Equation (6.3) originally *lowers* a threshold at toppling while saying fatigue *raises* it. For protective hardening, use

\[
\dot z_i^c=\frac{z_{0,i}^{c}(\kappa)-z_i^c}{\tau_c}\quad\text{between events},\qquad
\boxed{z_i^c(t^+)=(1+\varphi_F)z_i^c(t^-)}\quad\text{at a topple}.
\tag{C3}
\]

A weaker-after-failure mechanism would be a different, explicitly reinforcing model. Note that this negative feedback does **not** by itself prove self-organized criticality; measure the observed branching ratio and avalanche distributions before asserting a critical state.

## 3. Fractional strain and stochastic shocks (Parts 7–8)

For current-time variable-order Caputo ("type A") define

\[
{}^C D_t^{\alpha(t)}\eta(t)=\frac{1}{\Gamma(1-\alpha(t))}
\int_0^t\frac{\eta'(s)}{(t-s)^{\alpha(t)}}\,ds.
\tag{C4}
\]

The prototype uses an **L1 Caputo approximation** with the current \(\alpha\), a retained window of up to 320 steps, and implicit solution of the local quadratic damping. This does not represent an infinite exact history. To avoid a fractional impulse singularity, event strain is regularized as a finite-duration pulse with exponential decay; the total area and shape must be included in convergence tests.

An overdamped Langevin path is almost surely nondifferentiable, so \(\|\dot{\mathbf q}\|^2\) from (8.14) is not a meaningful instantaneous finite observable. The prototype instead uses the **squared deterministic drift**:

\[
\boxed{S_{\eta,q}=c_q\|\nabla V(\mathbf q,t)\|^2}.
\tag{C5}
\]

This is a *drift-strain proxy*, not stochastic heat production. Stochastic heat/work, if required, must use the consistent Stratonovich bookkeeping in (10.1) with the time-varying protocol explicitly tracked.

## 4. Hybrid event semantics (Part 5)

Spontaneous Hawkes events are stochastic arrivals with conditional intensity \(\Lambda(t)\). Avalanche-finished events are **scheduled endogenous marked jumps**, not additional arrivals drawn from the same conditional Poisson law. Both kinds can raise subsequent Hawkes excitation. Therefore the time-rescaling test in (5.13) applies to the intensity-generated arrivals *conditional on the observed avalanche schedule*, not blindly to the union of scheduled and stochastic events.

The real-time solver uses **piecewise-constant conditional Poisson time steps** of size \(\Delta t\), not Ogata thinning. High-rate regimes need smaller steps or exact-time event simulation. The marks use a capped Pareto draw for numerical safety, so the untruncated mean formulas (5.4)–(5.5) are not literal finite-run invariants in this prototype.

## 5. Thermodynamic measurements (Part 10)

Flow divergence, \(-\nabla\cdot F\), is a *phase-space contraction observable*. It is not generically equal to thermodynamic entropy production and is not guaranteed to be nonnegative. Equation (10.11) mixes rates and event losses with different units; coefficients require physical calibration before calling their sum total entropy production.

The real-time instrument computes a **nonnegative, smoothed dissipation proxy** from drift, fluid energy loss, SIRS throughput, and avalanche loss. It drives a confidence-like indicator for reservoir autonomy. This should never be relabeled an exact Seifert entropy-production rate or used to claim Jarzynski, Landauer, or TUR validation. A genuine thermodynamic audit requires pathwise energy/work bookkeeping and ensemble distributions.

The pressure/temperature feedback is an approximate advection–diffusion–compression fluid subsystem rather than a converged compressible Navier–Stokes solver. In particular, the baroclinic source vanishes for a barotropic equation of state and requires thermal pressure dependence or another non-barotropic mechanism.

## 6. Comparable dynamism and information statistics (Parts 14–15)

Equation (14.3) requires \(\mathcal D>1\) while defining every input component on \([0,1]\). The average of five numbers in \([0,1]\) cannot exceed 1. Use **comparable ratios** against a baseline with well-defined positive denominators instead:

\[
\mathcal D_{\rm rel}=\frac15\sum_{i=1}^5 r_i,
\qquad r_i=\frac{g_i(\mathrm{TIDE})+\epsilon}{g_i(\mathrm{OMEF})+\epsilon}.
\tag{C6}
\]

Choose transformations \(g_i\) *before* seeing results. A valid burstiness transformation is \(g_B=(B+1)/2\) because original \(B\in[-1,1]\); compare dimension-normalized \(D_{KY}\) if state dimensions differ; define the same type of switching event for both systems. Do not assert superiority until the denominators, transformations, benchmarks, statistical uncertainty, and equal computational budgets are specified. The prototype **does not compute** \(\mathcal D_{\rm rel}\).

The data-processing inequality in (15.8) applies to a source→strain→target Markov chain; other active routes in TIDE invalidate this reduction unless conditioned on adequately. Conditional transfer entropy may show indirect prediction through unobserved mediators and is not automatic proof of direct causality. For block entropy rates, divide by the sampling interval before comparing with continuous-time \(h_{KS}\). Pesin's identity is not universal for arbitrary noisy and jump-driven hybrid dynamics.

The Information view estimates

\[
\widehat T_{i\to j}^{(1)}=\frac12\log
\frac{\operatorname{var}(Y_{j,t+1}\mid Y_{j,t})}{\operatorname{var}(Y_{j,t+1}\mid Y_{j,t},Y_{i,t})}
\tag{C7}
\]

using **Gaussian linear one-lag regressions** over a moving window of 12 layer observables. This is exploratory predictive transfer, not the full Part 15 conditional/KSG/partial-information-decomposition suite and not a causal intervention test.

## 7. Real-time resolution and implemented connections

The app's active computations are 36×36 periodic scalar/velocity fields, 30 moving directed graph nodes with Burgers edge segments, 32 second-order Kuramoto oscillators, 48 Hopfield units with adaptation and sequential recall, a 56-unit RLS echo reservoir, a variable-order fractional strain with finite history, metadynamics hills and an overdamped Langevin walker, mark-triggered SIRS and avalanche events, a temperature field, and periodically updated entropy-regularized Ollivier-like curvature. It has **100 separately adjustable numeric controls**: 92 model coefficients and 8 Web Audio sonification coefficients.

Sound is produced by the simulated oscillator phases (pitch and phase relationships), memory overlaps (timbre), reaction–diffusion structure (brightness), fluid enstrophy (filtered noise), marked events (transients), and the walker (stereo location). It does not use pre-rendered music, loops, or decorative beats. Sound requires a user gesture to unlock Web Audio on mobile browsers.

### Tests actually run

- Browser generated exactly **100** range inputs with exactly 100 matching parameter keys; all accepted changes to their upper endpoints.
- Browser exercised the eight visual modes, enabled Web Audio and observed the context in the running state, and tested expansion and preset export. These are browser simulations, **not physical-device audio listening tests**.
- A seeded **1,000-step numerical smoke test** completed with finite measured core/strain/field outputs, coupled bursts, avalanches, and phase locking; this is **not** an analytic convergence, Turing, Hawkes rescaling, Kramers, or thermodynamic validation.
- The source was committed and re-fetched from `maaronfanberg-lab/me-/apps/tide.html` to confirm GitHub storage.

### Before making research claims

Implement the remaining Part 14 isolated and coupled checks, conduct mesh and timestep convergence, calibrate physical units, derive the new Hopf boundary from (C1), replace approximate Ollivier transport with certified optimal transport where needed, and validate the information estimators against known synthetic processes. This prototype is an instrument for exploring TIDE, not a claim that the 2026-11-18 paper's every mathematical hypothesis has been experimentally confirmed.