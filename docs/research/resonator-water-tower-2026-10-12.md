# RESONATOR — the Superior, Wisconsin water tower, empty: dimensions and acoustics (2026-10-12)

This is research only, before any change. Numbers come from `qa-resonator/tower_acoustics.py`.

## 1. Observed problem / request
Alex asked for a virtual water tower to hit with a humongous padded mallet. The tower is completely
empty (hollow steel). The mallet can be padded with thick leather, wool, tightly compressed
Styrofoam or rubber. The model is the city of Superior's tower (four photos supplied by Alex, one
credited to Dennis O'Hara and used by the City of Superior).

**Research question.**
- How big is this tower?
- What would it sound like, empty, struck from outside?
- How would each padding change the strike?

## 2–3. Sources (read 2026-10-12)
- **Spheroid sizes.** CB&I *Waterspheroid* brochure (2021): 150,000–2,000,000 US gal. The
  1,000,000 gal size is 74 ft 8 in (22.8 m) across, with a 40 ft head range. Roof plates are at least
  1/4 in.
- **Composite towers (concrete pedestal, for comparison).** Caldwell Tanks, composite elevated tank
  standard sizes: up to 3,000,000 gal, 116 ft across.
- **A documented spheroid.** City of Red Deer, Statement of Significance, Horton Water Spheroid (1957):
  - 40.2 m tall, ball 18.9 m across, 500,000 imperial gal;
  - about 240 t of steel. Spread over roughly 1,650 m² of shell, that implies an average wall of
    about 18–20 mm. This is a derived figure.
- **Shell vibration, the formula check.** Abaqus Benchmarks Guide 1.4.1, free vibrations of a
  spherical shell (citing Lamb 1882, Baker 1961, Silbiger 1962, Kalnins 1964).
  - The membrane frequency equation used here, Ω⁴ − Ω²(1+3ν+λ) + (λ−2)(1−ν²) = 0 with λ = n(n+1)
    and Ω = ωR/c_p, reproduces the benchmark's membrane column within 0.01 Hz for n = 2–4 and 6–10.
  - The listed n = 5 value (239.56 Hz) is out of line with its neighbours and with the benchmark's own
    finite-element rows (243.1–244.4 Hz). The formula gives 243.46 Hz, so it is read as a typo.
  - The benchmark's finite-element rows show bending lifting modes only when the wall is thick
    relative to the radius. That is how far the "cluster" below holds.
- **Felt.** D. A. Russell, "The piano hammer as a nonlinear spring" (1997):
  - F = K·x^p, with p ≈ 2–3.5;
  - a hardening pad gives shorter contact and a brighter sound when hit harder.
- **Styrofoam.** AFM Foam-Control EPS technical data (ASTM C578 types): compressive strength at 10%
  deformation is 69–414 kPa for 16–48 kg/m³.
- **An empty steel water tank from the inside.** *Colorado Country Life* (E. Buchanan, May 2026) and
  Aspen Public Radio (E. Arntsen, 2024-11-18): The Tank in Rangely, Colorado has reverberation up to
  40 s.
- **Standard formulas used, not re-sourced today:**
  - Donnell–Mushtari cylinder frequencies;
  - coincidence frequency f_c = c₀²/(1.81·c_p·h);
  - radiation loss factor η = ρ₀c₀σ/(ωρh);
  - Sabine T60 = 0.161·V/A.

## 4. Findings
### The tower (estimated)
- **Bowl:** about 23 m (75 ft) across and about 17.5 m (57 ft) tall.
- **Column:** about 5 m (16 ft) across.
- **Flared base:** about 10 m (32 ft) at the ground.
- **Height:** about 35 m (115 ft) to the roof.
- **Capacity:** about 1 million US gal.
- **How the estimate was made:**
  - The two side photos agree on the proportions within about 5%:
    - bowl width : height : column : base = 1 : 0.74–0.77 : 0.21–0.22 : 0.42;
    - total height ≈ 1.5 bowl widths.
  - The scale comes from the 42 in roof railing (22–27 m) and the standard 1 MG size (22.8 m).
  - The bowl volume implied by the measured shape is 1.05 million gal, which agrees with that size.
  - The likely error is ±15%.
- **Steel:** probably 10–25 mm, thicker in the lower bowl and the column. Not measured.

### Sound, struck from outside (linear: even a 1.6 kJ strike moves the 12 mm wall by about 0.5 mm)
| part | what rings | frequency |
|---|---|---|
| bowl | lowest bending mode (n = 2) | 51–60 Hz (about G♯1–B1) |
| bowl | the cluster: hundreds of mode shapes (n ≈ 4–30, each 2n+1-fold) packed just under the membrane limit | about 64–82 Hz (C♯2–E2) |
| bowl | breathing mode | 118–138 Hz (A♯2–C♯3) |
| bowl | in-plane (upper branch) modes | 145, 200–230, 270–310 Hz and up |
| column | lowest shell modes (3–4 lobes) | about 11 Hz, felt more than heard |
| column | dense band up to its ring frequency | up to about 340 Hz (E4) |
| plates | coincidence (bending waves radiate fully above it) | 490–1230 Hz for 25–10 mm walls |

The two frequencies in each row come from the volume-equivalent sphere (9.8 m) and the equator radius
(11.5 m). The real oblate bowl spreads its modes between them.

**Decay.**
- Low bowl modes radiate efficiently (ka ≈ 11–14 at 60–75 Hz) and die in about 3 s.
- The cluster's high-order modes radiate poorly and hum on for about 20 s, quietly.
- So the sound is a deep boom that settles into a long, faint, beating hum.
- A water tower would ring like a giant bell, not bloom like a tam-tam: its walls are too thick
  relative to the motion for the tam-tam's nonlinearity.

**Inside the empty bowl.**
- Reverberation of 26–51 s at low and mid frequencies (painted steel, α 0.01–0.02), consistent with
  The Tank's 40 s.
- The lowest air modes are at 12, 19 and 25 Hz.

### The mallets
Assumptions: a 200 kg head swung at 4 m/s (1.6 kJ), a 0.6 m face, and 8–10 cm of padding over a hard
core. The rigid-wall contact is simulated in the script.

| padding | contact | sound reaches (−20 dB) | rebound | character |
|---|---|---|---|---|
| compressed Styrofoam, 32 kg/m³ (crushes at 173 kPa) | 21 ms | 47 Hz | 0.19 | dead thud; dents 3 cm, permanently |
| thick wool (hardening, p 2.5) | 25 ms | 103 Hz | 0.73 | soft and dark; harder swings get brighter |
| dense Styrofoam, 48 kg/m³ (414 kPa) | 12 ms | 91 Hz | 0.45 | dull, dents 1 cm |
| rubber (E ≈ 4 MPa, Hertz-like) | 12 ms | 121 Hz | 0.90 | bouncy, round boom |
| thick leather over a hard core (E ≈ 30 MPa assumed) | 2 ms | 660 Hz | 0.86 | a clang over the boom |

## 6–7. Competing explanations and limits
- **Dimensions.** The tower's dimensions come from photos, not records. SWL&P or the builder's
  nameplate at the base door would give the real ones. All frequencies scale inversely with size.
- **Bowl shape.** The bowl is treated as a sphere of two possible radii. Its real oblate shape, the
  cone neck and the roof cap will split and spread the modes. The model built for the app must be
  checked against these numbers, and against a finite-element model where it matters.
- **Unchecked formula and materials.**
  - The cylinder formula (Donnell) is approximate for 2–3 lobes, and was not checked against a
    benchmark here.
  - The rubber and leather moduli are assumptions; the felt law and the Styrofoam strengths are
    sourced.
  - Real welded towers may damp more than the 0.001 assumed (joints, coatings, the access tube).
- **Phone speakers.** An iPhone speaker reproduces little below about 200 Hz. A tower at real size is
  mostly below that, so the app needs a decision (section 9).

## 8. Context transfer
- The shell formula is checked against the benchmark.
- The tank-reverb figure is a real empty steel water tank.
- The mallet numbers are model estimates with stated assumptions.

## 9. Proposed implementation (built in Stage T1 — see resonator-tower-T1-2026-10-12.md)
- A tower body for the engine: bowl, column and flared base as one mass-spring shell. Its lowest modes
  and cluster are checked against this table.
- A big strike pad.
- The mallet as material presets (padding law plus head mass and swing speed).
- **Undecided: real size or "phone size".**
  - Real size is a true sub-bass boom, for headphones or speakers.
  - A Size control shrinks the tower so the same sound rises into the phone speaker's range.
  - Or the keys transpose it.

## 10. Validation (proposed)
- Modelled tower modes within 10% of the table: n = 2, the cluster, breathing.
- Decay within 25% of the table.
- Each padding's contact time and bandwidth within 20% of the script.
- The phone check is Alex's.

**Post-change result:** built as Stage T1 (`resonator-tower-T1-2026-10-12.md`). Two corrections to this note came out of
the build:
- The sphere estimates above understate how far the oblate bowl spreads its modes. A finite-element model of the
  bowl as it is (an oblate spheroid clamped at the neck, `tower_fe.py`) puts the breathing mode at 129 Hz (inside
  118–138), the lowest two-lobed mode at 55 Hz (inside 51–60), and hundreds of modes from about 55 to 120 Hz — the
  cluster is wider than 64–82 Hz once all lobe counts are included.
- The phone-speaker question (section 9) was settled by keys: Real size plays the 35 m tower (lowest key C3, the
  breathing mode), Phone size starts at E4 (a 14 m tower). Alex can change this.
